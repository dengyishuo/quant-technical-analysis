# ============================================================
# 第038章 成交量震荡器（VO）
# 模块 06 量价类指标
# 源文件：模块06-量价类指标/第038章-成交量震荡器（VO）.md
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
volume <- Vo(data)

# 3. 计算指标：TTR 的 VO 默认 n = 10 与 20，percent = TRUE 返回比值型
vo_pct <- VO(volume, n = c(10, 20), percent = TRUE)
vo_abs <- VO(volume, n = c(10, 20), percent = FALSE)

# 4. 识别信号：比值型 VO 穿越零轴与阈值
cross_zero_up <- crossover(vo_pct, 0)
cross_zero_dn <- crossover(0, vo_pct)
cat("VO 上穿零轴次数：", sum(cross_zero_up, na.rm = TRUE), "\n")
cat("VO 下穿零轴次数：", sum(cross_zero_dn, na.rm = TRUE), "\n")
cat("VO 高于 30% 的天数：", sum(vo_pct > 30, na.rm = TRUE), "\n")

# 5. 绘图
chartSeries(data, theme = "white", name = "贵州茅台",
  TA = "addVo(); addTA(VO(Vo(.), n = c(10, 20)))")

# 6. 输出统计：VO 的分布与量价配合比例
cat("VO 均值：", round(mean(vo_pct, na.rm = TRUE), 2), "\n")
cat("VO 标准差：", round(sd(vo_pct, na.rm = TRUE), 2), "\n")
price_up <- diff(Cl(data)) > 0
vo_up <- diff(vo_pct) > 0
agree <- sum(price_up == vo_up, na.rm = TRUE) / sum(!is.na(vo_up))
cat("价格与 VO 同向比例：", round(agree, 3), "\n")

# ---- 代码块 2：拆解 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
library(dplyr)

# panel 已含 date / code / close / volume / forward_1 / forward_5
# 比值型 VO 按本章公式手写：(SMA10 - SMA20) / SMA20，输出为小数
panel <- panel |>
  group_by(code) |>
  arrange(date, .by_group = TRUE) |>
  mutate(
    v_s = zoo::rollmean(volume, 10, fill = NA, align = "right"),
    v_l = zoo::rollmean(volume, 20, fill = NA, align = "right"),
    vo_ratio = (v_s - v_l) / v_l,
    vo_state = sign(vo_ratio),
    # 阈值取 0.5，对应正文的 50%
    vo_thr = as.integer(abs(vo_ratio) > 0.5),
    vo_chg = vo_ratio - dplyr::lag(vo_ratio, 5)
  ) |>
  ungroup()

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
for (h in c("forward_1", "forward_5")) {
  cat("\n--- VO 比值 vs", h, "---\n")
  print(ic_summary(cross_section_ic(panel, "vo_ratio", h)))
}

print(layered_returns(panel, "vo_ratio", "forward_5"))

# 缩尾：分母偏小的标的会给出极端读数
panel <- panel |>
  group_by(date) |>
  mutate(vo_w = pmin(pmax(vo_ratio, quantile(vo_ratio, 0.01, na.rm = TRUE)),
                     quantile(vo_ratio, 0.99, na.rm = TRUE))) |>
  ungroup()

cat("\n--- 缩尾后 ---\n")
print(ic_summary(cross_section_ic(panel, "vo_w", "forward_5")))

# 按成交额分位分组，检查是否只是市值暴露
panel |>
  group_by(date) |>
  mutate(size_grp = ntile(volume, 3)) |>
  ungroup() |>
  group_by(size_grp) |>
  group_modify(~ ic_summary(cross_section_ic(.x, "vo_w", "forward_5")) |> as.data.frame()) |>
  print()

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df <- panel |> filter(code == "600519.SS") |> arrange(date)

cat("--- 信号触发日检验（读数高于 80 分位）---\n")
print(timing_signal_test(df, "vo_w", "forward_5", upper = 0.8))

cat("\n--- 条件分位收益（读数分五档）---\n")
print(conditional_quantile_return(df, "vo_w", "forward_5", q = 5))

cat("\n--- 择时策略与买入持有对照 ---\n")
print(timing_backtest(df, "vo_w", "forward_5", entry_q = 0.7))

# 把价格方向作为前置条件，比较两组触发日的收益
df |>
  mutate(价涨 = as.integer(close > TTR::SMA(close, 20)),
         组合 = paste0("价", 价涨, "量", as.integer(vo_w > 0))) |>
  group_by(组合) |>
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
  filter(!is.na(vo_w), !is.na(mom20)) |>
  summarise(rho = cor(vo_w, mom20, method = "spearman",
                      use = "complete.obs"), .groups = "drop") |>
  summarise(平均相关 = round(mean(rho, na.rm = TRUE), 3)) |>
  print()

panel <- combined_signal(panel, c("vo_w", "mom20"))

cat("\n--- 组合 vs 单特征 ---\n")
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "vo_w", "forward_5")))
print(ic_summary(cross_section_ic(panel, "mom20", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
df2 <- panel |>
  filter(code == "600519.SS") |>
  arrange(date) |>
  mutate(sma20 = as.numeric(TTR::SMA(close, 20)),
         cond = as.integer(vo_w > 0 & close > sma20))

print(timing_backtest(df2, "cond", "forward_5", entry_q = 0.5))
