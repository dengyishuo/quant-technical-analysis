# ============================================================
# 第026章 变化率动量指标（CMO）
# 模块 04 震荡类指标
# 源文件：模块04-震荡类指标/第026章-变化率动量指标（CMO）.md
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

# 3. 计算指标（TTR 的 CMO 默认 n = 14）
cmo_14 <- CMO(close_price, n = 14)
cmo_20 <- CMO(close_price, n = 20)

# 4. 识别信号
strong_long  <- cmo_14 > 50
strong_short <- cmo_14 < -50
cross_up_neg20   <- crossover(cmo_14, -20)
cross_down_pos20 <- crossover(20, cmo_14)
cat("读数越过正 50 的交易日：", sum(strong_long, na.rm = TRUE), "\n")
cat("读数跌破负 50 的交易日：", sum(strong_short, na.rm = TRUE), "\n")
cat("上穿负 20 的次数：", sum(cross_up_neg20, na.rm = TRUE), "\n")
cat("下穿正 20 的次数：", sum(cross_down_pos20, na.rm = TRUE), "\n")

# 5. 绘图
chartSeries(data, theme = "white", name = "贵州茅台",
  TA = "addCMO(n = 14)")

# 6. 输出统计
cat("CMO 均值：", round(mean(cmo_14, na.rm = TRUE), 3), "\n")
cat("CMO 标准差：", round(sd(cmo_14, na.rm = TRUE), 3), "\n")
cat("读数落在正负 20 以内的占比：",
    round(sum(abs(cmo_14) < 20, na.rm = TRUE) / sum(!is.na(cmo_14)), 3), "\n")

# ---- 代码块 2：拆解 ----

# 沿用第 007 章的数据准备（panel 含 date / code / close / high / low / volume）
library(dplyr)
library(TTR)
library(zoo)

panel <- panel |>
  group_by(code) |>
  arrange(date, .by_group = TRUE) |>
  mutate(
    # 读数：十四日窗口内净动量的相对强度
    cmo14 = as.numeric(TTR::CMO(close, n = 14)),
    # 零轴偏离：减六十日均值后除以六十日标准差，单位为标准差倍数
    cmo_z = (cmo14 - zoo::rollmean(cmo14, 60, fill = NA, align = "right")) /
      zoo::rollapply(cmo14, 60, sd, fill = NA, align = "right"),
    # 与自身三日均线的差：平滑后的一阶差分
    cmo_bar = cmo14 - TTR::SMA(cmo14, n = 3),
    # 五期读数变化：未平滑的差分
    cmo_chg5 = cmo14 - dplyr::lag(cmo14, 5)
  ) |>
  ungroup() |>
  arrange(code, date)

panel |>
  select(code, date, cmo14, cmo_z, cmo_bar, cmo_chg5) |>
  head(8)

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
panel <- panel |>
  group_by(code) |>
  mutate(cmo14 = as.numeric(TTR::CMO(close, n = 14)),
         cmo_bar = cmo14 - TTR::SMA(cmo14, n = 3),
         cmo_z = (cmo14 - zoo::rollmean(cmo14, 60, fill = NA, align = "right")) /
           zoo::rollapply(cmo14, 60, sd, fill = NA, align = "right")) |>
  ungroup()

# 状态型与边际型：一日与五日两个前向窗口
for (h in c("forward_1", "forward_5")) {
  print(ic_summary(cross_section_ic(panel, "cmo14", h)))
}
print(layered_returns(panel, "cmo14", "forward_5"))
print(ic_summary(cross_section_ic(panel, "cmo_bar", "forward_5")))
print(ic_summary(cross_section_ic(panel, "cmo_z", "forward_5")))

# 与 RSI 的对照：同源构造，平滑方式不同
panel <- panel |>
  group_by(code) |>
  mutate(rsi14 = as.numeric(TTR::RSI(close, n = 14))) |>
  ungroup()

panel |>
  group_by(date) |>
  summarise(rho = cor(cmo14, rsi14, method = "spearman",
                      use = "complete.obs"), .groups = "drop") |>
  summarise(平均相关 = round(mean(rho, na.rm = TRUE), 3)) |>
  print()

print(ic_summary(cross_section_ic(panel, "rsi14", "forward_5")))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(cmo_neg = -cmo14)   # 取负后上分位即对应强空头端

# 顺势写法：强多头端
print(timing_signal_test(df, "cmo14", "forward_5", upper = 0.8))
# 反向写法：把读数取负，再看强空头端的后续收益
print(timing_signal_test(df, "cmo_neg", "forward_5", upper = 0.8))

# 五档条件收益：重点看首末档与中间档的差，而不是单调性
print(conditional_quantile_return(df, "cmo14", "forward_5", q = 5))

print(timing_backtest(df, "cmo14", "forward_5", entry_q = 0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal / cross_section_ic / ic_summary / timing_backtest
# 先看 CMO 与 ROC 的横截面相关，再决定是否值得组合
panel <- panel |>
  group_by(code) |>
  mutate(roc12 = as.numeric(TTR::ROC(close, n = 12, type = "discrete")) * 100) |>
  ungroup()

panel |>
  group_by(date) |>
  summarise(rho = cor(cmo14, roc12, method = "spearman",
                      use = "complete.obs"), .groups = "drop") |>
  summarise(平均相关 = round(mean(rho, na.rm = TRUE), 3)) |>
  print()

# 组合的截面验证：加权型与乘积型各算一次
panel <- combined_signal(panel, c("cmo14", "roc12"))
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))

panel <- panel |>
  group_by(date) |>
  mutate(cmo_weight = roc12 * (cmo14 + 100) / 200) |>
  ungroup()
print(ic_summary(cross_section_ic(panel, "cmo_weight", "forward_5")))

# 组合的择时验证：读数转正且站上二十日均线才持仓
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(cond = as.integer(cmo14 > 0 & close > TTR::SMA(close, 20)))
print(timing_backtest(df, "cond", "forward_5", entry_q = 0))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
# 事件型写法：CMO 上穿自身三日均线且价格站上二十日均线才持仓
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(sma20 = TTR::SMA(close, 20),
         # cmo_bar 是读数与自身三日均线之差，由负转正即金叉
         cross_up = dplyr::coalesce(cmo_bar > 0 & dplyr::lag(cmo_bar) <= 0, FALSE),
         cond = as.integer(close > sma20 & cross_up))

print(timing_backtest(df, "cond", "forward_5", entry_q = 0.5))
