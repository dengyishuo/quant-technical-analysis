# ============================================================
# 第022章 随机指标（KDJ）
# 模块 04 震荡类指标
# 源文件：模块04-震荡类指标/第022章-随机指标（KDJ）.md
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
data = (_panel[_panel["code"] == "600519.SS"]
        .set_index("date").sort_index()[["open", "high", "low", "close", "volume"]])
data.columns = ["Open", "High", "Low", "Close", "Volume"]
high  = data["High"].squeeze()
low   = data["Low"].squeeze()
close = data["Close"].squeeze()

# 2. 计算 KDJ（n=9, m1=3, m2=3）
def kdj(high, low, close, n=9, m1=3, m2=3):
    hh = high.rolling(n).max()
    ll = low.rolling(n).min()
    rsv = (close - ll) / (hh - ll) * 100
    rsv = rsv.fillna(50)
    # 递推平滑：(m-1)/m * prev + 1/m * cur 等价于 alpha = 1/m 的 ewm
    k = rsv.ewm(alpha=1 / m1, adjust=False).mean()
    d = k.ewm(alpha=1 / m2, adjust=False).mean()
    j = 3 * k - 2 * d
    return rsv, k, d, j

df = pd.DataFrame({"high": high, "low": low, "close": close})
df["rsv"], df["k"], df["d"], df["j"] = kdj(df["high"], df["low"], df["close"])

# 3. 识别信号
df["golden"] = (df["k"] > df["d"]) & (df["k"].shift(1) <= df["d"].shift(1))
df["low_golden"] = df["golden"] & (df["k"] < 50)
print(f"金叉次数：{df['golden'].sum()}  其中低位金叉：{df['low_golden'].sum()}")
print(f"J 越过 100 次数：{(df['j'] > 100).sum()}  J 跌破 0 次数：{(df['j'] < 0).sum()}")

# 4. 绘图
import matplotlib
matplotlib.rcParams["font.sans-serif"] = ["PingFang SC", "SimHei", "Arial Unicode MS"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                               gridspec_kw={"height_ratios": [2, 1]})
ax1.plot(df.index, df["close"], color="#333", linewidth=1)
ax1.set_title("贵州茅台 收盘价与 KDJ")
ax2.plot(df.index, df["k"], label="K", color="#2f6fb5")
ax2.plot(df.index, df["d"], label="D", color="#c0392b")
ax2.plot(df.index, df["j"], label="J", color="#27ae60", linewidth=1)
ax2.axhline(80, color="#999", linestyle="--", linewidth=0.8)
ax2.axhline(20, color="#999", linestyle="--", linewidth=0.8)
ax2.legend()
plt.tight_layout()
plt.show()

# 5. 输出统计
extreme = ((df["k"] > 80) | (df["k"] < 20)).sum()
print("K 线处于极端区域的占比：", round(extreme / df["k"].notna().sum(), 3))

# ---- 代码块 2：拆解 ----

# 沿用第 007 章的数据准备（panel 含 date / code / close / high / low / volume）
import numpy as np
import pandas as pd

panel = panel.sort_values(["code", "date"]).reset_index(drop=True)
grp = panel.groupby("code")

hh9 = grp["high"].transform(lambda s: s.rolling(9).max())
ll9 = grp["low"].transform(lambda s: s.rolling(9).min())
rsv9 = ((panel["close"] - ll9) / (hh9 - ll9) * 100).where(hh9 != ll9, 50)

# 递推平滑：(m-1)/m * prev + 1/m * cur，等价于 alpha = 1/3 的 ewm
panel["k9"] = rsv9.groupby(panel["code"]).transform(
    lambda s: s.ewm(alpha=1 / 3, adjust=False).mean())
panel["d9"] = panel["k9"].groupby(panel["code"]).transform(
    lambda s: s.ewm(alpha=1 / 3, adjust=False).mean())

panel["kdj_pos"] = panel["k9"] - 50                     # 位置偏离
panel["kdj_diff"] = panel["k9"] - panel["d9"]           # 柱状值
panel["kdj_j"] = 3 * panel["k9"] - 2 * panel["d9"]      # J 值，可越界
panel["kdj_j_clip"] = panel["kdj_j"].clip(0, 100)       # 截断后的 J 值
panel["kdj_cross"] = (panel["k9"] > panel["d9"]).astype(int)  # K 在 D 上方记 1

