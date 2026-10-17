# ============================================================
# 第016章 指数平滑异同平均线（MACD）
# 模块 03 趋势类指标
# 源文件：模块03-趋势类指标/第016章-指数平滑异同平均线（MACD）.md
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

# 3. 计算 MACD：TTR 返回 macd（DIF）与 signal（DEA）两列
macd_res <- MACD(close_price, nFast = 12, nSlow = 26, nSig = 9,
                 maType = "EMA")
dif <- macd_res[, "macd"]
dea <- macd_res[, "signal"]
macd_bar <- (dif - dea) * 2

# 4. 识别信号：DIF 与 DEA 交叉
cross_up   <- crossover(dif, dea)
cross_down <- crossover(dea, dif)
cat("金叉次数：", sum(cross_up, na.rm = TRUE), "\n")
cat("死叉次数：", sum(cross_down, na.rm = TRUE), "\n")

# 5. 绘图
chartSeries(data, theme = "white", name = "贵州茅台",
  TA = "addMACD(fast = 12, slow = 26, signal = 9)")

# 6. 输出统计：DIF 在零轴上方的天数占比
above_zero <- sum(dif > 0, na.rm = TRUE) / sum(!is.na(dif))
cat("DIF 位于零轴上方的比例：", round(above_zero, 3), "\n")

# ---- 代码块 2：拆解 ----

# 沿用第 007 章的数据准备（panel 含 date / code / close / high / low / volume）
library(dplyr)
library(TTR)

# DIF 与 DEA，五个特征一律按价格归一后再比较
panel <- panel |>
  group_by(code) |>
  arrange(date, .by_group = TRUE) |>
  mutate(dif = TTR::MACD(close)[, "macd"],
         dea = TTR::MACD(close)[, "signal"],
         # DIF 归一：单位价格的动能水平
         dif_n = dif / close,
         # DEA 归一：动能的平滑基准
         dea_n = dea / close,
         # 柱状值归一：动能相对信号线的偏离
         bar_n = (dif - dea) / close,
         # 柱状值变化：柱状值的一阶差分再除以价格
         bar_chg = ((dif - dea) - dplyr::lag(dif - dea, 1)) / close,
         # 零轴穿越状态：DIF 的符号
         zero_state = sign(dif)) |>
  ungroup()

# 展示五个特征的取值形状
panel |>
  select(date, code, dif_n, dea_n, bar_n, bar_chg, zero_state) |>
  na.omit() |>
  head()

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
panel <- panel |>
  group_by(code) |>
  mutate(dif = TTR::MACD(close)[, "macd"],
         dea = TTR::MACD(close)[, "signal"],
         bar_n = (dif - dea) / close,
         dif_n = dif / close,
         zero_state = sign(dif)) |>
  ungroup()

for (h in c("forward_1", "forward_5")) {
  cat("\n--- 柱状值因子 vs", h, "---\n")
  print(ic_summary(cross_section_ic(panel, "bar_n", h)))
}

print(layered_returns(panel, "bar_n", "forward_5"))

# DIF 因子作对照，看信息来自动能水平还是动能变化
print(ic_summary(cross_section_ic(panel, "dif_n", "forward_5")))

# 按零轴状态分组，检查符号是否一致
panel |> group_by(zero_state) |>
  group_modify(~ data.frame(IC = mean(cross_section_ic(.x, "bar_n", "forward_5")))) |>
  print()

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df <- panel |> filter(code == "600519.SS")

cat("--- 信号触发日检验（柱状值高于 80 分位）---\n")
print(timing_signal_test(df, "bar_n", "forward_5", upper = 0.8))

cat("\n--- 条件分位收益（柱状值分五档）---\n")
print(conditional_quantile_return(df, "bar_n", "forward_5", q = 5))

cat("\n--- 择时策略与买入持有对照 ---\n")
print(timing_backtest(df, "bar_n", "forward_5", entry_q = 0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
panel <- panel |>
  group_by(code) |>
  mutate(vol_ratio = volume / zoo::rollmean(volume, 20, fill = NA, align = "right")) |>
  ungroup()

panel |> group_by(date) |>
  summarise(rho = cor(bar_n, vol_ratio, "spearman", use = "complete.obs"),
            .groups = "drop") |>
  summarise(平均相关 = round(mean(rho, na.rm = TRUE), 3)) |> print()

panel <- combined_signal(panel, c("bar_n", "vol_ratio"))

cat("\n--- 组合 vs 单特征 ---\n")
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "bar_n", "forward_5")))
print(ic_summary(cross_section_ic(panel, "vol_ratio", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(sma20 = TTR::SMA(close, 20),
         cond = as.integer(bar_n > 0 & close > sma20))

print(timing_backtest(df, "cond", "forward_5", entry_q = 0.5))
