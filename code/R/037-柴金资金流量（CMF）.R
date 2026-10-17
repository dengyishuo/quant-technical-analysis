# ============================================================
# 第037章 柴金资金流量（CMF）
# 模块 06 量价类指标
# 源文件：模块06-量价类指标/第037章-柴金资金流量（CMF）.md
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

# 1. 加载包
library(quantmod)
library(TTR)

# 2. 获取数据
panel <- read.csv("data/parquet/panel_blue_chip.csv", stringsAsFactors = FALSE)
.sub <- panel[panel$code == "300750.SZ", ]
data <- xts::xts(.sub[, c("open", "high", "low", "close", "volume", "adjusted")],
                 order.by = as.Date(.sub$date))
colnames(data) <- c("Open", "High", "Low", "Close", "Volume", "Adjusted")
high_price <- Hi(data)
low_price  <- Lo(data)
close_price <- Cl(data)
volume <- Vo(data)

# 3. 计算指标：TTR 的 CMF 默认 n = 20
cmf20 <- CMF(high_price, low_price, close_price, volume, n = 20)
cmf_ma <- SMA(cmf20, n = 10)

# 4. 识别信号：CMF 穿越零轴与阈值
cross_zero_up <- crossover(cmf20, 0)
above_thresh  <- sum(cmf20 > 0.05, na.rm = TRUE)
below_thresh  <- sum(cmf20 < -0.05, na.rm = TRUE)
cat("CMF 上穿零轴次数：", sum(cross_zero_up, na.rm = TRUE), "\n")
cat("CMF 高于 0.05 的天数：", above_thresh, "\n")
cat("CMF 低于 -0.05 的天数：", below_thresh, "\n")

# 5. 绘图
chartSeries(data, theme = "white", name = "宁德时代",
  TA = "addCMF(n = 20)")

# 6. 输出统计：CMF 的分布特征
cat("CMF 均值：", round(mean(cmf20, na.rm = TRUE), 4), "\n")
cat("CMF 标准差：", round(sd(cmf20, na.rm = TRUE), 4), "\n")
cat("CMF 的取值范围：", round(min(cmf20, na.rm = TRUE), 3), "至",
    round(max(cmf20, na.rm = TRUE), 3), "\n")

# ---- 代码块 2：拆解 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
library(dplyr)

# panel 已含 date / code / high / low / close / volume / forward_1 / forward_5
panel <- panel |>
  group_by(code) |>
  arrange(date, .by_group = TRUE) |>
  mutate(
    # CMF 有界于 -1 到 1，当期读数可读但噪声大
    cmf20 = as.numeric(TTR::CMF(
      cbind(High = high, Low = low, Close = close), volume, n = 20)),
    cmf_state = sign(cmf20),
    # 5 日均值：压掉日频锯齿，保留方向
    cmf_ma5 = zoo::rollmean(cmf20, 5, fill = NA, align = "right"),
    cmf_chg = cmf20 - dplyr::lag(cmf20, 10),
    # 零轴上方持续期，带符号
    above = as.integer(!is.na(cmf20) & cmf20 > 0),
    run_id = cumsum(above != dplyr::lag(above, default = dplyr::first(above))),
    run_len = ave(above, run_id, FUN = seq_along),
    cmf_dur = ifelse(above == 1, run_len, -run_len)
  ) |>
  ungroup() |>
  mutate(cmf_dur = ifelse(is.na(cmf20), NA_real_, cmf_dur))

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# 平滑读数与变化量分别检验
for (f in c("cmf_ma5", "cmf_chg")) {
  cat("\n---", f, "vs forward_5 ---\n")
  print(ic_summary(cross_section_ic(panel, f, "forward_5")))
}

print(layered_returns(panel, "cmf_ma5", "forward_5"))

# 对同期动量取残差，看是否还有独立信息
panel <- panel |>
  group_by(code) |>
  mutate(mom20 = close / dplyr::lag(close, 20) - 1) |>
  ungroup()

panel <- panel |>
  group_by(date) |>
  mutate(cmf_resid = {
    ok <- !is.na(cmf_ma5) & !is.na(mom20)
    r <- rep(NA_real_, dplyr::n())
    # 横截面样本足够时才回归，避免小样本给出无意义的残差
    if (sum(ok) >= 10) r[ok] <- residuals(lm(cmf_ma5[ok] ~ mom20[ok]))
    r
  }) |>
  ungroup()

cat("\n--- 动量残差 ---\n")
print(ic_summary(cross_section_ic(panel, "cmf_resid", "forward_5")))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df <- panel |> filter(code == "600519.SS") |> arrange(date)

cat("--- 信号触发日检验（读数高于 80 分位）---\n")
print(timing_signal_test(df, "cmf_ma5", "forward_5", upper = 0.8))

cat("\n--- 条件分位收益（读数分五档）---\n")
print(conditional_quantile_return(df, "cmf_ma5", "forward_5", q = 5))

cat("\n--- 择时策略与买入持有对照 ---\n")
print(timing_backtest(df, "cmf_ma5", "forward_5", entry_q = 0.6))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
panel <- panel |>
  group_by(code) |>
  mutate(vol_ratio = volume / zoo::rollmean(volume, 20, fill = NA, align = "right")) |>
  ungroup()

panel |>
  group_by(date) |>
  filter(!is.na(cmf_ma5), !is.na(vol_ratio)) |>
  summarise(rho = cor(cmf_ma5, vol_ratio, method = "spearman",
                      use = "complete.obs"), .groups = "drop") |>
  summarise(平均相关 = round(mean(rho, na.rm = TRUE), 3)) |>
  print()

panel <- combined_signal(panel, c("cmf_ma5", "vol_ratio"))

cat("\n--- 组合 vs 单特征 ---\n")
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "cmf_ma5", "forward_5")))
print(ic_summary(cross_section_ic(panel, "vol_ratio", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
df2 <- panel |>
  filter(code == "600519.SS") |>
  arrange(date) |>
  mutate(sma20 = as.numeric(TTR::SMA(close, 20)),
         cond = as.integer(cmf_ma5 > 0.05 & close > sma20))

print(timing_backtest(df2, "cond", "forward_5", entry_q = 0.5))
