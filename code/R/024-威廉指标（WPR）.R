# ============================================================
# 第024章 威廉指标（WPR）
# 模块 04 震荡类指标
# 源文件：模块04-震荡类指标/第024章-威廉指标（WPR）.md
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
# 3. 计算指标
# TTR 的 WPR 返回 0 到 1 的比例值，乘负 100 才还原为标准刻度（负 100 到 0）
wpr_6  <- WPR(HLC(data), n = 6)  * -100
wpr_14 <- WPR(HLC(data), n = 14) * -100
wpr_28 <- WPR(HLC(data), n = 28) * -100

# 4. 识别信号
oversold   <- wpr_14 < -80
overbought <- wpr_14 > -20
# 多周期超卖共振
resonance  <- (wpr_6 < -80) & (wpr_14 < -70) & (wpr_28 < -60)
cat("14 日超卖天数：", sum(oversold, na.rm = TRUE), "\n")
cat("14 日超买天数：", sum(overbought, na.rm = TRUE), "\n")
cat("三周期超卖共振天数：", sum(resonance, na.rm = TRUE), "\n")

# 5. 绘图
# 用 addTA 画已还原刻度的序列，参考线才能与负 20、负 80 对齐
chartSeries(data, theme = "white", name = "贵州茅台")
addTA(wpr_14, name = "WPR14", col = "blue")
abline(h = c(-80, -20), col = "gray", lty = 3)

# 6. 输出统计
cat("WPR14 落在负 80 以下的占比：",
    round(sum(oversold, na.rm = TRUE) / sum(!is.na(wpr_14)), 3), "\n")
cat("WPR14 落在负 20 以上的占比：",
    round(sum(overbought, na.rm = TRUE) / sum(!is.na(wpr_14)), 3), "\n")

# ---- 代码块 2：拆解 ----

# 沿用第 007 章的数据准备（panel 含 date / code / close / high / low / volume）
library(dplyr)
library(TTR)

# 极端状态的连续期数：超卖侧记正，超买侧记负，回到中性区归零
signed_run <- function(state) {
  r <- rle(state)
  len <- sequence(r$lengths)
  ifelse(state == 0, 0L, sign(state) * len)
}

panel <- panel |>
  group_by(code) |>
  arrange(date, .by_group = TRUE) |>
  mutate(
    # TTR 的 WPR 返回 0 到 1 的比例值，乘负 100 才是负 100 到 0 的标准刻度
    wpr14 = -100 * as.numeric(
      TTR::WPR(cbind(High = high, Low = low, Close = close), n = 14)),
    # 平移值：中心移到零轴
    wpr_dev = wpr14 + 50,
    # 镜像读数：取负，方向与 RSI 一致
    wpr_mirror = -wpr14,
    # 分位标记：250 日窗口内的经验百分位，含当日
    wpr_pctile = zoo::rollapply(wpr14, 250,
                                function(x) mean(x <= x[length(x)]),
                                fill = NA, align = "right"),
    # 极值持续期：连续低于负 80 记正，连续高于负 20 记负
    wpr_ext_run = signed_run(dplyr::case_when(
      is.na(wpr14) ~ 0L,
      wpr14 < -80 ~ 1L,
      wpr14 > -20 ~ -1L,
      TRUE ~ 0L
    ))
  ) |>
  ungroup()

panel |>
  select(date, code, wpr14, wpr_dev, wpr_mirror, wpr_pctile, wpr_ext_run) |>
  filter(!is.na(wpr14)) |>
  head(8) |>
  print()

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# panel 含 date / code / high / low / close / forward_1 / forward_5
# TTR 的 WPR 返回 0 到 1 的比例值，乘负 100 才是负 100 到 0 的标准刻度
panel <- panel |>
  group_by(code) |>
  mutate(wpr14 = -100 * as.numeric(
           TTR::WPR(cbind(High = high, Low = low, Close = close), n = 14)),
         wpr_dev = wpr14 + 50,
         wpr_mirror = -wpr14,
         wpr6 = -100 * as.numeric(
           TTR::WPR(cbind(High = high, Low = low, Close = close), n = 6))) |>
  ungroup()

for (h in c("forward_1", "forward_5")) {
  cat("\n--- WPR 平移值 vs", h, "---\n")
  print(ic_summary(cross_section_ic(panel, "wpr_dev", h)))
}

print(layered_returns(panel, "wpr_dev", "forward_5"))

# 镜像刻度只差一个符号，IC 应当近似相反
print(ic_summary(cross_section_ic(panel, "wpr_mirror", "forward_5")))

# 符号稳定性：按年切分
year_ic <- panel |>
  mutate(year = format(as.Date(date), "%Y")) |>
  group_split(year) |>
  lapply(function(d) {
    data.frame(年份 = d$year[1],
               IC均值 = round(mean(cross_section_ic(d, "wpr_dev", "forward_5")), 4))
  })
print(do.call(rbind, year_ic))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(wpr_rev = -wpr_dev)

cat("--- 上尾：平移值高于 80 分位，对应接近区间上沿 ---\n")
print(timing_signal_test(df, "wpr_dev", "forward_5", upper = 0.8))

cat("\n--- 下尾：取负后高于 80 分位，对应接近区间下沿 ---\n")
print(timing_signal_test(df, "wpr_rev", "forward_5", upper = 0.8))

cat("\n--- 条件分位收益 ---\n")
print(conditional_quantile_return(df, "wpr_dev", "forward_5", q = 5))

cat("\n--- 反转规则的回测（超卖一侧持仓）---\n")
print(timing_backtest(df, "wpr_rev", "forward_5", entry_q = 0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal / cross_section_ic / timing_backtest
# 截面路径：先做冗余检验，再做与量比的组合
panel <- panel |>
  group_by(code) |>
  mutate(rsi14 = as.numeric(TTR::RSI(close, n = 14)),
         vol_ratio = volume / zoo::rollmean(volume, 20, fill = NA, align = "right")) |>
  ungroup()

# 镜像刻度下，WPR 与 RSI 应当同向且高度相关
panel |>
  filter(!is.na(wpr_mirror), !is.na(rsi14)) |>
  group_by(date) |>
  summarise(rho = cor(wpr_mirror, rsi14, method = "spearman"), .groups = "drop") |>
  summarise(平均相关 = round(mean(rho, na.rm = TRUE), 3)) |>
  print()

panel <- combined_signal(panel, c("wpr_mirror", "vol_ratio"))

cat("\n--- 组合 vs 单特征 ---\n")
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "wpr_mirror", "forward_5")))
print(ic_summary(cross_section_ic(panel, "vol_ratio", "forward_5")))

# 择时路径：6 日与 14 日同时处于超卖区时，才评估镜像读数的信号
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(wpr_gate = ifelse(wpr6 < -80 & wpr14 < -70, wpr_mirror, NA_real_))

cat("\n--- 共振样本内的择时 ---\n")
print(timing_backtest(df, "wpr_gate", "forward_5", entry_q = 0.7))

cat("\n--- 全样本对照 ---\n")
print(timing_backtest(df, "wpr_mirror", "forward_5", entry_q = 0.7))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
# 趋势过滤：价格在 20 日均线上方，且平移值低于负 30（等价于标准读数低于负 80）
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(sma20 = TTR::SMA(close, 20),
         cond = as.integer(close > sma20 & wpr_dev < -30))

print(timing_backtest(df, "cond", "forward_5", entry_q = 0.5))
