# ============================================================
# 第040章 跨类别组合的量化验证
# 模块 07 跨类组合
# 源文件：模块07-跨类组合/第040章-跨类别组合的量化验证.md
# ============================================================
# 本文件由 scripts/extract_code.py 自动生成，请勿直接编辑。
# 修改代码请改 Markdown 源稿，再重新运行提取脚本。
#
# 依赖：先加载同目录下的公共函数与数据准备
#   exec(open("code/python/00-common.py").read())
#   exec(open("code/python/00-data.py").read())
#
# ------------------------------------------------------------

# ---- 代码块 1：跨类组合的互补性来源 ----

# 四类代表特征的横截面平均相关系数
feats = ["sma_dev", "rsi_dev", "atr_rank", "obv_change"]

# 先做横截面标准化，再按日计算相关矩阵并求平均
z = panel.copy()
for c in feats:
    z[c] = z.groupby("date")[c].transform(
        lambda s: (s - s.median()) / (s - s.median()).abs().median()
        if (s - s.median()).abs().median() > 0 else 0)

corr_daily = z.groupby("date")[feats].corr()
avg_corr = corr_daily.groupby(level=1).mean()
print(avg_corr.round(2))

# ---- 代码块 2：跨类组合的互补性来源 ----

# 正交化：把震荡特征对趋势特征回归后的残差作为增量因子
import numpy as np

resid = []
for _, gg in panel.groupby("date"):
    d = gg.dropna(subset=["sma_dev", "rsi_dev"])
    if len(d) < 5:
        resid.append(pd.Series(np.nan, index=d.index))
        continue
    x = np.column_stack([np.ones(len(d)), d["sma_dev"]])
    beta, *_ = np.linalg.lstsq(x, d["rsi_dev"], rcond=None)
    resid.append(pd.Series(d["rsi_dev"] - x @ beta, index=d.index))
panel["rsi_resid"] = pd.concat(resid).reindex(panel.index)

print(ic_summary(cross_section_ic(panel, "rsi_resid", "forward_5")))
# 残差因子的 IC 若仍为正，说明震荡特征含有趋势之外的信息

# ---- 代码块 3：组合方法及其检验 ----

# 等权合成：weights 留空
panel = combined_signal(panel, ["sma_dev", "rsi_dev", "atr_rank", "obv_change"])
ic_eq = cross_section_ic(panel, "combined", "forward_5")
print(ic_summary(ic_eq))
# 与四个单特征的 ICIR 并列，判断组合是否高于上界

# ---- 代码块 4：组合方法及其检验 ----

# IC 加权：先用单特征 IC 均值构造权重
feats = ["sma_dev", "rsi_dev", "atr_rank", "obv_change"]
ic_means = {c: cross_section_ic(panel, c, "forward_5").mean() for c in feats}
total = sum(abs(v) for v in ic_means.values())
w_ic = [ic_means[c] / total for c in feats]
print(dict(zip(feats, [round(w, 3) for w in w_ic])))

panel = combined_signal(panel, feats, weights=w_ic)
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))

# ---- 代码块 5：组合方法及其检验 ----

# ICIR 加权：用 IC 均值与 IC 标准差构造权重
feats = ["sma_dev", "rsi_dev", "atr_rank", "obv_change"]
icirs = {}
for c in feats:
    ic = cross_section_ic(panel, c, "forward_5")
    icirs[c] = ic.mean() / ic.std()
total = sum(icirs.values())
w_icir = [icirs[c] / total for c in feats]

panel = combined_signal(panel, feats, weights=w_icir)
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))

# ---- 代码块 6：组合方法及其检验 ----

from scipy.optimize import minimize

feats = ["sma_dev", "rsi_dev", "atr_rank", "obv_change"]
ic_mat = pd.concat(
    [cross_section_ic(panel, c, "forward_5").rename(c) for c in feats], axis=1)
mu = ic_mat.mean().values
sigma = ic_mat.cov().values

def neg_ratio(w):
    return -(w @ mu) / np.sqrt(w @ sigma @ w + 1e-12)

cons = [{"type": "eq", "fun": lambda w: w.sum() - 1}]
bounds = [(0.0, 0.5)] * len(feats)          # 单特征权重上限，抑制极端解
res = minimize(neg_ratio, np.ones(len(feats)) / len(feats),
               bounds=bounds, constraints=cons)
