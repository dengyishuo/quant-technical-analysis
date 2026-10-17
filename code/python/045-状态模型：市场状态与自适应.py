# ============================================================
# 第045章 状态模型：市场状态与自适应
# 模块 08 机器学习挖掘与融合
# 源文件：模块08-机器学习挖掘与融合/第045章-状态模型：市场状态与自适应.md
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
    d["ret1"] = d["close"].pct_change()
    d["vol20"] = d["ret1"].rolling(20).std()
    # 简化的趋势强度：价格偏离二十日均线的绝对值，再平滑
    d["ma20"] = d["close"].rolling(20).mean()
    d["trend"] = (d["close"] / d["ma20"] - 1).abs().rolling(14).mean() * 100
    d["forward_5"] = d["close"].pct_change().shift(-5)
    frames.append(d.reset_index().rename(columns={"Date": "date"}))

panel = pd.concat(frames, ignore_index=True).dropna(subset=["vol20", "trend"])

# 市场层的状态变量：横截面均值，代表整体市况
market = panel.groupby("date").agg(
    mvol=("vol20", "mean"), mtrend=("trend", "mean")).reset_index()

# 波动率分位用滚动窗口计算，避免全样本分位带来的未来信息
W = 120
market["vol_pct"] = market["mvol"].rolling(W, min_periods=40).apply(
    lambda x: (x[-1] > x).mean(), raw=True)
market["state_rule"] = np.select(
    [(market["vol_pct"] >= 0.5) & (market["mtrend"] >= market["mtrend"].median()),
     (market["vol_pct"] < 0.5) & (market["mtrend"] >= market["mtrend"].median()),
     (market["vol_pct"] >= 0.5) & (market["mtrend"] < market["mtrend"].median())],
    ["高波趋势", "低波趋势", "高波震荡"], default="低波震荡")

panel = panel.merge(market[["date", "state_rule"]], on="date", how="left")
print(panel["state_rule"].value_counts())

# ---- 代码块 2：代码实现 ----

from scipy import stats

def cross_section_ic(panel, factor_col, ret_col, date_col="date"):
    """沿用第 007 章的横截面 IC 序列。"""
    def _ic(g):
        sub = g.dropna(subset=[factor_col, ret_col])
        return stats.spearmanr(sub[factor_col], sub[ret_col])[0] if len(sub) >= 5 else np.nan
    return panel.groupby(date_col).apply(_ic).dropna()

def ic_summary(ic):
    """沿用第 007 章的 IC 汇总。"""
    m, s = ic.mean(), ic.std()
    icir = m / s if s > 0 else np.nan
    return pd.Series({"IC均值": round(m, 4), "IC标准差": round(s, 4),
                      "ICIR": round(icir, 3), "样本期数": len(ic)})

panel["sma20"] = panel.groupby("code")["close"].transform(lambda s: s.rolling(20).mean())
panel["sma_dev"] = panel["close"] / panel["sma20"] - 1

# 分状态计算同一个因子的 IC
for st, sub in panel.groupby("state_rule"):
    s = ic_summary(cross_section_ic(sub, "sma_dev", "forward_5"))
    print(st, s.to_dict())

# ---- 代码块 3：代码实现 ----

from hmmlearn.hmm import GaussianHMM

# 状态变量：滚动波动率与趋势强度
X = market[["mvol", "mtrend"]].dropna().to_numpy()
dates = market.loc[market[["mvol", "mtrend"]].notna().all(axis=1), "date"].to_numpy()

split = np.datetime64("2024-08-01")
tr_mask = dates <= split

# 标准化统计量只用训练期，避免泄漏
mu, sd = X[tr_mask].mean(axis=0), X[tr_mask].std(axis=0) + 1e-9
Xs = (X - mu) / sd

# 只用训练期估计参数
model = GaussianHMM(n_components=3, covariance_type="diag",
                    n_iter=200, random_state=0).fit(Xs[tr_mask])

# 验证期逐时点解码：用滤波概率取当期最可能状态
post = model.predict_proba(Xs)          # 每时点在三个状态上的后验概率
state_hmm = post.argmax(axis=1)

print("转移矩阵\n", pd.DataFrame(model.transmat_,
      index=[f"s{i}" for i in range(3)], columns=[f"s{i}" for i in range(3)]).round(3))
print("各状态出现天数", np.bincount(state_hmm, minlength=3))

# ---- 代码块 4：代码实现 ----

import matplotlib
matplotlib.rcParams["font.sans-serif"] = ["PingFang SC", "SimHei", "Arial Unicode MS"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt

m = market.loc[market[["mvol", "mtrend"]].notna().all(axis=1)].copy()
m["date"] = pd.to_datetime(m["date"])
m["state_hmm"] = state_hmm

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
ax1.plot(m["date"], m["mvol"], color="steelblue")
ax1.set_ylabel("市场平均波动率")
ax1.set_title("HMM 状态与波动率（示意）")
ax2.scatter(m["date"], m["state_hmm"], c=m["state_hmm"], cmap="tab10", s=8)
ax2.set_yticks([0, 1, 2])
ax2.set_ylabel("状态编号")
plt.tight_layout()
plt.show()

# ---- 代码块 5：代码实现 ----

def state_weights(panel, feats, state_col, lam=0.5):
    """按状态估计权重，向全样本 ICIR 权重收缩。状态内用 ICIR 加权而非最优化。"""
    glob = {}
    for c in feats:
        ic = cross_section_ic(panel, c, "forward_5")
        glob[c] = ic.mean() / ic.std() if ic.std() > 0 else 0.0
    g_sum = sum(abs(v) for v in glob.values()) or 1.0
    w_global = {c: glob[c] / g_sum for c in feats}

    out = {}
    for st, sub in panel.groupby(state_col):
        w = {}
        for c in feats:
            ic = cross_section_ic(sub, c, "forward_5")
            w[c] = ic.mean() / ic.std() if ic.std() > 0 else 0.0
        s_sum = sum(abs(v) for v in w.values()) or 1.0
        w_state = {c: w[c] / s_sum for c in feats}
        # 向全样本权重收缩
        out[st] = {c: (1 - lam) * w_state[c] + lam * w_global[c] for c in feats}
    return out

feats = ["sma_dev", "vol20"]     # 示意用两个因子
w_by_state = state_weights(panel, feats, "state_rule", lam=0.5)
for st, w in w_by_state.items():
    print(st, {k: round(v, 3) for k, v in w.items()})
