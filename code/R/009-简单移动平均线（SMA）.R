# ============================================================
# 第009章 简单移动平均线（SMA）
# 模块 03 趋势类指标
# 源文件：模块03-趋势类指标/第009章-简单移动平均线（SMA）.md
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

# 3. 计算 SMA
sma_20 <- SMA(close_price, n = 20)
sma_60 <- SMA(close_price, n = 60)

# 4. 识别信号：20 日上穿 60 日为金叉
cross_up   <- crossover(sma_20, sma_60)
cross_down <- crossover(sma_60, sma_20)
cat("金叉次数：", sum(cross_up, na.rm = TRUE), "\n")
cat("死叉次数：", sum(cross_down, na.rm = TRUE), "\n")

# 5. 绘图
chartSeries(data, theme = "white", name = "贵州茅台",
  TA = "addSMA(n = 20, col = 'blue'); addSMA(n = 60, col = 'red')")

# 6. 输出统计：价格在 200 日均线上方的天数占比
sma_200 <- SMA(close_price, n = 200)
above <- sum(close_price > sma_200, na.rm = TRUE) / sum(!is.na(sma_200))
cat("价格位于 200 日均线上方的比例：", round(above, 3), "\n")

# ---- 代码块 2：拆解 ----

# 沿用第 007 章口径，拆解四个特征
library(dplyr)

panel <- panel |>
  group_by(code) |>
  arrange(date, .by_group = TRUE) |>
  mutate(sma20 = zoo::rollmean(close, 20, fill = NA, align = "right"),
         # 价格偏离度：价格相对二十日均线的位置
         sma_dev = close / sma20 - 1,
         # 均线斜率：均线五期的推进速度
         sma_slope = sma20 / dplyr::lag(sma20, 5) - 1,
         # 斜率加速度：斜率相对五期前的变化
         slope_acc = sma_slope - dplyr::lag(sma_slope, 5),
         # 状态久期：连续位于均线同侧的期数，上方为正、下方为负
         state_dur = {
           s <- sign(close - sma20)
           r <- rle(ifelse(is.na(s), 0, s))
           ifelse(is.na(s), NA_real_, rep(r$lengths * r$values, r$lengths))
         }) |>
  ungroup()

panel |>
  select(date, code, sma_dev, sma_slope, slope_acc, state_dur) |>
  filter(!is.na(sma_dev), !is.na(slope_acc)) |>
  head(8) |>
  print()

# ---- 代码块 3：截面选股能力 ----

# 沿用「双重检验方法论」一章定义的 cross_section_ic / ic_summary / layered_returns
panel <- panel |>
  group_by(code) |>
  mutate(sma20 = zoo::rollmean(close, 20, fill = NA, align = "right"),
         sma_dev = close / sma20 - 1,
         sma60 = zoo::rollmean(close, 60, fill = NA, align = "right"),
         sma_slope = sma20 / dplyr::lag(sma20, 5) - 1) |>
  ungroup()

# 偏离度因子：一日与五日两个前向窗口对照
for (h in c("forward_1", "forward_5")) {
  cat("\n--- 偏离度 vs", h, "---\n")
  print(ic_summary(cross_section_ic(panel, "sma_dev", h)))
}

print(layered_returns(panel, "sma_dev", "forward_5"))

# 斜率因子作对照
print(ic_summary(cross_section_ic(panel, "sma_slope", "forward_5")))

# 对标的中立性做一次检查：偏离度与股价水平的相关
panel |>
  group_by(date) |>
  summarise(rho = cor(sma_dev, close, method = "spearman"), .groups = "drop") |>
  summarise(平均相关 = round(mean(rho, na.rm = TRUE), 3)) |>
  print()

# ---- 代码块 4：择时能力 ----

# 沿用「双重检验方法论」一章的三种择时检验
df <- panel |> filter(code == "600519.SS")

cat("--- 信号触发日检验（偏离度高于 80 分位）---\n")
print(timing_signal_test(df, "sma_dev", "forward_5", upper = 0.8))

cat("\n--- 条件分位收益（偏离度分五档）---\n")
print(conditional_quantile_return(df, "sma_dev", "forward_5", q = 5))

cat("\n--- 择时策略与买入持有对照 ---\n")
print(timing_backtest(df, "sma_dev", "forward_5", entry_q = 0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用「双重检验方法论」一章的 combined_signal
# 先看两个特征的横截面相关，再决定是否值得组合
panel <- panel |>
  group_by(date) |>
  mutate(vol_ratio = volume / zoo::rollmean(volume, 20, fill = NA, align = "right")) |>
  ungroup()

panel |>
  group_by(date) |>
  summarise(rho = cor(sma_dev, vol_ratio, method = "spearman",
                      use = "complete.obs"), .groups = "drop") |>
  summarise(平均相关 = round(mean(rho, na.rm = TRUE), 3)) |>
  print()

# 加权型组合：等权
panel <- combined_signal(panel, c("sma_dev", "vol_ratio"))

cat("\n--- 组合 vs 单特征 ---\n")
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "sma_dev", "forward_5")))
print(ic_summary(cross_section_ic(panel, "vol_ratio", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(sma20 = zoo::rollmean(close, 20, fill = NA, align = "right"),
         sma_dev = close / sma20 - 1,
         vol_ratio = volume / zoo::rollmean(volume, 20, fill = NA, align = "right"),
         # 组合条件：价格在均线上方且成交量高于二十日均量
         cond = as.integer(sma_dev > 0 & vol_ratio > 1))

cat("--- 组合条件 ---\n")
print(timing_backtest(df, "cond", "forward_5", entry_q = 0.5))

# 单条件对照
df <- df |>
  mutate(cond_dev = as.integer(sma_dev > 0),
         cond_vol = as.integer(vol_ratio > 1))

cat("\n--- 仅偏离度 ---\n")
print(timing_backtest(df, "cond_dev", "forward_5", entry_q = 0.5))

cat("\n--- 仅量能 ---\n")
print(timing_backtest(df, "cond_vol", "forward_5", entry_q = 0.5))
