# ============================================================
# 第015章 多空指数（BBI）
# 模块 03 趋势类指标
# 源文件：模块03-趋势类指标/第015章-多空指数（BBI）.md
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

# 3. 计算 BBI：四个周期 SMA 的算术平均
sma_5  <- SMA(close_price, n = 5)
sma_10 <- SMA(close_price, n = 10)
sma_20 <- SMA(close_price, n = 20)
sma_60 <- SMA(close_price, n = 60)
bbi <- (sma_5 + sma_10 + sma_20 + sma_60) / 4

# 4. 识别信号：价格由下向上突破 BBI
above     <- close_price > bbi
break_up  <- above & !Lag(above)
break_dn  <- !above & Lag(above)
cat("向上突破次数：", sum(break_up, na.rm = TRUE), "\n")
cat("向下跌破次数：", sum(break_dn, na.rm = TRUE), "\n")

# 5. 绘图
chartSeries(data, theme = "white", name = "贵州茅台",
  TA = "addTA(bbi, col = 'darkorange', lwd = 2);
        addSMA(n = 20, col = 'grey')")

# 6. 输出统计：价格位于 BBI 上方的天数占比
above_ratio <- sum(close_price > bbi, na.rm = TRUE) / sum(!is.na(bbi))
cat("价格位于 BBI 上方的天数占比：", round(above_ratio, 3), "\n")

# ---- 代码块 2：拆解 ----

# 沿用第 007 章的数据准备（panel 含 date / code / close / high / low / volume）
library(dplyr)
library(TTR)

# 四个周期的 SMA、综合线，以及表中四列特征
panel <- panel |>
  group_by(code) |>
  arrange(date, .by_group = TRUE) |>
  mutate(sma5  = TTR::SMA(close, 5),
         sma10 = TTR::SMA(close, 10),
         sma20 = TTR::SMA(close, 20),
         sma60 = TTR::SMA(close, 60),
         bbi = (sma5 + sma10 + sma20 + sma60) / 4,
         # 价格偏离度：价格相对多周期综合成本的位置
         bbi_dev = close / bbi - 1,
         # 综合线斜率：五日跨度上的相对变化
         bbi_slope = (bbi - dplyr::lag(bbi, 5)) / dplyr::lag(bbi, 5),
         # 排列一致性：四条均线相对五日前是否上行，取值 0 至 4
         bbi_align = (sma5  > dplyr::lag(sma5, 5)) +
                     (sma10 > dplyr::lag(sma10, 5)) +
                     (sma20 > dplyr::lag(sma20, 5)) +
                     (sma60 > dplyr::lag(sma60, 5)),
         # 综合与单周期之差：综合线相对 20 日均线的偏移
         bbi_sma_diff = bbi / sma20 - 1) |>
  ungroup()

# 展示四个特征的取值形状，前 60 个交易日为均线预热期，用 na.omit 略去
panel |>
  select(date, code, bbi_dev, bbi_slope, bbi_align, bbi_sma_diff) |>
  na.omit() |>
  head()

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
panel <- panel |>
  group_by(code) |>
  mutate(sma5  = TTR::SMA(close, 5),
         sma10 = TTR::SMA(close, 10),
         sma20 = TTR::SMA(close, 20),
         sma60 = TTR::SMA(close, 60),
         bbi = (sma5 + sma10 + sma20 + sma60) / 4,
         bbi_dev = close / bbi - 1,
         # 四条均线相对五日前是否上行，取值 0 至 4
         bbi_align = (sma5  > dplyr::lag(sma5, 5)) +
                     (sma10 > dplyr::lag(sma10, 5)) +
                     (sma20 > dplyr::lag(sma20, 5)) +
                     (sma60 > dplyr::lag(sma60, 5)),
         sma20_dev = close / sma20 - 1) |>
  ungroup()

for (h in c("forward_1", "forward_5")) {
  cat("\n--- BBI 偏离度 vs", h, "---\n")
  print(ic_summary(cross_section_ic(panel, "bbi_dev", h)))
}

print(layered_returns(panel, "bbi_dev", "forward_5"))

print(ic_summary(cross_section_ic(panel, "bbi_align", "forward_5")))

# 与单条 20 日均线偏离度对照，判断多周期是否带来增量
print(ic_summary(cross_section_ic(panel, "sma20_dev", "forward_5")))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df <- panel |> filter(code == "600519.SS")

cat("--- 信号触发日检验（偏离度高于 80 分位）---\n")
print(timing_signal_test(df, "bbi_dev", "forward_5", upper = 0.8))

cat("\n--- 条件分位收益（偏离度分五档）---\n")
print(conditional_quantile_return(df, "bbi_dev", "forward_5", q = 5))

cat("\n--- 择时策略与买入持有对照 ---\n")
print(timing_backtest(df, "bbi_dev", "forward_5", entry_q = 0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
panel <- panel |>
  group_by(code) |>
  mutate(vol_ratio = volume / zoo::rollmean(volume, 20, fill = NA, align = "right")) |>
  ungroup()

# 先看两个特征的横截面相关
panel |> group_by(date) |>
  summarise(rho = cor(bbi_dev, vol_ratio, "spearman", use = "complete.obs"),
            .groups = "drop") |>
  summarise(平均相关 = round(mean(rho, na.rm = TRUE), 3)) |> print()

panel <- combined_signal(panel, c("bbi_dev", "vol_ratio"))

cat("\n--- 组合 vs 单特征 ---\n")
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "bbi_dev", "forward_5")))
print(ic_summary(cross_section_ic(panel, "vol_ratio", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(cond = as.integer(bbi_dev > 0 & bbi_align == 4))

print(timing_backtest(df, "cond", "forward_5", entry_q = 0.5))
