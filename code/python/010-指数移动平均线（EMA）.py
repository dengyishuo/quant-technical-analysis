# ============================================================
# 第010章 指数移动平均线（EMA）
# 模块 03 趋势类指标
# 源文件：模块03-趋势类指标/第010章-指数移动平均线（EMA）.md
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

# 2. 计算 EMA（span = n，adjust = False 对应标准递推式）
df = pd.DataFrame({"close": close})
df["ema12"] = df["close"].ewm(span=12, adjust=False).mean()
df["ema26"] = df["close"].ewm(span=26, adjust=False).mean()

# 3. 识别信号
df["above"] = (df["ema12"] > df["ema26"]).astype(int)
df["cross_up"] = (df["above"] == 1) & (df["above"].shift(1) == 0)
df["cross_down"] = (df["above"] == 0) & (df["above"].shift(1) == 1)
print(f"金叉次数：{df['cross_up'].sum()}  死叉次数：{df['cross_down'].sum()}")

# 4. 绘图
fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(df.index, df["close"], label="收盘价", color="#333", linewidth=1)
ax.plot(df.index, df["ema12"], label="EMA12", color="#2f6fb5")
ax.plot(df.index, df["ema26"], label="EMA26", color="#c0392b")
ax.set_title("贵州茅台 EMA12 / EMA26")
ax.legend()
plt.tight_layout()
plt.show()

# 5. 输出统计
print("收盘价位于 26 日 EMA 上方的比例：",
      round((df["close"] > df["ema26"]).sum() / df["ema26"].notna().sum(), 3))

# ---- 代码块 2：拆解 ----

# 沿用第 007 章口径，拆解主要特征
g = panel.groupby("code")["close"]
for n in (12, 20, 26):
    panel[f"ema{n}"] = g.transform(lambda s, n=n: s.ewm(span=n, adjust=False).mean())
panel["ema_dev"] = panel["close"] / panel["ema20"] - 1
panel["ema_slope"] = panel["ema20"] / panel.groupby("code")["ema20"].shift(5) - 1
panel["ema_gap"] = panel["ema12"] / panel["ema26"] - 1

print(panel[["ema_dev", "ema_slope", "ema_gap"]].corr(method="spearman"))

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
import numpy as np

panel["ema_dev"] = panel["close"] / panel.groupby("code")["close"].transform(
    lambda s: s.ewm(span=20, adjust=False).mean()) - 1
panel["sma_dev"] = panel["close"] / panel.groupby("code")["close"].transform(
    lambda s: s.rolling(20).mean()) - 1

# 同源对照：同一交易日、同一前向窗口，比较两条 IC 序列的差值
ic_ema = cross_section_ic(panel, "ema_dev", "forward_5")
ic_sma = cross_section_ic(panel, "sma_dev", "forward_5")
common = ic_ema.index.intersection(ic_sma.index)
d = ic_ema[common] - ic_sma[common]
print("IC 差值均值：", round(d.mean(), 4), " t 值：",
      round(d.mean() / d.std() * np.sqrt(len(d)), 2))

print(ic_summary(ic_ema))
print(ic_summary(ic_sma))
print(layered_returns(panel, "ema_dev", "forward_5"))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df = panel[panel["code"] == "600519.SS"].copy()

# 快慢 EMA 差作为连续状态量，比 0/1 的交叉标记保留更多信息
df["ema12"] = df["close"].ewm(span=12, adjust=False).mean()
df["ema26"] = df["close"].ewm(span=26, adjust=False).mean()
df["ema_gap"] = df["ema12"] / df["ema26"] - 1

print(timing_signal_test(df, "ema_gap", "forward_5", upper=0.8))
print(conditional_quantile_return(df, "ema_gap", "forward_5", q=5))
print(timing_backtest(df, "ema_gap", "forward_5", entry_q=0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
panel["vol_ratio"] = panel["volume"] / panel.groupby("code")["volume"].transform(
    lambda s: s.rolling(20).mean())

# 先看横截面相关，再决定是否值得组合
rho = panel.groupby("date").apply(
    lambda g: g[["ema_dev", "vol_ratio"]].corr(method="spearman").iloc[0, 1])
print("两个特征的平均横截面相关：", round(rho.mean(), 3))

panel = combined_signal(panel, ["ema_dev", "vol_ratio"])

print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "ema_dev", "forward_5")))
print(ic_summary(cross_section_ic(panel, "vol_ratio", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
import numpy as np
import pandas as pd

df = panel[panel["code"] == "600519.SS"].copy()
df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()

# ADX(14)：方向运动经 Wilder 平滑后合成
up = df["high"].diff()
down = -df["low"].diff()
plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
tr = pd.concat([df["high"] - df["low"],
                (df["high"] - df["close"].shift()).abs(),
                (df["low"] - df["close"].shift()).abs()], axis=1).max(axis=1)
atr14 = tr.ewm(alpha=1 / 14, adjust=False).mean().replace(0, np.nan)
plus_di = 100 * plus_dm.ewm(alpha=1 / 14, adjust=False).mean() / atr14
minus_di = 100 * minus_dm.ewm(alpha=1 / 14, adjust=False).mean() / atr14
dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
df["adx14"] = dx.ewm(alpha=1 / 14, adjust=False).mean()

# 组合条件：价格在二十日 EMA 上方且趋势强度高于二十五
df["cond"] = ((df["close"] > df["ema20"]) & (df["adx14"] > 25)).astype(int)

print("--- 组合条件 ---")
print(timing_backtest(df, "cond", "forward_5", entry_q=0.5))

# 单条件对照
df["cond_ema"] = (df["close"] > df["ema20"]).astype(int)
df["cond_adx"] = (df["adx14"] > 25).astype(int)

print("\n--- 仅价格位置 ---")
print(timing_backtest(df, "cond_ema", "forward_5", entry_q=0.5))

print("\n--- 仅趋势强度 ---")
print(timing_backtest(df, "cond_adx", "forward_5", entry_q=0.5))
