# ============================================================
# 第043章 树模型：捕捉非线性与特征交互
# 模块 08 机器学习挖掘与融合
# 源文件：模块08-机器学习挖掘与融合/第043章-树模型：捕捉非线性与特征交互.md
# ============================================================
# 本文件由 scripts/extract_code.py 自动生成，请勿直接编辑。
# 修改代码请改 Markdown 源稿，再重新运行提取脚本。
#
# 依赖：先加载同目录下的公共函数与数据准备
#   exec(open("code/python/00-common.py").read())
#   exec(open("code/python/00-data.py").read())
#
# ------------------------------------------------------------

# ---- 代码块 1：代码实现 ----

import numpy as np
import pandas as pd

# 本地数据，由 xquant-db 导出，字段见 data/README.md
_panel = pd.read_parquet("data/parquet/panel_blue_chip.parquet")
import lightgbm as lgb

CODES = {"600519.SS": "贵州茅台", "600036.SS": "招商银行",
         "601318.SS": "中国平安", "300750.SZ": "宁德时代",
         "000858.SZ": "五粮液"}

frames = []
for code in CODES:
    _oneday = _panel[_panel["code"] == code].set_index("date").sort_index()
    raw = _oneday[["open", "high", "low", "close", "volume"]].copy()
    raw.columns = ["Open", "High", "Low", "Close", "Volume"]
    if raw.empty:
        continue
    d = raw.squeeze()[["Close", "Volume"]].copy()
    d.columns = ["close", "volume"]
    d["code"] = code
    # 一组示意用的技术特征
    d["ret5"] = d["close"].pct_change(5)
    d["ma20_dev"] = d["close"] / d["close"].rolling(20).mean() - 1
    d["vol20"] = d["close"].pct_change().rolling(20).std()
    d["vol_ratio"] = d["volume"] / d["volume"].rolling(20).mean()
    d["forward_5"] = d["close"].pct_change().shift(-5)
    frames.append(d.reset_index().rename(columns={"Date": "date"}))

panel = pd.concat(frames, ignore_index=True)

# 目标：逐日横截面标准化（按当日中位数与 MAD）
def cs_standardize(g):
    med = g.median()
    mad = (g - med).abs().median()
    return (g - med) / mad if mad > 0 else g * 0.0

panel["y"] = panel.groupby("date")["forward_5"].transform(cs_standardize)

FEATURES = ["ret5", "ma20_dev", "vol20", "vol_ratio"]
panel = panel.dropna(subset=FEATURES + ["y"])

# 按时间切分，禁止随机打乱
split_date = "2024-09-01"
tr = panel[panel["date"] < split_date]
va = panel[panel["date"] >= split_date]
print("训练样本", len(tr), "验证样本", len(va))

# ---- 代码块 2：代码实现 ----

import matplotlib
matplotlib.rcParams["font.sans-serif"] = ["PingFang SC", "SimHei", "Arial Unicode MS"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt

model = lgb.LGBMRegressor(
    n_estimators=1000,
    learning_rate=0.03,      # 小学习率配合早停
    num_leaves=15,           # 限制复杂度
    max_depth=4,             # 限制交互阶数
    subsample=0.8,           # 行采样
    subsample_freq=1,
    colsample_bytree=0.6,    # 列采样
    min_child_samples=200,   # 叶子样本下限，金融场景设大
    reg_lambda=5.0,          # L2 正则
    reg_alpha=0.5,           # L1 正则
    random_state=0)

model.fit(
    tr[FEATURES], tr["y"],
    eval_set=[(va[FEATURES], va["y"])],
    eval_metric="l2",
    callbacks=[lgb.early_stopping(50, verbose=False)])

# 特征重要性
imp = pd.Series(model.booster_.feature_importance("gain"),
                index=FEATURES).sort_values(ascending=False)

fig, ax = plt.subplots(figsize=(7, 4))
ax.barh(imp.index[::-1], imp.values[::-1])
ax.set_title("梯度提升特征重要性（示意）")
ax.set_xlabel("gain 重要性")
plt.tight_layout()
plt.show()

# 训练过程诊断：训练集与验证集误差随迭代轮数的变化
evals = model.evals_result_
tr_err = evals["training"]["l2"]
va_err = evals["valid_0"]["l2"]

fig, ax = plt.subplots(figsize=(7, 4))
ax.plot(tr_err, label="训练集")
ax.plot(va_err, label="验证集")
ax.axvline(model.best_iteration_, color="gray", linestyle="--", label="早停点")
ax.set_xlabel("迭代轮数")
ax.set_ylabel("L2 损失")
ax.set_title("训练与验证误差曲线（示意）")
ax.legend()
plt.tight_layout()
plt.show()
