# ============================================================
# 第034章 价格包络线（Envelope）
# 模块 05 波动率类指标
# 源文件：模块05-波动率类指标/第034章-价格包络线（Envelope）.md
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

# 3. 计算指标：SMA 中轨与固定百分比上下轨（手写）
n <- 20; pct <- 0.03
env_mid <- SMA(close_price, n = n)
env_up  <- env_mid * (1 + pct)
env_dn  <- env_mid * (1 - pct)

# 4. 识别信号：触轨与相对位置
pct_e <- (close_price - env_dn) / (env_up - env_dn)
touch_up <- close_price > env_up
touch_dn <- close_price < env_dn
cat("触上轨次数：", sum(touch_up, na.rm = TRUE), "\n")
cat("触下轨次数：", sum(touch_dn, na.rm = TRUE), "\n")

# 5. 绘图
chartSeries(data, theme = "white", name = "贵州茅台")
addTA(merge(env_up, env_mid, env_dn), col = c("red", "blue", "green"),
      legend = "Envelope upper / mid / lower")

# 6. 输出统计：价格处于通道内的天数占比
inside <- close_price <= env_up & close_price >= env_dn
cat("价格处于通道内的天数占比：", round(mean(inside, na.rm = TRUE), 3), "\n")

# ---- 代码块 2：拆解 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
library(dplyr)
library(TTR)

# panel 需包含 date / code / close
pct <- 0.03
panel <- panel |> group_by(code) |> arrange(date, .by_group = TRUE) |>
  mutate(env_mid = as.numeric(TTR::SMA(close, n = 20)),
         env_up = env_mid * (1 + pct),
         env_dn = env_mid * (1 - pct),
         env_pct = (close - env_dn) / (env_up - env_dn),
         env_dev = close / env_mid - 1,
         env_width = (env_up - env_dn) / env_mid,
         outside = as.integer(close > env_up | close < env_dn),
         out_share = zoo::rollmean(outside, 20, fill = NA, align = "right")) |>
  ungroup()

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# 第一组：%E 对收益目标
print(ic_summary(cross_section_ic(panel, "env_pct", "forward_1")))
print(ic_summary(cross_section_ic(panel, "env_pct", "forward_5")))
print(layered_returns(panel, "env_pct", "forward_5"))

# %E 与均线偏离的秩相关，理论上等于 1，偏离说明数据对齐有问题
panel |> filter(!is.na(env_pct), !is.na(env_dev)) |> group_by(date) |>
  summarise(rho = cor(env_pct, env_dev, method = "spearman"), .groups = "drop") |>
  summarise(平均相关 = round(mean(rho, na.rm = TRUE), 3)) |> print()

# 第二组：波动率目标。带宽是常数，横截面标准差应为 0；穿透占比才有信息
panel |> group_by(date) |>
  summarise(sd_w = sd(env_width, na.rm = TRUE), .groups = "drop") |>
  summarise(带宽的平均横截面标准差 = round(mean(sd_w, na.rm = TRUE), 6)) |> print()
print(ic_summary(cross_section_ic(panel, "out_share", "fwd_vol_20")))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的 timing_signal_test / conditional_quantile_return / timing_backtest
df <- panel |> filter(code == "600519.SS") |> arrange(date)

# 触轨事件：%E 高于 95 分位视为触及上轨
print(timing_signal_test(df, "env_pct", "forward_5", upper = 0.95))

# 条件分位收益：%E 分五档
print(conditional_quantile_return(df, "env_pct", "forward_5", q = 5))

# 连续穿透与通道内的收益分布对照
df <- df |> mutate(deep = as.integer(out_share > 0.2))
df |> group_by(deep) |>
  summarise(样本数 = n(),
            平均收益 = round(mean(forward_5, na.rm = TRUE) * 100, 3),
            标准差 = round(sd(forward_5, na.rm = TRUE) * 100, 3),
            夏普 = round(mean(forward_5, na.rm = TRUE) /
                           sd(forward_5, na.rm = TRUE) * sqrt(252 / 5), 2),
            左尾 = round(quantile(forward_5, 0.05, na.rm = TRUE) * 100, 3),
            .groups = "drop") |> print()

print(timing_backtest(df |> mutate(low_e = -env_pct),
                      "low_e", "forward_5", entry_q = 0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
# 组合的截面验证：位置取负，带宽取负，先补布林带宽度
panel <- panel |> group_by(code) |>
  mutate(bb_width = 4 * zoo::rollapply(close, 20, sd, fill = NA, align = "right") /
           zoo::rollmean(close, 20, fill = NA, align = "right"),
         low_e = -env_pct, low_bw = -bb_width) |> ungroup()

panel |> filter(!is.na(low_e), !is.na(low_bw)) |> group_by(date) |>
  summarise(rho = cor(low_e, low_bw, method = "spearman"), .groups = "drop") |>
  summarise(平均相关 = round(mean(rho, na.rm = TRUE), 3)) |> print()

panel <- combined_signal(panel, c("low_e", "low_bw"))
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "low_e", "forward_5")))
print(ic_summary(cross_section_ic(panel, "low_bw", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 沿用第 007 章定义的 timing_backtest
# 组合的择时验证：触轨且带宽处于低位才做回归
df <- panel |> filter(code == "600519.SS") |> arrange(date) |>
  mutate(cond_touch = as.integer(env_pct < 0.1),
         cond_calm = as.integer(bb_width < quantile(bb_width, 0.5, na.rm = TRUE)),
         cond = as.integer(cond_touch == 1 & cond_calm == 1))

print(timing_backtest(df, "cond_touch", "forward_5", entry_q = 0.5))
print(timing_backtest(df, "cond_calm", "forward_5", entry_q = 0.5))
print(timing_backtest(df, "cond", "forward_5", entry_q = 0.5))
