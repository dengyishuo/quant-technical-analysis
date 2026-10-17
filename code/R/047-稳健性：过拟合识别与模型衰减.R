# ============================================================
# 第047章 稳健性：过拟合识别与模型衰减
# 模块 08 机器学习挖掘与融合
# 源文件：模块08-机器学习挖掘与融合/第047章-稳健性：过拟合识别与模型衰减.md
# ============================================================
# 本文件由 scripts/extract_code.py 自动生成，请勿直接编辑。
# 修改代码请改 Markdown 源稿，再重新运行提取脚本。
#
# 依赖：先加载同目录下的公共函数与数据准备
#   source("code/R/00-common.R")
#   source("code/R/00-data.R")
#
# ------------------------------------------------------------

# ---- 代码块 1：代码实现 ----

library(dplyr)

# purged_splits() 的定义见本章 R 部分，参数与 Python 一致
# 逐折打印训练末日与测试区间，用于核对隔离区的位置
all_dates <- sort(unique(panel$date))
splits <- purged_splits(all_dates, n_splits = 4, horizon = 5, embargo = 5)

for (k in seq_along(splits)) {
  # 训练日期经过 unlist 之后失去 Date 类，这里还原
  tr <- as.Date(splits[[k]]$train, origin = "1970-01-01")
  te <- as.Date(splits[[k]]$test,  origin = "1970-01-01")
  cat(sprintf("第 %d 折：训练末日 %s，测试区间 %s 到 %s\n",
              k, format(max(tr)), format(min(te)), format(max(te))))
}

# ---- 代码块 2：代码实现 ----

library(dplyr)

# 横截面平均相关：把收益整理成日期乘标的的矩阵，求相关矩阵后取上三角平均
# 单个时点的横截面只有一个观测，相关系数只能在时间序列上估计
avg_cross_corr <- function(panel, ret_col = "forward_5") {
  wide <- panel |>
    select(date, code, all_of(ret_col)) |>
    tidyr::pivot_wider(names_from = code, values_from = all_of(ret_col)) |>
    arrange(date) |>
    select(-date)
  m <- cor(as.matrix(wide), use = "pairwise.complete.obs")
  m[upper.tri(m)]
}

# 有效样本量：标的数按平均相关折算，相关越高压缩越强
effective_n <- function(n_assets, avg_rho) n_assets / (1 + (n_assets - 1) * avg_rho)

rho <- mean(avg_cross_corr(panel), na.rm = TRUE)
n_assets <- dplyr::n_distinct(panel$code)
n_features <- 4        # 示意：四个候选特征

data.frame(
  标的数 = n_assets,
  平均相关 = round(rho, 3),
  有效样本量 = round(effective_n(n_assets, rho), 2),
  特征数 = n_features,
  有效样本量与特征数之比 = round(effective_n(n_assets, rho) / n_features, 2)
)

# ---- 代码块 3：代码实现 ----

# 沿用第 007 章的 cross_section_ic 与 ic_summary，逐个因子收集 t 统计量
cands <- c("ret5", "ma20_dev", "vol20", "vol_ratio")     # 示意候选

res <- bind_rows(lapply(cands, function(c0) {
  s <- ic_summary(cross_section_ic(panel, c0, "forward_5"))
  data.frame(因子 = c0, t = s$t统计量, 期数 = s$样本期数)
}))

# 双侧 p 值用正态近似，与 t 统计量的口径一致
res$p <- 2 * pnorm(-abs(res$t))

# BH 校正：p.adjust(method = "BH") 返回校正后 p 值，与原函数 bh_correction() 的判定等价
# N 取全部尝试过的候选数，包括未通过检验的那些
res$BH显著 <- p.adjust(res$p, method = "BH") < 0.05
print(res)

# ---- 代码块 4：代码实现 ----

library(zoo)

# 以单因子作为监控对象的示意，先按日算 IC，再对 IC 序列取滚动均值
ic <- cross_section_ic(panel, "ret5", "forward_5")
ic_df <- data.frame(date = as.Date(names(ic)), ic = as.numeric(ic)) |>
  arrange(date)

roll <- zoo::rollapply(ic_df$ic, 60, mean, na.rm = TRUE, fill = NA, align = "right")
low <- stats::quantile(roll, 0.1, na.rm = TRUE)

par(family = "STHeiti")        # 中文字体，避免标题与图例乱码
plot(ic_df$date, roll, type = "l", col = "steelblue", lwd = 1.5,
     xlab = NULL, ylab = "滚动 60 期 IC 均值",
     main = "滚动样本外 IC 监控（示意）")
abline(h = 0, col = "gray50")
abline(h = low, col = "firebrick", lty = 2)
legend("topright", legend = c("滚动 IC 均值", "历史 10% 分位"),
       col = c("steelblue", "firebrick"), lty = c(1, 2), bty = "n")

# ---- 代码块 5：代码实现 ----

library(dplyr)

# 净化切分：返回训练与测试日期集合，训练样本的标签区间不与测试重叠
purged_splits <- function(dates, n_splits = 4, horizon = 5, embargo = 5) {
  dates <- sort(unique(dates))
  bounds <- split(dates, cut(seq_along(dates), n_splits, labels = FALSE))
  lapply(seq(2, length(bounds)), function(i) {
    test <- bounds[[i]]
    train <- unlist(bounds[seq_len(i - 1)])
    t0 <- min(test); t1 <- max(test)
    test_end <- t1 + horizon
    train <- train[train + horizon < t0]          # 净化
    train <- train[!(train >= test_end & train <= test_end + embargo)]  # 禁运
    list(train = train, test = test)
  })
}

# BH 校正
bh_correction <- function(p, alpha = 0.05) {
  o <- order(p); n <- length(p)
  thr <- alpha * seq_len(n) / n
  pass <- p[o] <= thr
  k <- if (any(pass)) max(which(pass)) else 0
  sig <- logical(n); sig[o[seq_len(k)]] <- TRUE
  sig
}
