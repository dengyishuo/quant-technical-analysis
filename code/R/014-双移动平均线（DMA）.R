# ============================================================
# 第014章 双移动平均线（DMA）
# 模块 03 趋势类指标
# 源文件：模块03-趋势类指标/第014章-双移动平均线（DMA）.md
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

# 3. 计算 DMA：短期均线减长期均线
dma_line <- SMA(close_price, n = 10)
ama_line <- SMA(close_price, n = 50)
dma_diff <- dma_line - ama_line

# 4. 识别信号：差值线穿越零轴
cross_up   <- dma_diff > 0 & Lag(dma_diff) <= 0
cross_down <- dma_diff < 0 & Lag(dma_diff) >= 0
cat("差值上穿零轴次数：", sum(cross_up, na.rm = TRUE), "\n")
cat("差值下穿零轴次数：", sum(cross_down, na.rm = TRUE), "\n")

# 5. 绘图：主图叠加两条均线，副图为差值线
chartSeries(data, theme = "white", name = "贵州茅台",
  TA = "addSMA(n = 10, col = 'blue'); addSMA(n = 50, col = 'red');
        addTA(dma_diff, col = 'darkorange')")

# 6. 输出统计：差值为正的天数占比
pos_ratio <- sum(dma_diff > 0, na.rm = TRUE) / sum(!is.na(dma_diff))
cat("差值为正的天数占比：", round(pos_ratio, 3), "\n")

# ---- 代码块 2：拆解 ----

# 沿用第 007 章口径，拆解四个特征
panel <- panel |>
  group_by(code) |>
  mutate(sma10 = TTR::SMA(close, 10),
         sma50 = TTR::SMA(close, 50),
         dma_abs = sma10 - sma50,
         dma_rel = sma10 / sma50 - 1,
         dma_slope = (dma_abs - dplyr::lag(dma_abs, 5)) / sma50,
         dma_pct = zoo::rollapplyr(dma_abs, 250,
                                   function(x) mean(x <= x[length(x)]), fill = NA)) |>
  ungroup()

panel |> select(dma_abs, dma_rel, dma_slope, dma_pct) |>
  cor(use = "complete.obs", method = "spearman") |> print()

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
panel <- panel |>
  group_by(code) |>
  mutate(dma_norm = (TTR::SMA(close, 10) - TTR::SMA(close, 50)) / close) |>
  ungroup()

for (f in c("dma_rel", "dma_norm", "dma_pct")) {
  cat("\n---", f, "---\n")
  print(ic_summary(cross_section_ic(panel, f, "forward_5")))
}

print(layered_returns(panel, "dma_rel", "forward_5"))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df <- panel |> filter(code == "600519.SS")

print(timing_signal_test(df, "dma_rel", "forward_5", upper = 0.8))
print(conditional_quantile_return(df, "dma_rel", "forward_5", q = 5))
print(timing_backtest(df, "dma_rel", "forward_5", entry_q = 0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
panel <- panel |>
  group_by(date) |>
  mutate(vol_ratio = volume / zoo::rollmean(volume, 20, fill = NA, align = "right")) |>
  ungroup()

# 负面对照：与 MACD 差离值的相关
panel <- panel |>
  group_by(code) |>
  mutate(dif = TTR::EMA(close, 12) / TTR::EMA(close, 26) - 1) |>
  ungroup()

rho <- panel |> group_by(date) |>
  summarise(r = cor(dma_rel, dif, method = "spearman", use = "complete.obs"))
cat("DMA 与 DIF 的平均相关：", round(mean(rho$r, na.rm = TRUE), 3), "\n")

panel <- combined_signal(panel, c("dma_rel", "vol_ratio"))
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "dma_rel", "forward_5")))
print(ic_summary(cross_section_ic(panel, "vol_ratio", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
df <- panel |>
  filter(code == "600519.SS") |>
  mutate(sma10 = as.numeric(TTR::SMA(close, 10)),
         sma50 = as.numeric(TTR::SMA(close, 50)),
         dma_abs = sma10 - sma50,
         dma_rel = sma10 / sma50 - 1,
         # 差值斜率：五期变化除以长期均线，无量纲
         dma_slope = (dma_abs - dplyr::lag(dma_abs, 5)) / sma50,
         # 组合条件：差值为正且差值仍在扩大
         cond = as.integer(dma_rel > 0 & dma_slope > 0))

cat("--- 组合条件 ---\n")
print(timing_backtest(df, "cond", "forward_5", entry_q = 0.5))

# 单条件对照
df <- df |>
  mutate(cond_rel = as.integer(dma_rel > 0),
         cond_slope = as.integer(dma_slope > 0))

cat("\n--- 仅相对差值 ---\n")
print(timing_backtest(df, "cond_rel", "forward_5", entry_q = 0.5))

cat("\n--- 仅差值斜率 ---\n")
print(timing_backtest(df, "cond_slope", "forward_5", entry_q = 0.5))