print(dict(zip(feats, res.x.round(3))))

# ---- 代码块 7：组合方法及其检验 ----

# 条件组合：用趋势状态做掩码，只在趋势成立时启用震荡信号
# 掩码变量：价格是否在 20 日均线上方（sma_dev 大于零）
panel["mask"] = (panel["sma_dev"] > 0).astype(int)

for v in [0, 1]:
    sub = panel[panel["mask"] == v]
    ic_sub = cross_section_ic(sub, "rsi_dev", "forward_5")
    print("掩码取值", v, ic_summary(ic_sub)["IC均值"], ic_summary(ic_sub)["ICIR"])

# 与全样本的无条件 IC 对照
print("无条件", ic_summary(cross_section_ic(panel, "rsi_dev", "forward_5"))["ICIR"])

# ---- 代码块 8：组合方法及其检验 ----

# 分层组合的 Python 写法：先类内，再类间
classes = {
    "s_trend": ["sma_dev"],
    "s_osc": ["rsi_dev"],
    "s_vol": ["atr_rank"],
    "s_vp": ["obv_change"],
}
for name, cols in classes.items():
    panel = combined_signal(panel, cols)
    panel = panel.rename(columns={"combined": name})

# 类间等权合成
panel["combined"] = panel[list(classes)].mean(axis=1)
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
# 若某两个类别分数相关性很高，可改为 ICIR 加权或只保留其中一个类别

# ---- 代码块 9：组合增益的归因 ----

# 增益归因：分别比较组合与单特征的三个量
def triple(panel, col):
    s = ic_summary(cross_section_ic(panel, col, "forward_5"))
    return s[["IC均值", "IC标准差", "ICIR"]]

panel = combined_signal(panel, ["sma_dev", "rsi_dev"])
out = pd.DataFrame({
    "甲": triple(panel, "sma_dev"),
    "乙": triple(panel, "rsi_dev"),
    "组合": triple(panel, "combined"),
})
print(out)
# 判读：IC 均值上升且标准差基本不变，倾向信息互补
#       均值不变而标准差下降，倾向风险分散
#       样本内三项都明显更优但样本外回落，倾向权重拟合

# ---- 代码块 10：组合增益的归因 ----

# 样本内外对照：识别权重拟合
cut = panel["date"].quantile(0.6)            # 前 60% 作样本内，后 40% 作样本外
in_s, out_s = panel[panel["date"] <= cut], panel[panel["date"] > cut]

def icir_of(df, col):
    ic = cross_section_ic(df, col, "forward_5")
    return ic.mean() / ic.std()

panel = combined_signal(panel, ["sma_dev", "rsi_dev"])       # 等权组合
print("样本内 等权", icir_of(in_s.assign(combined=panel.loc[in_s.index, "combined"]), "combined"))
print("样本外 等权", icir_of(out_s.assign(combined=panel.loc[out_s.index, "combined"]), "combined"))
# 再用样本内估计的 ICIR 权重合成，重算两段，比较样本内外的差距是否扩大

# ---- 代码块 11：组合的截面验证 ----

import numpy as np
import pandas as pd

# panel 由第 007 章的数据获取代码得到，含 date / code / close / high / low / volume
g = panel.groupby("code")

# 趋势：价格相对 20 日均线的偏离度
panel["sma_dev"] = panel["close"] / g["close"].transform(lambda s: s.rolling(20).mean()) - 1

# 震荡：14 日 RSI 相对中轴的偏离
up = g["close"].transform(lambda s: s.diff().clip(lower=0).ewm(alpha=1/14, adjust=False).mean())
dn = g["close"].transform(lambda s: (-s.diff().clip(upper=0)).ewm(alpha=1/14, adjust=False).mean())
panel["rsi_dev"] = (100 - 100 / (1 + up / dn)) - 50

# 波动率：14 日 ATR 占价格的比率，再取横截面分位
tr = pd.concat([(panel["high"] - panel["low"]),
                (panel["high"] - g["close"].shift()).abs(),
                (panel["low"] - g["close"].shift()).abs()], axis=1).max(axis=1)
