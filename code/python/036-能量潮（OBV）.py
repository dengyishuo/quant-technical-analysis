# ============================================================
# 第036章 能量潮（OBV）
# 模块 06 量价类指标
# 源文件：模块06-量价类指标/第036章-能量潮（OBV）.md
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
import matplotlib
matplotlib.rcParams["font.sans-serif"] = ["PingFang SC", "SimHei", "Arial Unicode MS"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt

# 1. 获取数据
_panel = pd.read_parquet("data/parquet/panel_blue_chip.parquet")
data = (_panel[_panel["code"] == "600519.SS"]
        .set_index("date").sort_index()[["open", "high", "low", "close", "volume"]])
data.columns = ["Open", "High", "Low", "Close", "Volume"]
close = data["Close"].squeeze()
volume = data["Volume"].squeeze()

# 2. 计算 OBV：按涨跌符号给成交量定号后累加
direction = np.sign(close.diff()).fillna(0)
df = pd.DataFrame({"close": close, "obv": (direction * volume).cumsum()})

# 3. 计算 OBV 的 30 日均线
df["obv_ma30"] = df["obv"].rolling(30).mean()

# 4. 识别信号：OBV 上穿均线
df["above"] = (df["obv"] > df["obv_ma30"]).astype(int)
df["cross_up"] = (df["above"] == 1) & (df["above"].shift(1) == 0)
print(f"OBV 上穿均线次数：{df['cross_up'].sum()}")

# 5. 绘图
fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
axes[0].plot(df.index, df["close"], color="#333", linewidth=1)
axes[0].set_title("贵州茅台 收盘价与 OBV")
axes[1].plot(df.index, df["obv"], label="OBV", color="#2f6fb5")
axes[1].plot(df.index, df["obv_ma30"], label="OBV 30 日均线", color="#c0392b")
axes[1].legend()
plt.tight_layout()
plt.show()

# 6. 输出统计
price_up = close.diff() > 0
obv_up = df["obv"].diff() > 0
print("价格与 OBV 同向比例：", round((price_up == obv_up).mean(), 3))

# ---- 代码块 2：拆解 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
import numpy as np
import pandas as pd

# panel 已含 date / code / close / volume / forward_1 / forward_5
panel = panel.sort_values(["code", "date"]).reset_index(drop=True)
grp = panel.groupby("code")

# OBV：按涨跌符号给成交量定号后累加
direction = np.sign(grp["close"].diff()).fillna(0)
panel["obv"] = (direction * panel["volume"]).groupby(panel["code"]).cumsum()
panel["obv_level"] = panel["obv"]

# k 日变化率：分母取绝对值，并设下限防止接近零时放大
obv_lag = grp["obv"].shift(10)
panel["obv_chg"] = (panel["obv"] - obv_lag) / obv_lag.abs().clip(lower=1e-8)

# 相对自身 20 日均线的偏离
panel["obv_ma20"] = grp["obv"].transform(lambda s: s.rolling(20).mean())
panel["obv_dev"] = panel["obv"] / panel["obv_ma20"] - 1

# 量价背离：20 日价格新高但 OBV 未创新高（前 20 日为预热期，记 0）
px_hi = panel["close"] >= grp["close"].transform(lambda s: s.rolling(20).max())
obv_hi = panel["obv"] >= grp["obv"].transform(lambda s: s.rolling(20).max())
panel["diverge"] = (px_hi & ~obv_hi).astype(int)

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# 变化率因子：一日与五日两个前向窗口对照
for h in ["forward_1", "forward_5"]:
    print(f"\n--- OBV 变化率 vs {h} ---")
    print(ic_summary(cross_section_ic(panel, "obv_chg", h)))

print(layered_returns(panel, "obv_chg", "forward_5"))

# 缩尾后再算一次，观察极端读数对结论的影响
panel["obv_chg_w"] = panel.groupby("date")["obv_chg"].transform(
    lambda s: s.clip(s.quantile(0.01), s.quantile(0.99)))

print("\n--- 缩尾后 ---")
print(ic_summary(cross_section_ic(panel, "obv_chg_w", "forward_5")))

# 与成交量水平的相关：检查因子是否只是在排序流动性
rho = panel.groupby("date").apply(
    lambda g: g.assign(lv=np.log(g["volume"]))[["obv_chg_w", "lv"]]
    .corr(method="spearman").iloc[0, 1])
print("与对数成交量的平均横截面相关：", round(rho.mean(), 3))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df = panel[panel["code"] == "600519.SS"].sort_values("date").copy()

print("--- 信号触发日检验（变化率高于 80 分位）---")
print(timing_signal_test(df, "obv_chg_w", "forward_5", upper=0.8))

print("\n--- 条件分位收益（变化率分五档）---")
print(conditional_quantile_return(df, "obv_chg_w", "forward_5", q=5))

print("\n--- 择时策略与买入持有对照 ---")
print(timing_backtest(df, "obv_chg_w", "forward_5", entry_q=0.7))

# 背离是稀疏事件，先看频次与两组均值，再决定是否值得做检验
print(df.groupby("diverge")["forward_5"].agg(["count", "mean"]).round(4))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
# 先看两个特征的横截面相关，再决定是否值得组合
panel["vol_ratio"] = panel["volume"] / grp["volume"].transform(
    lambda s: s.rolling(20).mean())

rho = panel.groupby("date").apply(
    lambda g: g[["obv_chg_w", "vol_ratio"]].corr(method="spearman").iloc[0, 1])
print("两个特征的平均横截面相关：", round(rho.mean(), 3))

panel = combined_signal(panel, ["obv_chg_w", "vol_ratio"])

print("\n--- 组合 vs 单特征 ---")
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "obv_chg_w", "forward_5")))
print(ic_summary(cross_section_ic(panel, "vol_ratio", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
df2 = panel[panel["code"] == "600519.SS"].sort_values("date").copy()
df2["sma20"] = df2["close"].rolling(20).mean()
df2["cond"] = ((df2["obv_chg_w"] > 0) & (df2["close"] > df2["sma20"])).astype(int)

print(timing_backtest(df2, "cond", "forward_5", entry_q=0.5))
