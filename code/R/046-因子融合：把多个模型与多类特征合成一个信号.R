# ============================================================
# 第046章 因子融合：把多个模型与多类特征合成一个信号
# 模块 08 机器学习挖掘与融合
# 源文件：模块08-机器学习挖掘与融合/第046章-因子融合：把多个模型与多类特征合成一个信号.md
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
library(quantmod)

# 行情获取与特征构造，写法与第 047 章一致
codes <- c("600519.SS", "600036.SS", "601318.SS", "300750.SZ", "000858.SZ")

get_one <- function(code) {
  px <- local({
    # 从本地 CSV 取该标的，转成 quantmod 可用的 xts
    .p <- read.csv("data/parquet/panel_blue_chip.csv", stringsAsFactors = FALSE)
    .p <- .p[.p$code == code, ]
    .x <- xts::xts(.p[, c("open", "high", "low", "close", "volume", "adjusted")],
                       order.by = as.Date(.p$date))
    colnames(.x) <- c("Open", "High", "Low", "Close", "Volume", "Adjusted")
    .x
  })
  data.frame(date = index(px), close = as.numeric(Cl(px)),
             volume = as.numeric(Vo(px)), code = code)
}

panel <- bind_rows(lapply(codes, get_one)) |>
  group_by(code) |>
  mutate(
    ret5      = close / lag(close, 5) - 1,
    ma20_dev  = close / zoo::rollmean(close, 20, fill = NA, align = "right") - 1,
    vol20     = zoo::rollapply(close / lag(close) - 1, 20, sd, fill = NA, align = "right"),
    vol_ratio = volume / zoo::rollmean(volume, 20, fill = NA, align = "right"),
    forward_5 = close / lead(close, 5) - 1
  ) |>
  ungroup()

features <- c("ret5", "ma20_dev", "vol20", "vol_ratio")
panel <- panel |> tidyr::drop_na(all_of(c(features, "forward_5")))

# 中位数与 MAD 的横截面标准化，统计量只取当日
cs_std <- function(x) {
  m <- median(x, na.rm = TRUE)
  s <- median(abs(x - m), na.rm = TRUE)
  if (isTRUE(s > 0)) (x - m) / s else x * 0
}

# 目标与特征都逐日转成横截面标准化值，两者口径一致
panel <- panel |>
  group_by(date) |>
  mutate(y = cs_std(forward_5),
         across(all_of(features), cs_std, .names = "{.col}_z")) |>
  ungroup()

cat("面板维度", nrow(panel), "行", ncol(panel), "列\n")

# ---- 代码块 2：代码实现 ----

library(xgboost)
library(glmnet)

# 提示：此处用 5 只标的演示流程。真实建模请改用 data/parquet/panel.parquet
# （287 只、2021-06 起），并补足十年区间与行业中性化
# 扩张窗口：日期切成 6 段，前 k 段训练，预测第 k+1 段
dates <- sort(unique(panel$date))
folds <- split(dates, cut(seq_along(dates), 6, labels = FALSE))
zcols <- paste0(features, "_z")

oof <- data.frame(gbdt = rep(NA_real_, nrow(panel)),
                  linear = rep(NA_real_, nrow(panel)))

params <- list(objective = "reg:squarederror", eta = 0.05, max_depth = 4,
               min_child_weight = 200, subsample = 0.8,
               colsample_bytree = 0.6, lambda = 5)

set.seed(0)
for (k in 2:length(folds)) {
  tr <- panel |> filter(date %in% do.call(c, folds[seq_len(k - 1)]))   # 只用前面的折训练
  te <- which(panel$date %in% folds[[k]])                          # 预测当前折
  if (nrow(tr) < 200 || length(te) == 0) next

  # 折内不设早停：这一折就是验证集，用它定轮数等于用测试集调参
  gb <- xgb.train(params, xgb.DMatrix(as.matrix(tr[features]), label = tr$y),
                  nrounds = 300, verbose = 0)
  oof$gbdt[te] <- predict(gb, xgb.DMatrix(as.matrix(panel[te, features])))

  # 线性基模型用固定 lambda 的岭回归，折内同样不做交叉验证
  lin <- glmnet(as.matrix(tr[zcols]), tr$y, alpha = 0, lambda = 10)
  oof$linear[te] <- as.numeric(predict(lin, as.matrix(panel[te, zcols])))
}

# 每一行的 gbdt 与 linear 都来自样本外预测，这是元模型可用的前提
meta <- panel |>
  select(date, code, forward_5, y) |>
  bind_cols(oof) |>
  filter(!is.na(gbdt), !is.na(linear))

cat("元模型可用样本", nrow(meta), "\n")

# ---- 代码块 3：代码实现 ----

library(glmnet)

# 提示：此处用 5 只标的演示流程。真实建模请改用 data/parquet/panel.parquet
# （287 只、2021-06 起），并补足十年区间与行业中性化
# meta 的每一行都来自基模型的样本外预测，元模型才谈得上可用
# 各基模型输出逐日转横截面分位，统一尺度
meta <- meta |>
  group_by(date) |>
  mutate(across(c(gbdt, linear),
                ~ rank(.x, na.last = "keep") / sum(!is.na(.x)),
                .names = "{.col}_q")) |>
  ungroup()
qcols <- c("gbdt_q", "linear_q")

# 按时间切分，前 60% 拟合元模型，后 40% 留作对照
cut_date <- stats::quantile(as.numeric(meta$date), 0.6)
mt_tr <- meta |> filter(as.numeric(date) <  cut_date)
mt_te <- meta |> filter(as.numeric(date) >= cut_date)

