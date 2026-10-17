# ============================================================
# 第021章 相对强弱指数（RSI）
# 模块 04 震荡类指标
# 源文件：模块04-震荡类指标/第021章-相对强弱指数（RSI）.md
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

# 3. 计算指标（TTR 的 RSI 使用 Wilder 平滑）
rsi_14 <- RSI(close_price, n = 14)
rsi_6  <- RSI(close_price, n = 6)

# 4. 识别信号
overbought <- rsi_14 > 70
oversold   <- rsi_14 < 30
cross_up   <- crossover(rsi_6, rsi_14)
cross_down <- crossover(rsi_14, rsi_6)
cat("超买天数：", sum(overbought, na.rm = TRUE), "\n")
cat("超卖天数：", sum(oversold, na.rm = TRUE), "\n")
cat("6 日上穿 14 日次数：", sum(cross_up, na.rm = TRUE), "\n")

# 5. 绘图
chartSeries(data, theme = "white", name = "贵州茅台",
  TA = "addRSI(n = 14)")

# 6. 输出统计：极端区间的停留长度
in_extreme <- ifelse(rsi_14 > 70 | rsi_14 < 30, 1, 0)
cat("处于极端区域的交易日占比：",
    round(sum(in_extreme == 1, na.rm = TRUE) / sum(!is.na(rsi_14)), 3), "\n")

# ---- 代码块 2：拆解 ----

# 沿用第 007 章的数据准备（panel 含 date / code / close / high / low / volume）
library(dplyr)
library(TTR)

# 极端状态的连续期数：超买侧记正，超卖侧记负，回到中性区归零
signed_run <- function(state) {
  r <- rle(state)
  len <- sequence(r$lengths)
  ifelse(state == 0, 0L, sign(state) * len)
}

panel <- panel |>
  group_by(code) |>
  arrange(date, .by_group = TRUE) |>
  mutate(
    rsi14 = as.numeric(TTR::RSI(close, n = 14)),
    # 中轴偏离：读数相对 50 的位置
    rsi_dev = rsi14 - 50,
    # 变化率：五期差分，单位为点
    rsi_chg = rsi14 - dplyr::lag(rsi14, 5),
    # 极值持续期：连续高于 70 记正，连续低于 30 记负
    rsi_ext_run = signed_run(dplyr::case_when(
      is.na(rsi14) ~ 0L,
      rsi14 > 70 ~ 1L,
      rsi14 < 30 ~ -1L,
      TRUE ~ 0L
    ))
  ) |>
  ungroup()

panel |>
  select(date, code, rsi14, rsi_dev, rsi_chg, rsi_ext_run) |>
  filter(!is.na(rsi14)) |>
  head(8) |>
  print()

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# panel 含 date / code / close / forward_1 / forward_5
panel <- panel |>
  group_by(code) |>
  mutate(rsi14 = as.numeric(TTR::RSI(close, n = 14)),
         rsi_dev = rsi14 - 50,
         rsi_chg = rsi14 - dplyr::lag(rsi14, 5)) |>
  ungroup()

# 一日与五日两个前向窗口对照
for (h in c("forward_1", "forward_5")) {
  cat("\n--- 中轴偏离 vs", h, "---\n")
  print(ic_summary(cross_section_ic(panel, "rsi_dev", h)))
}
print(layered_returns(panel, "rsi_dev", "forward_5"))

# 变化率作对照
print(ic_summary(cross_section_ic(panel, "rsi_chg", "forward_5")))

# 符号稳定性：按年切分，检查 IC 是否反号
year_ic <- panel |>
  mutate(year = format(as.Date(date), "%Y")) |>
  group_split(year) |>
  lapply(function(d) {
    data.frame(年份 = d$year[1],
               IC均值 = round(mean(cross_section_ic(d, "rsi_dev", "forward_5")), 4))
  })
print(do.call(rbind, year_ic))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(rsi_low = -rsi_dev)

cat("--- 上尾：偏离值高于 80 分位 ---\n")
print(timing_signal_test(df, "rsi_dev", "forward_5", upper = 0.8))

cat("\n--- 下尾：取负后高于 80 分位，对应原值低于 20 分位 ---\n")
print(timing_signal_test(df, "rsi_low", "forward_5", upper = 0.8))

cat("\n--- 条件分位收益 ---\n")
print(conditional_quantile_return(df, "rsi_dev", "forward_5", q = 5))

cat("\n--- 择时策略与买入持有对照 ---\n")
print(timing_backtest(df, "rsi_dev", "forward_5", entry_q = 0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal / cross_section_ic / timing_backtest
# 截面路径：RSI 中轴偏离与价格对均线偏离的组合
panel <- panel |>
  group_by(code) |>
  mutate(sma20 = zoo::rollmean(close, 20, fill = NA, align = "right"),
         sma_dev = close / sma20 - 1) |>
  ungroup()

panel |>
  filter(!is.na(rsi_dev), !is.na(sma_dev)) |>
  group_by(date) |>
  summarise(rho = cor(rsi_dev, sma_dev, method = "spearman"), .groups = "drop") |>
  summarise(平均相关 = round(mean(rho, na.rm = TRUE), 3)) |>
  print()

# 方向对齐：若前一步判定 rsi_dev 为负向因子，先执行 panel$rsi_dev <- -panel$rsi_dev
panel <- combined_signal(panel, c("rsi_dev", "sma_dev"))

cat("\n--- 组合 vs 单特征 ---\n")
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "rsi_dev", "forward_5")))
print(ic_summary(cross_section_ic(panel, "sma_dev", "forward_5")))

# 择时路径：只在价格位于二十日均线上方时接受超卖信号
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(rsi_up = ifelse(close > sma20, rsi_dev, NA_real_))

cat("\n--- 上升趋势样本内的择时 ---\n")
print(timing_backtest(df, "rsi_up", "forward_5", entry_q = 0.7))

cat("\n--- 全样本对照 ---\n")
print(timing_backtest(df, "rsi_dev", "forward_5", entry_q = 0.7))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
# 趋势过滤：价格在 20 日均线上方时，超卖读数才视为持仓条件
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(sma20 = TTR::SMA(close, 20),
         cond = as.integer(close > sma20 & rsi14 < 30))

print(timing_backtest(df, "cond", "forward_5", entry_q = 0.5))
