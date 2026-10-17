# ============================================================
# 第011章 加权移动平均线（WMA）
# 模块 03 趋势类指标
# 源文件：模块03-趋势类指标/第011章-加权移动平均线（WMA）.md
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

# 3. 计算 WMA（TTR 的 WMA 使用线性递减权重）
wma_10 <- WMA(close_price, n = 10)
wma_30 <- WMA(close_price, n = 30)

# 4. 识别信号：10 日 WMA 上穿 30 日为金叉
cross_up   <- crossover(wma_10, wma_30)
cross_down <- crossover(wma_30, wma_10)
cat("金叉次数：", sum(cross_up, na.rm = TRUE), "\n")
cat("死叉次数：", sum(cross_down, na.rm = TRUE), "\n")

# 5. 绘图
chartSeries(data, theme = "white", name = "贵州茅台",
  TA = "addWMA(n = 10, col = 'blue'); addWMA(n = 30, col = 'red')")

# 6. 输出统计：WMA 与同周期 SMA 的平均绝对偏离
sma_10 <- SMA(close_price, n = 10)
gap <- abs(wma_10 - sma_10) / sma_10
cat("WMA10 与 SMA10 的平均相对偏离：",
    round(mean(gap, na.rm = TRUE), 4), "\n")

# ---- 代码块 2：拆解 ----

# 沿用第 007 章口径，拆解主要特征
panel <- panel |>
  group_by(code) |>
  mutate(sma20 = zoo::rollmean(close, 20, fill = NA, align = "right"),
         wma20 = TTR::WMA(close, 20),
         wma_dev = close / wma20 - 1,
         wma_slope = wma20 / dplyr::lag(wma20, 5) - 1,
         wma_gap = wma20 / sma20 - 1) |>
  ungroup()

panel |> select(wma_dev, wma_slope, wma_gap) |>
  cor(use = "complete.obs", method = "spearman") |> print()

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
panel <- panel |>
  group_by(code) |>
  mutate(sma_dev = close / zoo::rollmean(close, 20, fill = NA, align = "right") - 1,
         wma_dev = close / TTR::WMA(close, 20) - 1,
         ema_dev = close / TTR::EMA(close, 20) - 1,
         wma_gap = TTR::WMA(close, 20) /
           zoo::rollmean(close, 20, fill = NA, align = "right") - 1) |>
  ungroup()

# 三种权重体系的同周期对照
for (f in c("sma_dev", "wma_dev", "ema_dev")) {
  cat("\n---", f, "---\n")
  print(ic_summary(cross_section_ic(panel, f, "forward_5")))
}

print(ic_summary(cross_section_ic(panel, "wma_gap", "forward_5")))
print(layered_returns(panel, "wma_dev", "forward_5"))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df <- panel |> filter(code == "600519.SS")

# 用斜率代替拐头标记，保留方向的连续信息
df <- df |> mutate(wma_slope = TTR::WMA(close, 10) /
                     dplyr::lag(TTR::WMA(close, 10), 5) - 1)

print(timing_signal_test(df, "wma_slope", "forward_5", upper = 0.8))
print(conditional_quantile_return(df, "wma_slope", "forward_5", q = 5))
print(timing_backtest(df, "wma_slope", "forward_5", entry_q = 0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
panel <- panel |>
  group_by(date) |>
  mutate(vol_ratio = volume / zoo::rollmean(volume, 20, fill = NA, align = "right")) |>
  ungroup()

panel |>
  group_by(date) |>
  summarise(rho = cor(wma_dev, vol_ratio, method = "spearman",
                      use = "complete.obs"), .groups = "drop") |>
  summarise(平均相关 = round(mean(rho, na.rm = TRUE), 3)) |>
  print()

panel <- combined_signal(panel, c("wma_dev", "vol_ratio"))

print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "wma_dev", "forward_5")))
print(ic_summary(cross_section_ic(panel, "vol_ratio", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(wma20 = as.numeric(TTR::WMA(close, 20)),
         sma20 = zoo::rollmean(close, 20, fill = NA, align = "right"),
         wma_dev = close / wma20 - 1,
         wma_gap = wma20 / sma20 - 1,
         # 组合条件：线性加权与等权两个体系同时给出正偏离
         cond = as.integer(wma_dev > 0 & wma_gap > 0))

cat("--- 组合条件 ---\n")
print(timing_backtest(df, "cond", "forward_5", entry_q = 0.5))

# 单条件对照
df <- df |>
  mutate(cond_dev = as.integer(wma_dev > 0),
         cond_gap = as.integer(wma_gap > 0))

cat("\n--- 仅偏离度 ---\n")
print(timing_backtest(df, "cond_dev", "forward_5", entry_q = 0.5))

cat("\n--- 仅权重贡献差 ---\n")
print(timing_backtest(df, "cond_gap", "forward_5", entry_q = 0.5))
