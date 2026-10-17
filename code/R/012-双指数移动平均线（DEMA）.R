# ============================================================
# 第012章 双指数移动平均线（DEMA）
# 模块 03 趋势类指标
# 源文件：模块03-趋势类指标/第012章-双指数移动平均线（DEMA）.md
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

# 3. 计算 DEMA 与同周期 EMA、SMA 作对比
dema_20 <- DEMA(close_price, n = 20)
ema_20  <- EMA(close_price, n = 20)
sma_20  <- SMA(close_price, n = 20)

# 4. 识别信号：DEMA20 上穿 EMA20 视为趋势加速
accel_up   <- crossover(dema_20, ema_20)
accel_down <- crossover(ema_20, dema_20)
cat("加速上行次数：", sum(accel_up, na.rm = TRUE), "\n")
cat("加速下行次数：", sum(accel_down, na.rm = TRUE), "\n")

# 5. 绘图
chartSeries(data, theme = "white", name = "贵州茅台",
  TA = "addDEMA(n = 20, col = 'purple'); addEMA(n = 20, col = 'blue')")

# 6. 输出统计：DEMA 相对 EMA 的平均提前量
lead <- mean((dema_20 - ema_20) / ema_20, na.rm = TRUE)
cat("DEMA20 相对 EMA20 的平均相对偏离：", round(lead, 4), "\n")

# ---- 代码块 2：拆解 ----

# 沿用第 007 章口径，拆解主要特征
panel <- panel |>
  group_by(code) |>
  mutate(ema20 = TTR::EMA(close, 20),
         dema20 = TTR::DEMA(close, 20),
         dema_dev = close / dema20 - 1,
         accel = dema20 / ema20 - 1,
         comp = ifelse(abs(close - ema20) > 1e-6,
                       (dema20 - ema20) / (close - ema20), NA_real_)) |>
  ungroup()

panel |> select(dema_dev, accel, comp) |>
  cor(use = "complete.obs", method = "spearman") |> print()

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# dema_dev 沿用拆解中已算出的结果
panel <- panel |>
  group_by(code) |>
  mutate(ema_dev = close / TTR::EMA(close, 20) - 1) |>
  ungroup()

# 补偿是否带来增量：与同周期 EMA 成对比较
ic_dema <- cross_section_ic(panel, "dema_dev", "forward_5")
ic_ema <- cross_section_ic(panel, "ema_dev", "forward_5")
common <- intersect(names(ic_dema), names(ic_ema))
d <- ic_dema[common] - ic_ema[common]
cat("IC 差值均值：", round(mean(d), 4), " t 值：",
    round(mean(d) / sd(d) * sqrt(length(d)), 2), "\n")

print(ic_summary(ic_dema))
print(ic_summary(ic_ema))
print(layered_returns(panel, "dema_dev", "forward_5"))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df <- panel |> filter(code == "600519.SS")

# 加速量作为连续状态，正为向上外推
df <- df |> mutate(accel = TTR::DEMA(close, 20) / TTR::EMA(close, 20) - 1)

print(timing_signal_test(df, "accel", "forward_5", upper = 0.8))
print(conditional_quantile_return(df, "accel", "forward_5", q = 5))
print(timing_backtest(df, "accel", "forward_5", entry_q = 0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
panel <- panel |>
  group_by(date) |>
  mutate(vol_ratio = volume / zoo::rollmean(volume, 20, fill = NA, align = "right")) |>
  ungroup()

# 负面对照：同源因子的相关通常极高
rho <- panel |> group_by(date) |>
  summarise(r = cor(dema_dev, ema_dev, method = "spearman", use = "complete.obs"))
cat("DEMA 与 EMA 的平均相关：", round(mean(rho$r, na.rm = TRUE), 3), "\n")

panel <- combined_signal(panel, c("dema_dev", "vol_ratio"))

print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "dema_dev", "forward_5")))
print(ic_summary(cross_section_ic(panel, "vol_ratio", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(dema20 = as.numeric(TTR::DEMA(close, 20)),
         ema20 = as.numeric(TTR::EMA(close, 20)),
         dema_dev = close / dema20 - 1,
         accel = dema20 / ema20 - 1,
         # 组合条件：外推后的均线在价格下方，且外推量为正
         cond = as.integer(dema_dev > 0 & accel > 0))

cat("--- 组合条件 ---\n")
print(timing_backtest(df, "cond", "forward_5", entry_q = 0.5))

# 单条件对照
df <- df |>
  mutate(cond_dev = as.integer(dema_dev > 0),
         cond_accel = as.integer(accel > 0))

cat("\n--- 仅偏离度 ---\n")
print(timing_backtest(df, "cond_dev", "forward_5", entry_q = 0.5))

cat("\n--- 仅加速量 ---\n")
print(timing_backtest(df, "cond_accel", "forward_5", entry_q = 0.5))
