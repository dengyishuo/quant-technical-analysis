# ============================================================
# 第018章 平均趋向指数（ADX）
# 模块 03 趋势类指标
# 源文件：模块03-趋势类指标/第018章-平均趋向指数（ADX）.md
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

import matplotlib
matplotlib.rcParams["font.sans-serif"] = ["PingFang SC", "SimHei", "Arial Unicode MS"]
matplotlib.rcParams["axes.unicode_minus"] = False
import numpy as np
import pandas as pd

# 本地数据，由 xquant-db 导出，字段见 data/README.md
_panel = pd.read_parquet("data/parquet/panel_blue_chip.parquet")
import matplotlib.pyplot as plt

# 1. 获取数据
_panel = pd.read_parquet("data/parquet/panel_blue_chip.parquet")
data = (_panel[_panel["code"] == "600519.SS"]
        .set_index("date").sort_index()[["open", "high", "low", "close", "volume"]])
data.columns = ["Open", "High", "Low", "Close", "Volume"]
high, low, close = data["High"].squeeze(), data["Low"].squeeze(), data["Close"].squeeze()

# 2. 手写 ADX
n = 14
alpha = 1 / n  # Wilder 平滑，等价于 alpha = 1/n（与 TTR 默认的 EMA 平滑略有差异）
up = high.diff()
down = -low.diff()
dm_plus = np.where((up > down) & (up > 0), up, 0.0)
dm_minus = np.where((down > up) & (down > 0), down, 0.0)
tr = pd.concat([(high - low), (high - close.shift(1)).abs(),
                (low - close.shift(1)).abs()], axis=1).max(axis=1)

tr_s = tr.ewm(alpha=alpha, adjust=False).mean()
dp_s = pd.Series(dm_plus, index=close.index).ewm(alpha=alpha, adjust=False).mean()
dn_s = pd.Series(dm_minus, index=close.index).ewm(alpha=alpha, adjust=False).mean()

di_plus = 100 * dp_s / tr_s
di_minus = 100 * dn_s / tr_s
dx = 100 * (di_plus - di_minus).abs() / (di_plus + di_minus)
adx = dx.ewm(alpha=alpha, adjust=False).mean()

# 3. 识别信号
df = pd.DataFrame({"di_plus": di_plus, "di_minus": di_minus, "adx": adx})
df["strong"] = df["adx"] >= 40
df["cross_up"] = (df["di_plus"] > df["di_minus"]) & \
                 (df["di_plus"].shift(1) <= df["di_minus"].shift(1)) & (df["adx"] >= 25)
print("强趋势天数：", int(df["strong"].sum()))
print("趋势市中的金叉次数：", int(df["cross_up"].sum()))

# 4. 绘图
fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(df.index, df["adx"], label="ADX", color="#2c3e50", linewidth=2)
ax.plot(df.index, df["di_plus"], label="正向 DI", color="#c0392b", alpha=0.7)
ax.plot(df.index, df["di_minus"], label="负向 DI", color="#27ae60", alpha=0.7)
ax.axhline(25, color="#999", linewidth=0.8, linestyle="--")
ax.axhline(40, color="#999", linewidth=0.8, linestyle=":")
ax.set_title("贵州茅台 ADX(14)")
ax.legend()
plt.tight_layout()
plt.show()

# 5. 输出统计
print("ADX 中位数：", round(df["adx"].median(), 1))
print("ADX 不低于 40 的天数占比：",
      round((df["adx"] >= 40).sum() / df["adx"].notna().sum(), 3))

# ---- 代码块 2：拆解 ----

# 沿用第 007 章的数据准备（panel 含 date / code / close / high / low / volume）
import numpy as np
import pandas as pd

panel = panel.sort_values(["code", "date"]).reset_index(drop=True)

# 按标的计算 ADX，方向移动与真实波幅均取 Wilder 平滑
def adx_cols(g, n=14):
    up, dn = g["high"].diff(), -g["low"].diff()
    tr = pd.concat([g["high"] - g["low"], (g["high"] - g["close"].shift()).abs(),
                    (g["low"] - g["close"].shift()).abs()], axis=1).max(axis=1)
    a = 1 / n
    dp = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=g.index)
    dm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=g.index)
    tr_s, dp, dm = (x.ewm(alpha=a, adjust=False).mean() for x in (tr, dp, dm))
    di_p, di_m = 100 * dp / tr_s, 100 * dm / tr_s
    dx = 100 * (di_p - di_m).abs() / (di_p + di_m)
    return pd.DataFrame({"adx": dx.ewm(alpha=a, adjust=False).mean()})

