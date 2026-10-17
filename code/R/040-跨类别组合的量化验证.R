# ============================================================
# 第040章 跨类别组合的量化验证
# 模块 07 跨类组合
# 源文件：模块07-跨类组合/第040章-跨类别组合的量化验证.md
# ============================================================
# 本文件由 scripts/extract_code.py 自动生成，请勿直接编辑。
# 修改代码请改 Markdown 源稿，再重新运行提取脚本。
#
# 依赖：先加载同目录下的公共函数与数据准备
#   source("code/R/00-common.R")
#   source("code/R/00-data.R")
#
# ------------------------------------------------------------

# ---- 代码块 1：跨类组合的互补性来源 ----

# 四类代表特征的横截面平均相关系数
feats <- c("sma_dev", "rsi_dev", "atr_rank", "obv_change")

# 先按日做横截面标准化，再逐日计算相关矩阵并求平均
z <- panel |>
  group_by(date) |>
  mutate(across(all_of(feats), function(x) {
    # constant = 1 取裸中位绝对差，与 Python 侧一致
    m <- mad(x, na.rm = TRUE, constant = 1)
    if (isTRUE(m > 0)) (x - median(x, na.rm = TRUE)) / m else 0
  })) |>
  ungroup()

avg_corr <- matrix(0, length(feats), length(feats), dimnames = list(feats, feats))
for (d in split(z, z$date)) {
  cm <- cor(as.matrix(d[, feats]), method = "spearman")
  avg_corr <- avg_corr + replace(cm, is.na(cm), 0)
}
avg_corr <- avg_corr / length(unique(z$date))
print(round(avg_corr, 2))

# ---- 代码块 2：跨类组合的互补性来源 ----

# 正交化：把震荡特征对趋势特征做横截面回归，取残差作为增量因子
panel <- panel |>
  group_by(date) |>
  mutate(rsi_resid = {
    d <- pick(sma_dev, rsi_dev)
    ok <- stats::complete.cases(d)
    out <- rep(NA_real_, dplyr::n())
    if (sum(ok) >= 5) {
      out[ok] <- stats::resid(stats::lm(rsi_dev ~ sma_dev, data = d[ok, ]))
    }
    out
  }) |>
  ungroup()

print(ic_summary(cross_section_ic(panel, "rsi_resid", "forward_5")))
# 残差因子的 IC 若仍为正，说明震荡特征含有趋势之外的信息

# ---- 代码块 3：组合方法及其检验 ----

# 等权合成：weights 留空
panel <- combined_signal(panel, c("sma_dev", "rsi_dev", "atr_rank", "obv_change"))
ic_eq <- cross_section_ic(panel, "combined", "forward_5")
print(ic_summary(ic_eq))
# 与四个单特征的 ICIR 并列，判断组合是否高于上界

# ---- 代码块 4：组合方法及其检验 ----

# IC 加权：先用单特征 IC 均值构造权重
feats <- c("sma_dev", "rsi_dev", "atr_rank", "obv_change")
ic_means <- sapply(feats, function(f) {
  ic_summary(cross_section_ic(panel, f, "forward_5"))$IC均值
})
w_ic <- ic_means / sum(abs(ic_means))
print(round(w_ic, 3))

panel <- combined_signal(panel, feats, weights = as.numeric(w_ic))
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))

# ---- 代码块 5：组合方法及其检验 ----

# ICIR 加权：用 IC 均值与 IC 标准差构造权重
feats <- c("sma_dev", "rsi_dev", "atr_rank", "obv_change")
icirs <- sapply(feats, function(f) {
  ic_summary(cross_section_ic(panel, f, "forward_5"))$ICIR
})
w_icir <- icirs / sum(icirs)

panel <- combined_signal(panel, feats, weights = as.numeric(w_icir))
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))

# ---- 代码块 6：组合方法及其检验 ----

# 最优化权重：最大化组合 IC 均值与标准差的比值，限制单特征权重上限
feats <- c("sma_dev", "rsi_dev", "atr_rank", "obv_change")

# 各特征 IC 序列按日期对齐
ic_df <- NULL
for (f in feats) {
  one <- cross_section_ic(panel, f, "forward_5")
  colnames(one)[colnames(one) == "ic"] <- f
  ic_df <- if (is.null(ic_df)) one else merge(ic_df, one, by = "date")
}
mu <- colMeans(ic_df[, feats])
sigma <- cov(ic_df[, feats])

