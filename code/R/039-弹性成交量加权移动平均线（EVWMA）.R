# ============================================================
# 第039章 弹性成交量加权移动平均线（EVWMA）
# 模块 06 量价类指标
# 源文件：模块06-量价类指标/第039章-弹性成交量加权移动平均线（EVWMA）.md
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
volume <- Vo(data)

# 3. 计算指标：手写 EVWMA 递推（n 为成交量窗口天数）
my_evwma <- function(price, volume, n = 20) {
  p <- as.numeric(price); v <- as.numeric(volume)
  N <- length(p)
  out <- rep(NA_real_, N)
  if (N < n) return(xts::xts(out, order.by = index(price)))
  # 初值：前 n 日的成交量加权平均价
  w <- sum(v[1:n])
  out[n] <- sum(p[1:n] * v[1:n]) / w
  # 递推：当日权重为 v[t] / W[t]
  for (t in (n + 1):N) {
    w <- w - v[t - n] + v[t]
    out[t] <- (v[t] * p[t] + out[t - 1] * (w - v[t])) / w
  }
  xts::xts(out, order.by = index(price))
}

evwma20 <- my_evwma(close_price, volume, n = 20)
ema20   <- EMA(close_price, n = 20)

# 4. 识别信号：EVWMA 上穿 EMA 视为量能推动转强
cross_up   <- crossover(evwma20, ema20)
cross_down <- crossover(ema20, evwma20)
cat("EVWMA 上穿 EMA 次数：", sum(cross_up, na.rm = TRUE), "\n")
cat("EVWMA 下穿 EMA 次数：", sum(cross_down, na.rm = TRUE), "\n")

# 5. 绘图
chartSeries(data, theme = "white", name = "贵州茅台",
  TA = "addTA(EVWMA(Cl(.), Vo(.), n = 20), col = 'blue');
        addTA(EMA(Cl(.), n = 20), col = 'red')")

# 6. 输出统计：价格位于 EVWMA 上方的比例
above <- sum(close_price > evwma20, na.rm = TRUE) / sum(!is.na(evwma20))
cat("价格位于 EVWMA20 上方的比例：", round(above, 3), "\n")

# ---- 代码块 2：拆解 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
library(dplyr)

# EVWMA 递推：当日权重为 v_t / W_t，W_t 为 n 日成交量之和
evwma_calc <- function(p, v, n = 20) {
  p <- as.numeric(p); v <- as.numeric(v)
  N <- length(p); out <- rep(NA_real_, N)
  if (N < n) return(out)
  w <- sum(v[1:n])
  out[n] <- sum(p[1:n] * v[1:n]) / w
  for (t in (n + 1):N) {
    w <- w - v[t - n] + v[t]
    out[t] <- (v[t] * p[t] + out[t - 1] * (w - v[t])) / w
  }
  out
}

# panel 已含 date / code / close / volume / forward_1 / forward_5
panel <- panel |>
  group_by(code) |>
  arrange(date, .by_group = TRUE) |>
  mutate(
    evwma20 = evwma_calc(close, volume, 20),
    sma20 = zoo::rollmean(close, 20, fill = NA, align = "right"),
    evwma_dev = close / evwma20 - 1,
    # 成交集中度：量价加权均线相对等权均线的位移
    conc = evwma20 / sma20 - 1,
    conc_abs = abs(conc),
    # 当日成交占 20 日成交量之和的比例
    w_now = volume / zoo::rollsum(volume, 20, fill = NA, align = "right"),
    evwma_slope = evwma20 / dplyr::lag(evwma20, 10) - 1
  ) |>
  ungroup()

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# 集中度与偏离度并列检验
for (f in c("conc", "evwma_dev")) {
  cat("\n---", f, "vs forward_5 ---\n")
  print(ic_summary(cross_section_ic(panel, f, "forward_5")))
}

print(layered_returns(panel, "conc", "forward_5"))

# 集中度的绝对值版本：只保留集中程度，剥掉方向
cat("\n--- 集中度绝对值 ---\n")
print(ic_summary(cross_section_ic(panel, "conc_abs", "forward_5")))

# 对偏离度取残差，看集中度是否还有独立信息
panel <- panel |>
  group_by(date) |>
  mutate(conc_resid = {
    ok <- !is.na(conc) & !is.na(evwma_dev)
    r <- rep(NA_real_, dplyr::n())
    if (sum(ok) >= 10) r[ok] <- residuals(lm(conc[ok] ~ evwma_dev[ok]))
    r
  }) |>
  ungroup()

cat("\n--- 剔除偏离度后的残差 ---\n")
print(ic_summary(cross_section_ic(panel, "conc_resid", "forward_5")))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df <- panel |> filter(code == "600519.SS") |> arrange(date)

cat("--- 信号触发日检验（偏离度高于 80 分位）---\n")
print(timing_signal_test(df, "evwma_dev", "forward_5", upper = 0.8))

cat("\n--- 条件分位收益（偏离度分五档）---\n")
print(conditional_quantile_return(df, "evwma_dev", "forward_5", q = 5))

cat("\n--- 择时策略与买入持有对照 ---\n")
print(timing_backtest(df, "evwma_dev", "forward_5", entry_q = 0.7))

# 集中度极值日的后续收益，与其余交易日对照
df |>
  mutate(集中 = as.integer(conc_abs > quantile(conc_abs, 0.9, na.rm = TRUE))) |>
  group_by(集中) |>
  summarise(样本数 = n(),
            平均未来五日收益 = round(mean(forward_5, na.rm = TRUE), 4),
            .groups = "drop") |>
  print()

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
panel <- panel |>
  group_by(code) |>
  mutate(mom20 = close / dplyr::lag(close, 20) - 1) |>
  ungroup()

panel |>
  group_by(date) |>
  filter(!is.na(conc), !is.na(mom20)) |>
  summarise(rho = cor(conc, mom20, method = "spearman",
                      use = "complete.obs"), .groups = "drop") |>
  summarise(平均相关 = round(mean(rho, na.rm = TRUE), 3)) |>
  print()

panel <- combined_signal(panel, c("conc", "mom20"))

cat("\n--- 组合 vs 单特征 ---\n")
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "conc", "forward_5")))
print(ic_summary(cross_section_ic(panel, "mom20", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
df2 <- panel |>
  filter(code == "600519.SS") |>
  arrange(date) |>
  mutate(ema20 = as.numeric(TTR::EMA(close, 20)),
         cond = as.integer(evwma20 > ema20 & close > evwma20))

print(timing_backtest(df2, "cond", "forward_5", entry_q = 0.5))
