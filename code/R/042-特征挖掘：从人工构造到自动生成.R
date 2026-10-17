# ============================================================
# 第042章 特征挖掘：从人工构造到自动生成
# 模块 08 机器学习挖掘与融合
# 源文件：模块08-机器学习挖掘与融合/第042章-特征挖掘：从人工构造到自动生成.md
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

# 先验筛选：剔除经济含义不成立或引入未来信息的候选
screen_by_prior <- function(cols) {
  banned <- c("_diff_diff", "_logret_logret")   # 二阶差分等视为无经济含义
  keep <- rep(TRUE, length(cols))
  for (k in banned) keep <- keep & !grepl(k, cols, fixed = TRUE)
  cols[keep]
}

# 统计筛选：覆盖率、方差、相关性聚类
screen_by_stats <- function(zoo, cols, cov_thr = 0.8, var_thr = 1e-8, corr_thr = 0.9) {
  keep <- cols[colMeans(!is.na(zoo[, cols, drop = FALSE])) >= cov_thr]
  var_ok <- vapply(keep, function(c) {
    x <- zoo[[c]]
    v <- var(x, na.rm = TRUE)
    is.finite(v) && v > var_thr && length(unique(stats::na.omit(x))) > 2
  }, logical(1))
  keep <- keep[var_ok]
  if (length(keep) < 2) return(keep)

  corr <- abs(cor(zoo[, keep, drop = FALSE],
                  use = "pairwise.complete.obs", method = "spearman"))
  corr[is.na(corr)] <- 0
  # 平均连接聚类，把秩相关超过阈值的特征聚成一类
  hc <- stats::hclust(stats::as.dist(1 - corr), method = "average")
  lab <- stats::cutree(hc, h = 1 - corr_thr)

  # 每类里保留方差最大的一个作为代表
  v <- vapply(keep, function(c) var(zoo[[c]], na.rm = TRUE), numeric(1))
  names(v) <- keep
  unname(vapply(split(keep, lab), function(g) g[which.max(v[g])], character(1)))
}

# ---- 代码块 2：代码实现 ----

# 提示：此处用 5 只标的演示流程。真实建模请改用 data/parquet/panel.parquet
# （287 只、2021-06 起），并补足十年区间与行业中性化
library(ranger)
library(dplyr)

# 分块排列重要性：在时间块之间置换，保留块内时序结构
block_permutation_importance <- function(fit, data, features, target,
                                         block = 20, n_repeat = 5, seed = 0) {
  set.seed(seed)
  base <- -mean((predict(fit, data = data)$predictions - data[[target]])^2)
  idx <- seq_len(nrow(data))
  blocks <- split(idx, ceiling(idx / block))
  out <- numeric(length(features))
  for (j in seq_along(features)) {
    drops <- numeric(n_repeat)
    for (r in seq_len(n_repeat)) {
      ord <- sample(length(blocks))
      new_idx <- unlist(blocks[ord], use.names = FALSE)
      d <- data
      d[[features[j]]] <- d[[features[j]]][new_idx]
      p <- predict(fit, data = d)$predictions
      drops[r] <- base - (-mean((p - data[[target]])^2))
    }
    out[j] <- mean(drops)
  }
  names(out) <- features
  sort(out, decreasing = TRUE)
}

# 按时间切分训练，输出 gain 重要性与分块排列重要性
train_and_rank <- function(panel, feature_cols, target_col, split_date) {
  tr <- panel[panel$date <  split_date, ]
  va <- panel[panel$date >= split_date, ]
  form <- stats::as.formula(paste(target_col, "~", paste(feature_cols, collapse = " + ")))
  fit <- ranger(form, data = tr, num.trees = 500, mtry = 10,
                min.node.size = 200, importance = "impurity")
  gain <- sort(fit$variable.importance, decreasing = TRUE)
  perm <- block_permutation_importance(fit, va, feature_cols, target_col)
  list(gain = gain, perm = perm)
}

# ---- 代码块 3：代码实现 ----

# 沿用本节 R 部分定义的算子与 build_zoo
library(quantmod)
library(dplyr)

codes <- c("600519.SS", "600036.SS", "601318.SS", "300750.SZ", "000858.SZ")

