# ============================================================
# 第007章 定义的 R 公共函数（IC 汇总 / 分层回测 / 择时检验 / 组合合成）
#
# 本文件由 scripts/extract_code.py 自动生成，请勿直接编辑。
# 修改代码请改 Markdown 源稿（模块02-因子检验方法/第007章），再重新运行提取脚本。
# ============================================================
library(dplyr)

# 横截面 IC 序列
# 返回值是数值向量，names 为日期，便于直接交给 ic_summary 与绘图
cross_section_ic <- function(panel, factor_col, ret_col) {
  ic <- panel |>
    group_by(date) |>
    filter(!is.na(.data[[factor_col]]), !is.na(.data[[ret_col]])) |>
    summarise(
      ic = if (n() >= 5) cor(.data[[factor_col]], .data[[ret_col]],
                             method = "spearman") else NA_real_,
      .groups = "drop"
    ) |>
    filter(!is.na(ic))
  out <- as.numeric(ic$ic)
  names(out) <- as.character(ic$date)
  out
}

# IC 汇总
ic_summary <- function(ic) {
  ic <- as.numeric(ic)
  m <- mean(ic); s <- sd(ic)
  data.frame(
    IC均值 = round(m, 4),
    IC标准差 = round(s, 4),
    ICIR = round(m / s, 3),
    t统计量 = round(m / s * sqrt(length(ic)), 2),
    IC大于零比例 = round(mean(ic > 0), 3),
    样本期数 = length(ic)
  )
}

# 分层回测
layered_returns <- function(panel, factor_col, ret_col, q = 5) {
  res <- panel |>
    group_by(date) |>
    filter(!is.na(.data[[factor_col]]), !is.na(.data[[ret_col]])) |>
    mutate(group = ntile(.data[[factor_col]], q)) |>
    group_by(date, group) |>
    summarise(r = mean(.data[[ret_col]]), .groups = "drop") |>
    tidyr::pivot_wider(names_from = group, values_from = r)
  mat <- as.data.frame(res)[, -1, drop = FALSE]
  group_mean <- colMeans(mat, na.rm = TRUE)
  list(组均收益 = round(group_mean, 6),
       单调性 = round(cor(as.numeric(names(group_mean)), group_mean,
                        method = "spearman"), 3))
}

# 择时：信号触发日检验
timing_signal_test <- function(df, factor_col, ret_col, upper = 0.8) {
  f <- df[[factor_col]]
  r <- df[[ret_col]]
  ok <- !is.na(f) & !is.na(r)
  f <- f[ok]; r <- r[ok]
  thr <- quantile(f, upper, na.rm = TRUE)
  trig <- r[f >= thr]
  rest <- r[f <  thr]
  # 两组样本都足够时才做检验，否则返回 NA 以免中断
  if (length(trig) < 3 || length(rest) < 3) {
    return(data.frame(触发日数 = length(trig),
                      触发日平均收益 = NA_real_,
                      非触发日平均收益 = round(mean(rest) * 100, 3),
                      t统计量 = NA_real_, p值 = NA_real_))
  }
  tt <- t.test(trig, rest)
  data.frame(触发日数 = length(trig),
             触发日平均收益 = round(mean(trig) * 100, 3),
             非触发日平均收益 = round(mean(rest) * 100, 3),
             t统计量 = round(unname(tt$statistic), 2),
             p值 = round(tt$p.value, 4))
}

# 择时：条件分位收益
conditional_quantile_return <- function(df, factor_col, ret_col, q = 5) {
  df |>
    filter(!is.na(.data[[factor_col]]), !is.na(.data[[ret_col]])) |>
    mutate(bucket = ntile(.data[[factor_col]], q)) |>
    group_by(bucket) |>
    summarise(mean = round(mean(.data[[ret_col]]), 4),
              count = n(),
              .groups = "drop")
}

# 择时策略回测
timing_backtest <- function(df, factor_col, ret_col, entry_q = 0.7) {
  f <- df[[factor_col]]
  r <- df[[ret_col]]
  ok <- !is.na(f) & !is.na(r)
  f <- f[ok]; r <- r[ok]
  thr <- quantile(f, entry_q)
  # 信号在当日收盘产生，次日持仓，因此仓位滞后一期
  pos <- dplyr::lag(ifelse(f > thr, 1, 0), 1)
  stat <- function(x) {
    x <- x[!is.na(x)]
    if (length(x) < 2 || sd(x) == 0) {
      return(c(年化收益 = NA_real_, 夏普 = NA_real_, 最大回撤 = NA_real_))
    }
    cum <- cumprod(1 + x)
    c(年化收益 = round(prod(1 + x)^(252 / length(x)) - 1, 4),
      夏普 = round(mean(x) / sd(x) * sqrt(252), 2),
      最大回撤 = round(min(cum / cummax(cum) - 1), 4))
  }
  data.frame(策略 = stat(pos * r),
             买入持有 = stat(r))
}

# 加权型组合：先横截面标准化，再等权或指定权重相加
combined_signal <- function(panel, factor_cols, weights = NULL) {
  z_cols <- paste0(factor_cols, "_z")
  out <- panel |>
    group_by(date) |>
    mutate(across(all_of(factor_cols), function(x) {
      # constant = 1 取裸中位绝对差，与 Python 侧保持一致
      # （R 的 mad() 默认 constant = 1.4826，会放大 1.4826 倍）
      m <- mad(x, na.rm = TRUE, constant = 1)
      if (isTRUE(m > 0)) (x - median(x, na.rm = TRUE)) / m else 0
    }, .names = "{.col}_z")) |>
    ungroup()
  w <- if (is.null(weights)) rep(1 / length(z_cols), length(z_cols)) else weights
  stopifnot(length(w) == length(z_cols))
  out$combined <- as.matrix(out[, z_cols]) %*% w
  out
}
