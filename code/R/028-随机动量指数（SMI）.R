# ============================================================
# 第028章 随机动量指数（SMI）
# 模块 04 震荡类指标
# 源文件：模块04-震荡类指标/第028章-随机动量指数（SMI）.md
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
library(xts)

# 2. 获取数据
panel <- read.csv("data/parquet/panel_blue_chip.csv", stringsAsFactors = FALSE)
.sub <- panel[panel$code == "600519.SS", ]
data <- xts::xts(.sub[, c("open", "high", "low", "close", "volume", "adjusted")],
                 order.by = as.Date(.sub$date))
colnames(data) <- c("Open", "High", "Low", "Close", "Volume", "Adjusted")
# 3. 计算指标（手写实现，TTR 无 SMI 函数）
smi_calc <- function(data, n = 14, m = 3) {
  hh <- runMax(Hi(data), n)
  ll <- runMin(Lo(data), n)
  mid <- (hh + ll) / 2
  max_dev <- pmax(hh - mid, mid - ll)
  smi <- (Cl(data) - mid) / max_dev * 100
  signal <- SMA(smi, n = m)
  merge(smi = smi, signal = signal)
}

smi_14 <- smi_calc(data, n = 14, m = 3)
smi_line    <- smi_14[, "smi"]
signal_line <- smi_14[, "signal"]

# 4. 识别信号
golden <- crossover(smi_line, signal_line)
dead   <- crossover(signal_line, smi_line)
low_golden <- golden & (smi_line < 40)
cat("金叉次数：", sum(golden, na.rm = TRUE), "\n")
cat("其中中低位金叉：", sum(low_golden, na.rm = TRUE), "\n")
cat("读数越过 80 的交易日：", sum(smi_line > 80, na.rm = TRUE), "\n")
cat("读数跌破负 80 的交易日：", sum(smi_line < -80, na.rm = TRUE), "\n")

# 5. 绘图
chartSeries(data, theme = "white", name = "贵州茅台",
  TA = "addTA(smi_line, col = 'blue'); addTA(signal_line, col = 'red')")

# 6. 输出统计
cat("SMI 均值：", round(mean(smi_line, na.rm = TRUE), 3), "\n")
cat("SMI 标准差：", round(sd(smi_line, na.rm = TRUE), 3), "\n")
cat("读数落在正负 40 以内的占比：",
    round(sum(abs(smi_line) < 40, na.rm = TRUE) / sum(!is.na(smi_line)), 3), "\n")

# ---- 代码块 2：拆解 ----

# 沿用第 007 章的数据准备（panel 含 date / code / close / high / low / volume）
library(dplyr)
library(TTR)
library(zoo)

panel <- panel |>
  group_by(code) |>
  arrange(date, .by_group = TRUE) |>
  mutate(
    hh14 = TTR::runMax(high, 14),
    ll14 = TTR::runMin(low, 14),
    mid14 = (hh14 + ll14) / 2,
    maxdev14 = (hh14 - ll14) / 2,
    # 读数：偏离中点除以半个区间高度，区间高度为零时置空
    smi14 = ifelse(maxdev14 > 0, (close - mid14) / maxdev14 * 100, NA),
    # 零轴偏离：相对自身六十日均值的位置，单位为点
    smi_center = smi14 - zoo::rollmean(smi14, 60, fill = NA, align = "right"),
    # 与信号线的差：即柱状值，读数减去三日均线
    smi_diff = smi14 - TTR::SMA(smi14, n = 3),
    # 极值状态：读数在正负 80 之外取符号，其余为零
    smi_ext = sign(smi14) * as.integer(abs(smi14) > 80)
  ) |>
  ungroup() |>
  arrange(code, date)

panel |>
  select(code, date, smi14, smi_center, smi_diff, smi_ext) |>
  head(8)

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
panel <- panel |>
  group_by(code) |>
  mutate(hh14 = TTR::runMax(high, 14), ll14 = TTR::runMin(low, 14),
         mid14 = (hh14 + ll14) / 2, maxdev14 = (hh14 - ll14) / 2,
         smi14 = ifelse(maxdev14 > 0, (close - mid14) / maxdev14 * 100, NA),
         smi_diff = smi14 - TTR::SMA(smi14, n = 3),
         rsv_c = ifelse(hh14 > ll14,
                        (close - ll14) / (hh14 - ll14) * 100 - 50, NA_real_)) |>
  ungroup()

for (h in c("forward_1", "forward_5")) {
  print(ic_summary(cross_section_ic(panel, "smi14", h)))
}
print(layered_returns(panel, "smi14", "forward_5"))
print(ic_summary(cross_section_ic(panel, "smi_diff", "forward_5")))

# 与 KDJ 的区间位置对照：同源，SMI 多一层中点偏离
print(ic_summary(cross_section_ic(panel, "rsv_c", "forward_5")))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df <- panel |> filter(code == "600519.SS") |> mutate(smi_neg = -smi14)

print(timing_signal_test(df, "smi14", "forward_5", upper = 0.8))
print(timing_signal_test(df, "smi_neg", "forward_5", upper = 0.8))
print(conditional_quantile_return(df, "smi14", "forward_5", q = 5))

# 反向写法：读数越低越持仓；顺势写法取原读数，两条对照
print(timing_backtest(df, "smi_neg", "forward_5", entry_q = 0.7))
print(timing_backtest(df, "smi14", "forward_5", entry_q = 0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / timing_backtest
# 正交化：SMI 对区间位置取横截面残差
panel <- panel |>
  group_by(date) |>
  mutate(beta = cov(smi14, rsv_c, use = "complete.obs") /
           var(rsv_c, use = "complete.obs"),
         smi_resid = smi14 - mean(smi14, na.rm = TRUE) -
           beta * (rsv_c - mean(rsv_c, na.rm = TRUE))) |>
  ungroup()

print(ic_summary(cross_section_ic(panel, "smi14", "forward_5")))
print(ic_summary(cross_section_ic(panel, "rsv_c", "forward_5")))
print(ic_summary(cross_section_ic(panel, "smi_resid", "forward_5")))

# 组合的择时验证：超卖且价格站上二十日均线
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(cond = as.integer(smi14 < -20 & close > TTR::SMA(close, 20)))
print(timing_backtest(df, "cond", "forward_5", entry_q = 0))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
# 事件型写法：SMI 上穿信号线且价格站上二十日均线才持仓
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(sma20 = TTR::SMA(close, 20),
         # smi_diff 是读数与信号线之差，由负转正即金叉
         cross_up = dplyr::coalesce(smi_diff > 0 & dplyr::lag(smi_diff) <= 0, FALSE),
         cond = as.integer(close > sma20 & cross_up))

print(timing_backtest(df, "cond", "forward_5", entry_q = 0.5))
