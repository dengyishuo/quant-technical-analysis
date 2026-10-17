# ============================================================
# 第017章 动向指标（DMI）
# 模块 03 趋势类指标
# 源文件：模块03-趋势类指标/第017章-动向指标（DMI）.md
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
# 3. 计算 DMI：TTR 的 ADX() 返回 DIp、DIn、DX、ADX 四列
hlc <- HLC(data)
dmi <- ADX(hlc, n = 14, maType = "EMA")
di_plus  <- dmi[, "DIp"]
di_minus <- dmi[, "DIn"]
adx      <- dmi[, "ADX"]
adxr     <- (adx + Lag(adx, 14)) / 2   # 平均趋向评级

# 4. 识别信号：趋势市中的方向指数金叉
trend_ok <- adx >= 25
cross_up   <- crossover(di_plus, di_minus) & trend_ok
cross_down <- crossover(di_minus, di_plus) & trend_ok
cat("趋势市中的金叉次数：", sum(cross_up, na.rm = TRUE), "\n")
cat("趋势市中的死叉次数：", sum(cross_down, na.rm = TRUE), "\n")

# 5. 绘图
chartSeries(data, theme = "white", name = "贵州茅台",
  TA = "addADX(n = 14, maType = 'EMA')")

# 6. 输出统计：处于趋势市的天数占比
trend_ratio <- sum(adx >= 25, na.rm = TRUE) / sum(!is.na(adx))
cat("ADX 不低于 25 的天数占比：", round(trend_ratio, 3), "\n")

# ---- 代码块 2：拆解 ----

# 沿用第 007 章的数据准备（panel 含 date / code / close / high / low / volume）
library(dplyr)
library(xts)
library(TTR)

# 按标的计算 DI 与 ADX，TTR::ADX 一次返回三列
dmi_cols <- function(d) {
  m <- TTR::ADX(xts::xts(cbind(d$high, d$low, d$close), order.by = d$date), n = 14)
  data.frame(di_p = as.numeric(m[, "DIp"]), di_m = as.numeric(m[, "DIn"]),
             adx = as.numeric(m[, "ADX"]))
}

panel <- panel |>
  group_by(code) |>
  arrange(date, .by_group = TRUE) |>
  group_modify(~ cbind(.x, dmi_cols(.x))) |>
  ungroup() |>
  group_by(code) |>
  # 方向强度先归一再取变化，交叉与门限是两个离散状态
  mutate(# 方向强度：正负 DI 之差除以两者之和，归一到 -1 至 1
         dir_str = (di_p - di_m) / (di_p + di_m),
         # 方向强度变化：五个交易日内的净强度变化
         dir_chg = dir_str - dplyr::lag(dir_str, 5),
         # 交叉状态：正向 DI 是否占优
         cross_state = as.integer(di_p > di_m),
         # 门限标记：ADX 是否达到 25
         gate = as.integer(adx >= 25)) |>
  ungroup()

# 展示四个特征的取值形状
panel |>
  select(date, code, dir_str, dir_chg, cross_state, gate) |>
  na.omit() |>
  head()

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
dmi_cols <- function(d) {
  m <- TTR::ADX(xts::xts(cbind(d$high, d$low, d$close), order.by = d$date), n = 14)
  data.frame(di_p = as.numeric(m[, "DIp"]), di_m = as.numeric(m[, "DIn"]),
             adx = as.numeric(m[, "ADX"]))
}

panel <- panel |>
  group_by(code) |>
  group_modify(~ cbind(.x, dmi_cols(.x))) |>
  ungroup() |>
  mutate(dir_str = (di_p - di_m) / (di_p + di_m),
         cross_state = as.integer(di_p > di_m),
         gate = as.integer(adx >= 25))

for (h in c("forward_1", "forward_5")) {
  print(ic_summary(cross_section_ic(panel, "dir_str", h)))
}

print(layered_returns(panel, "dir_str", "forward_5"))
print(ic_summary(cross_section_ic(panel, "cross_state", "forward_5")))

# 按门限分段，检查弱市是否稀释了因子
panel |> group_by(gate) |>
  group_modify(~ ic_summary(cross_section_ic(.x, "dir_str", "forward_5"))) |>
  print()

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df <- panel |> filter(code == "600519.SS")

cat("--- 信号触发日检验（方向强度高于 80 分位）---\n")
print(timing_signal_test(df, "dir_str", "forward_5", upper = 0.8))

cat("\n--- 条件分位收益（方向强度分五档）---\n")
print(conditional_quantile_return(df, "dir_str", "forward_5", q = 5))

cat("\n--- 择时策略与买入持有对照 ---\n")
print(timing_backtest(df, "dir_str", "forward_5", entry_q = 0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
panel <- panel |>
  group_by(code) |>
  mutate(vol_ratio = volume / zoo::rollmean(volume, 20, fill = NA, align = "right")) |>
  ungroup()

panel <- combined_signal(panel, c("dir_str", "vol_ratio"))

print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "dir_str", "forward_5")))
print(ic_summary(cross_section_ic(panel, "vol_ratio", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(cond = as.integer(dir_str > 0 & gate == 1))

print(timing_backtest(df, "cond", "forward_5", entry_q = 0.5))
