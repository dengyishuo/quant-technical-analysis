# ============================================================
# 第046章 因子融合：把多个模型与多类特征合成一个信号
# 模块 08 机器学习挖掘与融合
# 源文件：模块08-机器学习挖掘与融合/第046章-因子融合：把多个模型与多类特征合成一个信号.md
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
    d["ret5"] = d["close"].pct_change(5)
    d["ma20_dev"] = d["close"] / d["close"].rolling(20).mean() - 1
    d["vol20"] = d["close"].pct_change().rolling(20).std()
    d["vol_ratio"] = d["volume"] / d["volume"].rolling(20).mean()
    d["forward_5"] = d["close"].pct_change().shift(-5)
    frames.append(d.reset_index().rename(columns={"Date": "date"}))

panel = pd.concat(frames, ignore_index=True)
FEATURES = ["ret5", "ma20_dev", "vol20", "vol_ratio"]
panel = panel.dropna(subset=FEATURES + ["forward_5"])

def cs_rank(g):
    """逐日横截面转分位，输入输出都落在零到一之间。"""
    return g.rank(pct=True)

# 目标：逐日横截面标准化的未来收益
def cs_std(g):
    med = g.median()
    mad = (g - med).abs().median()
    return (g - med) / mad if mad > 0 else g * 0.0

panel["y"] = panel.groupby("date")["forward_5"].transform(cs_std)

# 逐日横截面标准化的特征，作为其中一个基模型的输入
for c in FEATURES:
    panel[c + "_z"] = panel.groupby("date")[c].transform(
        lambda s: (s - s.median()) / (s - s.median()).abs().median()
        if (s - s.median()).abs().median() > 0 else 0)
print("面板维度", panel.shape)

# ---- 代码块 2：代码实现 ----

import lightgbm as lgb
from sklearn.linear_model import Ridge

# 扩张窗口的折边界：把时间轴切成若干段，前 k 段训练，预测第 k 加 1 段
dates = np.sort(panel["date"].unique())
folds = np.array_split(dates, 6)          # 示意用六折
ZCOLS = [c + "_z" for c in FEATURES]

oof = pd.DataFrame(index=panel.index, columns=["gbdt", "linear"], dtype=float)

for k in range(1, len(folds)):
    tr_dates = np.concatenate(folds[:k])   # 只用前面的折训练
    te_dates = folds[k]                    # 预测当前的折
    tr = panel[panel["date"].isin(tr_dates)]
    te = panel[panel["date"].isin(te_dates)]
    if len(tr) < 200 or len(te) == 0:
        continue

    gb = lgb.LGBMRegressor(
        n_estimators=300, learning_rate=0.05, num_leaves=15, max_depth=4,
        subsample=0.8, subsample_freq=1, colsample_bytree=0.6,
        min_child_samples=200, reg_lambda=5.0, random_state=0)
    gb.fit(tr[FEATURES], tr["y"])
    oof.loc[te.index, "gbdt"] = gb.predict(te[FEATURES])

    lin = Ridge(alpha=10.0)
    lin.fit(tr[ZCOLS], tr["y"])
    oof.loc[te.index, "linear"] = lin.predict(te[ZCOLS])

# 每一行的基模型预测都来自样本外，这是元模型可用的前提
meta = panel[["date", "code", "forward_5", "y"]].copy()
meta["gbdt"] = oof["gbdt"]
meta["linear"] = oof["linear"]
meta = meta.dropna()
print("元模型可用样本", len(meta))

# ---- 代码块 3：代码实现 ----

# 各基模型输出逐日转分位，统一尺度
for c in ["gbdt", "linear"]:
    meta[c + "_q"] = meta.groupby("date")[c].transform(cs_rank)
QCOLS = ["gbdt_q", "linear_q"]

# 取前半段训练元模型，后半段评估，保持时间顺序
cut = np.sort(meta["date"].unique())[int(len(meta["date"].unique()) * 0.6)]
mt_tr = meta[meta["date"] < cut]
mt_te = meta[meta["date"] >= cut]

meta_model = Ridge(alpha=1.0)              # 线性元模型，参数少，相对稳健
meta_model.fit(mt_tr[QCOLS], mt_tr["y"])
meta_te = mt_te.assign(fused=meta_model.predict(mt_te[QCOLS]))

print("元模型系数", dict(zip(QCOLS, meta_model.coef_.round(3))))

# ---- 代码块 4：代码实现 ----

from scipy import stats

def cross_section_ic(panel, col, ret_col="forward_5", date_col="date"):
    def _ic(g):
        s = g.dropna(subset=[col, ret_col])
        return stats.spearmanr(s[col], s[ret_col])[0] if len(s) >= 5 else np.nan
    return panel.groupby(date_col).apply(_ic).dropna()

def ic_summary(ic):
    m, s = ic.mean(), ic.std()
    return pd.Series({"IC均值": round(m, 4), "IC标准差": round(s, 4),
                      "ICIR": round(m / s, 3) if s > 0 else np.nan, "期数": len(ic)})

# 单因子等权：四个标准化特征平均
meta_te = meta_te.assign(equal=meta_te[["gbdt", "linear"]].rank(pct=True).mean(axis=1))

for col in ["gbdt", "linear", "equal", "fused"]:
    print(col, ic_summary(cross_section_ic(meta_te, col, "y")).to_dict())

# ---- 代码块 5：代码实现 ----

# 逐日横截面相关，再对时间求平均，避免把时序共动误当成横截面相关
daily_corr = meta.groupby("date")[["gbdt_q", "linear_q"]].corr().unstack().iloc[:, 1]
print("平均横截面相关", round(daily_corr.mean(), 3))

# 若相关偏高，把其中一个对另一个做横截面回归，取残差作为增量输入
resid = []
for _, gg in meta.groupby("date"):
    d = gg.dropna(subset=["gbdt_q", "linear_q"])
    if len(d) < 5:
        resid.append(pd.Series(np.nan, index=d.index))
        continue
    x = np.column_stack([np.ones(len(d)), d["gbdt_q"]])
    beta, *_ = np.linalg.lstsq(x, d["linear_q"], rcond=None)
    resid.append(pd.Series(d["linear_q"] - x @ beta, index=d.index))
meta["linear_resid"] = pd.concat(resid).reindex(meta.index)

# ---- 代码块 6：代码实现 ----

import matplotlib
matplotlib.rcParams["font.sans-serif"] = ["PingFang SC", "SimHei", "Arial Unicode MS"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt

def rolling_ic_weight(meta, cols, window=60, lam=0.5, w_floor=0.1, w_cap=0.9):
    """按滚动样本外 IC 给基模型加权，权重向等权收缩并设上下限。"""
    ic_ts = pd.DataFrame({c: cross_section_ic(meta, c, "y") for c in cols})
    ic_roll = ic_ts.rolling(window, min_periods=20).mean()       # 指数或简单滚动均可
    raw = ic_roll.div(ic_roll.abs().sum(axis=1), axis=0).fillna(1 / len(cols))
    eq = 1 / len(cols)
    w = (1 - lam) * raw + lam * eq                              # 向等权收缩
    w = w.clip(w_floor, w_cap)
    return w.div(w.sum(axis=1), axis=0)

w = rolling_ic_weight(meta, ["gbdt_q", "linear_q"], window=60, lam=0.5)
fig, ax = plt.subplots(figsize=(8, 4))
w.plot(ax=ax, title="滚动 IC 加权并收缩后的基模型权重（示意）")
ax.set_ylabel("权重")
plt.tight_layout()
plt.show()