neg_ratio <- function(w) {
  -(w %*% mu) / sqrt(as.numeric(w %*% sigma %*% w) + 1e-12)
}
# 单特征权重上限 0.5，抑制极端解；归一后再比较
res <- stats::optim(rep(1 / length(feats), length(feats)), neg_ratio,
                    method = "L-BFGS-B",
                    lower = rep(0, length(feats)), upper = rep(0.5, length(feats)))
w_opt <- res$par / sum(res$par)
print(round(stats::setNames(w_opt, feats), 3))

# ---- 代码块 7：组合方法及其检验 ----

# 条件组合：用趋势状态做掩码，只在趋势成立时启用震荡信号
# 掩码变量：价格是否在 20 日均线上方（sma_dev 大于零）
panel <- panel |>
  mutate(mask = ifelse(sma_dev > 0, 1L, 0L),
         rsi_masked = ifelse(sma_dev > 0, rsi_dev, NA_real_))

for (v in c(0L, 1L)) {
  sub <- panel |> filter(mask == v)
  s <- ic_summary(cross_section_ic(sub, "rsi_dev", "forward_5"))
  print(list(掩码取值 = v, IC均值 = s$IC均值, ICIR = s$ICIR))
}

# 与全样本的无条件 IC 对照
print(ic_summary(cross_section_ic(panel, "rsi_dev", "forward_5"))$ICIR)

# ---- 代码块 8：组合方法及其检验 ----

library(dplyr)
library(TTR)

# 类内合成：按日期分组做横截面标准化，再取类内均值
class_score <- function(panel, cols, name) {
  panel |>
    group_by(date) |>
    mutate(across(all_of(cols),
      ~ (.x - median(.x, na.rm = TRUE)) / mad(.x, na.rm = TRUE, constant = 1))) |>
    summarise(score = rowMeans(across(all_of(cols)), na.rm = TRUE),
              .groups = "drop") |>
    rename(!!name := score)
}

# 类间合成：对四个类别分数再做一次等权或加权平均
final <- class_score(panel, "sma_dev", "s_trend") |>
  left_join(class_score(panel, "rsi_dev", "s_osc"), by = "date") |>
  left_join(class_score(panel, "atr_rank", "s_vol"), by = "date") |>
  left_join(class_score(panel, "obv_change", "s_vp"), by = "date") |>
  mutate(combined = rowMeans(pick(s_trend, s_osc, s_vol, s_vp), na.rm = TRUE))

# ---- 代码块 9：组合增益的归因 ----

# 增益归因：分别比较组合与单特征的三个量
triple <- function(col) {
  s <- ic_summary(cross_section_ic(panel, col, "forward_5"))
  c(IC均值 = s$IC均值, IC标准差 = s$IC标准差, ICIR = s$ICIR)
}

panel <- combined_signal(panel, c("sma_dev", "rsi_dev"))
print(rbind(甲 = triple("sma_dev"), 乙 = triple("rsi_dev"), 组合 = triple("combined")))
# 判读：IC 均值上升且标准差基本不变，倾向信息互补
#       均值不变而标准差下降，倾向风险分散
#       样本内三项都明显更优但样本外回落，倾向权重拟合

# ---- 代码块 10：组合增益的归因 ----

# 样本内外对照：识别权重拟合
cut <- as.Date(quantile(as.numeric(panel$date), 0.6), origin = "1970-01-01")   # 前 60% 作样本内

icir_of <- function(df, col) ic_summary(cross_section_ic(df, col, "forward_5"))$ICIR

panel <- combined_signal(panel, c("sma_dev", "rsi_dev"))       # 等权组合
print(list(样本内_等权 = icir_of(panel |> filter(date <= cut), "combined"),
           样本外_等权 = icir_of(panel |> filter(date >  cut), "combined")))
# 再用样本内估计的 ICIR 权重合成，重算两段，比较样本内外的差距是否扩大

# ---- 代码块 11：组合的截面验证 ----

# 四类代表特征的构造口径（参见第 60、65、70、75 章）
panel <- panel |>
  group_by(code) |>
  mutate(
    sma20 = zoo::rollmean(close, 20, fill = NA, align = "right"),
    sma_dev = close / sma20 - 1,
    rsi14 = TTR::RSI(close, n = 14),
    rsi_dev = rsi14 - 50,
    atr14 = TTR::ATR(cbind(High = high, Low = low, Close = close), n = 14)[, "atr"],
    atr_ratio = atr14 / close,
    obv = TTR::OBV(close, volume),
    obv_change = (obv - dplyr::lag(obv, 10)) / abs(dplyr::lag(obv, 10))
  ) |>
  ungroup()

