# ============================================================
# 第007章 定义的 Python 公共函数（IC 汇总 / 分层回测 / 择时检验 / 组合合成）
#
# 本文件由 scripts/extract_code.py 自动生成，请勿直接编辑。
# 修改代码请改 Markdown 源稿（模块02-因子检验方法/第007章），再重新运行提取脚本。
# ============================================================
import numpy as np
import pandas as pd
from scipy import stats


def cross_section_ic(panel, factor_col, ret_col, date_col="date"):
    """计算横截面 IC 序列。panel 需含 date / code / factor_col / ret_col。"""
    def _ic(g):
        sub = g.dropna(subset=[factor_col, ret_col])
        if len(sub) < 5:
            return np.nan
        rho, _ = stats.spearmanr(sub[factor_col], sub[ret_col])
        return rho
    ic = panel.groupby(date_col).apply(_ic)
    return ic.dropna()


def ic_summary(ic):
    """汇总 IC 序列的统计量。"""
    mean_ic = ic.mean()
    std_ic = ic.std()
    icir = mean_ic / std_ic if std_ic > 0 else np.nan
    t_stat = icir * np.sqrt(len(ic))
    win_rate = (ic > 0).mean()
    return pd.Series({
        "IC均值": round(mean_ic, 4),
        "IC标准差": round(std_ic, 4),
        "ICIR": round(icir, 3),
        "t统计量": round(t_stat, 2),
        "IC大于零比例": round(win_rate, 3),
        "样本期数": len(ic),
    })


def layered_returns(panel, factor_col, ret_col, q=5, date_col="date"):
    """分层回测，返回各组的平均收益与单调性。"""
    def _assign(g):
        g = g.dropna(subset=[factor_col, ret_col]).copy()
        if len(g) < q:
            return None
        g["group"] = pd.qcut(g[factor_col].rank(method="first"), q, labels=False) + 1
        return g
    tmp = panel.groupby(date_col, group_keys=False).apply(_assign).dropna(subset=["group"])
    grp_ret = tmp.groupby(["date", "group"])[ret_col].mean().unstack()
    group_mean = grp_ret.mean()
    mono, _ = stats.spearmanr(group_mean.index.values, group_mean.values)
    return group_mean, round(mono, 3)


def timing_signal_test(df, factor_col, ret_col, upper=0.8, lower=0.2):
    """择时检验：极端分位触发日与非触发日的收益差异（Welch t 检验）。"""
    f = df[factor_col].dropna()
    hi = f.quantile(upper)
    lo = f.quantile(lower)
    trig = df.loc[f.index, ret_col][f >= hi].dropna()
    rest = df.loc[f.index, ret_col][f < hi].dropna()
    t_stat, p_val = stats.ttest_ind(trig, rest, equal_var=False)
    return pd.Series({
        "触发日数": len(trig),
        "触发日平均收益": round(trig.mean() * 100, 3),
        "非触发日平均收益": round(rest.mean() * 100, 3),
        "差异t统计量": round(t_stat, 2),
        "p值": round(p_val, 4),
    })


def conditional_quantile_return(df, factor_col, ret_col, q=5):
    """择时检验：特征时序分档后的条件平均收益。"""
    tmp = df[[factor_col, ret_col]].dropna().copy()
    tmp["bucket"] = pd.qcut(tmp[factor_col].rank(method="first"), q, labels=False) + 1
    return tmp.groupby("bucket")[ret_col].agg(["mean", "count"]).round(4)


def timing_backtest(df, factor_col, ret_col, entry_q=0.7):
    """择时策略：特征值高于分位阈值时持仓，否则空仓，并与买入持有对比。"""
    tmp = df[[factor_col, ret_col]].dropna().copy()
    thr = tmp[factor_col].quantile(entry_q)
    tmp["pos"] = (tmp[factor_col] > thr).astype(int)
    tmp["strat"] = tmp["pos"].shift(1).fillna(0) * tmp[ret_col]
    def _stats(r):
        ann = (1 + r).prod() ** (252 / len(r)) - 1
        sharpe = r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else np.nan
        cum = (1 + r).cumprod()
        mdd = ((cum / cum.cummax()) - 1).min()
        return round(ann, 4), round(sharpe, 2), round(mdd, 4)
    s_ann, s_sh, s_mdd = _stats(tmp["strat"])
    b_ann, b_sh, b_mdd = _stats(tmp[ret_col])
    return pd.DataFrame({
        "策略": [s_ann, s_sh, s_mdd],
        "买入持有": [b_ann, b_sh, b_mdd],
    }, index=["年化收益", "夏普", "最大回撤"])


def combined_signal(panel, factor_cols, weights=None, date_col="date"):
    """加权型组合：横截面标准化后加权求和。"""
    df = panel.copy()

    def _z(s):
        # 绝对中位差用显式计算：pandas 2.0 起已移除 Series.mad()
        m = (s - s.median()).abs().median()
        return (s - s.median()) / m if m and m > 0 else 0.0

    z_cols = []
    for c in factor_cols:
        zc = c + "_z"
        df[zc] = df.groupby(date_col)[c].transform(_z)
        z_cols.append(zc)
    w = np.ones(len(z_cols)) / len(z_cols) if weights is None else np.array(weights)
    df["combined"] = (df[z_cols] * w).sum(axis=1)
    return df
