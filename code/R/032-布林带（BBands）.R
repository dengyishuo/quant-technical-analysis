# ============================================================
# 第032章 布林带（BBands）
# 模块 05 波动率类指标
# 源文件：模块05-波动率类指标/第032章-布林带（BBands）.md
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

# 3. 计算布林带（返回 dn / mavg / up / pctB 四列）
bb <- BBands(close_price, n = 20, sd = 2)

# 4. 识别信号：带宽（上下轨之差 / 中轨）与 %B
band_width <- (bb[, "up"] - bb[, "dn"]) / bb[, "mavg"]
pctB <- bb[, "pctB"]
cat("当前带宽：", round(tail(band_width, 1), 4), "\n")
cat("当前 %B：", round(tail(pctB, 1), 4), "\n")

# 5. 绘图
chartSeries(data, theme = "white", name = "贵州茅台",
  TA = "addBBands(n = 20, sd = 2)")

# 6. 输出统计：带宽处于低位的天数占比
squeeze <- band_width < quantile(band_width, 0.2, na.rm = TRUE)
cat("带宽处于低 20 百分位的天数占比：",
    round(mean(squeeze, na.rm = TRUE), 3), "\n")

# ---- 代码块 2：拆解 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
library(dplyr)
library(TTR)

# panel 需包含 date / code / high / low / close
bb_cols <- function(d, n = 20, k = 2) {
  bb <- TTR::BBands(cbind(High = d$high, Low = d$low, Close = d$close), n = n, sd = k)
  d$bb_up <- as.numeric(bb[, "up"])
  d$bb_mid <- as.numeric(bb[, "mavg"])
  d$bb_dn <- as.numeric(bb[, "dn"])
  d$bb_pctb <- as.numeric(bb[, "pctB"])
  d
}

panel <- panel |> group_by(code) |> arrange(date, .by_group = TRUE) |>
  group_modify(~ bb_cols(.x)) |> ungroup() |>
  mutate(bb_width = (bb_up - bb_dn) / bb_mid,
         bb_width_chg = bb_width / dplyr::lag(bb_width, 4) - 1,
         # 挤压：带宽低于全样本 20 分位，实盘须改滚动分位
         squeeze = as.integer(bb_width < quantile(bb_width, 0.2, na.rm = TRUE)))

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# 第一组：%B 对收益目标
print(ic_summary(cross_section_ic(panel, "bb_pctb", "forward_1")))
print(ic_summary(cross_section_ic(panel, "bb_pctb", "forward_5")))
print(layered_returns(panel, "bb_pctb", "forward_5"))

# 第二组：带宽对波动率目标，单独成表
print(ic_summary(cross_section_ic(panel, "bb_width", "fwd_vol_20")))

# 挤压是二值状态，用分组对照而不是 IC
panel |> group_by(squeeze) |>
  summarise(样本数 = n(),
            未来波动 = round(mean(fwd_vol_20, na.rm = TRUE), 4),
            未来收益 = round(mean(forward_5, na.rm = TRUE) * 100, 3),
            收益标准差 = round(sd(forward_5, na.rm = TRUE) * 100, 3),
            .groups = "drop") |> print()

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的 timing_signal_test / conditional_quantile_return / timing_backtest
df <- panel |> filter(code == "600519.SS") |> arrange(date)

# 触轨事件：%B 高于 95 分位视为触及上轨
print(timing_signal_test(df, "bb_pctb", "forward_5", upper = 0.95))

# 条件分位收益：%B 分五档
print(conditional_quantile_return(df, "bb_pctb", "forward_5", q = 5))

# 挤压与非挤压的收益分布对照
df |> group_by(squeeze) |>
  summarise(样本数 = n(),
            平均收益 = round(mean(forward_5, na.rm = TRUE) * 100, 3),
            标准差 = round(sd(forward_5, na.rm = TRUE) * 100, 3),
            夏普 = round(mean(forward_5, na.rm = TRUE) /
                           sd(forward_5, na.rm = TRUE) * sqrt(252 / 5), 2),
            左尾 = round(quantile(forward_5, 0.05, na.rm = TRUE) * 100, 3),
            .groups = "drop") |> print()

print(timing_backtest(df |> mutate(low_b = -bb_pctb),
                      "low_b", "forward_5", entry_q = 0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
# 组合的截面验证：两个维度都反向使用，符号先摆正
panel <- panel |> group_by(code) |>
  mutate(low_pos = -bb_pctb,
         low_bw = -bb_width) |> ungroup()

panel |> filter(!is.na(low_pos), !is.na(low_bw)) |> group_by(date) |>
  summarise(rho = cor(low_pos, low_bw, method = "spearman"), .groups = "drop") |>
  summarise(平均相关 = round(mean(rho, na.rm = TRUE), 3)) |> print()

panel <- combined_signal(panel, c("low_pos", "low_bw"))
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "low_pos", "forward_5")))
print(ic_summary(cross_section_ic(panel, "low_bw", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 沿用第 007 章定义的 timing_backtest
# 组合的择时验证：挤压状态下价格上穿中轨才持仓
df <- panel |> filter(code == "600519.SS") |> arrange(date) |>
  mutate(cond_sq = as.integer(bb_width < quantile(bb_width, 0.3, na.rm = TRUE)),
         cond_up = as.integer(close > bb_mid),
         cond = as.integer(cond_sq == 1 & cond_up == 1))

print(timing_backtest(df, "cond_sq", "forward_5", entry_q = 0.5))
print(timing_backtest(df, "cond_up", "forward_5", entry_q = 0.5))
print(timing_backtest(df, "cond", "forward_5", entry_q = 0.5))
