# ============================================================
# 第025章 变化率指标（ROC）
# 模块 04 震荡类指标
# 源文件：模块04-震荡类指标/第025章-变化率指标（ROC）.md
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

# 3. 计算指标（type = "discrete" 返回百分比变化）
roc_12 <- ROC(close_price, n = 12, type = "discrete")

# 4. 识别信号
cross_zero_up   <- crossover(roc_12, 0)
cross_zero_down <- crossover(0, roc_12)
overbought <- roc_12 > 20
oversold   <- roc_12 < -20
cat("上穿零轴次数：", sum(cross_zero_up, na.rm = TRUE), "\n")
cat("下穿零轴次数：", sum(cross_zero_down, na.rm = TRUE), "\n")
cat("读数越过正 20 的交易日：", sum(overbought, na.rm = TRUE), "\n")
cat("读数跌破负 20 的交易日：", sum(oversold, na.rm = TRUE), "\n")

# 5. 绘图
chartSeries(data, theme = "white", name = "贵州茅台")
addTA(roc_12, col = "blue", on = NA)

# 6. 输出统计
cat("ROC 均值：", round(mean(roc_12, na.rm = TRUE), 3), "\n")
cat("ROC 标准差：", round(sd(roc_12, na.rm = TRUE), 3), "\n")
cat("读数落在正负 20 以内的占比：",
    round(sum(abs(roc_12) < 20, na.rm = TRUE) / sum(!is.na(roc_12)), 3), "\n")

# ---- 代码块 2：拆解 ----

# 沿用第 007 章的数据准备（panel 含 date / code / close / high / low / volume）
library(dplyr)
library(TTR)
library(zoo)

panel <- panel |>
  group_by(code) |>
  arrange(date, .by_group = TRUE) |>
  mutate(
    ret1 = close / dplyr::lag(close) - 1,
    # 变化率读数：十二个交易日的累计变化，单位为百分比
    roc12 = as.numeric(TTR::ROC(close, n = 12, type = "discrete")) * 100,
    # 分位标准化值：近 120 日窗口内的经验百分位，含当日，映射到 0 到 100
    roc_pct = zoo::rollapply(roc12, 120,
                             function(x) mean(x <= x[length(x)], na.rm = TRUE),
                             fill = NA, align = "right") * 100,
    # 符号状态：方向单独提出，幅度归零
    roc_sign = as.integer(roc12 > 0),
    # 波动调整值：读数除以收益率的滚动标准差，换算成倍数
    vol20 = zoo::rollapply(ret1, 20, sd, fill = NA, align = "right") * 100,
    roc_std = roc12 / vol20
  ) |>
  ungroup() |>
  arrange(code, date)

panel |>
  select(code, date, roc12, roc_pct, roc_sign, roc_std) |>
  head(8)

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
panel <- panel |>
  group_by(code) |>
  mutate(
    ret1 = close / dplyr::lag(close) - 1,
    roc12 = as.numeric(TTR::ROC(close, n = 12, type = "discrete")) * 100,
    roc60 = as.numeric(TTR::ROC(close, n = 60, type = "discrete")) * 100,
    vol20 = zoo::rollapply(ret1, 20, sd, fill = NA, align = "right") * 100,
    roc_std = roc12 / vol20,          # 波动调整值
    roc_sign = as.integer(roc12 > 0)  # 符号状态，幅度归零
  ) |>
  ungroup()

# 原始读数：一日与五日两个前向窗口
for (h in c("forward_1", "forward_5")) {
  print(ic_summary(cross_section_ic(panel, "roc12", h)))
}

print(layered_returns(panel, "roc12", "forward_5"))

# 符号状态与波动调整值作对照
print(ic_summary(cross_section_ic(panel, "roc_sign", "forward_5")))
print(ic_summary(cross_section_ic(panel, "roc_std", "forward_5")))

# 按年份切分，检查 IC 符号是否稳定
ic <- cross_section_ic(panel, "roc12", "forward_5")
data.frame(date = as.Date(names(ic)), ic = as.numeric(ic)) |>
  mutate(year = format(date, "%Y")) |>
  group_by(year) |>
  summarise(IC均值 = round(mean(ic), 4), 期数 = n(), .groups = "drop") |>
  print()

# 对照回归：对 60 日读数取横截面残差，看短周期项是否还有增量
panel <- panel |>
  group_by(date) |>
  mutate(beta = cov(roc12, roc60, use = "complete.obs") /
           var(roc60, use = "complete.obs"),
         roc_resid = roc12 - mean(roc12, na.rm = TRUE) -
           beta * (roc60 - mean(roc60, na.rm = TRUE))) |>
  ungroup()

print(ic_summary(cross_section_ic(panel, "roc_resid", "forward_5")))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(roc_neg = -roc12)   # 取负后上分位即对应超卖端

cat("--- 信号触发日检验（读数高于 80 分位）---\n")
print(timing_signal_test(df, "roc12", "forward_5", upper = 0.8))

cat("\n--- 超卖端（读数低于 20 分位）---\n")
print(timing_signal_test(df, "roc_neg", "forward_5", upper = 0.8))

cat("\n--- 条件分位收益（读数分五档）---\n")
print(conditional_quantile_return(df, "roc12", "forward_5", q = 5))

cat("\n--- 择时策略与买入持有对照 ---\n")
print(timing_backtest(df, "roc12", "forward_5", entry_q = 0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal / cross_section_ic / ic_summary / timing_backtest
panel <- panel |>
  group_by(code) |>
  mutate(vol_ratio = volume /
           zoo::rollmean(volume, 20, fill = NA, align = "right")) |>
  ungroup()

# 组合的截面验证：先看相关，再看加权后的 ICIR
panel |>
  group_by(date) |>
  summarise(rho = cor(roc12, vol_ratio, method = "spearman",
                      use = "complete.obs"), .groups = "drop") |>
  summarise(平均相关 = round(mean(rho, na.rm = TRUE), 3)) |>
  print()

panel <- combined_signal(panel, c("roc12", "vol_ratio"))
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "roc12", "forward_5")))
print(ic_summary(cross_section_ic(panel, "vol_ratio", "forward_5")))

# 组合的择时验证：读数转正且站上二十日均线才持仓
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(cond = as.integer(roc12 > 0 & close > TTR::SMA(close, 20)))

# 条件信号为 0 或 1，阈值取 0 等价于条件成立即持仓
print(timing_backtest(df, "cond", "forward_5", entry_q = 0))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
# 二值条件经 entry_q = 0.5 转成仓位，并与单用读数大于零的对照组并列
# 条件成立的交易日若超过半数，中位数升到 1，仓位会恒为零，此时改用 entry_q = 0
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(sma20 = TTR::SMA(close, 20),
         cond = as.integer(close > sma20 & roc12 > 0),
         cond_base = as.integer(roc12 > 0))

print(timing_backtest(df, "cond", "forward_5", entry_q = 0.5))
print(timing_backtest(df, "cond_base", "forward_5", entry_q = 0.5))