panel = panel.join(panel.groupby("code", group_keys=False).apply(adx_cols))

# ADX 斜率：五日跨度上的读数变化
panel["adx_chg"] = panel.groupby("code")["adx"].transform(lambda s: s - s.shift(5))
# ADX 分位：250 日窗口内不大于当日读数的比例，等价于秩次除以窗口长度
panel["adx_pctile"] = panel.groupby("code")["adx"].transform(
    lambda s: s.rolling(250).apply(lambda x: (x <= x[-1]).mean(), raw=True))
# 门限状态：ADX 是否达到 25
panel["gate"] = (panel["adx"] >= 25).astype(int)

# 展示四个特征的取值形状，分位列需要 250 日窗口
print(panel[["date", "code", "adx", "adx_chg",
             "adx_pctile", "gate"]].dropna().head())

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
def adx_cols(g, n=14):
    up, dn = g["high"].diff(), -g["low"].diff()
    tr = pd.concat([g["high"] - g["low"], (g["high"] - g["close"].shift()).abs(),
                    (g["low"] - g["close"].shift()).abs()], axis=1).max(axis=1)
    a = 1 / n
    dp = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=g.index)
    dm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=g.index)
    tr_s, dp, dm = (x.ewm(alpha=a, adjust=False).mean() for x in (tr, dp, dm))
    di_p, di_m = 100 * dp / tr_s, 100 * dm / tr_s
    dx = 100 * (di_p - di_m).abs() / (di_p + di_m)
    return pd.DataFrame({"adx": dx.ewm(alpha=a, adjust=False).mean()})

panel = panel.join(panel.groupby("code", group_keys=False).apply(adx_cols))
panel["mom20"] = panel.groupby("code")["close"].transform(lambda s: s / s.shift(20) - 1)
panel["adx_chg"] = panel.groupby("code")["adx"].transform(lambda s: s - s.shift(5))

# 自身排序：预期接近零，作为对照
print(ic_summary(cross_section_ic(panel, "adx", "forward_5")))

panel["adx_grp"] = panel.groupby("date")["adx"].transform(
    lambda s: pd.qcut(s.rank(method="first"), 3, labels=False) + 1)

for k in (1, 2, 3):
    print(f"\n--- ADX 第 {k} 组，动量因子 ---")
    print(ic_summary(cross_section_ic(panel[panel["adx_grp"] == k], "mom20", "forward_5")))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df = panel[panel["code"] == "600519.SS"].copy()

print("--- 信号触发日检验（ADX 高于 80 分位）---")
print(timing_signal_test(df, "adx", "forward_5", upper=0.8))

print("\n--- 条件分位收益（ADX 分五档）---")
print(conditional_quantile_return(df, "adx", "forward_5", q=5))

# 门限开关：ADX 达标且价格在二十日均线上方才持仓
df["cond"] = ((df["adx"] >= 25) & (df["close"] > df["close"].rolling(20).mean())).astype(int)
print("\n--- 开关策略与买入持有对照 ---")
print(timing_backtest(df, "cond", "forward_5", entry_q=0.5))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
# 门限变量用条件分组，不做加权；先做组内组合，再看组间差异
panel["vol_ratio"] = panel["volume"] / panel.groupby("code")["volume"].transform(
    lambda s: s.rolling(20).mean())
panel = combined_signal(panel, ["mom20", "vol_ratio"])

for k in (1, 2, 3):
    print(f"\n--- ADX 第 {k} 组，动量与量比组合 ---")
    print(ic_summary(cross_section_ic(panel[panel["adx_grp"] == k], "combined", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
df = panel[panel["code"] == "600519.SS"].copy()
df["cond"] = ((df["adx"] >= 25) & (df["close"] > df["close"].rolling(20).mean())).astype(int)

print(timing_backtest(df, "cond", "forward_5", entry_q=0.5))
