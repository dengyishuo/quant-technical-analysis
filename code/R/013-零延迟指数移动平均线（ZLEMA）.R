# ============================================================
# 第013章 零延迟指数移动平均线（ZLEMA）
# 模块 03 趋势类指标
# 源文件：模块03-趋势类指标/第013章-零延迟指数移动平均线（ZLEMA）.md
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

# 3. 计算 ZLEMA，并与同周期 EMA 对比
zlema_20 <- ZLEMA(close_price, n = 20)
ema_20   <- EMA(close_price, n = 20)

# 4. 识别信号：ZLEMA 拐头方向
turn_up   <- Lag(zlema_20) < zlema_20 & Lag(zlema_20, 2) >= Lag(zlema_20)
turn_down <- Lag(zlema_20) > zlema_20 & Lag(zlema_20, 2) <= Lag(zlema_20)
cat("向上拐头次数：", sum(turn_up, na.rm = TRUE), "\n")
cat("向下拐头次数：", sum(turn_down, na.rm = TRUE), "\n")

# 5. 绘图
chartSeries(data, theme = "white", name = "贵州茅台",
  TA = "addZLEMA(n = 20, col = 'darkgreen'); addEMA(n = 20, col = 'blue')")

# 6. 输出统计：ZLEMA 相对 EMA 的平均提前量（以价格偏离衡量）
lead <- mean((zlema_20 - ema_20), na.rm = TRUE)
cat("ZLEMA20 与 EMA20 的平均价差：", round(lead, 3), "元\n")

# ---- 代码块 2：拆解 ----

# 沿用第 007 章口径，拆解四个特征
panel <- panel |>
  group_by(code) |>
  mutate(zlema20 = TTR::ZLEMA(close, 20),
         ema20 = TTR::EMA(close, 20),
         zlema_dev = close / zlema20 - 1,
         zlema_slope = zlema20 / dplyr::lag(zlema20, 5) - 1,
         zl_gap = zlema20 / ema20 - 1,
         r_lag = close / dplyr::lag(close, 9) - 1) |>
  ungroup()

panel |> select(zlema_dev, zlema_slope, zl_gap, r_lag) |>
  cor(use = "complete.obs", method = "spearman") |> print()

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
panel <- panel |>
  group_by(code) |>
  mutate(ema_dev = close / TTR::EMA(close, 20) - 1) |>
  ungroup()

# 去滞后是否优于普通 EMA，以及窗口位移本身的预测力
ic_zl <- cross_section_ic(panel, "zlema_dev", "forward_5")
ic_ema <- cross_section_ic(panel, "ema_dev", "forward_5")
common <- intersect(names(ic_zl), names(ic_ema))
d <- ic_zl[common] - ic_ema[common]
cat("IC 差值均值：", round(mean(d), 4), " t 值：",
    round(mean(d) / sd(d) * sqrt(length(d)), 2), "\n")

print(ic_summary(ic_zl))
print(ic_summary(ic_ema))
print(ic_summary(cross_section_ic(panel, "r_lag", "forward_5")))
print(layered_returns(panel, "zlema_dev", "forward_5"))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df <- panel |> filter(code == "600519.SS")

# 去滞后量作为连续状态
print(timing_signal_test(df, "zl_gap", "forward_5", upper = 0.8))
print(conditional_quantile_return(df, "zl_gap", "forward_5", q = 5))
print(timing_backtest(df, "zl_gap", "forward_5", entry_q = 0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
panel <- panel |>
  group_by(date) |>
  mutate(vol_ratio = volume / zoo::rollmean(volume, 20, fill = NA, align = "right")) |>
  ungroup()

rho <- panel |> group_by(date) |>
  summarise(r = cor(zlema_dev, r_lag, method = "spearman", use = "complete.obs"))
cat("偏离度与窗口位移的平均相关：", round(mean(rho$r, na.rm = TRUE), 3), "\n")

panel <- combined_signal(panel, c("zlema_dev", "vol_ratio"))

print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "zlema_dev", "forward_5")))
print(ic_summary(cross_section_ic(panel, "vol_ratio", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(zlema20 = as.numeric(TTR::ZLEMA(close, 20)),
         ema20 = as.numeric(TTR::EMA(close, 20)),
         zlema_dev = close / zlema20 - 1,
         zl_gap = zlema20 / ema20 - 1,
         # 组合条件：价格在去滞后均线上方，且去滞后量为正
         cond = as.integer(zlema_dev > 0 & zl_gap > 0))

cat("--- 组合条件 ---\n")
print(timing_backtest(df, "cond", "forward_5", entry_q = 0.5))

# 单条件对照
df <- df |>
  mutate(cond_dev = as.integer(zlema_dev > 0),
         cond_gap = as.integer(zl_gap > 0))

cat("\n--- 仅偏离度 ---\n")
print(timing_backtest(df, "cond_dev", "forward_5", entry_q = 0.5))

cat("\n--- 仅去滞后量 ---\n")
print(timing_backtest(df, "cond_gap", "forward_5", entry_q = 0.5))
