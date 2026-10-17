# ============================================================
# 第048章 端到端案例：从指标到可交易信号
# 模块 08 机器学习挖掘与融合
# 源文件：模块08-机器学习挖掘与融合/第048章-端到端案例：从指标到可交易信号.md
# ============================================================
# 本文件由 scripts/extract_code.py 自动生成，请勿直接编辑。
# 修改代码请改 Markdown 源稿，再重新运行提取脚本。
#
# 依赖：先加载同目录下的公共函数与数据准备
#   source("code/R/00-common.R")
#   source("code/R/00-data.R")
#
# ------------------------------------------------------------

# ---- 代码块 1：第一步：特征构建 ----

# 面板特征构建：8 个跨类别指标，全部用滚动窗口，只依赖当日及之前
library(quantmod)
library(dplyr)
library(TTR)

CODES <- c("600519.SS", "600036.SS", "601318.SS", "300750.SZ", "000858.SZ")

build_features <- function(code) {
  raw <- local({
    # 从本地 CSV 取该标的，转成 quantmod 可用的 xts
    .p <- read.csv("data/parquet/panel_blue_chip.csv", stringsAsFactors = FALSE)
    .p <- .p[.p$code == code, ]
    .x <- xts::xts(.p[, c("open", "high", "low", "close", "volume", "adjusted")],
                       order.by = as.Date(.p$date))
    colnames(.x) <- c("Open", "High", "Low", "Close", "Volume", "Adjusted")
    .x
  })
  d <- data.frame(date = index(raw), close = as.numeric(Cl(raw)),
                  high = as.numeric(Hi(raw)), low = as.numeric(Lo(raw)),
                  volume = as.numeric(Vo(raw)), code = code)
  sma20 <- zoo::rollmean(d$close, 20, fill = NA, align = "right")
  sd20  <- zoo::rollapply(d$close, 20, sd, fill = NA, align = "right")
  hl    <- d[, c("high", "low", "close")]

  # 趋势：价格相对二十日均线的偏离度
  d$sma_dev  <- d$close / sma20 - 1
  # 趋势：MACD 柱状值归一
  macd <- TTR::MACD(d$close, 12, 26, 9)
  d$macd_bar <- macd[, "macd"] / d$close
  # 趋势：ADX 强度值
  d$adx <- TTR::ADX(hl, n = 14)[, "ADX"]
  # 震荡：RSI 相对中轴的偏离
  d$rsi_dev <- TTR::RSI(d$close, n = 14) - 50
  # 震荡：随机指标 K 减 D
  stoch <- TTR::stoch(hl, nFastK = 9, nFastD = 3, nSlowD = 3)
  d$kd_diff <- (stoch[, "fastK"] - stoch[, "slowD"]) / 100
  # 波动率：真实波幅占价格比率的历史分位（120 日窗口）
  d$atr_ratio <- TTR::ATR(hl, n = 14)[, "atr"] / d$close
  d$atr_rank <- zoo::rollapply(d$atr_ratio, 120,
                               function(x) mean(x[-length(x)] < x[length(x)]),
                               fill = NA, align = "right")
  # 波动率：布林带带宽
  d$bb_width <- (4 * sd20) / sma20
  # 量价：OBV 的十日变化率
  obv <- TTR::OBV(d$close, d$volume)
  d$obv_change <- (obv - dplyr::lag(obv, 10)) /
                  pmax(abs(dplyr::lag(obv, 10)), 1e-9)
  # 标签：未来五日收益
  d$forward_5 <- d$close / dplyr::lead(d$close, 5) - 1
  d
}

panel <- bind_rows(lapply(CODES, function(k)
  tryCatch(build_features(k), error = function(e) NULL)))

FEATURES <- c("sma_dev", "macd_bar", "adx", "rsi_dev",
              "kd_diff", "atr_rank", "bb_width", "obv_change")
cat("面板维度", dim(panel), "\n")
print(round(colMeans(is.na(panel[, FEATURES])), 3))

# ---- 代码块 2：第二步：特征预处理与横截面标准化 ----

# 逐日横截面标准化（中位数与 MAD），再截断到正负三
winsorize_z <- function(s) {
  med <- median(s, na.rm = TRUE)
  mad_ <- median(abs(s - med), na.rm = TRUE)
  z <- if (mad_ > 0) (s - med) / mad_ else s * 0
  pmax(pmin(z, 3), -3)
}

panel <- panel |>
  group_by(date) |>
  mutate(across(all_of(FEATURES), winsorize_z, .names = "{.col}_z")) |>
  ungroup()

ZFEATURES <- paste0(FEATURES, "_z")