frames <- lapply(codes, function(cd) {
  x <- local({
    # 从本地 CSV 取该标的，转成 quantmod 可用的 xts
    .p <- read.csv("data/parquet/panel_blue_chip.csv", stringsAsFactors = FALSE)
    .p <- .p[.p$code == cd, ]
    .x <- xts::xts(.p[, c("open", "high", "low", "close", "volume", "adjusted")],
                       order.by = as.Date(.p$date))
    colnames(.x) <- c("Open", "High", "Low", "Close", "Volume", "Adjusted")
    .x
  })
  d <- data.frame(
    date   = index(x),
    open   = as.numeric(Op(x)),
    high   = as.numeric(Hi(x)),
    low    = as.numeric(Lo(x)),
    close  = as.numeric(Cl(x)),
    volume = as.numeric(Vo(x)),
    code   = cd
  )
  d$forward_5 <- d$close / dplyr::lead(d$close, 5) - 1
  d
})
panel <- bind_rows(frames)
base_cols <- c("open", "high", "low", "close", "volume", "adjusted")

# 逐标的生成特征库，避免跨标的时间错位
zoo_list <- lapply(codes, function(cd) {
  g <- panel[panel$code == cd, ]
  z <- build_zoo(g, base_cols)
  z$code <- cd
  z
})

# ---- 代码块 4：代码实现 ----

# 提示：此处用 5 只标的演示流程。真实建模请改用 data/parquet/panel.parquet
# （287 只、2021-06 起），并补足十年区间与行业中性化
zoo <- bind_rows(zoo_list)
cand <- setdiff(colnames(zoo), "code")

cand <- screen_by_prior(cand)                               # 第一层：先验筛选
cand <- screen_by_stats(zoo[, cand, drop = FALSE], cand)    # 第二层：统计筛选

# 把特征库与标签并在一个面板里（行序与 panel 一致）
full <- cbind(zoo[, c(cand, "code"), drop = FALSE], panel[, c("date", "forward_5")])
full <- full[stats::complete.cases(full), ]

# 第三层：模型驱动筛选
ranked <- train_and_rank(full, cand, "forward_5", split_date = as.Date("2024-09-01"))
top <- head(names(ranked$gain), 15)

# 并列展示 gain 重要性与分块排列重要性
imp <- data.frame(gain = ranked$gain[top],
                  perm = ifelse(is.na(ranked$perm[top]), 0, ranked$perm[top]))
barplot(t(as.matrix(imp)), beside = TRUE, names.arg = top, las = 2, cex.names = 0.7,
        col = c("steelblue", "gray70"),
        legend.text = c("gain 重要性", "分块排列重要性"),
        main = "两套特征重要性对照（示意）", ylab = "重要性")

# ---- 代码块 5：代码实现 ----

library(dplyr)
library(xts)
library(TTR)
library(ranger)

WINDOWS <- c(5, 10, 20, 60)

# 变化类算子
ops_change <- function(s, nm) {
  lag1 <- stats::lag(s, 1)
  data.frame(
    diff    = s - lag1,
    ret     = s / lag1 - 1,
    logret  = log(pmax(s, 1e-9)) - log(pmax(lag1, 1e-9))
  ) |> setNames(paste0(nm, "_", c("diff", "ret", "logret")))
}

# 滚动统计类算子
ops_rolling <- function(s, nm) {
  res <- lapply(WINDOWS, function(w) {
    ma <- runMean(s, w)
    sdv <- runSD(s, w)
    data.frame(dev = s / ma - 1, std = sdv) |>
      setNames(paste0(nm, "_", c(paste0("ma", w, "_dev"), paste0("std", w))))
  })
  do.call(cbind, res)
}

# 两层生成
build_zoo <- function(df, base_cols) {
  layer1 <- lapply(base_cols, function(c) {
    s <- xts::xts(df[[c]], order.by = df$date)
    cbind(ops_change(s, c), ops_rolling(s, c))
  })
  zoo <- do.call(cbind, layer1)
  # 二层：对一层输出再做变化类算子
  layer2 <- lapply(colnames(zoo), function(c) {
    ops_change(zoo[, c], paste0("L2_", c))
  })
  cbind(zoo, do.call(cbind, layer2))
}

# 统计筛选：覆盖率与方差
screen_by_stats <- function(zoo, cov_thr = 0.8, var_thr = 1e-8) {
  cov <- colMeans(!is.na(zoo))
  v <- apply(zoo, 2, function(x) var(x, na.rm = TRUE))
  colnames(zoo)[cov >= cov_thr & v > var_thr]
}

# 模型驱动：ranger 的变量重要性（impurity 口径）
train_and_rank <- function(panel, feature_cols, target_col) {
  form <- as.formula(paste(target_col, "~", paste(feature_cols, collapse = "+")))
  fit <- ranger(form, data = panel, num.trees = 500, mtry = 10,
                min.node.size = 100, importance = "impurity")
  sort(fit$variable.importance, decreasing = TRUE) |> head(20)
}
