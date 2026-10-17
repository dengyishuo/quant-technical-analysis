# ============================================================
# 第033章 肯特纳通道（Keltner）
# 模块 05 波动率类指标
# 源文件：模块05-波动率类指标/第033章-肯特纳通道（Keltner）.md
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
close_price <- Cl(data)

# 3. 计算指标：EMA 中轨与 ATR 宽度（手写）
n <- 20; m <- 10; k <- 2
kc_mid <- EMA(close_price, n = n)
atr_m  <- ATR(HLC(data), n = m)[, "atr"]
kc_up  <- kc_mid + k * atr_m
kc_dn  <- kc_mid - k * atr_m

# 4. 识别信号：通道宽度与 %K
kc_width <- (kc_up - kc_dn) / kc_mid
kc_pct   <- (close_price - kc_dn) / (kc_up - kc_dn)
cat("当前通道宽度：", round(tail(kc_width, 1), 4), "\n")
cat("当前 %K：", round(tail(kc_pct, 1), 4), "\n")

# 5. 绘图
chartSeries(data, theme = "white", name = "贵州茅台")
addTA(merge(kc_up, kc_mid, kc_dn), col = c("red", "blue", "green"),
      legend = "KC upper / mid / lower")

# 6. 输出统计：通道宽度处于低 20 百分位的天数占比
sq <- kc_width < quantile(kc_width, 0.2, na.rm = TRUE)
cat("通道宽度处于低 20 百分位的天数占比：",
    round(mean(sq, na.rm = TRUE), 3), "\n")

# ---- 代码块 2：拆解 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
library(dplyr)
library(TTR)

# panel 需包含 date / code / high / low / close
panel <- panel |> group_by(code) |> arrange(date, .by_group = TRUE) |>
  mutate(kc_mid = as.numeric(TTR::EMA(close, n = 20)),
         atr10 = as.numeric(TTR::ATR(
           cbind(High = high, Low = low, Close = close), n = 10)[, "atr"]),
         kc_up = kc_mid + 2 * atr10,
         kc_dn = kc_mid - 2 * atr10,
         kc_width = (kc_up - kc_dn) / kc_mid,
         kc_pct = (close - kc_dn) / (kc_up - kc_dn),
         kc_dev = close / kc_mid - 1,
         kc_width_chg = kc_width / dplyr::lag(kc_width, 5) - 1) |> ungroup()

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# 第一组：%K 对收益目标
print(ic_summary(cross_section_ic(panel, "kc_pct", "forward_1")))
print(ic_summary(cross_section_ic(panel, "kc_pct", "forward_5")))
print(layered_returns(panel, "kc_pct", "forward_5"))

# 第二组：宽度对波动率目标，单独成表
print(ic_summary(cross_section_ic(panel, "kc_width", "fwd_vol_20")))

# 第三组：双通道宽度比，先补布林带宽度再检验
panel <- panel |> group_by(code) |>
  mutate(bb_width = 4 * zoo::rollapply(close, 20, sd, fill = NA, align = "right") /
           zoo::rollmean(close, 20, fill = NA, align = "right"),
         bw_ratio = bb_width / kc_width) |> ungroup()

print(ic_summary(cross_section_ic(panel, "bw_ratio", "fwd_vol_20")))
panel |> filter(!is.na(kc_width), !is.na(bw_ratio)) |> group_by(date) |>
  summarise(rho = cor(kc_width, bw_ratio, method = "spearman"), .groups = "drop") |>
  summarise(平均相关 = round(mean(rho, na.rm = TRUE), 3)) |> print()

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的 timing_signal_test / conditional_quantile_return / timing_backtest
df <- panel |> filter(code == "600519.SS") |> arrange(date)

# 突破事件：%K 高于 95 分位视为站上上轨
print(timing_signal_test(df, "kc_pct", "forward_5", upper = 0.95))

# 条件分位收益：%K 分五档
print(conditional_quantile_return(df, "kc_pct", "forward_5", q = 5))

# 收窄与常态的收益分布对照
df <- df |> mutate(narrow = as.integer(kc_width < quantile(kc_width, 0.2, na.rm = TRUE)))
df |> group_by(narrow) |>
  summarise(样本数 = n(),
            平均收益 = round(mean(forward_5, na.rm = TRUE) * 100, 3),
            标准差 = round(sd(forward_5, na.rm = TRUE) * 100, 3),
            夏普 = round(mean(forward_5, na.rm = TRUE) /
                           sd(forward_5, na.rm = TRUE) * sqrt(252 / 5), 2),
            左尾 = round(quantile(forward_5, 0.05, na.rm = TRUE) * 100, 3),
            .groups = "drop") |> print()

print(timing_backtest(df, "kc_pct", "forward_5", entry_q = 0.8))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
# 组合的截面验证：两条通道的宽度都反向，合成双通道低波动得分
panel <- panel |> group_by(code) |>
  mutate(low_bb = -bb_width, low_kc = -kc_width) |> ungroup()

panel |> filter(!is.na(low_bb), !is.na(low_kc)) |> group_by(date) |>
  summarise(rho = cor(low_bb, low_kc, method = "spearman"), .groups = "drop") |>
  summarise(平均相关 = round(mean(rho, na.rm = TRUE), 3)) |> print()

panel <- combined_signal(panel, c("low_bb", "low_kc"))
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "low_bb", "forward_5")))
print(ic_summary(cross_section_ic(panel, "low_kc", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 沿用第 007 章定义的 timing_backtest
# 组合的择时验证：突破上轨且中轨向上才持仓
df <- panel |> filter(code == "600519.SS") |> arrange(date) |>
  mutate(kc_slope = kc_mid / dplyr::lag(kc_mid, 5) - 1,
         cond_break = as.integer(kc_pct > 0.9),
         cond_trend = as.integer(kc_slope > 0),
         cond = as.integer(cond_break == 1 & cond_trend == 1))

print(timing_backtest(df, "cond_break", "forward_5", entry_q = 0.5))
print(timing_backtest(df, "cond_trend", "forward_5", entry_q = 0.5))
print(timing_backtest(df, "cond", "forward_5", entry_q = 0.5))
