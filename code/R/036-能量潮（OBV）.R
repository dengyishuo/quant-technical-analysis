# ============================================================
# 第036章 能量潮（OBV）
# 模块 06 量价类指标
# 源文件：模块06-量价类指标/第036章-能量潮（OBV）.md
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

# 3. 计算指标：OBV 及其 30 日均线
obv_value <- OBV(close_price, volume)
obv_ma30  <- SMA(obv_value, n = 30)

# 4. 识别信号：OBV 上穿其均线视为资金流入增强
cross_up   <- crossover(obv_value, obv_ma30)
cross_down <- crossover(obv_ma30, obv_value)
cat("OBV 上穿均线次数：", sum(cross_up, na.rm = TRUE), "\n")
cat("OBV 下穿均线次数：", sum(cross_down, na.rm = TRUE), "\n")

# 5. 绘图
chartSeries(data, theme = "white", name = "贵州茅台",
  TA = "addOBV()")

# 6. 输出统计：OBV 与价格的同向率
price_up <- diff(close_price) > 0
obv_up   <- diff(obv_value) > 0
agree <- sum(price_up == obv_up, na.rm = TRUE) / sum(!is.na(obv_up))
cat("价格与 OBV 同向比例：", round(agree, 3), "\n")

# ---- 代码块 2：拆解 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
library(dplyr)

# panel 已含 date / code / close / volume / forward_1 / forward_5
panel <- panel |>
  group_by(code) |>
  arrange(date, .by_group = TRUE) |>
  mutate(
    obv = as.numeric(TTR::OBV(close, volume)),
    # 累积量本身只作记录，不进入横截面排序
    obv_level = obv,
    # k 日变化率：分母取绝对值，并设下限防止接近零时放大
    obv_lag = dplyr::lag(obv, 10),
    obv_chg = (obv - obv_lag) / pmax(abs(obv_lag), 1e-8),
    # 相对自身 20 日均线的偏离
    obv_ma20 = zoo::rollmean(obv, 20, fill = NA, align = "right"),
    obv_dev = obv / obv_ma20 - 1,
    # 量价背离：20 日价格新高但 OBV 未创新高
    px_hi = as.integer(close >= zoo::rollmax(close, 20, fill = NA, align = "right")),
    obv_hi = as.integer(obv >= zoo::rollmax(obv, 20, fill = NA, align = "right")),
    diverge = as.integer(px_hi == 1 & obv_hi == 0)
  ) |>
  ungroup()

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# 变化率因子：一日与五日两个前向窗口对照
for (h in c("forward_1", "forward_5")) {
  cat("\n--- OBV 变化率 vs", h, "---\n")
  print(ic_summary(cross_section_ic(panel, "obv_chg", h)))
}

print(layered_returns(panel, "obv_chg", "forward_5"))

# 缩尾后再算一次，观察极端读数对结论的影响
panel <- panel |>
  group_by(date) |>
  mutate(obv_chg_w = pmin(pmax(obv_chg,
                               quantile(obv_chg, 0.01, na.rm = TRUE)),
                          quantile(obv_chg, 0.99, na.rm = TRUE))) |>
  ungroup()

cat("\n--- 缩尾后 ---\n")
print(ic_summary(cross_section_ic(panel, "obv_chg_w", "forward_5")))

# 与成交量水平的相关：检查因子是否只是在排序流动性
panel |>
  group_by(date) |>
  # 预热期缺失，先剔除
  filter(!is.na(obv_chg_w)) |>
  summarise(rho = cor(obv_chg_w, log(volume), method = "spearman",
                      use = "complete.obs"), .groups = "drop") |>
  summarise(平均相关 = round(mean(rho, na.rm = TRUE), 3)) |>
  print()

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df <- panel |> filter(code == "600519.SS") |> arrange(date)

cat("--- 信号触发日检验（变化率高于 80 分位）---\n")
print(timing_signal_test(df, "obv_chg_w", "forward_5", upper = 0.8))

cat("\n--- 条件分位收益（变化率分五档）---\n")
print(conditional_quantile_return(df, "obv_chg_w", "forward_5", q = 5))

cat("\n--- 择时策略与买入持有对照 ---\n")
print(timing_backtest(df, "obv_chg_w", "forward_5", entry_q = 0.7))

# 背离是稀疏事件，先看频次与两组均值，再决定是否值得做检验
df |>
  group_by(diverge) |>
  summarise(样本数 = n(),
            平均未来五日收益 = round(mean(forward_5, na.rm = TRUE), 4),
            .groups = "drop") |>
  print()

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
# 先看两个特征的横截面相关，再决定是否值得组合
panel <- panel |>
  group_by(code) |>
  mutate(vol_ratio = volume / zoo::rollmean(volume, 20, fill = NA, align = "right")) |>
  ungroup()

panel |>
  group_by(date) |>
  filter(!is.na(obv_chg_w), !is.na(vol_ratio)) |>
  summarise(rho = cor(obv_chg_w, vol_ratio, method = "spearman",
                      use = "complete.obs"), .groups = "drop") |>
  summarise(平均相关 = round(mean(rho, na.rm = TRUE), 3)) |>
  print()

panel <- combined_signal(panel, c("obv_chg_w", "vol_ratio"))

cat("\n--- 组合 vs 单特征 ---\n")
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "obv_chg_w", "forward_5")))
print(ic_summary(cross_section_ic(panel, "vol_ratio", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
df2 <- panel |>
  filter(code == "600519.SS") |>
  arrange(date) |>
  mutate(sma20 = as.numeric(TTR::SMA(close, 20)),
         cond = as.integer(obv_chg_w > 0 & close > sma20))

print(timing_backtest(df2, "cond", "forward_5", entry_q = 0.5))
