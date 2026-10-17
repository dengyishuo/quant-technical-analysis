# ============================================================
# 第023章 商品通道指数（CCI）
# 模块 04 震荡类指标
# 源文件：模块04-震荡类指标/第023章-商品通道指数（CCI）.md
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
# 3. 计算指标（TTR 的 CCI 默认 n = 20）
cci_20 <- CCI(HLC(data), n = 20)
cci_14 <- CCI(HLC(data), n = 14)

# 4. 识别信号
overbought <- cci_20 > 100
oversold   <- cci_20 < -100
strong_up  <- cci_20 > 200
cat("越过正 100 的次数：", sum(crossover(cci_20, 100), na.rm = TRUE), "\n")
cat("跌破负 100 的次数：", sum(crossover(-100, cci_20), na.rm = TRUE), "\n")
cat("停留在正 200 以上的交易日：", sum(strong_up, na.rm = TRUE), "\n")

# 5. 绘图
chartSeries(data, theme = "white", name = "贵州茅台",
  TA = "addCCI(n = 20)")

# 6. 输出统计
cat("CCI 读数落在正负 100 以内的占比：",
    round(sum(abs(cci_20) < 100, na.rm = TRUE) / sum(!is.na(cci_20)), 3), "\n")
cat("标准差：", round(sd(cci_20, na.rm = TRUE), 2), "\n")

# ---- 代码块 2：拆解 ----

# 沿用第 007 章的数据准备（panel 含 date / code / close / high / low / volume）
library(dplyr)
library(TTR)

panel <- panel |>
  group_by(code) |>
  arrange(date, .by_group = TRUE) |>
  mutate(
    cci20 = as.numeric(
      TTR::CCI(cbind(High = high, Low = low, Close = close), n = 20)),
    # 穿越状态：上穿 100 记 1，下穿负 100 记 -1，其余记 0
    cci_cross = dplyr::case_when(
      cci20 > 100 & dplyr::lag(cci20) <= 100 ~ 1,
      cci20 < -100 & dplyr::lag(cci20) >= -100 ~ -1,
      TRUE ~ 0
    )
  ) |>
  ungroup()

# 横截面标准化后截断在正负 3，尾部被压缩
panel <- panel |>
  group_by(date) |>
  mutate(
    cci_z = (cci20 - median(cci20, na.rm = TRUE)) /
      pmax(mad(cci20, na.rm = TRUE, constant = 1), 1e-8),
    cci_z = pmax(pmin(cci_z, 3), -3),
    # 偏离强度：绝对值，不带方向
    cci_abs = abs(cci20)
  ) |>
  ungroup()

panel |>
  select(date, code, cci20, cci_z, cci_abs, cci_cross) |>
  filter(!is.na(cci20)) |>
  head(8) |>
  print()

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# panel 含 date / code / high / low / close / forward_1 / forward_5
panel <- panel |>
  group_by(code) |>
  mutate(cci20 = as.numeric(
    TTR::CCI(cbind(High = high, Low = low, Close = close), n = 20))) |>
  ungroup()

# 横截面标准化后截断在正负 3
# mad 取 constant = 1，与第 007 章的中位绝对差定义一致
panel <- panel |>
  group_by(date) |>
  mutate(cci_z = (cci20 - median(cci20, na.rm = TRUE)) /
                   pmax(mad(cci20, na.rm = TRUE, constant = 1), 1e-8),
         cci_z = pmax(pmin(cci_z, 3), -3)) |>
  ungroup()

for (h in c("forward_1", "forward_5")) {
  cat("\n--- CCI 标准化值 vs", h, "---\n")
  print(ic_summary(cross_section_ic(panel, "cci_z", h)))
}

print(layered_returns(panel, "cci_z", "forward_5"))

# 符号稳定性：按年切分
year_ic <- panel |>
  mutate(year = format(as.Date(date), "%Y")) |>
  group_split(year) |>
  lapply(function(d) {
    data.frame(年份 = d$year[1],
               IC均值 = round(mean(cross_section_ic(d, "cci_z", "forward_5")), 4))
  })
print(do.call(rbind, year_ic))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(cci_neg = -cci_z)

cat("--- 顺势方向：读数高于 80 分位 ---\n")
print(timing_signal_test(df, "cci_z", "forward_5", upper = 0.8))

cat("\n--- 反转方向：取负后高于 80 分位 ---\n")
print(timing_signal_test(df, "cci_neg", "forward_5", upper = 0.8))

cat("\n--- 条件分位收益 ---\n")
print(conditional_quantile_return(df, "cci_z", "forward_5", q = 5))

cat("\n--- 顺势规则的回测 ---\n")
print(timing_backtest(df, "cci_z", "forward_5", entry_q = 0.7))

cat("\n--- 反转规则的回测 ---\n")
print(timing_backtest(df, "cci_neg", "forward_5", entry_q = 0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal / cross_section_ic / timing_backtest
# 截面路径：先按市况给 CCI 定方向，再与均线偏离组合
panel <- panel |>
  group_by(code) |>
  mutate(sma20 = zoo::rollmean(close, 20, fill = NA, align = "right"),
         sma_dev = close / sma20 - 1,
         adx14 = as.numeric(TTR::ADX(cbind(High = high, Low = low,
                                           Close = close), n = 14)[, "ADX"]),
         # 震荡段取反转方向，趋势段取顺势方向
         cci_signed = ifelse(adx14 < 25, -cci_z, cci_z)) |>
  ungroup()

panel |>
  filter(!is.na(cci_signed), !is.na(sma_dev)) |>
  group_by(date) |>
  summarise(rho = cor(cci_signed, sma_dev, method = "spearman"), .groups = "drop") |>
  summarise(平均相关 = round(mean(rho, na.rm = TRUE), 3)) |>
  print()

panel <- combined_signal(panel, c("cci_signed", "sma_dev"))

cat("\n--- 组合 vs 单特征 ---\n")
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "cci_signed", "forward_5")))
print(ic_summary(cross_section_ic(panel, "sma_dev", "forward_5")))

# 择时路径：同一套符号规则，直接转成仓位
df <- panel |> filter(code == "600519.SS")

cat("\n--- 分段定方向的择时 ---\n")
print(timing_backtest(df, "cci_signed", "forward_5", entry_q = 0.7))

cat("\n--- 不分段、只做顺势的对照 ---\n")
print(timing_backtest(df, "cci_z", "forward_5", entry_q = 0.7))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
# 趋势过滤：价格在 20 日均线上方，且 CCI 由负转正时持仓
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(sma20 = TTR::SMA(close, 20),
         cond = as.integer(close > sma20 & cci20 > 0 & dplyr::lag(cci20) <= 0))

print(timing_backtest(df, "cond", "forward_5", entry_q = 0.5))
