# ============================================================
# 第014章 双移动平均线（DMA）
# 模块 03 趋势类指标
# 源文件：模块03-趋势类指标/第014章-双移动平均线（DMA）.md
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

# 2. 计算 DMA：短期 SMA 减长期 SMA
df = pd.DataFrame({"close": close})
df["dma_line"] = df["close"].rolling(10).mean()
df["ama_line"] = df["close"].rolling(50).mean()
df["dma_diff"] = df["dma_line"] - df["ama_line"]

# 3. 识别信号
df["cross_up"] = (df["dma_diff"] > 0) & (df["dma_diff"].shift(1) <= 0)
df["cross_down"] = (df["dma_diff"] < 0) & (df["dma_diff"].shift(1) >= 0)
print(f"上穿零轴：{df['cross_up'].sum()}  下穿零轴：{df['cross_down'].sum()}")

# 4. 绘图
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                               gridspec_kw={"height_ratios": [2, 1]})
ax1.plot(df.index, df["close"], label="收盘价", color="#333", linewidth=1)
ax1.plot(df.index, df["dma_line"], label="SMA10", color="#2f6fb5")
ax1.plot(df.index, df["ama_line"], label="SMA50", color="#c0392b")
ax1.set_title("贵州茅台 DMA 双均线")
ax1.legend()
ax2.plot(df.index, df["dma_diff"], color="#d35400")
ax2.axhline(0, color="#666", linewidth=0.8, linestyle="--")
ax2.set_ylabel("DMA 差值")
plt.tight_layout()
plt.show()

# 5. 输出统计
print("差值为正的天数占比：",
      round((df["dma_diff"] > 0).sum() / df["dma_diff"].notna().sum(), 3))

# ---- 代码块 2：拆解 ----

# 沿用第 007 章口径，拆解四个特征
g = panel.groupby("code")["close"]
panel["sma10"] = g.transform(lambda s: s.rolling(10).mean())
panel["sma50"] = g.transform(lambda s: s.rolling(50).mean())
panel["dma_abs"] = panel["sma10"] - panel["sma50"]
panel["dma_rel"] = panel["sma10"] / panel["sma50"] - 1
panel["dma_slope"] = panel.groupby("code")["dma_abs"].diff(5) / panel["sma50"]
panel["dma_pct"] = panel.groupby("code")["dma_abs"].transform(
    lambda s: s.rolling(250).apply(lambda x: (x <= x[-1]).mean(), raw=True))

print(panel[["dma_abs", "dma_rel", "dma_slope", "dma_pct"]].corr(method="spearman"))

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
g = panel.groupby("code")["close"]
panel["dma_norm"] = (g.transform(lambda s: s.rolling(10).mean())
                     - g.transform(lambda s: s.rolling(50).mean())) / panel["close"]

for f in ["dma_rel", "dma_norm", "dma_pct"]:
    print(f"\n--- {f} ---")
    print(ic_summary(cross_section_ic(panel, f, "forward_5")))

print(layered_returns(panel, "dma_rel", "forward_5"))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df = panel[panel["code"] == "600519.SS"].copy()

print(timing_signal_test(df, "dma_rel", "forward_5", upper=0.8))
print(conditional_quantile_return(df, "dma_rel", "forward_5", q=5))
print(timing_backtest(df, "dma_rel", "forward_5", entry_q=0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
panel["vol_ratio"] = panel["volume"] / panel.groupby("code")["volume"].transform(
    lambda s: s.rolling(20).mean())

# 负面对照：与 MACD 差离值的相关
g = panel.groupby("code")["close"]
panel["dif"] = g.transform(lambda s: s.ewm(span=12, adjust=False).mean()) / g.transform(
    lambda s: s.ewm(span=26, adjust=False).mean()) - 1
rho = panel.groupby("date").apply(
    lambda x: x[["dma_rel", "dif"]].corr(method="spearman").iloc[0, 1])
print("DMA 与 DIF 的平均相关：", round(rho.mean(), 3))

panel = combined_signal(panel, ["dma_rel", "vol_ratio"])
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "dma_rel", "forward_5")))
print(ic_summary(cross_section_ic(panel, "vol_ratio", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
df = panel[panel["code"] == "600519.SS"].copy()
df["sma10"] = df["close"].rolling(10).mean()
df["sma50"] = df["close"].rolling(50).mean()
df["dma_abs"] = df["sma10"] - df["sma50"]
df["dma_rel"] = df["sma10"] / df["sma50"] - 1
# 差值斜率：五期变化除以长期均线，无量纲
df["dma_slope"] = df["dma_abs"].diff(5) / df["sma50"]
# 组合条件：差值为正且差值仍在扩大
df["cond"] = ((df["dma_rel"] > 0) & (df["dma_slope"] > 0)).astype(int)

print("--- 组合条件 ---")
print(timing_backtest(df, "cond", "forward_5", entry_q=0.5))

# 单条件对照
df["cond_rel"] = (df["dma_rel"] > 0).astype(int)
df["cond_slope"] = (df["dma_slope"] > 0).astype(int)

print("\n--- 仅相对差值 ---")
print(timing_backtest(df, "cond_rel", "forward_5", entry_q=0.5))

print("\n--- 仅差值斜率 ---")
print(timing_backtest(df, "cond_slope", "forward_5", entry_q=0.5))
