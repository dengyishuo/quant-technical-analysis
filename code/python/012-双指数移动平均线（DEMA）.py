# ============================================================
# 第012章 双指数移动平均线（DEMA）
# 模块 03 趋势类指标
# 源文件：模块03-趋势类指标/第012章-双指数移动平均线（DEMA）.md
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

# 2. 手写 DEMA：EMA 与二重 EMA 的外推组合
df = pd.DataFrame({"close": close})
alpha = 2 / (20 + 1)
df["ema"] = df["close"].ewm(alpha=alpha, adjust=False).mean()
df["ema2"] = df["ema"].ewm(alpha=alpha, adjust=False).mean()
df["dema"] = 2 * df["ema"] - df["ema2"]
df["sma20"] = df["close"].rolling(20).mean()

# 3. 识别信号
df["accel"] = (df["dema"] > df["ema"]).astype(int)
df["accel_up"] = (df["accel"] == 1) & (df["accel"].shift(1) == 0)
print("加速上行次数：", df["accel_up"].sum())

# 4. 绘图
fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(df.index, df["close"], label="收盘价", color="#333", linewidth=1)
ax.plot(df.index, df["sma20"], label="SMA20", color="#999", linewidth=1)
ax.plot(df.index, df["ema"], label="EMA20", color="#2f6fb5")
ax.plot(df.index, df["dema"], label="DEMA20", color="#8e44ad")
ax.set_title("贵州茅台 DEMA20 与 EMA20 对照")
ax.legend()
plt.tight_layout()
plt.show()

# 5. 输出统计
lead = ((df["dema"] - df["ema"]) / df["ema"]).mean()
print("DEMA20 相对 EMA20 的平均相对偏离：", round(lead, 4))

# ---- 代码块 2：拆解 ----

# 沿用第 007 章口径，拆解主要特征
import numpy as np

def dema(s, n=20):
    a = 2 / (n + 1)
    e1 = s.ewm(alpha=a, adjust=False).mean()
    return 2 * e1 - e1.ewm(alpha=a, adjust=False).mean()

g = panel.groupby("code")["close"]
panel["dema20"] = g.transform(dema)
panel["ema20"] = g.transform(lambda s: s.ewm(span=20, adjust=False).mean())
panel["dema_dev"] = panel["close"] / panel["dema20"] - 1
panel["accel"] = panel["dema20"] / panel["ema20"] - 1
gap = panel["close"] - panel["ema20"]
panel["comp"] = np.where(gap.abs() > 1e-6, (panel["dema20"] - panel["ema20"]) / gap, np.nan)

print(panel[["dema_dev", "accel", "comp"]].corr(method="spearman"))

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
import numpy as np

# dema_dev 沿用拆解中已算出的结果
panel["ema_dev"] = panel["close"] / panel.groupby("code")["close"].transform(
    lambda s: s.ewm(span=20, adjust=False).mean()) - 1

# 补偿是否带来增量：与同周期 EMA 成对比较
ic_dema = cross_section_ic(panel, "dema_dev", "forward_5")
ic_ema = cross_section_ic(panel, "ema_dev", "forward_5")
common = ic_dema.index.intersection(ic_ema.index)
d = ic_dema[common] - ic_ema[common]
print("IC 差值均值：", round(d.mean(), 4), " t 值：",
      round(d.mean() / d.std() * np.sqrt(len(d)), 2))

print(ic_summary(ic_dema))
print(ic_summary(ic_ema))
print(layered_returns(panel, "dema_dev", "forward_5"))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df = panel[panel["code"] == "600519.SS"].copy()

# 加速量作为连续状态，正为向上外推
e1 = df["close"].ewm(alpha=2 / 21, adjust=False).mean()
df["accel"] = (2 * e1 - e1.ewm(alpha=2 / 21, adjust=False).mean()) / e1 - 1

print(timing_signal_test(df, "accel", "forward_5", upper=0.8))
print(conditional_quantile_return(df, "accel", "forward_5", q=5))
print(timing_backtest(df, "accel", "forward_5", entry_q=0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
panel["vol_ratio"] = panel["volume"] / panel.groupby("code")["volume"].transform(
    lambda s: s.rolling(20).mean())

# 负面对照：同源因子的相关通常极高
rho = panel.groupby("date").apply(
    lambda g: g[["dema_dev", "ema_dev"]].corr(method="spearman").iloc[0, 1])
print("平均相关：", round(rho.mean(), 3))

panel = combined_signal(panel, ["dema_dev", "vol_ratio"])

print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "dema_dev", "forward_5")))
print(ic_summary(cross_section_ic(panel, "vol_ratio", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
df = panel[panel["code"] == "600519.SS"].copy()

# DEMA20 = 2 * EMA20 - EMA20 的再平滑
e1 = df["close"].ewm(span=20, adjust=False).mean()
df["dema20"] = 2 * e1 - e1.ewm(span=20, adjust=False).mean()
df["ema20"] = e1
df["dema_dev"] = df["close"] / df["dema20"] - 1
df["accel"] = df["dema20"] / df["ema20"] - 1
# 组合条件：外推后的均线在价格下方，且外推量为正
df["cond"] = ((df["dema_dev"] > 0) & (df["accel"] > 0)).astype(int)

print("--- 组合条件 ---")
print(timing_backtest(df, "cond", "forward_5", entry_q=0.5))

# 单条件对照
df["cond_dev"] = (df["dema_dev"] > 0).astype(int)
df["cond_accel"] = (df["accel"] > 0).astype(int)

print("\n--- 仅偏离度 ---")
print(timing_backtest(df, "cond_dev", "forward_5", entry_q=0.5))

print("\n--- 仅加速量 ---")
print(timing_backtest(df, "cond_accel", "forward_5", entry_q=0.5))
