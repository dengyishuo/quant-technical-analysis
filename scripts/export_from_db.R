#!/usr/bin/env Rscript
# 从本地 MySQL 导出书稿所需数据到 data/staging/（CSV）
# 后续由 scripts/csv_to_parquet.py 转成 parquet。
#
# 用法：
#   先在环境变量里给出连接信息，再运行：
#     export DB_USER=your_user DB_PASSWORD=your_password
#     Rscript scripts/export_from_db.R
#
#   也可以写在 ~/.Renviron 里，R 启动时自动读取：
#     DB_USER=your_user
#     DB_PASSWORD=your_password
#
#   可选：DB_HOST（默认 127.0.0.1）、DB_PORT（默认 3306）、DB_NAME（默认 strategy_monitor）
#
# 依赖：DBI、RMySQL

suppressMessages({
  library(DBI)
  library(RMySQL)
})

# 以脚本所在位置定位项目根目录，换机器也能跑
args <- commandArgs(trailingOnly = FALSE)
here <- dirname(sub("^--file=", "", args[grep("^--file=", args)]))
PROJ <- normalizePath(file.path(here, ".."))
STAGING <- file.path(PROJ, "data", "staging")
dir.create(STAGING, showWarnings = FALSE, recursive = TRUE)

# 连接信息只从环境变量读，不写进代码
DB <- list(
  host     = Sys.getenv("DB_HOST", "127.0.0.1"),
  port     = as.integer(Sys.getenv("DB_PORT", "3306")),
  user     = Sys.getenv("DB_USER"),
  password = Sys.getenv("DB_PASSWORD"),
  dbname   = Sys.getenv("DB_NAME", "strategy_monitor")
)

if (DB$user == "" || DB$password == "") {
  stop("未设置数据库连接信息。请先 export DB_USER=... DB_PASSWORD=...，",
       "或把它们写进 ~/.Renviron。", call. = FALSE)
}

connect <- function() {
  dbConnect(MySQL(), host = DB$host, port = DB$port,
            user = DB$user, password = DB$password, dbname = DB$dbname)
}

# 书稿用的示例蓝筹（正文反复引用这 5 只）
BLUE_CHIP <- c("600519.SS", "600036.SS", "601318.SS", "300750.SZ", "000858.SZ")

# 时间范围：从 2021-06 起，留出 250 个交易日预热，正式研究区间 2023-01 至 2025-12
DATE_FROM <- "2021-06-01"
DATE_TO   <- "2025-12-31"

# 扩展股票池规模（按市值取前 N）
TOP_N <- 300

cat("== 连接数据库 ==\n")
con <- connect()
on.exit(dbDisconnect(con), add = TRUE)
cat("   OK\n")

# ---------- 1. 行业与市值快照 ----------
cat("\n== 行业与市值快照 ==\n")
ind <- dbGetQuery(con, "
  SELECT secucode, name, industry, trade_date,
         total_mv, float_mv, pe_ttm
  FROM a_share_industry_cap
")
# MySQL 侧用 .SH，行情表用 .SS，统一成 yfinance 风格
ind$code <- sub("\\.SH$", ".SS", ind$secucode)
ind <- ind[!is.na(ind$industry) & ind$industry != "", ]
cat(sprintf("    %d 行，%d 个行业，快照日 %s\n",
            nrow(ind), length(unique(ind$industry)), unique(ind$trade_date)[1]))

# 按市值取前 N，作为扩展股票池
ind <- ind[order(-ind$total_mv), ]
pool <- head(ind, TOP_N)
# 确保 5 只蓝筹在池内
miss <- setdiff(BLUE_CHIP, pool$code)
if (length(miss) > 0) {
  extra <- ind[ind$code %in% miss, ]
  pool <- rbind(pool, extra)
}
pool <- pool[!duplicated(pool$code), ]
cat(sprintf("    扩展股票池 %d 只（市值门槛 %.0f 亿）\n",
            nrow(pool), min(pool$total_mv) / 1e8))

write.csv(ind,  file.path(STAGING, "industry_snapshot.csv"), row.names = FALSE)
write.csv(pool[, c("code", "name", "industry", "total_mv", "float_mv", "pe_ttm")],
          file.path(STAGING, "universe.csv"), row.names = FALSE)
cat("    已写 industry_snapshot.csv / universe.csv\n")

# ---------- 2. 行情 ----------
cat("\n== 导出行情 ==\n")

fetch_one <- function(sym) {
  q <- sprintf(
    "SELECT symbol AS code, date, open, high, low, close, adjusted, volume
     FROM raw_price
     WHERE symbol = '%s' AND date BETWEEN '%s' AND '%s'
     ORDER BY date", sym, DATE_FROM, DATE_TO)
  d <- dbGetQuery(con, q)
  if (nrow(d) == 0) return(NULL)
  # 同一 symbol+date 可能因数据源变更存在多条（name 不同），保留最后一条非空 close
  d <- d[!is.na(d$close), ]
  d <- d[!duplicated(d$date, fromLast = TRUE), ]
  d$name <- NULL
  d
}

# 目标标的：扩展池 + 5 只蓝筹
targets <- unique(c(pool$code, BLUE_CHIP))
cat(sprintf("    目标标的 %d 个\n", length(targets)))

frames <- vector("list", length(targets))
ok <- 0L
for (i in seq_along(targets)) {
  d <- tryCatch(fetch_one(targets[i]), error = function(e) NULL)
  if (!is.null(d) && nrow(d) > 0) {
    frames[[i]] <- d
    ok <- ok + 1L
  }
  if (i %% 50 == 0) cat(sprintf("    %d / %d\n", i, length(targets)))
}
prices <- do.call(rbind, frames)
cat(sprintf("    成功 %d 个标的，共 %d 行\n", ok, nrow(prices)))

write.csv(prices, file.path(STAGING, "prices.csv"), row.names = FALSE)
cat("    已写 prices.csv\n")

# ---------- 3. 指数与 ETF（择时检验用） ----------
# 数据库中没有指数本身的日线，只有跟踪指数的 ETF，用 ETF 代替指数作为择时对象，
# 这一点在 data/README.md 里注明。
cat("\n== 导出基准 ETF ==\n")
idx_syms <- c("510300.SS", "510500.SS", "510050.SS",
              "159915.SZ", "159845.SZ", "588000.SS")
idx_frames <- list()
for (s in idx_syms) {
  d <- tryCatch(fetch_one(s), error = function(e) NULL)
  if (!is.null(d) && nrow(d) > 0) idx_frames[[s]] <- d
}
if (length(idx_frames) > 0) {
  idx <- do.call(rbind, idx_frames)
  cat(sprintf("    %d 个指数，%d 行\n", length(idx_frames), nrow(idx)))
  write.csv(idx, file.path(STAGING, "index.csv"), row.names = FALSE)
} else {
  cat("    未取到指数数据\n")
}

# ---------- 4. 覆盖度报告 ----------
cat("\n== 覆盖度 ==\n")
cover <- aggregate(date ~ code, data = prices, FUN = function(x) length(unique(x)))
names(cover)[2] <- "n_days"
cat(sprintf("    每个标的的交易日数：中位数 %d，最少 %d，最多 %d\n",
            median(cover$n_days), min(cover$n_days), max(cover$n_days)))
cat(sprintf("    日期范围：%s 至 %s\n", min(prices$date), max(prices$date)))
cat(sprintf("    标的数 %d，总行数 %d\n", nrow(cover), nrow(prices)))

write.csv(cover, file.path(STAGING, "coverage.csv"), row.names = FALSE)
cat("\n完成。下一步：python3 scripts/csv_to_parquet.py\n")
