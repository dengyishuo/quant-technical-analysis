# ============================================================
# 第047章 稳健性：过拟合识别与模型衰减
# 模块 08 机器学习挖掘与融合
# 源文件：模块08-机器学习挖掘与融合/第047章-稳健性：过拟合识别与模型衰减.md
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

def purged_splits(dates, n_splits=4, label_horizon=5, embargo=5):
    """按时间切分并返回各折的训练与测试索引。
    dates 为按时间排序的唯一交易日；label_horizon 为标签持有期（交易日）；
    embargo 为禁运宽度（交易日）。训练样本剔除标签区间与测试重叠的部分。"""
    dates = np.sort(np.asarray(dates))
    bounds = np.array_split(dates, n_splits)
    splits = []
    for i in range(1, len(bounds)):
        test_dates = bounds[i]
        train_dates = np.concatenate(bounds[:i])
        t0, t1 = test_dates[0], test_dates[-1]
        # 测试标签区间上界：测试最后一天加上持有期
        test_label_end = np.datetime64(t1) + np.timedelta64(label_horizon, "D")
        # 净化：训练样本的标签区间若延伸进测试标签区间，则剔除
        keep = []
        for d in train_dates:
            train_label_end = np.datetime64(d) + np.timedelta64(label_horizon, "D")
            if train_label_end < np.datetime64(t0):
                keep.append(d)
        # 禁运：测试块之后再剔除一段，防止特征自相关传递
        embargo_start = test_label_end
        embargo_end = embargo_start + np.timedelta64(embargo, "D")
        keep = [d for d in keep if not (np.datetime64(d) >= embargo_start
                                         and np.datetime64(d) <= embargo_end)]
        splits.append((np.array(keep), test_dates))
    return splits

# ---- 代码块 2：代码实现 ----

# 假设 panel 含 date / code / forward_5，且已按 date 排序
all_dates = np.sort(panel["date"].unique())
splits = purged_splits(all_dates, n_splits=4, label_horizon=5, embargo=5)
for k, (tr_d, te_d) in enumerate(splits):
    print(f"第 {k+1} 折：训练末日 {tr_d[-1]}，测试区间 {te_d[0]} 到 {te_d[-1]}")

# ---- 代码块 3：代码实现 ----

def avg_cross_corr(panel, ret_col="forward_5", date_col="date"):
    """标的间平均相关：整理成日期乘标的的收益矩阵，求相关矩阵后取上三角平均。
    注意这里算的是标的之间的相关，不是某个时点内两列因子的相关。
    后者在单时点上只有一个观测，估不出相关。"""
    wide = panel.pivot_table(index=date_col, columns="code", values=ret_col)
    corr = wide.corr(method="spearman")
    arr = corr.to_numpy()
    iu = np.triu_indices_from(arr, k=1)
    return float(np.nanmean(arr[iu]))

def effective_n(n_assets, avg_rho):
    """由标的数与平均相关估算有效样本量：相关越高，独立信息越少。"""
    return n_assets / (1 + (n_assets - 1) * avg_rho)

rho = avg_cross_corr(panel)
n_assets = panel["code"].nunique()
print("标的间平均相关", round(rho, 3),
      "有效标的数", round(effective_n(n_assets, rho), 2),
      "名义标的数", n_assets)

# ---- 代码块 4：代码实现 ----

from scipy import stats

def bh_correction(pvals, alpha=0.05):
    """Benjamini-Hochberg 假发现率校正，返回每个检验是否显著。"""
    p = np.asarray(pvals)
    order = np.argsort(p)
    n = len(p)
    thresh = alpha * (np.arange(1, n + 1) / n)
    passed = p[order] <= thresh
    # 取满足条件的最大序号，之前的都算显著
    k = np.where(passed)[0].max() + 1 if passed.any() else 0
    sig = np.zeros(n, dtype=bool)
    sig[order[:k]] = True
    return sig

# 示意：对若干候选因子做单因子 IC 检验，收集 t 统计量
def ic_tstat(panel, col, ret_col="forward_5", date_col="date"):
    def _ic(g):
        s = g.dropna(subset=[col, ret_col])
        return stats.spearmanr(s[col], s[ret_col])[0] if len(s) >= 5 else np.nan
    ic = panel.groupby(date_col).apply(_ic).dropna()
    return ic.mean() / ic.std() * np.sqrt(len(ic)) if ic.std() > 0 else np.nan

cands = ["ret5", "ma20_dev", "vol20", "vol_ratio"]     # 示意候选
ts = np.array([ic_tstat(panel, c) for c in cands])
pvals = 2 * (1 - stats.norm.cdf(np.abs(ts)))           # 双侧近似
sig = bh_correction(pvals, alpha=0.05)
print(pd.DataFrame({"因子": cands, "t": ts.round(2),
                    "p": pvals.round(4), "BH显著": sig}))

# ---- 代码块 5：代码实现 ----

import matplotlib
matplotlib.rcParams["font.sans-serif"] = ["PingFang SC", "SimHei", "Arial Unicode MS"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt

# 假设 score 为某模型在样本外的逐日预测，forward_5 为真实收益
def rolling_oos_ic(panel, score_col, ret_col="forward_5", date_col="date", window=60):
    def _ic(g):
        s = g.dropna(subset=[score_col, ret_col])
        return stats.spearmanr(s[score_col], s[ret_col])[0] if len(s) >= 5 else np.nan
    ic = panel.groupby(date_col).apply(_ic).dropna()
    return ic.rolling(window, min_periods=20).mean(), ic

score_col = "ret5"     # 以单因子作为监控对象的示意
roll, ic = rolling_oos_ic(panel, score_col)

fig, ax = plt.subplots(figsize=(9, 4))
ax.plot(pd.to_datetime(roll.index) if not np.issubdtype(roll.index.dtype, np.number)
        else roll.index, roll.values, label="滚动 60 期 IC 均值")
ax.axhline(0, color="gray", linewidth=1)
low = roll.quantile(0.1)
ax.axhline(low, color="red", linestyle="--", label="历史 10% 分位")
ax.set_title("滚动样本外 IC 监控（示意）")
ax.legend()
plt.tight_layout()
plt.show()
