# ============================================================
# 第022章 随机指标（KDJ）
# 模块 04 震荡类指标
# 源文件：模块04-震荡类指标/第022章-随机指标（KDJ）.md
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
# TTR 的 stoch() 按顺序返回三列：第 1 列是 RSV，第 2 列与第 3 列是两次平滑的结果
st <- stoch(HLC(data), nFastK = 9, nFastD = 3, nSlowD = 3)
rsv    <- st[, 1]                 # 未成熟随机值
k_line <- st[, 2]                 # K 线：对 RSV 做 3 期平滑
d_line <- st[, 3]                 # D 线：对 K 线再做 3 期平滑
j_line <- 3 * k_line - 2 * d_line

# 4. 识别信号
golden_cross <- crossover(k_line, d_line)
dead_cross   <- crossover(d_line, k_line)
low_golden   <- golden_cross & (k_line < 50)   # 低位金叉
cat("金叉次数：", sum(golden_cross, na.rm = TRUE), "\n")
cat("其中低位金叉：", sum(low_golden, na.rm = TRUE), "\n")
cat("J 线越过 100 的次数：", sum(j_line > 100, na.rm = TRUE), "\n")
cat("J 线跌破 0 的次数：", sum(j_line < 0, na.rm = TRUE), "\n")

# 5. 绘图
chartSeries(data, theme = "white", name = "贵州茅台",
  TA = "addTA(k_line, col = 'blue'); addTA(d_line, col = 'red'); addTA(j_line, col = 'darkgreen')")

# 6. 输出统计
kdj_extreme <- (k_line > 80) | (k_line < 20)
cat("K 线处于极端区域的占比：",
    round(sum(kdj_extreme, na.rm = TRUE) / sum(!is.na(k_line)), 3), "\n")

# ---- 代码块 2：拆解 ----

# 沿用第 007 章的数据准备（panel 含 date / code / close / high / low / volume）
library(dplyr)
library(TTR)

panel <- panel |>
  group_by(code) |>
  arrange(date, .by_group = TRUE) |>
  mutate(
    hh9 = TTR::runMax(high, 9),
    ll9 = TTR::runMin(low, 9),
    rsv9 = ifelse(hh9 == ll9, 50, (close - ll9) / (hh9 - ll9) * 100),
    # 按正文的递推平滑，1/m 系数对应 wilder 口径
    k9 = TTR::EMA(rsv9, n = 3, wilder = TRUE),
    d9 = TTR::EMA(k9, n = 3, wilder = TRUE),
    # 位置偏离：K 相对 50 的位置
    kdj_pos = k9 - 50,
    # 柱状值：短期相对中期的领先程度
    kdj_diff = k9 - d9,
    # J 值：3K - 2D，原式可越出 0 到 100
    kdj_j = 3 * k9 - 2 * d9,
    # 截断后的 J 值，越界部分被压平
    kdj_j_clip = pmax(pmin(kdj_j, 100), 0),
    # 交叉状态：K 在 D 上方记 1，否则记 0
    kdj_cross = as.integer(k9 > d9)
  ) |>
  ungroup()

panel |>
  select(date, code, kdj_pos, kdj_diff, kdj_j, kdj_j_clip, kdj_cross) |>
  filter(!is.na(kdj_diff)) |>
  head(8) |>
  print()

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# panel 含 date / code / high / low / close / forward_1 / forward_5
# K、D 按正文的递推平滑计算，1/m 系数对应 wilder 口径
panel <- panel |>
  group_by(code) |>
  mutate(hh9 = TTR::runMax(high, 9),
         ll9 = TTR::runMin(low, 9),
         rsv9 = ifelse(hh9 == ll9, 50, (close - ll9) / (hh9 - ll9) * 100),
         k9 = TTR::EMA(rsv9, n = 3, wilder = TRUE),
         d9 = TTR::EMA(k9, n = 3, wilder = TRUE),
         kdj_pos = k9 - 50,
         kdj_diff = k9 - d9) |>
  ungroup()

for (h in c("forward_1", "forward_5")) {
  cat("\n--- 柱状值 vs", h, "---\n")
  print(ic_summary(cross_section_ic(panel, "kdj_diff", h)))
}
print(layered_returns(panel, "kdj_diff", "forward_1"))

# 符号稳定性：按年切分
year_ic <- panel |>
  mutate(year = format(as.Date(date), "%Y")) |>
  group_split(year) |>
  lapply(function(d) data.frame(
    年份 = d$year[1],
    IC均值 = round(mean(cross_section_ic(d, "kdj_diff", "forward_5")), 4)))
print(do.call(rbind, year_ic))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(golden = k9 > d9 & dplyr::lag(k9) <= dplyr::lag(d9))

# 金叉按 K 的位置分组，两类交叉的含义相反
df |> filter(golden) |> group_by(位置 = ifelse(k9 >= 50, "高位", "低位")) |>
  summarise(次数 = n(),
            平均收益 = round(mean(forward_5, na.rm = TRUE) * 100, 3)) |>
  print()

cat("\n--- 信号触发日检验（柱状值高于 80 分位）---\n")
print(timing_signal_test(df, "kdj_diff", "forward_5", upper = 0.8))

cat("\n--- 条件分位收益（位置偏离分五档）---\n")
print(conditional_quantile_return(df, "kdj_pos", "forward_5", q = 5))

cat("\n--- 择时策略与买入持有对照 ---\n")
print(timing_backtest(df, "kdj_diff", "forward_5", entry_q = 0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal / cross_section_ic / timing_backtest
# 截面路径：KDJ 柱状值与价格对均线偏离的组合
panel <- panel |>
  group_by(code) |>
  mutate(sma20 = zoo::rollmean(close, 20, fill = NA, align = "right"),
         sma_dev = close / sma20 - 1) |>
  ungroup()

panel |>
  filter(!is.na(kdj_diff), !is.na(sma_dev)) |>
  group_by(date) |>
  summarise(rho = cor(kdj_diff, sma_dev, method = "spearman"), .groups = "drop") |>
  summarise(平均相关 = round(mean(rho, na.rm = TRUE), 3)) |>
  print()

panel <- combined_signal(panel, c("kdj_diff", "sma_dev"))

cat("\n--- 组合 vs 单特征 ---\n")
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "kdj_diff", "forward_5")))
print(ic_summary(cross_section_ic(panel, "sma_dev", "forward_5")))

# 择时路径：只在 ADX 低于 40 时接受交叉信号
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(adx14 = as.numeric(TTR::ADX(cbind(High = high, Low = low,
                                            Close = close), n = 14)[, "ADX"]),
         kdj_calm = ifelse(adx14 < 40, kdj_diff, NA_real_))

cat("\n--- 弱趋势样本内的择时 ---\n")
print(timing_backtest(df, "kdj_calm", "forward_5", entry_q = 0.7))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
# 趋势过滤：价格在 20 日均线上方，且 K 上穿 D 时持仓
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(sma20 = TTR::SMA(close, 20),
         cond = as.integer(close > sma20 & k9 > d9 &
                             dplyr::lag(k9) <= dplyr::lag(d9)))

print(timing_backtest(df, "cond", "forward_5", entry_q = 0.5))