# 标签：逐日横截面标准化的未来五日收益，作为回归目标
cs_std <- function(g) {
  med <- median(g, na.rm = TRUE)
  mad_ <- median(abs(g - med), na.rm = TRUE)
  if (mad_ > 0) (g - med) / mad_ else g * 0
}
panel <- panel |>
  group_by(date) |>
  mutate(y = cs_std(forward_5)) |>
  ungroup()
panel <- panel |> tidyr::drop_na(all_of(c(ZFEATURES, "y")))
cat("可用样本", nrow(panel), "\n")

# ---- 代码块 3：第三步：标签构造 ----

# 排名标签：逐日按分位排名减 0.5，便于与标准分版本对照
panel <- panel |>
  group_by(date) |>
  mutate(y_rank = percent_rank(forward_5) - 0.5) |>
  ungroup()
cat("标签标准差", round(sd(panel$y), 3),
    "排名标签取值范围", round(min(panel$y_rank), 2),
    round(max(panel$y_rank), 2), "\n")

# ---- 代码块 4：第四步：数据切分 ----

TRAIN_END   <- as.Date("2024-05-31")
VALID_START <- as.Date("2024-06-11")     # 训练末日后留十天
VALID_END   <- as.Date("2024-12-31")
TEST_START  <- as.Date("2025-01-11")     # 验证末日后留十天

train <- panel |> filter(date <= TRAIN_END)
valid <- panel |> filter(date >= VALID_START, date <= VALID_END)
test  <- panel |> filter(date >= TEST_START)
cat("训练", format(min(train$date)), format(max(train$date)), nrow(train), "\n")
cat("验证", format(min(valid$date)), format(max(valid$date)), nrow(valid), "\n")
cat("测试", format(min(test$date)), format(max(test$date)), nrow(test), "\n")

# ---- 代码块 5：第五步：单因子基线 ----

# 沿用第 007 章的 cross_section_ic / ic_summary，对八个特征分别计算
baseline <- do.call(rbind, lapply(FEATURES, function(f) {
  ic_summary(cross_section_ic(train, paste0(f, "_z"), "forward_5"))
}))
rownames(baseline) <- FEATURES
print(baseline)

# ---- 代码块 6：第六步：树模型 ----

# 提示：此处用 5 只标的演示流程。真实建模请改用 data/parquet/panel.parquet
# （287 只、2021-06 起），并补足十年区间与行业中性化
library(xgboost)

dtrain <- xgb.DMatrix(as.matrix(train[ZFEATURES]), label = train$y)
dvalid <- xgb.DMatrix(as.matrix(valid[ZFEATURES]), label = valid$y)

params <- list(
  objective = "reg:squarederror",
  eta = 0.03,               # 小学习率，配合早停
  max_depth = 4,            # 限制交互阶数
  min_child_weight = 200,   # 叶子样本下限，金融场景设大
  subsample = 0.8,          # 行采样
  colsample_bytree = 0.6,   # 列采样
  lambda = 5,               # L2 正则
  alpha = 0.5)              # L1 正则

set.seed(0)
model_gb <- xgb.train(
  params, dtrain, nrounds = 1000,
  watchlist = list(valid = dvalid),
  early_stopping_rounds = 50, verbose = 0)

# gain 重要性
print(xgb.importance(model = model_gb))

# ---- 代码块 7：第六步：树模型 ----

# 分块排列重要性：在时间块之间置换，保留块内时序结构
block_permutation_importance <- function(model, X, y, block = 20,
                                         n_repeat = 5, seed = 0) {
  set.seed(seed)
  base <- -mean((predict(model, as.matrix(X)) - y)^2)
  n <- nrow(X)
  # 按时间顺序切成若干块，块内元素保持原有顺序
  blocks <- split(seq_len(n), ceiling(seq_len(n) / block))
  out <- numeric(ncol(X)); names(out) <- colnames(X)
  for (c in colnames(X)) {
    drops <- numeric(n_repeat)
    for (r in seq_len(n_repeat)) {
      Xp <- X
      order_idx <- sample(seq_along(blocks))            # 打乱块的顺序
      new_idx <- unlist(blocks[order_idx], use.names = FALSE)
      Xp[[c]] <- X[[c]][new_idx]                        # 按块顺序重排该列
      drops[r] <- base - (-mean((predict(model, as.matrix(Xp)) - y)^2))
    }
    out[c] <- mean(drops)
  }
  sort(out, decreasing = TRUE)
}

perm <- block_permutation_importance(model_gb, valid[ZFEATURES], valid$y)
print(round(perm, 4))

# ---- 代码块 8：第六步：树模型 ----

# 沿用第 007 章的 cross_section_ic / ic_summary
valid_gb <- valid |> mutate(gb = predict(model_gb, as.matrix(valid[ZFEATURES])))
print(ic_summary(cross_section_ic(valid_gb, "gb", "forward_5")))

