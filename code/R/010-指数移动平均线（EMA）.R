# ============================================================
# 第010章 指数移动平均线（EMA）
# 模块 03 趋势类指标
# 源文件：模块03-趋势类指标/第010章-指数移动平均线（EMA）.md
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
.sub <- panel[panel$code == "600519.SS", ]
data <- xts::xts(.sub[, c("open", "high", "low", "close", "volume", "adjusted")],
                 order.by = as.Date(.sub$date))
colnames(data) <- c("Open", "High", "Low", "Close", "Volume", "Adjusted")
close_price <- Cl(data)

# 3. 计算 EMA（TTR 的 EMA 以首个可用值作为递推起点）
ema_12 <- EMA(close_price, n = 12)
ema_26 <- EMA(close_price, n = 26)

# 4. 识别信号：12 日 EMA 上穿 26 日为金叉
cross_up   <- crossover(ema_12, ema_26)
cross_down <- crossover(ema_26, ema_12)
cat("金叉次数：", sum(cross_up, na.rm = TRUE), "\n")
cat("死叉次数：", sum(cross_down, na.rm = TRUE), "\n")

# 5. 绘图
chartSeries(data, theme = "white", name = "贵州茅台",
  TA = "addEMA(n = 12, col = 'blue'); addEMA(n = 26, col = 'red')")

# 6. 输出统计：12 日 EMA 与 26 日 EMA 的方向一致天数占比
same_dir <- sum(sign(diff(ema_12)) == sign(diff(ema_26)), na.rm = TRUE)
cat("两条 EMA 方向一致的比例：",
    round(same_dir / (length(ema_12) - 1), 3), "\n")

# ---- 代码块 2：拆解 ----

# 沿用第 007 章口径，拆解主要特征
panel <- panel |>
  group_by(code) |>
  mutate(ema20 = TTR::EMA(close, 20),
         ema_dev = close / ema20 - 1,
         ema_slope = ema20 / dplyr::lag(ema20, 5) - 1,
         ema_gap = TTR::EMA(close, 12) / TTR::EMA(close, 26) - 1) |>
  ungroup()

panel |> select(ema_dev, ema_slope, ema_gap) |>
  cor(use = "complete.obs", method = "spearman") |> print()

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
panel <- panel |>
  group_by(code) |>
  mutate(ema_dev = close / TTR::EMA(close, 20) - 1,
         sma_dev = close / zoo::rollmean(close, 20, fill = NA, align = "right") - 1) |>
  ungroup()

# 同源对照：同一交易日、同一前向窗口，比较两条 IC 序列的差值
ic_ema <- cross_section_ic(panel, "ema_dev", "forward_5")
ic_sma <- cross_section_ic(panel, "sma_dev", "forward_5")
common <- intersect(names(ic_ema), names(ic_sma))
d <- ic_ema[common] - ic_sma[common]
cat("IC 差值均值：", round(mean(d), 4), " t 值：",
    round(mean(d) / sd(d) * sqrt(length(d)), 2), "\n")

print(ic_summary(ic_ema))
print(ic_summary(ic_sma))
print(layered_returns(panel, "ema_dev", "forward_5"))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df <- panel |> filter(code == "600519.SS")

# 快慢 EMA 差作为连续状态量，比 0/1 的交叉标记保留更多信息
df <- df |>
  mutate(ema_gap = TTR::EMA(close, 12) / TTR::EMA(close, 26) - 1)

print(timing_signal_test(df, "ema_gap", "forward_5", upper = 0.8))
print(conditional_quantile_return(df, "ema_gap", "forward_5", q = 5))
print(timing_backtest(df, "ema_gap", "forward_5", entry_q = 0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
panel <- panel |>
  group_by(date) |>
  mutate(vol_ratio = volume / zoo::rollmean(volume, 20, fill = NA, align = "right")) |>
  ungroup()

# 先看横截面相关，再决定是否值得组合
panel |>
  group_by(date) |>
  summarise(rho = cor(ema_dev, vol_ratio, method = "spearman",
                      use = "complete.obs"), .groups = "drop") |>
  summarise(平均相关 = round(mean(rho, na.rm = TRUE), 3)) |>
  print()

panel <- combined_signal(panel, c("ema_dev", "vol_ratio"))

print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "ema_dev", "forward_5")))
print(ic_summary(cross_section_ic(panel, "vol_ratio", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(ema20 = as.numeric(TTR::EMA(close, 20)),
         # ADX 需要高、低、收三列，取 14 日
         adx14 = as.numeric(TTR::ADX(cbind(High = high, Low = low, Close = close),
                                     n = 14)[, "ADX"]),
         # 组合条件：价格在二十日 EMA 上方且趋势强度高于二十五
         cond = as.integer(close > ema20 & adx14 > 25))

cat("--- 组合条件 ---\n")
print(timing_backtest(df, "cond", "forward_5", entry_q = 0.5))

# 单条件对照
df <- df |>
  mutate(cond_ema = as.integer(close > ema20),
         cond_adx = as.integer(adx14 > 25))

cat("\n--- 仅价格位置 ---\n")
print(timing_backtest(df, "cond_ema", "forward_5", entry_q = 0.5))

cat("\n--- 仅趋势强度 ---\n")
print(timing_backtest(df, "cond_adx", "forward_5", entry_q = 0.5))
