# ============================================================
# 第031章 历史波动率（HV）
# 模块 05 波动率类指标
# 源文件：模块05-波动率类指标/第031章-历史波动率（HV）.md
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

# 3. 计算 HV：TTR 的 volatility 支持收盘价口径与年化因子
hv20 <- volatility(close_price, n = 20, calc = "close", N = 252)
hv60 <- volatility(close_price, n = 60, calc = "close", N = 252)

# 4. 识别信号：HV20 上穿 HV60 视为波动扩张
expand <- crossover(hv20, hv60)
cat("波动扩张信号次数：", sum(expand, na.rm = TRUE), "\n")

# 5. 绘图
chartSeries(data, theme = "white", name = "贵州茅台")
addTA(merge(hv20, hv60), col = c("blue", "red"), legend = "HV20 / HV60")

# 6. 输出统计：当前 HV20 的历史百分位
pctile <- mean(hv20 <= tail(hv20, 1), na.rm = TRUE)
cat("当前 HV20 的历史百分位：", round(pctile, 3), "\n")

# ---- 代码块 2：拆解 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
library(dplyr)
library(TTR)

# panel 需包含 date / code / close
panel <- panel |>
  group_by(code) |>
  arrange(date, .by_group = TRUE) |>
  mutate(hv20 = as.numeric(TTR::volatility(close, n = 20, calc = "close", N = 252)),
         hv60 = as.numeric(TTR::volatility(close, n = 60, calc = "close", N = 252)),
         hv_chg = hv20 / dplyr::lag(hv20, 5) - 1,
         hv_ratio = hv20 / hv60,
         # 历史分位：250 日窗口内的经验百分位，含当日
         hv_pctile = zoo::rollapply(hv20, 250, function(x) mean(x <= x[length(x)]),
                                    fill = NA, align = "right")) |>
  ungroup()

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# 收益目标：一日与五日两个前向窗口
print(ic_summary(cross_section_ic(panel, "hv20", "forward_1")))
print(ic_summary(cross_section_ic(panel, "hv20", "forward_5")))
print(layered_returns(panel, "hv20", "forward_5"))
# 长短周期之比作第二个候选
print(ic_summary(cross_section_ic(panel, "hv_ratio", "forward_5")))

# 波动率目标：单独成表，不与上一组的数值比较大小
print(ic_summary(cross_section_ic(panel, "hv20", "fwd_vol_20")))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的 timing_signal_test / conditional_quantile_return / timing_backtest
df <- panel |> filter(code == "600519.SS") |> arrange(date) |>
  mutate(state = dplyr::case_when(
    hv_pctile >= 0.67 ~ "高波动",
    hv_pctile <= 0.33 ~ "低波动",
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

# 长短周期之比落到九成分位以上，视为波动扩张事件
print(timing_signal_test(df, "hv_ratio", "forward_5", upper = 0.9))
print(conditional_quantile_return(df, "hv_pctile", "forward_5", q = 5))
print(timing_backtest(df |> mutate(low_vol = -hv20),
                      "low_vol", "forward_5", entry_q = 0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
# 组合的截面验证：先统一符号方向，再做加权
panel <- panel |> group_by(code) |>
  mutate(low_vol = -hv20,
         mom20 = close / dplyr::lag(close, 20) - 1) |> ungroup()

panel |> filter(!is.na(low_vol), !is.na(mom20)) |> group_by(date) |>
  summarise(rho = cor(low_vol, mom20, method = "spearman"), .groups = "drop") |>
  summarise(平均相关 = round(mean(rho, na.rm = TRUE), 3)) |> print()

panel <- combined_signal(panel, c("low_vol", "mom20"))
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "low_vol", "forward_5")))
print(ic_summary(cross_section_ic(panel, "mom20", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 沿用第 007 章定义的 timing_backtest
# 组合的择时验证：中低波动与中期均线之上同时成立才持仓
df <- panel |> filter(code == "600519.SS") |> arrange(date) |>
  mutate(sma60 = as.numeric(TTR::SMA(close, 60)),
         cond_vol = as.integer(hv_pctile < 0.67),
         cond_trend = as.integer(close > sma60),
         cond = as.integer(cond_vol == 1 & cond_trend == 1))

print(timing_backtest(df, "cond_vol", "forward_5", entry_q = 0.5))
print(timing_backtest(df, "cond_trend", "forward_5", entry_q = 0.5))
print(timing_backtest(df, "cond", "forward_5", entry_q = 0.5))