# ---- 代码块 9：第七步：序列模型 ----

T <- 20          # 回看窗口
STRIDE <- 1      # 步长

make_sequences <- function(df, features, target, T, stride = 1) {
  # 把面板切成 [N, T, F] 张量与标签，窗口不含未来
  Xs <- list(); ys <- numeric()
  dates <- as.Date(character()); codes <- character()
  for (code in unique(df$code)) {
    g <- df |> filter(.data$code == !!code) |> arrange(date)
    X <- as.matrix(g[, features]); y <- g[[target]]; dd <- g$date
    for (e in seq(T + 1, nrow(g), by = stride)) {
      win <- X[(e - T):(e - 1), , drop = FALSE]
      if (anyNA(win) || is.na(y[e])) next
      Xs[[length(Xs) + 1]] <- win
      ys <- c(ys, y[e]); dates <- c(dates, dd[e]); codes <- c(codes, code)
    }
  }
  list(X = simplify2array(Xs), y = ys, date = dates, code = codes)
}

# 窗口在训练期内构造，避免跨越切分边界
tr <- make_sequences(train, ZFEATURES, "y", T, STRIDE)
va <- make_sequences(valid, ZFEATURES, "y", T, STRIDE)

# 标准化统计量只用训练窗口
mu <- apply(tr$X, 3, mean)
sd_ <- apply(tr$X, 3, sd) + 1e-8
sweep3 <- function(A, m, s) {        # 逐特征在 [N, T, F] 张量上标准化
  for (k in seq_along(m)) A[, , k] <- (A[, , k] - m[k]) / s[k]
  A
}
trX <- sweep3(tr$X, mu, sd_)
vaX <- sweep3(va$X, mu, sd_)
cat("训练窗口", dim(trX)[1], dim(trX)[2], dim(trX)[3],
    "验证窗口", dim(vaX)[1], dim(vaX)[2], dim(vaX)[3], "\n")

# ---- 代码块 10：第七步：序列模型 ----

# 提示：此处用 5 只标的演示流程。真实建模请改用 data/parquet/panel.parquet
# （287 只、2021-06 起），并补足十年区间与行业中性化
# R 侧用 keras3 接口，需单独安装 TensorFlow 后端（keras3::install_keras()），
# 且 R 的深度学习生态在调试工具与社区资料上不及 Python
library(keras3)

set.seed(0)
model_lstm <- keras_model_sequential() |>
  layer_lstm(units = 16, input_shape = c(T, length(ZFEATURES))) |>
  layer_dropout(rate = 0.2) |>
  layer_dense(units = 1)
model_lstm |> compile(loss = "mse", optimizer = "adam")

# 早停：验证损失连续 10 轮不改善则停止，并回到最佳权重
cb <- callback_early_stopping(patience = 10, restore_best_weights = TRUE)
hist <- model_lstm |> fit(
  trX, tr$y, validation_data = list(vaX, va$y),
  epochs = 200, batch_size = nrow(trX),
  callbacks = list(cb), verbose = 0)
cat("最佳验证损失", round(min(hist$metrics$val_loss), 5), "\n")

# ---- 代码块 11：第七步：序列模型 ----

# 沿用第 007 章的 cross_section_ic / ic_summary
lstm_score <- as.numeric(predict(model_lstm, vaX))
valid_lstm <- data.frame(date = va$date, code = va$code, lstm = lstm_score) |>
  left_join(valid[, c("date", "code", "forward_5")], by = c("date", "code"))
print(ic_summary(cross_section_ic(valid_lstm, "lstm", "forward_5")))

# ---- 代码块 12：第八步：融合 ----

# 提示：此处用 5 只标的演示流程。真实建模请改用 data/parquet/panel.parquet
# （287 只、2021-06 起），并补足十年区间与行业中性化
# 沿用第 007 章的 cross_section_ic / ic_summary
library(glmnet)

# 用验证期的基模型输出作为示意；真实流程需在训练期用扩张窗口生成 OOF 预测
fuse <- valid |>
  mutate(gb = predict(model_gb, as.matrix(valid[ZFEATURES]))) |>
  left_join(valid_lstm[, c("date", "code", "lstm")], by = c("date", "code"))

# 基模型输出逐日转横截面分位
for (c in c("gb", "lstm")) {
  fuse[[paste0(c, "_q")]] <- ave(fuse[[c]], fuse$date,
                                 FUN = function(x) rank(x) / length(x))
}

