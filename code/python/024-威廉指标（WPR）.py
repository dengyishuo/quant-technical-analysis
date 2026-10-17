# ============================================================
# 第024章 威廉指标（WPR）
# 模块 04 震荡类指标
# 源文件：模块04-震荡类指标/第024章-威廉指标（WPR）.md
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

# 2. 计算 WPR（负 100 到 0）
def wpr(high, low, close, n=14):
    hh = high.rolling(n).max()
    ll = low.rolling(n).min()
    return (hh - close) / (hh - ll) * -100

df = pd.DataFrame({"high": high, "low": low, "close": close})
df["wpr6"]  = wpr(df["high"], df["low"], df["close"], 6)
df["wpr14"] = wpr(df["high"], df["low"], df["close"], 14)
df["wpr28"] = wpr(df["high"], df["low"], df["close"], 28)

# 3. 识别信号
df["oversold"]   = (df["wpr14"] < -80).astype(int)
df["overbought"] = (df["wpr14"] > -20).astype(int)
df["resonance"]  = ((df["wpr6"] < -80) & (df["wpr14"] < -70) & (df["wpr28"] < -60)).astype(int)
print(f"14 日超卖天数：{df['oversold'].sum()}  超买天数：{df['overbought'].sum()}")
print(f"三周期超卖共振天数：{df['resonance'].sum()}")

# 4. 绘图
import matplotlib
matplotlib.rcParams["font.sans-serif"] = ["PingFang SC", "SimHei", "Arial Unicode MS"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                               gridspec_kw={"height_ratios": [2, 1]})
ax1.plot(df.index, df["close"], color="#333", linewidth=1)
ax1.set_title("贵州茅台 收盘价与 WPR")
ax2.plot(df.index, df["wpr14"], label="WPR14", color="#2f6fb5")
ax2.plot(df.index, df["wpr6"], label="WPR6", color="#c0392b", linewidth=1)
ax2.axhline(-20, color="#999", linestyle="--", linewidth=0.8)
ax2.axhline(-80, color="#999", linestyle="--", linewidth=0.8)
ax2.legend()
plt.tight_layout()
plt.show()

# 5. 输出统计
print("WPR14 落在负 80 以下的占比：",
      round((df["wpr14"] < -80).sum() / df["wpr14"].notna().sum(), 3))
print("WPR14 落在负 20 以上的占比：",
      round((df["wpr14"] > -20).sum() / df["wpr14"].notna().sum(), 3))

# ---- 代码块 2：拆解 ----

# 沿用第 007 章的数据准备（panel 含 date / code / close / high / low / volume）
import numpy as np
import pandas as pd

panel = panel.sort_values(["code", "date"]).reset_index(drop=True)

# 标准读数：上沿减收盘价，除以区间高度，再乘负 100（负 100 到 0）
hh14 = panel.groupby("code")["high"].transform(lambda s: s.rolling(14).max())
ll14 = panel.groupby("code")["low"].transform(lambda s: s.rolling(14).min())
panel["wpr14"] = (hh14 - panel["close"]) / (hh14 - ll14) * -100

panel["wpr_dev"] = panel["wpr14"] + 50     # 平移值，中心移到零轴
panel["wpr_mirror"] = -panel["wpr14"]      # 镜像读数，与 RSI 同向

# 分位标记：250 日窗口内的经验百分位，含当日
panel["wpr_pctile"] = panel.groupby("code")["wpr14"].transform(
    lambda s: s.rolling(250).apply(lambda x: (x <= x[-1]).mean(), raw=True))

# 极值持续期：超卖侧记正，超买侧记负，中性段归零
def signed_run(state):
    block = state.ne(state.shift()).cumsum()
    run = state.groupby(block).cumcount() + 1
    return run.where(state != 0, 0) * state

state = pd.Series(np.where(panel["wpr14"] < -80, 1,
                           np.where(panel["wpr14"] > -20, -1, 0)), index=panel.index)
panel["wpr_ext_run"] = state.groupby(panel["code"]).transform(signed_run)

print(panel.dropna(subset=["wpr14"]).head(8)[
    ["date", "code", "wpr14", "wpr_dev", "wpr_mirror", "wpr_pctile", "wpr_ext_run"]])

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# panel 含 date / code / high / low / close / forward_1 / forward_5

