# ============================================================
# 第023章 商品通道指数（CCI）
# 模块 04 震荡类指标
# 源文件：模块04-震荡类指标/第023章-商品通道指数（CCI）.md
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

# 2. 计算 CCI（手写平均绝对偏差）
def cci(high, low, close, n=20):
    tp = (high + low + close) / 3
    ma = tp.rolling(n).mean()
    mad = tp.rolling(n).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    return (tp - ma) / (0.015 * mad)

df = pd.DataFrame({"high": high, "low": low, "close": close})
df["cci20"] = cci(df["high"], df["low"], df["close"], 20)
df["cci14"] = cci(df["high"], df["low"], df["close"], 14)

# 3. 识别信号
df["over_100"] = (df["cci20"] > 100).astype(int)
df["under_-100"] = (df["cci20"] < -100).astype(int)
print(f"越过正 100 的交易日：{df['over_100'].sum()}")
print(f"跌破负 100 的交易日：{df['under_-100'].sum()}")
print(f"停留在正 200 以上的交易日：{(df['cci20'] > 200).sum()}")

# 4. 绘图
import matplotlib
matplotlib.rcParams["font.sans-serif"] = ["PingFang SC", "SimHei", "Arial Unicode MS"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                               gridspec_kw={"height_ratios": [2, 1]})
ax1.plot(df.index, df["close"], color="#333", linewidth=1)
ax1.set_title("贵州茅台 收盘价与 CCI")
ax2.plot(df.index, df["cci20"], label="CCI20", color="#2f6fb5")
for lv in (100, -100, 200, -200):
    ax2.axhline(lv, color="#bbb", linestyle="--", linewidth=0.8)
ax2.axhline(0, color="#888", linewidth=0.8)
ax2.legend()
plt.tight_layout()
plt.show()

# 5. 输出统计
print("CCI 落于正负 100 以内的占比：",
      round((df["cci20"].abs() < 100).sum() / df["cci20"].notna().sum(), 3))
print("CCI 标准差：", round(df["cci20"].std(), 2))

# ---- 代码块 2：拆解 ----

# 沿用第 007 章的数据准备（panel 含 date / code / close / high / low / volume）
import numpy as np
import pandas as pd

panel = panel.sort_values(["code", "date"]).reset_index(drop=True)

# 原始读数：典型价格偏离中枢，除以 0.015 倍平均绝对偏差
tp = (panel["high"] + panel["low"] + panel["close"]) / 3
ma20 = tp.groupby(panel["code"]).transform(lambda s: s.rolling(20).mean())
mad20 = tp.groupby(panel["code"]).transform(
    lambda s: s.rolling(20).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True))
panel["cci20"] = (tp - ma20) / (0.015 * mad20)

# 分位标准化：横截面中位数与中位绝对差，截断在正负 3
med = panel.groupby("date")["cci20"].transform("median")
mad = panel.groupby("date")["cci20"].transform(
    lambda s: (s - s.median()).abs().median())
panel["cci_z"] = ((panel["cci20"] - med) / mad.where(mad > 0, 1)).clip(-3, 3)

panel["cci_abs"] = panel["cci20"].abs()   # 偏离强度，不带方向

# 穿越状态：上穿 100 记 1，下穿负 100 记 -1，其余记 0
prev = panel.groupby("code")["cci20"].shift(1)
panel["cci_cross"] = np.select(
    [(panel["cci20"] > 100) & (prev <= 100),
     (panel["cci20"] < -100) & (prev >= -100)],
    [1, -1], default=0)

print(panel.dropna(subset=["cci20"]).head(8)[
    ["date", "code", "cci20", "cci_z", "cci_abs", "cci_cross"]])

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# panel 含 date / code / high / low / close / forward_1 / forward_5
import numpy as np

tp = (panel["high"] + panel["low"] + panel["close"]) / 3
ma20 = tp.groupby(panel["code"]).transform(lambda s: s.rolling(20).mean())
mad20 = tp.groupby(panel["code"]).transform(
    lambda s: s.rolling(20).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True))
panel["cci20"] = (tp - ma20) / (0.015 * mad20)

# 横截面标准化后截断在正负 3
panel["cci_z"] = panel.groupby("date")["cci20"].transform(
    lambda s: (s - s.median()) / ((s - s.median()).abs().median() or 1)).clip(-3, 3)

for h in ["forward_1", "forward_5"]:
    print(f"\n--- CCI 标准化值 vs {h} ---")
    print(ic_summary(cross_section_ic(panel, "cci_z", h)))

print(layered_returns(panel, "cci_z", "forward_5"))

# 符号稳定性：按年切分
panel["year"] = pd.to_datetime(panel["date"]).dt.year
for y, g in panel.groupby("year"):
    print(y, round(cross_section_ic(g, "cci_z", "forward_5").mean(), 4))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df = panel[panel["code"] == "600519.SS"].copy()
df["cci_neg"] = -df["cci_z"]

print("--- 顺势方向：读数高于 80 分位 ---")
print(timing_signal_test(df, "cci_z", "forward_5", upper=0.8))

print("\n--- 反转方向：取负后高于 80 分位 ---")
print(timing_signal_test(df, "cci_neg", "forward_5", upper=0.8))

print("\n--- 条件分位收益 ---")
print(conditional_quantile_return(df, "cci_z", "forward_5", q=5))

print("\n--- 顺势规则的回测 ---")
print(timing_backtest(df, "cci_z", "forward_5", entry_q=0.7))

print("\n--- 反转规则的回测 ---")
print(timing_backtest(df, "cci_neg", "forward_5", entry_q=0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal / cross_section_ic / timing_backtest
# ADX 按 Wilder 口径就地实现，与第 022 章相同
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

# 截面路径：先按市况给 CCI 定方向，再与均线偏离组合
panel["sma20"] = panel.groupby("code")["close"].transform(lambda s: s.rolling(20).mean())
panel["sma_dev"] = panel["close"] / panel["sma20"] - 1

# 每只标的各自计算 ADX，再按市况给 CCI 定方向
panel["adx14"] = pd.concat(
    [adx(g["high"], g["low"], g["close"], 14)
     for _, g in panel.groupby("code")]).sort_index()
panel["cci_signed"] = np.where(panel["adx14"] < 25, -panel["cci_z"], panel["cci_z"])

rho = panel.groupby("date").apply(
    lambda g: g[["cci_signed", "sma_dev"]].corr(method="spearman").iloc[0, 1])
print("两个特征的平均横截面相关：", round(rho.mean(), 3))

panel = combined_signal(panel, ["cci_signed", "sma_dev"])

print("\n--- 组合 vs 单特征 ---")
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "cci_signed", "forward_5")))
print(ic_summary(cross_section_ic(panel, "sma_dev", "forward_5")))

# 择时路径：同一套符号规则，直接转成仓位
df = panel[panel["code"] == "600519.SS"].copy()

print("\n--- 分段定方向的择时 ---")
print(timing_backtest(df, "cci_signed", "forward_5", entry_q=0.7))

print("\n--- 不分段、只做顺势的对照 ---")
print(timing_backtest(df, "cci_z", "forward_5", entry_q=0.7))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
# 趋势过滤：价格在 20 日均线上方，且 CCI 由负转正时持仓
df = panel[panel["code"] == "600519.SS"].sort_values("date").copy()
df["sma20"] = df["close"].rolling(20).mean()
df["cond"] = ((df["close"] > df["sma20"]) & (df["cci20"] > 0)
              & (df["cci20"].shift(1) <= 0)).astype(int)

print(timing_backtest(df, "cond", "forward_5", entry_q=0.5))
