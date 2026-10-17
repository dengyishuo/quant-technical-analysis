# ============================================================
# 第045章 状态模型：市场状态与自适应
# 模块 08 机器学习挖掘与融合
# 源文件：模块08-机器学习挖掘与融合/第045章-状态模型：市场状态与自适应.md
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

library(quantmod)
library(dplyr)
library(zoo)

codes <- c("600519.SS", "600036.SS", "601318.SS", "300750.SZ", "000858.SZ")

frames <- lapply(codes, function(cd) {
  x <- local({
    # 从本地 CSV 取该标的，转成 quantmod 可用的 xts
    .p <- read.csv("data/parquet/panel_blue_chip.csv", stringsAsFactors = FALSE)
    .p <- .p[.p$code == cd, ]
    .x <- xts::xts(.p[, c("open", "high", "low", "close", "volume", "adjusted")],
                       order.by = as.Date(.p$date))
    colnames(.x) <- c("Open", "High", "Low", "Close", "Volume", "Adjusted")
    .x
  })
  d <- data.frame(
    date   = index(x),
    close  = as.numeric(Cl(x)),
    volume = as.numeric(Vo(x)),
    code   = cd
  )
  d |>
    mutate(
      ret1 = close / dplyr::lag(close) - 1,
      vol20 = zoo::rollapply(ret1, 20, sd, fill = NA, align = "right"),
      ma20 = zoo::rollmean(close, 20, fill = NA, align = "right"),
      # 简化的趋势强度：价格偏离二十日均线的绝对值，再平滑
      trend = zoo::rollapply(abs(close / ma20 - 1), 14, mean, fill = NA, align = "right") * 100,
      forward_5 = close / dplyr::lead(close, 5) - 1)
})
panel <- bind_rows(frames)
panel <- panel[stats::complete.cases(panel[, c("vol20", "trend")]), ]

# 市场层的状态变量：横截面均值，代表整体市况
market <- panel |>
  group_by(date) |>
  summarise(mvol = mean(vol20, na.rm = TRUE),
            mtrend = mean(trend, na.rm = TRUE), .groups = "drop") |>
  arrange(date)

# 波动率分位用滚动窗口计算，避免全样本分位带来的未来信息
W <- 120
market <- market |>
  mutate(vol_pct = zoo::rollapply(mvol, W, function(x) mean(x > x[length(x)]),
                                  fill = NA, align = "right"),
         trend_med = median(mtrend, na.rm = TRUE),
         state_rule = dplyr::case_when(
           vol_pct >= 0.5 & mtrend >= trend_med ~ "高波趋势",
           vol_pct <  0.5 & mtrend >= trend_med ~ "低波趋势",
           vol_pct >= 0.5 & mtrend <  trend_med ~ "高波震荡",
           TRUE ~ "低波震荡"))

panel <- panel |> left_join(market[, c("date", "state_rule")], by = "date")
print(table(panel$state_rule))

# ---- 代码块 2：代码实现 ----

# 沿用第 007 章的 cross_section_ic / ic_summary
panel <- panel |>
  group_by(code) |>
  mutate(sma20 = zoo::rollmean(close, 20, fill = NA, align = "right"),
         sma_dev = close / sma20 - 1) |>
  ungroup()

# 分状态计算同一个因子的 IC
for (st in sort(unique(panel$state_rule))) {
  sub <- panel |> filter(state_rule == st)
  s <- ic_summary(cross_section_ic(sub, "sma_dev", "forward_5"))
  print(list(状态 = st, IC均值 = s$IC均值, ICIR = s$ICIR, 样本期数 = s$样本期数))
}

# ---- 代码块 3：代码实现 ----

# HMM 状态与波动率对照（示意），state_hmm 取自本节 HMM 块解码的结果
m <- market |> filter(!is.na(mvol), !is.na(mtrend))
m$state_hmm <- dat$state_hmm[match(m$date, dat$date)]

par(mfrow = c(2, 1), mar = c(4, 4, 3, 1))
plot(m$date, m$mvol, type = "l", col = "steelblue",
     ylab = "市场平均波动率", main = "HMM 状态与波动率（示意）")
plot(m$date, m$state_hmm, pch = 19, cex = 0.5, col = "gray30",
     ylab = "状态编号", xlab = "")

# ---- 代码块 4：代码实现 ----

# 状态自适应权重：状态内用 ICIR 加权，再向全样本权重收缩
state_weights <- function(panel, feats, state_col, lam = 0.5) {
  glob <- sapply(feats, function(f) ic_summary(cross_section_ic(panel, f, "forward_5"))$ICIR)
  g_sum <- sum(abs(glob)); if (g_sum == 0) g_sum <- 1
  w_global <- glob / g_sum

  out <- list()
  for (st in sort(unique(panel[[state_col]]))) {
    if (is.na(st)) next
    sub <- panel[panel[[state_col]] == st, ]
    w <- sapply(feats, function(f) ic_summary(cross_section_ic(sub, f, "forward_5"))$ICIR)
    s_sum <- sum(abs(w)); if (s_sum == 0) s_sum <- 1
    w_state <- w / s_sum
    # 向全样本权重收缩
    out[[as.character(st)]] <- (1 - lam) * w_state + lam * w_global
  }
  out
}

feats <- c("sma_dev", "vol20")     # 示意用两个因子
w_by_state <- state_weights(panel, feats, "state_rule", lam = 0.5)
print(lapply(w_by_state, function(w) round(w, 3)))

# ---- 代码块 5：代码实现 ----

library(depmixS4)
library(dplyr)
library(TTR)

# 假设 market 已含 date / mvol / mtrend 三列
dat <- market |> filter(!is.na(mvol), !is.na(mtrend))

# 三个状态的 HMM，观测为两个连续变量，用高斯发射
mod <- depmix(list(mvol ~ 1, mtrend ~ 1), data = dat,
              nstates = 3, family = list(gaussian(), gaussian()))
fit <- fit(mod, verbose = FALSE)

# 后验状态概率与解码序列
post <- posterior(fit)
dat$state_hmm <- post$state

# 分状态统计趋势因子的 IC（因子列假设已并入 dat）
for (st in sort(unique(dat$state_hmm))) {
  sub <- dat[dat$state_hmm == st, ]
  if (nrow(sub) > 30) {
    print(list(状态 = st, 样本数 = nrow(sub)))
  }
}