# 固定 lambda 的岭回归，避免折内再做一次交叉验证
ridge_fit <- function(df) glmnet(as.matrix(df[qcols]), df$y, alpha = 0, lambda = 1)
m_tr <- ridge_fit(mt_tr)

# 系数的大小与符号是元模型的第一项诊断
print(data.frame(基模型 = qcols, 系数 = round(as.numeric(coef(m_tr))[-1], 3)))

# 第二项诊断：后段单独拟合一次，两段系数接近才说明权重不是拟合出来的
print(data.frame(基模型 = qcols,
                 前段系数 = round(as.numeric(coef(m_tr))[-1], 3),
                 后段系数 = round(as.numeric(coef(ridge_fit(mt_te)))[-1], 3)))

# 元模型的样本外合成与三种方案对照，见本节 R 部分末尾的代码

# ---- 代码块 4：代码实现 ----

# 逐日横截面相关，再对时间求平均，避免把时序共动误当成横截面相关
daily_rho <- meta |>
  group_by(date) |>
  summarise(rho = if (n() >= 5) cor(gbdt_q, linear_q, method = "spearman") else NA_real_,
            .groups = "drop") |>
  filter(!is.na(rho))
cat("平均横截面相关", round(mean(daily_rho$rho), 3), "\n")

# 相关偏高时，把 linear_q 对 gbdt_q 做横截面回归，取残差作为增量输入
# 残差携带的是 gbdt_q 没有覆盖的部分，含义比原始输出更窄
meta <- meta |>
  group_by(date) |>
  group_modify(~ {
    if (nrow(.x) >= 5) {
      .x$linear_resid <- as.numeric(residuals(lm(linear_q ~ gbdt_q, data = .x)))
    } else {
      .x$linear_resid <- NA_real_
    }
    .x
  }) |>
  ungroup()

# ---- 代码块 5：代码实现 ----

library(zoo)
library(ggplot2)

# 沿用第 007 章的 cross_section_ic
# 按滚动样本外 IC 给基模型加权，再向等权收缩并设上下限
rolling_ic_weight <- function(dat, cols, window = 60, lam = 0.5,
                              w_floor = 0.1, w_cap = 0.9) {
  ic_long <- bind_rows(lapply(cols, function(c0) {
    ic <- cross_section_ic(dat |> rename(f = all_of(c0)), "f", "y")
    data.frame(date = as.Date(names(ic)), ic = as.numeric(ic), 模型 = c0)
  }))
  ic_wide <- ic_long |>
    tidyr::pivot_wider(names_from = 模型, values_from = ic) |>
    arrange(date)

  # 滚动均值，窗口不足时留空
  roll <- sapply(cols, function(c0) {
    zoo::rollapply(ic_wide[[c0]], window, mean, na.rm = TRUE,
                   fill = NA, align = "right")
  })

  den <- rowSums(abs(roll), na.rm = TRUE)
  raw <- roll / ifelse(den > 0, den, NA)
  raw[!is.finite(raw)] <- 1 / length(cols)      # 无历史时退回等权

  eq <- 1 / length(cols)
  w <- (1 - lam) * raw + lam * eq               # 向等权收缩
  w <- pmin(pmax(w, w_floor), w_cap)            # 权重上下限
  w <- w / rowSums(w)
  data.frame(date = ic_wide$date, w)
}

w_df <- rolling_ic_weight(meta, c("gbdt_q", "linear_q")) |>
  tidyr::pivot_longer(-date, names_to = "模型", values_to = "权重") |>
  filter(!is.na(权重))

ggplot(w_df, aes(date, 权重, colour = 模型)) +
  geom_line(linewidth = 0.7) +
  labs(title = "滚动 IC 加权并收缩后的基模型权重（示意）",
       x = NULL, y = "权重") +
  theme_minimal() +
  theme(text = element_text(family = "STHeiti"))

# ---- 代码块 6：代码实现 ----

library(dplyr)
library(glmnet)
library(xgboost)

# 假设 meta 已含 date / code / y / gbdt / linear，
# 其中 gbdt 与 linear 为扩张窗口生成的样本外预测
cs_rank <- function(x) rank(x, na.last = "keep") / sum(!is.na(x))
mutate_cs <- function(df, cols) {
  df |> group_by(date) |>
    mutate(across(all_of(cols), cs_rank, .names = "{.col}_q")) |> ungroup()
}
meta <- mutate_cs(meta, c("gbdt", "linear"))

qcols <- c("gbdt_q", "linear_q")
cut <- quantile(as.numeric(meta$date), 0.6)
mt_tr <- meta[as.numeric(meta$date) <  cut, ]
mt_te <- meta[as.numeric(meta$date) >= cut, ]

# 岭回归元模型，alpha 在验证集上选
fit <- cv.glmnet(as.matrix(mt_tr[qcols]), mt_tr$y, alpha = 0)
meta_te <- mt_te |> mutate(fused = as.numeric(predict(fit, as.matrix(mt_te[qcols]), s = "lambda.min")))
meta_te <- meta_te |> mutate(equal = (rank(gbdt) + rank(linear)) / (2 * n()))

# 三种方案的 IC 对照沿用第 007 章的检验函数
for (col in c("gbdt", "linear", "equal", "fused")) {
  dat <- meta_te |> rename(f = all_of(col))
  ic <- cross_section_ic(dat, "f", "y")
  print(list(方案 = col, 汇总 = ic_summary(ic)))
}