# 波动率取横截面分位
panel <- panel |>
  group_by(date) |>
  mutate(atr_rank = rank(atr_ratio, ties.method = "average") / dplyr::n()) |>
  ungroup()

# ---- 代码块 12：组合的截面验证 ----

# 分步合成：从两个特征开始，逐个加入
steps <- list(c("sma_dev", "rsi_dev"),
              c("sma_dev", "rsi_dev", "atr_rank"),
              c("sma_dev", "rsi_dev", "atr_rank", "obv_change"))

for (cols in steps) {
  panel <- combined_signal(panel, cols)
  # 去极值：标准化后的列截断在正负 3 之间，再重新平均
  zcols <- grep("_z$", colnames(panel), value = TRUE)
  panel <- panel |> mutate(across(all_of(zcols), ~ pmin(pmax(.x, -3), 3)))
  panel$combined <- rowMeans(panel[, zcols, drop = FALSE], na.rm = TRUE)
  s <- ic_summary(cross_section_ic(panel, "combined", "forward_5"))
  print(list(特征数 = length(cols), IC均值 = s$IC均值,
             IC标准差 = s$IC标准差, ICIR = s$ICIR))
}

# ---- 代码块 13：组合的截面验证 ----

# 分步合成的边际贡献（示意）
labels <- c("趋势", "加震荡", "加波动率", "加量价")
combos <- list("sma_dev", c("sma_dev", "rsi_dev"),
               c("sma_dev", "rsi_dev", "atr_rank"),
               c("sma_dev", "rsi_dev", "atr_rank", "obv_change"))
icir_vals <- mean_vals <- numeric(length(combos))
for (i in seq_along(combos)) {
  panel <- combined_signal(panel, combos[[i]])
  s <- ic_summary(cross_section_ic(panel, "combined", "forward_5"))
  icir_vals[i] <- s$ICIR
  mean_vals[i] <- s$IC均值
}

# 双轴展示：柱形为 ICIR，折线为 IC 均值
par(mar = c(4, 4, 3, 4))
bp <- barplot(icir_vals, names.arg = labels, col = "steelblue",
              ylab = "ICIR", main = "分步合成的边际贡献（示意）")
par(new = TRUE)
plot(as.numeric(bp), mean_vals, type = "b", pch = 19, axes = FALSE, xlab = "", ylab = "")
axis(4, col.axis = "gray30")
mtext("IC 均值", side = 4, line = 2.5)
legend("topright", legend = c("ICIR", "IC 均值"), pch = c(15, 19),
       col = c("steelblue", "black"), bty = "n")

# ---- 代码块 14：组合的择时验证 ----

# 把截面组合分数聚合成市场时序信号
panel <- combined_signal(panel, c("sma_dev", "rsi_dev", "atr_rank", "obv_change"))
market <- panel |>
  group_by(date) |>
  summarise(mkt_signal = median(combined, na.rm = TRUE),   # 横截面中位数，代表市场整体状态
            mkt_ret = mean(forward_1, na.rm = TRUE),       # 等权平均的前向收益，作为市场收益代理
            .groups = "drop")

# 与单个趋势特征的择时结果对照
single <- panel |>
  group_by(date) |>
  summarise(mkt_signal = median(sma_dev, na.rm = TRUE),
            mkt_ret = mean(forward_1, na.rm = TRUE),
            .groups = "drop")

print(timing_backtest(market, "mkt_signal", "mkt_ret", entry_q = 0.7))
print(timing_backtest(single, "mkt_signal", "mkt_ret", entry_q = 0.7))
print(conditional_quantile_return(market, "mkt_signal", "mkt_ret", q = 5))

# ---- 代码块 15：组合的择时验证 ----

# 组合信号择时与买入持有的净值对照（示意）
market <- market |>
  arrange(date) |>
  mutate(pos = ifelse(mkt_signal > quantile(mkt_signal, 0.7, na.rm = TRUE), 1, 0),
         strat = dplyr::lag(pos, 1, default = 0) * mkt_ret)

curve <- data.frame(
  date = market$date,
  组合择时 = cumprod(1 + ifelse(is.na(market$strat), 0, market$strat)),
  买入持有 = cumprod(1 + ifelse(is.na(market$mkt_ret), 0, market$mkt_ret))
)
plot(curve$date, curve$组合择时, type = "l", col = "steelblue",
     ylab = "净值", xlab = "", main = "组合信号择时与买入持有对照（示意）")
lines(curve$date, curve$买入持有, col = "gray50")
legend("topleft", legend = c("组合择时", "买入持有"),
       col = c("steelblue", "gray50"), lty = 1, bty = "n")
