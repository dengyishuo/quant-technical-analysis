# ============================================================
# 第019章 抛物线指标（SAR）
# 模块 03 趋势类指标
# 源文件：模块03-趋势类指标/第019章-抛物线指标（SAR）.md
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

# 3. 计算 SAR（TTR 的 SAR 需要最高价与最低价）
sar <- SAR(HLC(data)[, c("High", "Low")], accel = c(0.02, 0.2))

# 4. 识别信号：价格穿越 SAR 触发反转
above     <- close_price > sar
flip_down <- above & !Lag(above)   # 由下穿过 SAR 上方，转多
flip_up   <- !above & Lag(above)   # 由上跌破 SAR，转空
cat("转多信号次数：", sum(flip_down, na.rm = TRUE), "\n")
cat("转空信号次数：", sum(flip_up, na.rm = TRUE), "\n")

# 5. 绘图
chartSeries(data, theme = "white", name = "贵州茅台",
  TA = "addSAR(accel = c(0.02, 0.2))")

# 6. 输出统计：价格位于 SAR 上方的天数占比
above_ratio <- sum(above, na.rm = TRUE) / sum(!is.na(sar))
cat("价格位于 SAR 上方的天数占比：", round(above_ratio, 3), "\n")

# ---- 代码块 2：拆解 ----

# 沿用第 007 章的数据准备（panel 含 date / code / close / high / low / volume）
library(dplyr)
library(xts)
library(TTR)

panel <- panel |>
  group_by(code) |>
  arrange(date, .by_group = TRUE) |>
  mutate(sar = as.numeric(TTR::SAR(xts::xts(cbind(high, low), order.by = date),
                                   accel = c(0.02, 0.2))),
         atr = as.numeric(TTR::ATR(xts::xts(cbind(high, low, close), order.by = date),
                                   n = 14)[, "atr"]),
         # 偏离度：价格相对止损位的距离
         sar_dev = close / sar - 1,
         # 方向状态：价格在 SAR 上方记 1，下方记 0
         sar_state = as.integer(close > sar),
         # 归一化止损距离：以 ATR 倍数衡量的缓冲空间
         sar_atr = (close - sar) / atr,
         flip = sar_state != dplyr::lag(sar_state)) |>
  # 状态段编号在标的内部累计，翻转一次加一
  mutate(run = cumsum(ifelse(is.na(flip), TRUE, flip))) |>
  group_by(code, run) |>
  # 趋势年龄：段内序号，翻转后从 1 重新计数
  mutate(sar_age = dplyr::row_number()) |>
  ungroup()

# 展示四个特征的取值形状
panel |>
  select(date, code, sar_dev, sar_state, sar_age, sar_atr) |>
  na.omit() |>
  head()

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
panel <- panel |>
  group_by(code) |>
  mutate(sar = as.numeric(TTR::SAR(xts::xts(cbind(high, low), order.by = date),
                                   accel = c(0.02, 0.2))),
         atr = as.numeric(TTR::ATR(xts::xts(cbind(high, low, close),
                                            order.by = date), n = 14)[, "atr"]),
         sar_dev = close / sar - 1,
         sar_atr = (close - sar) / atr,
         sar_state = as.integer(close > sar),
         flip = sar_state != dplyr::lag(sar_state)) |>
  mutate(run = cumsum(ifelse(is.na(flip), TRUE, flip))) |>
  group_by(code, run) |>
  mutate(sar_age = dplyr::row_number()) |>
  ungroup()

for (h in c("forward_1", "forward_5")) {
  print(ic_summary(cross_section_ic(panel, "sar_dev", h)))
}

print(layered_returns(panel, "sar_dev", "forward_5"))
print(ic_summary(cross_section_ic(panel, "sar_atr", "forward_5")))

# 剔除翻转日，检查跳变对 IC 的影响
d <- panel |> filter(!flip | is.na(flip))
print(ic_summary(cross_section_ic(d, "sar_dev", "forward_5")))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df <- panel |> filter(code == "600519.SS")

cat("--- 信号触发日检验（偏离度高于 80 分位）---\n")
print(timing_signal_test(df, "sar_dev", "forward_5", upper = 0.8))

cat("\n--- 条件分位收益（趋势年龄分五档）---\n")
print(conditional_quantile_return(df, "sar_age", "forward_5", q = 5))

# 状态即仓位：价格在 SAR 上方持有，翻转即出场
cat("\n--- 状态策略与买入持有对照 ---\n")
print(timing_backtest(df, "sar_state", "forward_5", entry_q = 0.5))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
panel <- panel |>
  group_by(code) |>
  mutate(vol_ratio = volume / zoo::rollmean(volume, 20, fill = NA, align = "right")) |>
  ungroup()

panel |> group_by(date) |>
  summarise(rho = cor(sar_dev, vol_ratio, "spearman", use = "complete.obs"),
            .groups = "drop") |>
  summarise(平均相关 = round(mean(rho, na.rm = TRUE), 3)) |> print()

panel <- combined_signal(panel, c("sar_dev", "vol_ratio"))

print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "sar_dev", "forward_5")))
print(ic_summary(cross_section_ic(panel, "vol_ratio", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(cond = as.integer(sar_state == 1 & close > TTR::SMA(close, 20)))

print(timing_backtest(df, "cond", "forward_5", entry_q = 0.5))
