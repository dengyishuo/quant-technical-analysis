# ============================================================
# 第042章 特征挖掘：从人工构造到自动生成
# 模块 08 机器学习挖掘与融合
# 源文件：模块08-机器学习挖掘与融合/第042章-特征挖掘：从人工构造到自动生成.md
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

WINDOWS = [5, 10, 20, 60]

def ops_change(s):
    """变化类算子：差分、变化率、对数变化率。"""
    out = {}
    out[f"{s.name}_diff"] = s.diff()
    out[f"{s.name}_ret"] = s.pct_change()
    out[f"{s.name}_logret"] = np.log(s.clip(lower=1e-9)).diff()
    return out

def ops_relative(s):
    """相对类算子：与滚动均值之比、在滚动区间内的位置。"""
    out = {}
    for w in WINDOWS:
        ma = s.rolling(w).mean()
        lo = s.rolling(w).min()
        hi = s.rolling(w).max()
        out[f"{s.name}_ma{w}_dev"] = s / ma - 1
        out[f"{s.name}_pos{w}"] = (s - lo) / (hi - lo + 1e-9)
    return out

def ops_rolling(s):
    """滚动统计类算子：标准差、偏度、滚动分位位置。"""
    out = {}
    for w in WINDOWS:
        out[f"{s.name}_std{w}"] = s.rolling(w).std()
        out[f"{s.name}_skew{w}"] = s.rolling(w).skew()
        r = s.rolling(w).apply(lambda x: (x[-1] > x).mean(), raw=True)
        out[f"{s.name}_rank{w}"] = r
    return out

def ops_state(s):
    """状态标记类算子：符号、穿越、带符号的久期。"""
    sign = np.sign(s.diff())
    turn = sign.diff().abs() > 0
    dur = sign.groupby(turn.cumsum()).cumcount() + 1
    return {f"{s.name}_sign": sign, f"{s.name}_dur": sign * dur}

OPS_ONE = [ops_change, ops_relative, ops_rolling, ops_state]

def build_zoo(df, base_cols, two_layer=True):
    """两层生成：一层 O(B)，二层 O(O(B))。"""
    zoo = {}
    for c in base_cols:
        for op in OPS_ONE:
            zoo.update(op(df[c]))
    if two_layer:
        layer1 = pd.DataFrame(zoo, index=df.index)
        for c in layer1.columns:
            for op in OPS_ONE:
                for k, v in op(layer1[c]).items():
                    # 二层结果加前缀，避免与一层同名
                    zoo[f"L2_{k}"] = v
    return pd.DataFrame(zoo, index=df.index)

# ---- 代码块 2：代码实现 ----

from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform

def screen_by_prior(cols):
    """先验筛选：剔除经济含义不成立或引入未来信息的候选。"""
    banned_kw = ["_diff_diff", "_logret_logret"]  # 二阶差分等视为无经济含义
    return [c for c in cols if not any(k in c for k in banned_kw)]

def screen_by_stats(zoo, cols, cov_thr=0.8, var_thr=1e-8, corr_thr=0.9):
    """统计筛选：覆盖率、方差、相关性聚类。"""
    keep = [c for c in cols if zoo[c].notna().mean() >= cov_thr]
    keep = [c for c in keep if zoo[c].var() > var_thr and zoo[c].nunique() > 2]
    if len(keep) < 2:
        return keep
    corr = zoo[keep].corr(method="spearman").abs().fillna(0.0)
    dist = squareform(1 - corr.values, checks=False)
    lab = fcluster(linkage(dist, "average"), t=1 - corr_thr, criterion="distance")
    # 每类里保留方差最大的一个作为代表
    rep = {}
    for c, g in zip(keep, lab):
        if g not in rep or zoo[c].var() > zoo[rep[g]].var():
            rep[g] = c
    return list(rep.values())

# ---- 代码块 3：代码实现 ----

import lightgbm as lgb

def block_permutation_importance(model, X, y, block=20, n_repeat=5, seed=0):
    """分块排列重要性：在时间块之间置换，保留块内时序结构。"""
    rng = np.random.default_rng(seed)
    base = -np.mean((model.predict(X) - y) ** 2)
    idx = np.arange(len(X))
    blocks = np.array_split(idx, max(1, len(X) // block))
    out = {}
    for c in X.columns:
        drops = []
        for _ in range(n_repeat):
            Xp = X.copy()
            order = rng.permutation(len(blocks))
            new_idx = np.concatenate([blocks[p] for p in order])
            Xp[c] = Xp[c].to_numpy()[new_idx]
            drops.append(base - (-np.mean((model.predict(Xp) - y) ** 2)))
        out[c] = float(np.mean(drops))
    return pd.Series(out).sort_values(ascending=False)

def train_and_rank(panel, feature_cols, target_col, split_date):
    """按时间切分训练，输出 gain 重要性与分块排列重要性。"""
    tr = panel[panel["date"] < split_date]
    va = panel[panel["date"] >= split_date]
    model = lgb.LGBMRegressor(
        n_estimators=500, learning_rate=0.05, num_leaves=15,
        subsample=0.8, colsample_bytree=0.6, min_child_samples=200,
        reg_lambda=1.0, random_state=0)
    model.fit(tr[feature_cols], tr[target_col],
              eval_set=[(va[feature_cols], va[target_col])],
              eval_metric="l2", callbacks=[lgb.early_stopping(30, verbose=False)])
    gain = pd.Series(model.booster_.feature_importance("gain"),
                     index=feature_cols).sort_values(ascending=False)
    perm = block_permutation_importance(model, va[feature_cols], va[target_col])
    return gain, perm

# ---- 代码块 4：代码实现 ----

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
    d = raw.squeeze()[["Open", "High", "Low", "Close", "Volume"]].copy()
    d.columns = ["open", "high", "low", "close", "volume"]
    d["code"] = code
    d["forward_5"] = d["close"].pct_change().shift(-5)
    frames.append(d.reset_index().rename(columns={"Date": "date"}))

panel = pd.concat(frames, ignore_index=True)
base_cols = ["open", "high", "low", "close", "volume"]

# 逐标的生成特征库，避免跨标的时间错位
zoo_list = []
for code, g in panel.groupby("code"):
    z = build_zoo(g.reset_index(drop=True), base_cols)
    z["code"] = code
    zoo_list.append(z)

# ---- 代码块 5：代码实现 ----

import numpy as np
import matplotlib
matplotlib.rcParams["font.sans-serif"] = ["PingFang SC", "SimHei", "Arial Unicode MS"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt

zoo = pd.concat(zoo_list, ignore_index=True)
cand = [c for c in zoo.columns if c not in ("code",)]

# 第一层：先验筛选
cand = screen_by_prior(cand)
# 第二层：统计筛选
cand = screen_by_stats(zoo.loc[:, cand], cand)

# 把特征库与标签并在一个面板里
full = pd.concat([zoo[cand + ["code"]],
                  panel[["code", "date", "forward_5"]]], axis=1).dropna()

# 第三层：模型驱动筛选
gain, perm = train_and_rank(full, cand, "forward_5", split_date="2024-09-01")
top = gain.head(15).index

fig, ax = plt.subplots(figsize=(9, 5))
x = np.arange(len(top))
ax.barh(x - 0.2, gain[top], height=0.4, label="gain 重要性")
ax.barh(x + 0.2, perm.reindex(top).fillna(0), height=0.4, label="分块排列重要性")
ax.set_yticks(x)
ax.set_yticklabels(top, fontsize=8)
ax.invert_yaxis()
ax.set_title("两套特征重要性对照（示意）")
ax.legend()
plt.tight_layout()
plt.show()
