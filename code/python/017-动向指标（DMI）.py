# ============================================================
# 第017章 动向指标（DMI）
# 模块 03 趋势类指标
# 源文件：模块03-趋势类指标/第017章-动向指标（DMI）.md
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

# 2. 手写 DMI
n = 14
alpha = 1 / n  # Wilder 平滑，等价于 alpha = 1/n（与 TTR 默认的 EMA 平滑略有差异）

up = high.diff()
down = -low.diff()
dm_plus = np.where((up > down) & (up > 0), up, 0.0)
dm_minus = np.where((down > up) & (down > 0), down, 0.0)

tr = pd.concat([(high - low), (high - close.shift(1)).abs(),
                (low - close.shift(1)).abs()], axis=1).max(axis=1)

tr_s = pd.Series(tr, index=close.index).ewm(alpha=alpha, adjust=False).mean()
dm_plus_s = pd.Series(dm_plus, index=close.index).ewm(alpha=alpha, adjust=False).mean()
dm_minus_s = pd.Series(dm_minus, index=close.index).ewm(alpha=alpha, adjust=False).mean()

di_plus = 100 * dm_plus_s / tr_s
di_minus = 100 * dm_minus_s / tr_s
dx = 100 * (di_plus - di_minus).abs() / (di_plus + di_minus)
adx = dx.ewm(alpha=alpha, adjust=False).mean()
adxr = (adx + adx.shift(n)) / 2

# 3. 识别信号
df = pd.DataFrame({"di_plus": di_plus, "di_minus": di_minus, "adx": adx, "adxr": adxr})
df["trend_ok"] = df["adx"] >= 25
df["cross_up"] = (df["di_plus"] > df["di_minus"]) & \
                 (df["di_plus"].shift(1) <= df["di_minus"].shift(1)) & df["trend_ok"]
print("趋势市中的金叉次数：", int(df["cross_up"].sum()))

# 4. 绘图
fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(df.index, df["di_plus"], label="正向 DI", color="#c0392b")
ax.plot(df.index, df["di_minus"], label="负向 DI", color="#27ae60")
ax.plot(df.index, df["adx"], label="ADX", color="#2c3e50", linewidth=2)
ax.axhline(25, color="#999", linewidth=0.8, linestyle="--")
ax.set_title("贵州茅台 DMI(14)")
ax.legend()
plt.tight_layout()
plt.show()

# 5. 输出统计
print("ADX 不低于 25 的天数占比：",
      round((df["adx"] >= 25).sum() / df["adx"].notna().sum(), 3))

# ---- 代码块 2：拆解 ----

# 沿用第 007 章的数据准备（panel 含 date / code / close / high / low / volume）
import numpy as np
import pandas as pd

panel = panel.sort_values(["code", "date"]).reset_index(drop=True)

# 按标的计算 DI 与 ADX，方向移动取正负两侧的较大者并截去负值
def dmi_cols(g, n=14):
    up, dn = g["high"].diff(), -g["low"].diff()
    tr = pd.concat([g["high"] - g["low"], (g["high"] - g["close"].shift()).abs(),
                    (g["low"] - g["close"].shift()).abs()], axis=1).max(axis=1)
    a = 1 / n
    dp = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=g.index)
    dm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=g.index)
    tr_s, dp, dm = (x.ewm(alpha=a, adjust=False).mean() for x in (tr, dp, dm))
    di_p, di_m = 100 * dp / tr_s, 100 * dm / tr_s
    dx = 100 * (di_p - di_m).abs() / (di_p + di_m)
    return pd.DataFrame({"di_p": di_p, "di_m": di_m,
                         "adx": dx.ewm(alpha=a, adjust=False).mean()})

panel = panel.join(panel.groupby("code", group_keys=False).apply(dmi_cols))

# 方向强度：正负 DI 之差除以两者之和，归一到 -1 至 1
panel["dir_str"] = (panel["di_p"] - panel["di_m"]) / (panel["di_p"] + panel["di_m"])
# 方向强度变化：五个交易日内的净强度变化
panel["dir_chg"] = panel.groupby("code")["dir_str"].transform(lambda s: s - s.shift(5))
# 交叉状态：正向 DI 是否占优
panel["cross_state"] = (panel["di_p"] > panel["di_m"]).astype(int)
# 门限标记：ADX 是否达到 25
panel["gate"] = (panel["adx"] >= 25).astype(int)

# 展示四个特征的取值形状
print(panel[["date", "code", "dir_str", "dir_chg",
             "cross_state", "gate"]].dropna().head())

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
def dmi_cols(g, n=14):
    up, dn = g["high"].diff(), -g["low"].diff()
    tr = pd.concat([g["high"] - g["low"], (g["high"] - g["close"].shift()).abs(),
                    (g["low"] - g["close"].shift()).abs()], axis=1).max(axis=1)
    a = 1 / n
    dp = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=g.index)
    dm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=g.index)
    tr_s, dp, dm = (x.ewm(alpha=a, adjust=False).mean() for x in (tr, dp, dm))
    di_p, di_m = 100 * dp / tr_s, 100 * dm / tr_s
    dx = 100 * (di_p - di_m).abs() / (di_p + di_m)
    return pd.DataFrame({"di_p": di_p, "di_m": di_m,
                         "adx": dx.ewm(alpha=a, adjust=False).mean()})

panel = panel.join(panel.groupby("code", group_keys=False).apply(dmi_cols))
panel["dir_str"] = (panel["di_p"] - panel["di_m"]) / (panel["di_p"] + panel["di_m"])
panel["cross_state"] = (panel["di_p"] > panel["di_m"]).astype(int)
panel["gate"] = (panel["adx"] >= 25).astype(int)

for h in ["forward_1", "forward_5"]:
    print(ic_summary(cross_section_ic(panel, "dir_str", h)))
print(layered_returns(panel, "dir_str", "forward_5"))
print(ic_summary(cross_section_ic(panel, "cross_state", "forward_5")))

# 按门限分段，检查弱市是否稀释了因子
for g, sub in panel.groupby("gate"):
    print(g, ic_summary(cross_section_ic(sub, "dir_str", "forward_5")).to_dict())

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df = panel[panel["code"] == "600519.SS"].copy()

print("--- 信号触发日检验（方向强度高于 80 分位）---")
print(timing_signal_test(df, "dir_str", "forward_5", upper=0.8))

print("\n--- 条件分位收益（方向强度分五档）---")
print(conditional_quantile_return(df, "dir_str", "forward_5", q=5))

print("\n--- 择时策略与买入持有对照 ---")
print(timing_backtest(df, "dir_str", "forward_5", entry_q=0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
panel["vol_ratio"] = panel["volume"] / panel.groupby("code")["volume"].transform(
    lambda s: s.rolling(20).mean())
panel = combined_signal(panel, ["dir_str", "vol_ratio"])

print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "dir_str", "forward_5")))
print(ic_summary(cross_section_ic(panel, "vol_ratio", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
df = panel[panel["code"] == "600519.SS"].copy()
df["cond"] = ((df["dir_str"] > 0) & (df["gate"] == 1)).astype(int)

print(timing_backtest(df, "cond", "forward_5", entry_q=0.5))
