# ============================================================
# 第043章 树模型：捕捉非线性与特征交互
# 模块 08 机器学习挖掘与融合
# 源文件：模块08-机器学习挖掘与融合/第043章-树模型：捕捉非线性与特征交互.md
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

# 提示：此处用 5 只标的演示流程。真实建模请改用 data/parquet/panel.parquet
# （287 只、2021-06 起），并补足十年区间与行业中性化
# panel 与特征列由本节 R 部分的数据准备得到
library(xgboost)
library(dplyr)

features <- c("ret5", "ma20_dev", "vol20", "vol_ratio")
tr <- panel |> filter(date <  as.Date("2024-09-01"))
va <- panel |> filter(date >= as.Date("2024-09-01"))

dtrain <- xgb.DMatrix(as.matrix(tr[features]), label = tr$y)
dvalid <- xgb.DMatrix(as.matrix(va[features]), label = va$y)

params <- list(
  objective = "reg:squarederror",
  eta = 0.03,               # 小学习率配合早停
  max_depth = 4,            # 限制交互阶数
  min_child_weight = 200,   # 叶子样本下限，金融场景设大
  subsample = 0.8,          # 行采样
  colsample_bytree = 0.6,   # 列采样
  lambda = 5,               # L2 正则
  alpha = 0.5               # L1 正则
)

# watchlist 传入验证集，early_stopping_rounds 由验证损失决定停止轮数
set.seed(0)
fit <- xgb.train(
  params, dtrain, nrounds = 1000,
  watchlist = list(train = dtrain, valid = dvalid),
  early_stopping_rounds = 50, verbose = 0)

# 特征重要性：gain 口径
imp <- xgb.importance(model = fit)
print(imp)

if (nrow(imp) > 0) {   # 样本过少时模型可能不产生分裂，此时跳过作图
  barplot(stats::setNames(imp$Gain, imp$Feature)[order(imp$Gain)],
          horiz = TRUE, las = 1, col = "steelblue",
          xlab = "gain 重要性", main = "梯度提升特征重要性（示意）")
}

# 训练过程诊断：用 xgb.cv 得到训练集与验证集误差随迭代轮数的变化
# 折按时间顺序切分，避免随机打乱带来的未来信息
folds <- split(seq_len(nrow(tr)), cut(seq_len(nrow(tr)), breaks = 3, labels = FALSE))
cv <- xgb.cv(params, dtrain, nrounds = 1000, folds = folds,
             early_stopping_rounds = 50, verbose = 0)
evlog <- as.data.frame(cv$evaluation_log)
plot(evlog$iter, evlog$train_rmse_mean, type = "l", col = "steelblue",
     ylab = "RMSE", xlab = "迭代轮数", main = "训练与验证误差曲线（示意）")
lines(evlog$iter, evlog$test_rmse_mean, col = "firebrick")
abline(v = evlog$iter[which.min(evlog$test_rmse_mean)], lty = 2, col = "gray40")
legend("topright", legend = c("训练集", "验证集", "早停点"),
       col = c("steelblue", "firebrick", "gray40"), lty = c(1, 1, 2), bty = "n")

# ---- 代码块 2：代码实现 ----

library(quantmod)
library(dplyr)
library(xgboost)

codes <- c("600519.SS", "600036.SS", "601318.SS", "300750.SZ", "000858.SZ")

get_one <- function(code) {
  px <- local({
    # 从本地 CSV 取该标的，转成 quantmod 可用的 xts
    .p <- read.csv("data/parquet/panel_blue_chip.csv", stringsAsFactors = FALSE)
    .p <- .p[.p$code == code, ]
    .x <- xts::xts(.p[, c("open", "high", "low", "close", "volume", "adjusted")],
                       order.by = as.Date(.p$date))
    colnames(.x) <- c("Open", "High", "Low", "Close", "Volume", "Adjusted")
    .x
  })
  d <- data.frame(
    date     = index(px),
    close    = as.numeric(Cl(px)),
    volume   = as.numeric(Vo(px)),
    code     = code
  )
  d <- d |>
    mutate(
      ret5      = close / lag(close, 5) - 1,
      ma20_dev  = close / zoo::rollmean(close, 20, fill = NA, align = "right") - 1,
      vol20     = zoo::rollapply(close / lag(close) - 1, 20, sd,
                                 fill = NA, align = "right"),
      vol_ratio = volume / zoo::rollmean(volume, 20, fill = NA, align = "right"),
      forward_5 = close / lead(close, 5) - 1
    )
  d
}

panel <- bind_rows(lapply(codes, get_one))

# 目标：逐日横截面标准化
cs_std <- function(x) {
  m <- median(x, na.rm = TRUE)
  mad_ <- median(abs(x - m), na.rm = TRUE)
  if (mad_ > 0) (x - m) / mad_ else rep(0, length(x))
}
panel <- panel |>
  group_by(date) |>
  mutate(y = cs_std(forward_5)) |>
  ungroup()

features <- c("ret5", "ma20_dev", "vol20", "vol_ratio")
panel <- panel |> tidyr::drop_na(all_of(c(features, "y")))

# 按时间切分
tr <- panel |> filter(date < as.Date("2024-09-01"))
va <- panel |> filter(date >= as.Date("2024-09-01"))

dtrain <- xgb.DMatrix(as.matrix(tr[features]), label = tr$y)
dvalid <- xgb.DMatrix(as.matrix(va[features]), label = va$y)

params <- list(
  objective = "reg:squarederror",
  eta = 0.03,               # 学习率
  max_depth = 4,            # 限制交互阶数
  min_child_weight = 200,   # 叶子样本下限
  subsample = 0.8,          # 行采样
  colsample_bytree = 0.6,   # 列采样
  lambda = 5,               # L2 正则
  alpha = 0.5               # L1 正则
)

fit <- xgb.train(
  params, dtrain, nrounds = 1000,
  watchlist = list(valid = dvalid),
  early_stopping_rounds = 50, verbose = 0)

# 特征重要性（gain 口径）
imp <- xgb.importance(model = fit)
print(imp)

# 用随机森林做对照，比较两种集成方法的重要性排序
library(ranger)
rf <- ranger(y ~ ret5 + ma20_dev + vol20 + vol_ratio,
             data = tr, num.trees = 500, mtry = 3,
             min.node.size = 200, importance = "impurity")
print(sort(rf$variable.importance, decreasing = TRUE))
