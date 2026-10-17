# ============================================================
# 第044章 序列模型：时间结构的建模
# 模块 08 机器学习挖掘与融合
# 源文件：模块08-机器学习挖掘与融合/第044章-序列模型：时间结构的建模.md
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

# 面板到张量的重组：按 code 分组后沿时间滑动切窗，窗口只覆盖末端及之前
library(quantmod)
library(dplyr)

FEATURES <- c("ret5", "ma20_dev", "vol20", "vol_ratio")
T <- 20        # 窗口长度：回看 20 个交易日
STRIDE <- 1    # 步长：逐日滑动

build_panel <- function(codes) {
  frames <- lapply(codes, function(code) {
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
                    volume = as.numeric(Vo(raw)), code = code)
    d |>
      mutate(
        ret5      = close / lag(close, 5) - 1,
        ma20_dev  = close / zoo::rollmean(close, 20, fill = NA, align = "right") - 1,
        vol20     = zoo::rollapply(close / lag(close) - 1, 20, sd,
                                   fill = NA, align = "right"),
        vol_ratio = volume / zoo::rollmean(volume, 20, fill = NA, align = "right"),
        # 目标：未来 5 日收益（收盘对收盘，仅在窗口末端之后）
        forward_5 = close / lead(close, 5) - 1)
    d
  })
  bind_rows(frames)
}

make_sequences <- function(panel, features, target, T, stride = 1) {
  # 每个窗口覆盖末端及之前，标签取末端处的未来收益，窗口不含未来
  Xs <- list(); ys <- numeric()
  dates <- as.Date(character()); codes <- character()
  for (code in unique(panel$code)) {
    g <- panel |> filter(.data$code == !!code) |> arrange(date)
    X <- as.matrix(g[, features])
    y <- g[[target]]
    dd <- g$date
    for (e in seq(T + 1, nrow(g), by = stride)) {
      win <- X[(e - T):(e - 1), , drop = FALSE]
      if (anyNA(win) || is.na(y[e])) next   # 末端的标签在窗口之后，缺失样本跳过
      Xs[[length(Xs) + 1]] <- win
      ys <- c(ys, y[e]); dates <- c(dates, dd[e]); codes <- c(codes, code)
    }
  }
  list(X = simplify2array(Xs), y = ys, date = dates, code = codes)
}

# ---- 代码块 2：代码实现 ----

split_with_buffer <- function(X, y, dates, train_end, buffer_days) {
  # 按时间切分。缓冲期使验证窗口不与训练窗口在时间上重叠
  train_end <- as.Date(train_end)
  valid_start <- train_end + buffer_days
  tr <- dates <= train_end
  va <- dates > valid_start
  list(train = list(X = X[tr, , , drop = FALSE], y = y[tr]),
       valid = list(X = X[va, , , drop = FALSE], y = y[va]))
}

codes <- c("600519.SS", "600036.SS", "601318.SS", "300750.SZ", "000858.SZ")
panel <- build_panel(codes) |> tidyr::drop_na(all_of(c(FEATURES, "forward_5")))
seqs <- make_sequences(panel, FEATURES, "forward_5", T, STRIDE)
cat("窗口总数", dim(seqs$X), "\n")

sp <- split_with_buffer(seqs$X, seqs$y, seqs$date, "2024-08-01",
                        buffer_days = T + 20)
trX <- sp$train$X; trY <- sp$train$y
vaX <- sp$valid$X; vaY <- sp$valid$y

# 特征标准化只用训练集统计量，避免泄漏
mu <- apply(trX, 3, mean)
sd_ <- apply(trX, 3, sd) + 1e-8
sweep3 <- function(A, m, s) {          # 逐特征在 [N, T, F] 张量上标准化
  for (k in seq_along(m)) A[, , k] <- (A[, , k] - m[k]) / s[k]
  A
}
trX <- sweep3(trX, mu, sd_)
vaX <- sweep3(vaX, mu, sd_)
cat("训练窗口", dim(trX)[1], "验证窗口", dim(vaX)[1], "\n")

# ---- 代码块 3：代码实现 ----

# 提示：此处用 5 只标的演示流程。真实建模请改用 data/parquet/panel.parquet
# （287 只、2021-06 起），并补足十年区间与行业中性化
# R 侧用 keras3 接口，需单独安装 TensorFlow 后端（keras3::install_keras()），
# 且 R 的深度学习生态在调试工具与社区资料上不及 Python
library(keras3)

build_lstm <- function(n_features, hidden = 16, dropout = 0.2) {
  model <- keras_model_sequential() |>
    layer_lstm(units = hidden, input_shape = c(T, n_features)) |>
    layer_dropout(rate = dropout) |>
    layer_dense(units = 1)
  model |> compile(loss = "mse", optimizer = "adam")
  model
}