# Ridge 等价于 glmnet 在 alpha = 0；逐个加入基模型，观察边际贡献
steps <- list("gb_q", c("gb_q", "lstm_q"))
for (cols in steps) {
  sub <- fuse[stats::complete.cases(fuse[, c(cols, "y")]), ]
  Xm <- as.matrix(sub[, cols]); ym <- sub$y
  m <- glmnet(Xm, ym, alpha = 0, lambda = 1)
  sub$fused <- as.numeric(predict(m, Xm))
  print(list(基模型 = cols, IC = ic_summary(cross_section_ic(sub, "fused", "y")),
             系数 = round(as.numeric(coef(m)[-1]), 3)))
}

# ---- 代码块 13：第八步：融合 ----

# 沿用第 007 章的 cross_section_ic / ic_summary / layered_returns
# 单因子等权：八个方向对齐后的标准化特征平均
fuse$equal <- rowMeans(as.matrix(fuse[, ZFEATURES]), na.rm = TRUE)

for (col in c("equal", "gb", "fused")) {
  print(list(方案 = col, IC = ic_summary(cross_section_ic(fuse, col, "y"))))
}
print(layered_returns(fuse, "fused", "forward_5"))

# ---- 代码块 14：第九步：回测与成本 ----

# 多空组合回测：按月调仓，计入费率与印花税
backtest_ls <- function(panel, factor_col, ret_col, q = 3,
                        fee = 0.0003, stamp = 0.001) {
  df <- panel |>
    filter(!is.na(.data[[factor_col]]), !is.na(.data[[ret_col]])) |>
    mutate(period = format(date, "%Y-%m"))

  prev_long <- character(); prev_short <- character()
  rows <- list()
  for (p in sort(unique(df$period))) {
    g <- df |> filter(period == p)
    g$grp <- ntile(rank(g[[factor_col]]), q)
    long <- g |> filter(grp == q); short <- g |> filter(grp == 1)
    lset <- long$code; sset <- short$code
    gross <- mean(long[[ret_col]]) - mean(short[[ret_col]])
    # 单边换手：本次持仓相对上期的差异比例，多空各算一次
    turnover <- function(now, prev) {
      if (length(prev) == 0) return(1.0)
      1 - length(intersect(now, prev)) / max(length(now), 1)
    }
    turn <- turnover(lset, prev_long) + turnover(sset, prev_short)
    # 成本近似：单边换手之和乘以单边成本，费率双边计，印花税按卖出计
    cost <- turn * (fee + stamp)
    rows[[length(rows) + 1]] <- data.frame(period = p, gross = gross,
                                           turnover = turn, net = gross - cost)
    prev_long <- lset; prev_short <- sset
  }
  out <- bind_rows(rows)
  ann <- prod(1 + out$net)^(12 / nrow(out)) - 1
  sharpe <- if (sd(out$net) > 0) mean(out$net) / sd(out$net) * sqrt(12) else NA_real_
  list(out = out, ann = round(ann, 4), sharpe = round(sharpe, 2))
}

bt <- backtest_ls(fuse, "fused", "forward_5")
cat("平均单边换手", round(mean(bt$out$turnover), 3),
    "平均毛收益", round(mean(bt$out$gross), 4),
    "平均净收益", round(mean(bt$out$net), 4), "\n")

# ---- 代码块 15：第九步：回测与成本 ----

# 简化的可交易性过滤示意：按涨跌幅识别可能难以成交的时点
tradable_mask <- function(df, limit = 0.098) {
  df <- df |> arrange(code, date) |> group_by(code) |>
    mutate(ret1 = close / lag(close) - 1) |> ungroup()
  # 首行无前收，按可交易处理；涨跌幅达到阈值视为难以成交
  is.na(df$ret1) | abs(df$ret1) < limit
}

fuse <- fuse |> arrange(code, date)
fuse$tradable <- tradable_mask(fuse)
cat("可交易样本占比", round(mean(fuse$tradable), 3), "\n")

# ---- 代码块 16：第十一步：上线与监控 ----

# 沿用第 007 章的 cross_section_ic；滚动样本外 IC 曲线
ic <- cross_section_ic(fuse, "fused")
roll <- zoo::rollmean(ic, 60, fill = NA, align = "right")

# 中文字体用 macOS 自带的 STHeiti
par(family = "STHeiti")
plot(seq_along(roll), roll, type = "l", col = "steelblue",
     xlab = "期数", ylab = "滚动 IC 均值",
     main = "融合信号滚动样本外 IC（示意）")
abline(h = 0, col = "gray")
abline(h = quantile(roll, 0.1, na.rm = TRUE), col = "firebrick", lty = 2)
legend("topright", legend = c("滚动 IC 均值", "历史 10% 分位"),
       col = c("steelblue", "firebrick"), lty = c(1, 2), bty = "n")
