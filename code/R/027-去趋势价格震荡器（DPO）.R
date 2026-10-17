# ============================================================
# 第027章 去趋势价格震荡器（DPO）
# 模块 04 震荡类指标
# 源文件：模块04-震荡类指标/第027章-去趋势价格震荡器（DPO）.md
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
close_price <- Cl(data)

# 3. 计算指标（手写实现，TTR 无 DPO 函数）
dpo_calc <- function(close_price, n = 20) {
  k <- floor(n / 2) + 1
  sma_k <- TTR::SMA(close_price, n = k)
  raw_diff <- as.numeric(close_price - sma_k)
  # 位移对齐：整体左移 k-1 期，最近 k-1 个交易日留空
  shifted <- c(raw_diff[-(1:(k - 1))], rep(NA, k - 1))
  xts::xts(shifted, order.by = index(close_price))
}

dpo_20 <- dpo_calc(close_price, n = 20)
dpo_10 <- dpo_calc(close_price, n = 10)

# 4. 识别信号：零轴穿越
up   <- crossover(dpo_20, 0)
down <- crossover(0, dpo_20)
cat("上穿零轴次数：", sum(up, na.rm = TRUE), "\n")
cat("下穿零轴次数：", sum(down, na.rm = TRUE), "\n")
cat("端部空白交易日：", sum(is.na(tail(dpo_20, 20))), "\n")

# 5. 绘图
chartSeries(data, theme = "white", name = "贵州茅台",
  TA = "addTA(dpo_20, col = 'blue'); addTA(dpo_10, col = 'red')")

# 6. 输出统计
cat("DPO 均值：", round(mean(dpo_20, na.rm = TRUE), 3), "\n")
cat("DPO 标准差：", round(sd(dpo_20, na.rm = TRUE), 3), "\n")
cat("正负值天数比：", round(sum(dpo_20 > 0, na.rm = TRUE) /
    sum(dpo_20 < 0, na.rm = TRUE), 3), "\n")

# ---- 代码块 2：拆解 ----

# 沿用第 007 章的数据准备（panel 含 date / code / close / high / low / volume）
library(dplyr)
library(TTR)
library(zoo)

# n = 20 时 k = floor(20 / 2) + 1 = 11，位移长度 k - 1 = 10 期
panel <- panel |>
  group_by(code) |>
  arrange(date, .by_group = TRUE) |>
  mutate(
    sma11 = TTR::SMA(close, n = 11),
    # 未位移的原始差值：t 时刻只用到 t 及之前的收盘价，因子取自这一列
    dpo_raw = close - sma11,
    # 相对化差值：除以同一期的均线，消除价格量纲
    dpo_rel = dpo_raw / sma11,
    # 分位值：近 120 日窗口内的经验百分位，含当日，映射到 0 到 100
    dpo_pct = zoo::rollapply(dpo_rel, 120,
                             function(x) mean(x <= x[length(x)], na.rm = TRUE),
                             fill = NA, align = "right") * 100,
    # 相位状态：周期处在基线之上为 1，之下为 0
    dpo_sign = as.integer(dpo_raw > 0),
    # 位移版：t 时刻取 dpo_raw 在 t + 10 时刻的值，含未来十期信息
    # 仅作诊断，因子不得使用位移版本
    dpo_shift = dplyr::lead(dpo_raw, 10)
  ) |>
  ungroup() |>
  arrange(code, date)

panel |>
  select(code, date, dpo_raw, dpo_rel, dpo_pct, dpo_sign, dpo_shift) |>
  head(8)

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# k = floor(20 / 2) + 1 = 11；因子取未位移的原始差值
panel <- panel |>
  group_by(code) |>
  mutate(sma11 = TTR::SMA(close, n = 11),
         dpo_raw = close - sma11,
         dpo_rel = dpo_raw / sma11,
         dpo_pct = zoo::rollapply(dpo_rel, 120,
                   function(x) mean(x <= x[length(x)], na.rm = TRUE),
                   fill = NA, align = "right"),
         dpo_shift = dplyr::lead(dpo_raw, 10)) |>  # 位移版，仅作诊断
  ungroup()

for (h in c("forward_1", "forward_5")) {
  print(ic_summary(cross_section_ic(panel, "dpo_rel", h)))
}
print(layered_returns(panel, "dpo_rel", "forward_5"))
print(ic_summary(cross_section_ic(panel, "dpo_pct", "forward_5")))

# 诊断：位移版含未来十期信息，IC 会明显偏高，不可用于实盘
print(ic_summary(cross_section_ic(panel, "dpo_shift", "forward_5")))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df <- panel |> filter(code == "600519.SS") |> mutate(dpo_neg = -dpo_pct)

print(timing_signal_test(df, "dpo_pct", "forward_5", upper = 0.8))
print(timing_signal_test(df, "dpo_neg", "forward_5", upper = 0.8))
print(conditional_quantile_return(df, "dpo_pct", "forward_5", q = 5))

# 状态即仓位：未位移差值在零轴上方时持仓
df <- df |> mutate(dpo_pos = as.integer(dpo_raw > 0))
print(timing_backtest(df, "dpo_pos", "forward_5", entry_q = 0))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal / cross_section_ic / ic_summary / timing_backtest
panel <- panel |>
  group_by(code) |>
  mutate(roc12 = as.numeric(TTR::ROC(close, 12, type = "discrete")) * 100) |>
  ungroup()

# 剥离趋势的 DPO 与保留趋势的 ROC，相关性通常不高
panel |>
  group_by(date) |>
  summarise(rho = cor(dpo_rel, roc12, method = "spearman",
                      use = "complete.obs"), .groups = "drop") |>
  summarise(平均相关 = round(mean(rho, na.rm = TRUE), 3)) |>
  print()

panel <- combined_signal(panel, c("dpo_rel", "roc12"))
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "dpo_rel", "forward_5")))
print(ic_summary(cross_section_ic(panel, "roc12", "forward_5")))

# 组合的择时验证：周期在零轴上方且站上二十日均线才持仓
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(cond = as.integer(dpo_raw > 0 & close > TTR::SMA(close, 20)))
print(timing_backtest(df, "cond", "forward_5", entry_q = 0))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
# 事件型写法：未位移的差值由负转正且价格站上二十日均线才持仓
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(sma20 = TTR::SMA(close, 20),
         # 相位转换：当日为正、前一日非正，取值一律来自 dpo_raw
         turn_up = dplyr::coalesce(dpo_raw > 0 & dplyr::lag(dpo_raw) <= 0, FALSE),
         cond = as.integer(close > sma20 & turn_up))

print(timing_backtest(df, "cond", "forward_5", entry_q = 0.5))