set.seed(0)
model <- build_lstm(n_features = length(FEATURES))

# 早停：验证损失连续 10 轮不改善则停止，并回到最佳权重
cb <- callback_early_stopping(patience = 10, restore_best_weights = TRUE)
hist <- model |> fit(
  trX, trY, validation_data = list(vaX, vaY),
  epochs = 200, batch_size = nrow(trX),   # 全量批，仅演示
  callbacks = list(cb), verbose = 0)
cat("最佳验证损失", round(min(hist$metrics$val_loss), 5), "\n")

# ---- 代码块 4：代码实现 ----

# 训练与验证损失曲线；中文字体用 macOS 自带的 STHeiti
tr_hist <- hist$metrics$loss
va_hist <- hist$metrics$val_loss
par(family = "STHeiti")
plot(tr_hist, type = "l", col = "steelblue",
     ylim = range(c(tr_hist, va_hist)),
     xlab = "轮次", ylab = "MSE", main = "LSTM 训练过程（示意）")
lines(va_hist, col = "firebrick")
legend("topright", legend = c("训练损失", "验证损失"),
       col = c("steelblue", "firebrick"), lty = 1, bty = "n")

# ---- 代码块 5：代码实现 ----

# 提示：此处用 5 只标的演示流程。真实建模请改用 data/parquet/panel.parquet
# （287 只、2021-06 起），并补足十年区间与行业中性化
# R 侧用 keras3 接口，需单独安装 TensorFlow 后端（keras3::install_keras()），
# 且 R 的深度学习生态在调试工具与社区资料上不及 Python
library(keras3)

# 因果卷积：padding = "causal" 即只在序列左侧补零，等价于 Python 的
# nn.functional.pad(x, (pad, 0))，时点 t 的输出只依赖 t 及之前的输入
build_tcn <- function(n_features, hidden = 16, dilations = c(1, 2, 4)) {
  input <- layer_input(shape = c(T, n_features))
  h <- input
  for (d in dilations) {               # 膨胀率成倍增长，扩大感受野
    h <- h |> layer_conv_1d(filters = hidden, kernel_size = 3,
                            dilation_rate = d, padding = "causal",
                            activation = "relu")
  }
  out <- h |>
    layer_lambda(function(x) x[, dim(x)[2], ]) |>   # 取最后一个时点
    layer_dense(units = 1)
  keras_model(input, out)
}

model_tcn <- build_tcn(n_features = length(FEATURES))

# ---- 代码块 6：代码实现 ----

# 提示：此处用 5 只标的演示流程。真实建模请改用 data/parquet/panel.parquet
# （287 只、2021-06 起），并补足十年区间与行业中性化
library(xgboost)
library(dplyr)

window_stats <- function(X) {
  # 把每个窗口压成少量统计量，作为树模型的基线输入
  data.frame(
    mean  = apply(X, 1, mean),                       # 全部 T×F 的均值
    std   = apply(apply(X, c(1, 3), sd), 1, mean),   # 先按时间求标准差，再对特征取均值
    slope = apply(X[, dim(X)[2], , drop = FALSE], 1, mean) -
            apply(X[, 1, , drop = FALSE], 1, mean),
    last  = apply(X[, dim(X)[2], , drop = FALSE], 1, mean))
}

trS <- as.matrix(window_stats(trX))
vaS <- as.matrix(window_stats(vaX))
dtrain_base <- xgb.DMatrix(trS, label = trY)
dvalid_base <- xgb.DMatrix(vaS, label = vaY)

params <- list(objective = "reg:squarederror", eta = 0.03, max_depth = 4,
               min_child_weight = 100, subsample = 0.8, colsample_bytree = 0.8)
set.seed(0)
baseline <- xgb.train(params, dtrain_base, nrounds = 200,
                      watchlist = list(valid = dvalid_base), verbose = 0)
pred_base <- predict(baseline, dvalid_base)
cat("基线验证 MSE", round(mean((pred_base - vaY)^2), 5), "\n")

# ---- 代码块 7：代码实现 ----

# 沿用第 007 章的 cross_section_ic / ic_summary
train_end <- as.Date("2024-08-01")
valid_start <- train_end + (T + 20)      # 缓冲期不小于窗口长度
va_mask <- seqs$date > valid_start

score <- data.frame(date = seqs$date[va_mask], code = seqs$code[va_mask],
                    score = as.numeric(predict(model, vaX)), forward_5 = vaY)
ic <- cross_section_ic(score, "score", "forward_5")
print(ic_summary(ic))