def wpr_col(n):
    # 原式：(上沿减收盘价) / 区间高度，乘负 100 后落在负 100 到 0
    hh = panel["high"].groupby(panel["code"]).transform(lambda s: s.rolling(n).max())
    ll = panel["low"].groupby(panel["code"]).transform(lambda s: s.rolling(n).min())
    return (hh - panel["close"]) / (hh - ll) * -100

panel["wpr14"] = wpr_col(14)
panel["wpr6"] = wpr_col(6)
panel["wpr_dev"] = panel["wpr14"] + 50
panel["wpr_mirror"] = -panel["wpr14"]

for h in ["forward_1", "forward_5"]:
    print(f"\n--- WPR 平移值 vs {h} ---")
    print(ic_summary(cross_section_ic(panel, "wpr_dev", h)))

print(layered_returns(panel, "wpr_dev", "forward_5"))

# 镜像刻度只差一个符号，IC 应当近似相反
print(ic_summary(cross_section_ic(panel, "wpr_mirror", "forward_5")))

# 符号稳定性：按年切分
panel["year"] = pd.to_datetime(panel["date"]).dt.year
for y, g in panel.groupby("year"):
    print(y, round(cross_section_ic(g, "wpr_dev", "forward_5").mean(), 4))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df = panel[panel["code"] == "600519.SS"].copy()
df["wpr_rev"] = -df["wpr_dev"]

print("--- 上尾：平移值高于 80 分位，对应接近区间上沿 ---")
print(timing_signal_test(df, "wpr_dev", "forward_5", upper=0.8))

print("\n--- 下尾：取负后高于 80 分位，对应接近区间下沿 ---")
print(timing_signal_test(df, "wpr_rev", "forward_5", upper=0.8))

print("\n--- 条件分位收益 ---")
print(conditional_quantile_return(df, "wpr_dev", "forward_5", q=5))

print("\n--- 反转规则的回测（超卖一侧持仓）---")
print(timing_backtest(df, "wpr_rev", "forward_5", entry_q=0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal / cross_section_ic / timing_backtest
# 截面路径：先做冗余检验，再做与量比的组合

def rsi_wilder(series, n=14):
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + gain / loss)

panel["rsi14"] = panel.groupby("code")["close"].transform(rsi_wilder)
panel["vol_ratio"] = panel["volume"] / panel.groupby("code")["volume"].transform(
    lambda s: s.rolling(20).mean())

# 镜像刻度下，WPR 与 RSI 应当同向且高度相关
rho = panel.groupby("date").apply(
    lambda g: g[["wpr_mirror", "rsi14"]].corr(method="spearman").iloc[0, 1])
print("WPR 镜像刻度与 RSI 的平均相关：", round(rho.mean(), 3))

panel = combined_signal(panel, ["wpr_mirror", "vol_ratio"])

print("\n--- 组合 vs 单特征 ---")
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "wpr_mirror", "forward_5")))
print(ic_summary(cross_section_ic(panel, "vol_ratio", "forward_5")))

# 择时路径：6 日与 14 日同时处于超卖区时，才评估镜像读数的信号
df = panel[panel["code"] == "600519.SS"].copy()
df["wpr_gate"] = np.where((df["wpr6"] < -80) & (df["wpr14"] < -70),
                          df["wpr_mirror"], np.nan)

print("\n--- 共振样本内的择时 ---")
print(timing_backtest(df, "wpr_gate", "forward_5", entry_q=0.7))

print("\n--- 全样本对照 ---")
print(timing_backtest(df, "wpr_mirror", "forward_5", entry_q=0.7))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
# 趋势过滤：价格在 20 日均线上方，且平移值低于负 30（等价于标准读数低于负 80）
df = panel[panel["code"] == "600519.SS"].sort_values("date").copy()
df["sma20"] = df["close"].rolling(20).mean()
df["cond"] = ((df["close"] > df["sma20"]) & (df["wpr_dev"] < -30)).astype(int)

print(timing_backtest(df, "cond", "forward_5", entry_q=0.5))
