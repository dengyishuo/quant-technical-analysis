# ============================================================
# 第018章 平均趋向指数（ADX）
# 模块 03 趋势类指标
# 源文件：模块03-趋势类指标/第018章-平均趋向指数（ADX）.md
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
# 3. 计算 ADX：ADX() 返回 DIp、DIn、DX、ADX 四列
hlc <- HLC(data)
adx_res  <- ADX(hlc, n = 14, maType = "EMA")
di_plus  <- adx_res[, "DIp"]
di_minus <- adx_res[, "DIn"]
adx      <- adx_res[, "ADX"]

# 4. 识别信号：趋势强度分档与方向指数交叉
strong_trend <- adx >= 40
cross_up   <- crossover(di_plus, di_minus) & (adx >= 25)
cross_down <- crossover(di_minus, di_plus) & (adx >= 25)
cat("强趋势天数：", sum(strong_trend, na.rm = TRUE), "\n")
cat("趋势市中的金叉次数：", sum(cross_up, na.rm = TRUE), "\n")

# 5. 绘图
chartSeries(data, theme = "white", name = "贵州茅台",
  TA = "addADX(n = 14, maType = 'EMA')")

# 6. 输出统计：ADX 的中位数与强趋势占比
cat("ADX 中位数：", round(median(adx, na.rm = TRUE), 1), "\n")
cat("ADX 不低于 40 的天数占比：",
    round(sum(adx >= 40, na.rm = TRUE) / sum(!is.na(adx)), 3), "\n")

# ---- 代码块 2：拆解 ----

# 沿用第 007 章的数据准备（panel 含 date / code / close / high / low / volume）
library(dplyr)
library(xts)
library(zoo)
library(TTR)

# 按标的计算 ADX，方向移动与真实波幅均取 Wilder 平滑
adx_cols <- function(d) {
  m <- TTR::ADX(xts::xts(cbind(d$high, d$low, d$close), order.by = d$date), n = 14)
  data.frame(adx = as.numeric(m[, "ADX"]))
}

panel <- panel |>
  group_by(code) |>
  arrange(date, .by_group = TRUE) |>
  group_modify(~ cbind(.x, adx_cols(.x))) |>
  ungroup() |>
  group_by(code) |>
  # 斜率、分位、门限三层：变化方向、历史位置、二元状态
  mutate(# ADX 斜率：五日跨度上的读数变化
         adx_chg = adx - dplyr::lag(adx, 5),
         # ADX 分位：250 日窗口内不大于当日读数的比例，等价于秩次除以窗口长度
         adx_pctile = zoo::rollapply(adx, 250, function(x) mean(x <= x[length(x)]),
                                     fill = NA, align = "right"),
         # 门限状态：ADX 是否达到 25
         gate = as.integer(adx >= 25)) |>
  ungroup()

# 展示四个特征的取值形状，分位列需要 250 日窗口
panel |>
  select(date, code, adx, adx_chg, adx_pctile, gate) |>
  na.omit() |>
  head()

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
adx_cols <- function(d) {
  m <- TTR::ADX(xts::xts(cbind(d$high, d$low, d$close), order.by = d$date), n = 14)
  data.frame(adx = as.numeric(m[, "ADX"]))
}

panel <- panel |>
  group_by(code) |>
  group_modify(~ cbind(.x, adx_cols(.x))) |>
  ungroup() |>
  group_by(code) |>
  mutate(mom20 = close / dplyr::lag(close, 20) - 1,
         adx_chg = adx - dplyr::lag(adx, 5)) |>
  ungroup()

# 自身排序：预期接近零，作为对照
print(ic_summary(cross_section_ic(panel, "adx", "forward_5")))

panel <- panel |> group_by(date) |> mutate(adx_grp = dplyr::ntile(adx, 3)) |> ungroup()

for (k in 1:3) {
  cat("\n--- ADX 第", k, "组，动量因子 ---\n")
  print(ic_summary(cross_section_ic(panel |> filter(adx_grp == k), "mom20", "forward_5")))
}

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df <- panel |> filter(code == "600519.SS")

cat("--- 信号触发日检验（ADX 高于 80 分位）---\n")
print(timing_signal_test(df, "adx", "forward_5", upper = 0.8))

cat("\n--- 条件分位收益（ADX 分五档）---\n")
print(conditional_quantile_return(df, "adx", "forward_5", q = 5))

# 门限开关：ADX 达标且价格在二十日均线上方才持仓
df <- df |> mutate(cond = as.integer(adx >= 25 & close > TTR::SMA(close, 20)))
cat("\n--- 开关策略与买入持有对照 ---\n")
print(timing_backtest(df, "cond", "forward_5", entry_q = 0.5))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
# 门限变量用条件分组，不做加权；先做组内组合，再看组间差异
panel <- panel |>
  group_by(code) |>
  mutate(vol_ratio = volume / zoo::rollmean(volume, 20, fill = NA, align = "right")) |>
  ungroup()

panel <- combined_signal(panel, c("mom20", "vol_ratio"))

for (k in 1:3) {
  cat("\n--- ADX 第", k, "组，动量与量比组合 ---\n")
  print(ic_summary(cross_section_ic(panel |> filter(adx_grp == k), "combined", "forward_5")))
}

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(cond = as.integer(adx >= 25 & close > TTR::SMA(close, 20)))

print(timing_backtest(df, "cond", "forward_5", entry_q = 0.5))
