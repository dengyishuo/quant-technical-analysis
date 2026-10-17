# ============================================================
# 第030章 平均真实波幅（ATR）
# 模块 05 波动率类指标
# 源文件：模块05-波动率类指标/第030章-平均真实波幅（ATR）.md
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
# 3. 计算 ATR（TTR 的 ATR 基于最高、最低、收盘三个序列）
atr14 <- ATR(HLC(data), n = 14)

# 4. 识别信号：ATR 追踪止损，止损位 = 20 日最高价 - 3 倍 ATR
highest   <- runMax(Hi(data), n = 20)
trail_stop <- highest - 3 * atr14[, "atr"]
cat("当前追踪止损位：", round(tail(trail_stop, 1), 2), "\n")

# 5. 绘图
chartSeries(data, theme = "white", name = "贵州茅台")
addTA(atr14[, "atr"], col = "purple", legend = "ATR14")

# 6. 输出统计：ATR 比率的均值
atr_ratio <- atr14[, "atr"] / Cl(data)
cat("ATR 比率的均值：", round(mean(atr_ratio, na.rm = TRUE), 4), "\n")

# ---- 代码块 2：拆解 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
library(dplyr)
library(TTR)

# panel 需包含 date / code / high / low / close
panel <- panel |>
  group_by(code) |>
  arrange(date, .by_group = TRUE) |>
  mutate(atr14 = as.numeric(TTR::ATR(
           cbind(High = high, Low = low, Close = close), n = 14)[, "atr"]),
         atr_ratio = atr14 / close,
         atr_chg = atr14 / dplyr::lag(atr14, 10) - 1,
         # 历史分位：250 日窗口内的经验百分位，含当日
         atr_pctile = zoo::rollapply(atr14, 250, function(x) mean(x <= x[length(x)]),
                                     fill = NA, align = "right")) |>
  ungroup()

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# 第一组：收益目标
for (h in c("forward_1", "forward_5")) {
  cat("\n--- 收益目标：ATR 比率 vs", h, "---\n")
  print(ic_summary(cross_section_ic(panel, "atr_ratio", h)))
}
print(layered_returns(panel, "atr_ratio", "forward_5"))
# 分位版本作稳健性对照，极值影响应明显减弱
print(ic_summary(cross_section_ic(panel, "atr_pctile", "forward_5")))

# 第二组：波动率目标，单独成表，不与上一组的数值比较大小
cat("\n--- 波动率目标 ---\n")
print(ic_summary(cross_section_ic(panel, "atr_ratio", "fwd_vol_20")))
print(layered_returns(panel, "atr_ratio", "fwd_vol_20"))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的 timing_signal_test / conditional_quantile_return / timing_backtest
df <- panel |> filter(code == "600519.SS") |> arrange(date) |>
  mutate(state = dplyr::case_when(
    atr_ratio >= quantile(atr_ratio, 0.8, na.rm = TRUE) ~ "高波动",
    atr_ratio <= quantile(atr_ratio, 0.2, na.rm = TRUE) ~ "低波动",
    TRUE ~ NA_character_))

# 分布对照：均值之外，同时看标准差、夏普、胜率与左尾
df |> filter(!is.na(state)) |> group_by(state) |>
  summarise(样本数 = n(),
            平均收益 = round(mean(forward_5, na.rm = TRUE) * 100, 3),
            标准差 = round(sd(forward_5, na.rm = TRUE) * 100, 3),
            夏普 = round(mean(forward_5, na.rm = TRUE) /
                           sd(forward_5, na.rm = TRUE) * sqrt(252 / 5), 2),
            胜率 = round(mean(forward_5 > 0, na.rm = TRUE), 3),
            左尾 = round(quantile(forward_5, 0.05, na.rm = TRUE) * 100, 3),
            .groups = "drop") |> print()

# 方差齐性检验：两组的离散程度是否真的不同
var.test(forward_5 ~ state, data = df)

print(timing_signal_test(df, "atr_ratio", "forward_5", upper = 0.8))
print(conditional_quantile_return(df, "atr_ratio", "forward_5", q = 5))
print(timing_backtest(df |> mutate(low_vol = -atr_ratio),
                      "low_vol", "forward_5", entry_q = 0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
# 组合的截面验证：先统一符号方向，再做加权
panel <- panel |> group_by(code) |>
  mutate(low_vol = -atr_ratio,
         mom20 = close / dplyr::lag(close, 20) - 1) |> ungroup()

# 先看两个特征的横截面相关，相关性高则组合难有增量
panel |> filter(!is.na(low_vol), !is.na(mom20)) |> group_by(date) |>
  summarise(rho = cor(low_vol, mom20, method = "spearman"), .groups = "drop") |>
  summarise(平均相关 = round(mean(rho, na.rm = TRUE), 3)) |> print()

panel <- combined_signal(panel, c("low_vol", "mom20"))
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "low_vol", "forward_5")))
print(ic_summary(cross_section_ic(panel, "mom20", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 沿用第 007 章定义的 timing_backtest
# 组合的择时验证：低波动与中轨向上同时成立才持仓
df <- panel |> filter(code == "600519.SS") |> arrange(date) |>
  mutate(sma20 = as.numeric(TTR::SMA(close, 20)),
         cond_vol = as.integer(atr_pctile < 0.8),
         cond_trend = as.integer(close > sma20),
         cond = as.integer(cond_vol == 1 & cond_trend == 1))

print(timing_backtest(df, "cond_vol", "forward_5", entry_q = 0.5))
print(timing_backtest(df, "cond_trend", "forward_5", entry_q = 0.5))
print(timing_backtest(df, "cond", "forward_5", entry_q = 0.5))
