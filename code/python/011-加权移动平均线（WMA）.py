# ============================================================
# 第011章 加权移动平均线（WMA）
# 模块 03 趋势类指标
# 源文件：模块03-趋势类指标/第011章-加权移动平均线（WMA）.md
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

# 2. 手写 WMA：线性递减权重，越近权重越大
def wma(series, n):
    w = np.arange(1, n + 1)          # 权重自 1 起递增，最新一期最大
    return series.rolling(n).apply(lambda x: np.dot(x, w) / w.sum(), raw=True)

df = pd.DataFrame({"close": close})
df["wma10"] = wma(df["close"], 10)
df["wma30"] = wma(df["close"], 30)

# 3. 识别信号
df["above"] = (df["wma10"] > df["wma30"]).astype(int)
df["cross_up"] = (df["above"] == 1) & (df["above"].shift(1) == 0)
df["cross_down"] = (df["above"] == 0) & (df["above"].shift(1) == 1)
print(f"金叉次数：{df['cross_up'].sum()}  死叉次数：{df['cross_down'].sum()}")

# 4. 绘图
fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(df.index, df["close"], label="收盘价", color="#333", linewidth=1)
ax.plot(df.index, df["wma10"], label="WMA10", color="#2f6fb5")
ax.plot(df.index, df["wma30"], label="WMA30", color="#c0392b")
ax.set_title("贵州茅台 WMA10 / WMA30")
ax.legend()
plt.tight_layout()
plt.show()

# 5. 输出统计：WMA 与 SMA 的偏离
df["sma10"] = df["close"].rolling(10).mean()
gap = ((df["wma10"] - df["sma10"]).abs() / df["sma10"]).mean()
print("WMA10 与 SMA10 的平均相对偏离：", round(gap, 4))

# ---- 代码块 2：拆解 ----

# 沿用第 007 章口径，拆解主要特征
import numpy as np

def wma(s, n):
    w = np.arange(1, n + 1)
    return s.rolling(n).apply(lambda x: np.dot(x, w) / w.sum(), raw=True)

g = panel.groupby("code")["close"]
panel["wma20"] = g.transform(lambda s: wma(s, 20))
panel["wma_dev"] = panel["close"] / panel["wma20"] - 1
panel["wma_slope"] = panel["wma20"] / panel.groupby("code")["wma20"].shift(5) - 1
panel["wma_gap"] = panel["wma20"] / g.transform(lambda s: s.rolling(20).mean()) - 1

print(panel[["wma_dev", "wma_slope", "wma_gap"]].corr(method="spearman"))

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
import numpy as np

g = panel.groupby("code")["close"]
w20 = g.transform(lambda s: s.rolling(20).apply(
    lambda x: x @ np.arange(1, 21) / 210, raw=True))   # 线性权重，总和 210
panel["sma_dev"] = panel["close"] / g.transform(lambda s: s.rolling(20).mean()) - 1
panel["wma_dev"] = panel["close"] / w20 - 1
panel["ema_dev"] = panel["close"] / g.transform(
    lambda s: s.ewm(span=20, adjust=False).mean()) - 1
panel["wma_gap"] = w20 / g.transform(lambda s: s.rolling(20).mean()) - 1

# 三种权重体系的同周期对照
for f in ["sma_dev", "wma_dev", "ema_dev"]:
    print(f"\n--- {f} ---")
    print(ic_summary(cross_section_ic(panel, f, "forward_5")))

print(ic_summary(cross_section_ic(panel, "wma_gap", "forward_5")))
print(layered_returns(panel, "wma_dev", "forward_5"))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df = panel[panel["code"] == "600519.SS"].copy()

# 用斜率代替拐头标记，保留方向的连续信息
df["wma10"] = df["close"].rolling(10).apply(
    lambda x: x @ np.arange(1, 11) / 55, raw=True)
df["wma_slope"] = df["wma10"] / df["wma10"].shift(5) - 1

print(timing_signal_test(df, "wma_slope", "forward_5", upper=0.8))
print(conditional_quantile_return(df, "wma_slope", "forward_5", q=5))
print(timing_backtest(df, "wma_slope", "forward_5", entry_q=0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
panel["vol_ratio"] = panel["volume"] / panel.groupby("code")["volume"].transform(
    lambda s: s.rolling(20).mean())

rho = panel.groupby("date").apply(
    lambda g: g[["wma_dev", "vol_ratio"]].corr(method="spearman").iloc[0, 1])
print("两个特征的平均横截面相关：", round(rho.mean(), 3))

panel = combined_signal(panel, ["wma_dev", "vol_ratio"])

print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "wma_dev", "forward_5")))
print(ic_summary(cross_section_ic(panel, "vol_ratio", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
import numpy as np

df = panel[panel["code"] == "600519.SS"].copy()
df["wma20"] = df["close"].rolling(20).apply(
    lambda x: x @ np.arange(1, 21) / 210, raw=True)   # 线性权重，总和 210
df["sma20"] = df["close"].rolling(20).mean()
df["wma_dev"] = df["close"] / df["wma20"] - 1
df["wma_gap"] = df["wma20"] / df["sma20"] - 1
# 组合条件：线性加权与等权两个体系同时给出正偏离
df["cond"] = ((df["wma_dev"] > 0) & (df["wma_gap"] > 0)).astype(int)

print("--- 组合条件 ---")
print(timing_backtest(df, "cond", "forward_5", entry_q=0.5))

# 单条件对照
df["cond_dev"] = (df["wma_dev"] > 0).astype(int)
df["cond_gap"] = (df["wma_gap"] > 0).astype(int)

print("\n--- 仅偏离度 ---")
print(timing_backtest(df, "cond_dev", "forward_5", entry_q=0.5))

print("\n--- 仅权重贡献差 ---")
print(timing_backtest(df, "cond_gap", "forward_5", entry_q=0.5))