print(panel.dropna(subset=["kdj_diff"]).head(8)[
    ["date", "code", "kdj_pos", "kdj_diff", "kdj_j", "kdj_j_clip", "kdj_cross"]])

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# panel 含 date / code / high / low / close / forward_1 / forward_5
grp = panel.groupby("code")
hh = grp["high"].transform(lambda s: s.rolling(9).max())
ll = grp["low"].transform(lambda s: s.rolling(9).min())
rsv = ((panel["close"] - ll) / (hh - ll) * 100).where(hh != ll, 50)

# 递推平滑：(m-1)/m * prev + 1/m * cur，等价于 alpha = 1/m 的 ewm
panel["k9"] = rsv.groupby(panel["code"]).transform(
    lambda s: s.ewm(alpha=1 / 3, adjust=False).mean())
panel["d9"] = panel["k9"].groupby(panel["code"]).transform(
    lambda s: s.ewm(alpha=1 / 3, adjust=False).mean())
panel["kdj_pos"] = panel["k9"] - 50
panel["kdj_diff"] = panel["k9"] - panel["d9"]

for h in ["forward_1", "forward_5"]:
    print(f"\n--- 柱状值 vs {h} ---")
    print(ic_summary(cross_section_ic(panel, "kdj_diff", h)))
print(layered_returns(panel, "kdj_diff", "forward_1"))

# 符号稳定性：按年切分
panel["year"] = pd.to_datetime(panel["date"]).dt.year
for y, g in panel.groupby("year"):
    print(y, round(cross_section_ic(g, "kdj_diff", "forward_5").mean(), 4))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df = panel[panel["code"] == "600519.SS"].copy()
df["golden"] = (df["k9"] > df["d9"]) & (df["k9"].shift(1) <= df["d9"].shift(1))

# 金叉按 K 的位置分组，两类交叉的含义相反
sub = df[df["golden"]]
g = sub.groupby(np.where(sub["k9"] >= 50, "高位", "低位"))["forward_5"]
print(g.agg(["count", "mean"]).round(4))

print("\n--- 信号触发日检验（柱状值高于 80 分位）---")
print(timing_signal_test(df, "kdj_diff", "forward_5", upper=0.8))

print("\n--- 条件分位收益（位置偏离分五档）---")
print(conditional_quantile_return(df, "kdj_pos", "forward_5", q=5))

print("\n--- 择时策略与买入持有对照 ---")
print(timing_backtest(df, "kdj_diff", "forward_5", entry_q=0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal / cross_section_ic / timing_backtest
# ADX 按 Wilder 口径就地实现，作为市况开关
def adx(high, low, close, n=14):
    up, dn = high.diff(), -low.diff()
    plus_dm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=high.index)
    minus_dm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=high.index)
    tr = pd.concat([high - low, (high - close.shift()).abs(),
                    (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / n, adjust=False).mean()
    pdi = 100 * plus_dm.ewm(alpha=1 / n, adjust=False).mean() / atr
    mdi = 100 * minus_dm.ewm(alpha=1 / n, adjust=False).mean() / atr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False).mean()

# 截面路径：KDJ 柱状值与价格对均线偏离的组合
panel["sma20"] = panel.groupby("code")["close"].transform(lambda s: s.rolling(20).mean())
panel["sma_dev"] = panel["close"] / panel["sma20"] - 1

rho = panel.groupby("date").apply(
    lambda g: g[["kdj_diff", "sma_dev"]].corr(method="spearman").iloc[0, 1])
print("两个特征的平均横截面相关：", round(rho.mean(), 3))

panel = combined_signal(panel, ["kdj_diff", "sma_dev"])

print("\n--- 组合 vs 单特征 ---")
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "kdj_diff", "forward_5")))
print(ic_summary(cross_section_ic(panel, "sma_dev", "forward_5")))

# 择时路径：只在 ADX 低于 40 时接受交叉信号
df = panel[panel["code"] == "600519.SS"].copy()
df["adx14"] = adx(df["high"], df["low"], df["close"], 14)
df["kdj_calm"] = np.where(df["adx14"] < 40, df["kdj_diff"], np.nan)

print("\n--- 弱趋势样本内的择时 ---")
print(timing_backtest(df, "kdj_calm", "forward_5", entry_q=0.7))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
# 趋势过滤：价格在 20 日均线上方，且 K 上穿 D 时持仓
df = panel[panel["code"] == "600519.SS"].sort_values("date").copy()
df["sma20"] = df["close"].rolling(20).mean()
df["golden"] = (df["k9"] > df["d9"]) & (df["k9"].shift(1) <= df["d9"].shift(1))
df["cond"] = ((df["close"] > df["sma20"]) & df["golden"]).astype(int)

print(timing_backtest(df, "cond", "forward_5", entry_q=0.5))