panel["atr_ratio"] = tr.groupby(panel["code"]).transform(
    lambda s: s.ewm(alpha=1/14, adjust=False).mean()) / panel["close"]
panel["atr_rank"] = panel.groupby("date")["atr_ratio"].transform(lambda s: s.rank(pct=True))

# 量价：OBV 的 10 日变化率
sign = np.sign(panel.groupby("code")["close"].diff().fillna(0))
panel["obv"] = (sign * panel["volume"]).groupby(panel["code"]).cumsum()
panel["obv_change"] = panel.groupby("code")["obv"].transform(
    lambda s: s.diff(10) / s.shift(10).abs())

# ---- 代码块 12：组合的截面验证 ----

# 分步合成：从两个特征开始，逐个加入
steps = [["sma_dev", "rsi_dev"],
         ["sma_dev", "rsi_dev", "atr_rank"],
         ["sma_dev", "rsi_dev", "atr_rank", "obv_change"]]

for cols in steps:
    panel = combined_signal(panel, cols)
    # 去极值：标准化后的列截断在正负 3 之间，再重新平均
    zcols = [c for c in panel.columns if c.endswith("_z")]
    panel[zcols] = panel[zcols].clip(-3, 3)
    panel["combined"] = panel[zcols].mean(axis=1)
    ic_c = cross_section_ic(panel, "combined", "forward_5")
    print(len(cols), ic_summary(ic_c).to_dict())

# ---- 代码块 13：组合的截面验证 ----

import matplotlib
matplotlib.rcParams["font.sans-serif"] = ["PingFang SC", "SimHei", "Arial Unicode MS"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt

labels = ["趋势", "加震荡", "加波动率", "加量价"]
combos = [["sma_dev"], ["sma_dev", "rsi_dev"],
          ["sma_dev", "rsi_dev", "atr_rank"],
          ["sma_dev", "rsi_dev", "atr_rank", "obv_change"]]
icir_vals, mean_vals = [], []
for cols in combos:
    panel = combined_signal(panel, cols)
    s = ic_summary(cross_section_ic(panel, "combined", "forward_5"))
    icir_vals.append(s["ICIR"])
    mean_vals.append(s["IC均值"])

ax = pd.DataFrame({"ICIR": icir_vals, "IC均值": mean_vals},
                  index=labels).plot(kind="bar", secondary_y="IC均值")
ax.set_title("分步合成的边际贡献（示意）")
ax.set_ylabel("ICIR")
ax.right_ax.set_ylabel("IC 均值")
plt.tight_layout()
plt.show()

# ---- 代码块 14：组合的择时验证 ----

# 把截面组合分数聚合成市场时序信号
panel = combined_signal(panel, ["sma_dev", "rsi_dev", "atr_rank", "obv_change"])
market = panel.groupby("date").agg(
    mkt_signal=("combined", "median"),      # 横截面中位数，代表市场整体状态
    mkt_ret=("forward_1", "mean"),          # 等权平均的前向收益，作为市场收益代理
).reset_index()

# 与单个趋势特征的择时结果对照
single = panel.groupby("date").agg(
    mkt_signal=("sma_dev", "median"),
    mkt_ret=("forward_1", "mean"),
).reset_index()

print("组合信号：", timing_backtest(market, "mkt_signal", "mkt_ret", entry_q=0.7))
print("单趋势信号：", timing_backtest(single, "mkt_signal", "mkt_ret", entry_q=0.7))
print("条件分位：", conditional_quantile_return(market, "mkt_signal", "mkt_ret", q=5))

# ---- 代码块 15：组合的择时验证 ----

import matplotlib
matplotlib.rcParams["font.sans-serif"] = ["PingFang SC", "SimHei", "Arial Unicode MS"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt

thr = market["mkt_signal"].quantile(0.7)
market["pos"] = (market["mkt_signal"] > thr).astype(int)
market["strat"] = market["pos"].shift(1).fillna(0) * market["mkt_ret"]
curve = pd.DataFrame({
    "组合择时": (1 + market["strat"].fillna(0)).cumprod(),
    "买入持有": (1 + market["mkt_ret"].fillna(0)).cumprod(),
}, index=pd.to_datetime(market["date"]))
curve.plot(title="组合信号择时与买入持有对照（示意）")
plt.ylabel("净值")
plt.tight_layout()
plt.show()
