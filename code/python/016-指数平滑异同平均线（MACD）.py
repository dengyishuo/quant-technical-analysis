# ============================================================
# 第016章 指数平滑异同平均线（MACD）
# 模块 03 趋势类指标
# 源文件：模块03-趋势类指标/第016章-指数平滑异同平均线（MACD）.md
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
close = data["Close"].squeeze()

# 2. 手写 MACD
df = pd.DataFrame({"close": close})
ema12 = df["close"].ewm(span=12, adjust=False).mean()
ema26 = df["close"].ewm(span=26, adjust=False).mean()
df["dif"] = ema12 - ema26
df["dea"] = df["dif"].ewm(span=9, adjust=False).mean()
df["bar"] = (df["dif"] - df["dea"]) * 2

# 3. 识别信号
df["above"] = (df["dif"] > df["dea"]).astype(int)
df["cross_up"] = (df["above"] == 1) & (df["above"].shift(1) == 0)
df["cross_down"] = (df["above"] == 0) & (df["above"].shift(1) == 1)
print(f"金叉次数：{df['cross_up'].sum()}  死叉次数：{df['cross_down'].sum()}")

# 4. 绘图：上为价格，下为 MACD
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                               gridspec_kw={"height_ratios": [2, 1]})
ax1.plot(df.index, df["close"], color="#333", linewidth=1)
ax1.set_title("贵州茅台 MACD(12,26,9)")
ax2.plot(df.index, df["dif"], label="DIF", color="#2f6fb5")
ax2.plot(df.index, df["dea"], label="DEA", color="#c0392b")
ax2.bar(df.index, df["bar"], color=np.where(df["bar"] >= 0, "#c0392b", "#27ae60"),
        width=1.0, alpha=0.6)
ax2.axhline(0, color="#666", linewidth=0.8, linestyle="--")
ax2.legend()
plt.tight_layout()
plt.show()

# 5. 输出统计
print("DIF 位于零轴上方的比例：",
      round((df["dif"] > 0).sum() / df["dif"].notna().sum(), 3))

# ---- 代码块 2：拆解 ----

# 沿用第 007 章的数据准备（panel 含 date / code / close / high / low / volume）
import numpy as np
import pandas as pd

panel = panel.sort_values(["code", "date"]).reset_index(drop=True)

# DIF 为快慢两条指数平均之差，DEA 为 DIF 的再一次平滑
panel["dif"] = panel.groupby("code")["close"].transform(
    lambda s: s.ewm(span=12, adjust=False).mean() - s.ewm(span=26, adjust=False).mean())
panel["dea"] = panel.groupby("code")["dif"].transform(
    lambda s: s.ewm(span=9, adjust=False).mean())

# DIF 归一：单位价格的动能水平
panel["dif_n"] = panel["dif"] / panel["close"]
# DEA 归一：动能的平滑基准
panel["dea_n"] = panel["dea"] / panel["close"]
# 柱状值与其一阶差分，差分只作用于分子，分母统一用当日价格
panel["bar"] = panel["dif"] - panel["dea"]
panel["bar_diff"] = panel.groupby("code")["bar"].transform(lambda s: s.diff())
# 柱状值归一：动能相对信号线的偏离
panel["bar_n"] = panel["bar"] / panel["close"]
# 柱状值变化：柱状值的一阶差分再除以价格
panel["bar_chg"] = panel["bar_diff"] / panel["close"]
# 零轴穿越状态：DIF 的符号
panel["zero_state"] = np.sign(panel["dif"])

# 展示五个特征的取值形状
print(panel[["date", "code", "dif_n", "dea_n", "bar_n",
             "bar_chg", "zero_state"]].dropna().head())

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
panel["dif"] = panel.groupby("code")["close"].transform(
    lambda s: s.ewm(span=12, adjust=False).mean() - s.ewm(span=26, adjust=False).mean())
panel["dea"] = panel.groupby("code")["dif"].transform(
    lambda s: s.ewm(span=9, adjust=False).mean())
panel["bar_n"] = (panel["dif"] - panel["dea"]) / panel["close"]
panel["dif_n"] = panel["dif"] / panel["close"]
panel["zero_state"] = np.sign(panel["dif"])

for h in ["forward_1", "forward_5"]:
    print(f"\n--- 柱状值因子 vs {h} ---")
    print(ic_summary(cross_section_ic(panel, "bar_n", h)))

print(layered_returns(panel, "bar_n", "forward_5"))

# DIF 因子作对照，看信息来自动能水平还是动能变化
print(ic_summary(cross_section_ic(panel, "dif_n", "forward_5")))

# 按零轴状态分组，检查符号是否一致
for st, g in panel.groupby("zero_state"):
    print(st, round(cross_section_ic(g, "bar_n", "forward_5").mean(), 4))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df = panel[panel["code"] == "600519.SS"].copy()

print("--- 信号触发日检验（柱状值高于 80 分位）---")
print(timing_signal_test(df, "bar_n", "forward_5", upper=0.8))

print("\n--- 条件分位收益（柱状值分五档）---")
print(conditional_quantile_return(df, "bar_n", "forward_5", q=5))

print("\n--- 择时策略与买入持有对照 ---")
print(timing_backtest(df, "bar_n", "forward_5", entry_q=0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
panel["vol_ratio"] = panel["volume"] / panel.groupby("code")["volume"].transform(
    lambda s: s.rolling(20).mean())

rho = panel.groupby("date").apply(
    lambda g: g[["bar_n", "vol_ratio"]].corr(method="spearman").iloc[0, 1])
print("两个特征的平均横截面相关：", round(rho.mean(), 3))

panel = combined_signal(panel, ["bar_n", "vol_ratio"])

print("\n--- 组合 vs 单特征 ---")
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "bar_n", "forward_5")))
print(ic_summary(cross_section_ic(panel, "vol_ratio", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
df = panel[panel["code"] == "600519.SS"].copy()
df["sma20"] = df["close"].rolling(20).mean()
df["cond"] = ((df["bar_n"] > 0) & (df["close"] > df["sma20"])).astype(int)

print(timing_backtest(df, "cond", "forward_5", entry_q=0.5))
