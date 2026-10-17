# ============================================================
# 第013章 零延迟指数移动平均线（ZLEMA）
# 模块 03 趋势类指标
# 源文件：模块03-趋势类指标/第013章-零延迟指数移动平均线（ZLEMA）.md
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

# 2. 手写 ZLEMA：先去滞后，再做指数平滑
n = 20
lag = (n - 1) // 2
alpha = 2 / (n + 1)

df = pd.DataFrame({"close": close})
df["d"] = 2 * df["close"] - df["close"].shift(lag)   # 去滞后价格
df["zlema"] = df["d"].ewm(alpha=alpha, adjust=False).mean()
df["ema"] = df["close"].ewm(alpha=alpha, adjust=False).mean()

# 3. 识别拐头
df["turn_up"] = (df["zlema"] > df["zlema"].shift(1)) & (df["zlema"].shift(1) <= df["zlema"].shift(2))
print("向上拐头次数：", int(df["turn_up"].sum()))

# 4. 绘图
fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(df.index, df["close"], label="收盘价", color="#333", linewidth=1)
ax.plot(df.index, df["ema"], label="EMA20", color="#2f6fb5")
ax.plot(df.index, df["zlema"], label="ZLEMA20", color="#1e8449")
ax.set_title("贵州茅台 ZLEMA20 与 EMA20 对照")
ax.legend()
plt.tight_layout()
plt.show()

# 5. 输出统计
print("ZLEMA20 与 EMA20 的平均价差：", round((df["zlema"] - df["ema"]).mean(), 3))

# ---- 代码块 2：拆解 ----

# 沿用第 007 章口径，拆解四个特征
g = panel.groupby("code")["close"]
panel["d"] = 2 * panel["close"] - g.shift(9)
panel["zlema20"] = panel.groupby("code")["d"].transform(
    lambda s: s.ewm(alpha=2 / 21, adjust=False).mean())
panel["zlema_dev"] = panel["close"] / panel["zlema20"] - 1
panel["zlema_slope"] = panel["zlema20"] / panel.groupby("code")["zlema20"].shift(5) - 1
panel["zl_gap"] = panel["zlema20"] / g.transform(
    lambda s: s.ewm(span=20, adjust=False).mean()) - 1
panel["r_lag"] = panel["close"] / g.shift(9) - 1

print(panel[["zlema_dev", "zlema_slope", "zl_gap", "r_lag"]].corr(method="spearman"))

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
import numpy as np

panel["ema_dev"] = panel["close"] / panel.groupby("code")["close"].transform(
    lambda s: s.ewm(span=20, adjust=False).mean()) - 1

# 去滞后是否优于普通 EMA，以及窗口位移本身的预测力
ic_zl = cross_section_ic(panel, "zlema_dev", "forward_5")
ic_ema = cross_section_ic(panel, "ema_dev", "forward_5")
common = ic_zl.index.intersection(ic_ema.index)
d = ic_zl[common] - ic_ema[common]
print("IC 差值均值：", round(d.mean(), 4), " t 值：",
      round(d.mean() / d.std() * np.sqrt(len(d)), 2))

print(ic_summary(ic_zl))
print(ic_summary(ic_ema))
print(ic_summary(cross_section_ic(panel, "r_lag", "forward_5")))
print(layered_returns(panel, "zlema_dev", "forward_5"))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df = panel[panel["code"] == "600519.SS"].copy()

# 去滞后量作为连续状态
print(timing_signal_test(df, "zl_gap", "forward_5", upper=0.8))
print(conditional_quantile_return(df, "zl_gap", "forward_5", q=5))
print(timing_backtest(df, "zl_gap", "forward_5", entry_q=0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
panel["vol_ratio"] = panel["volume"] / panel.groupby("code")["volume"].transform(
    lambda s: s.rolling(20).mean())

rho = panel.groupby("date").apply(
    lambda g: g[["zlema_dev", "r_lag"]].corr(method="spearman").iloc[0, 1])
print("偏离度与窗口位移的平均相关：", round(rho.mean(), 3))

panel = combined_signal(panel, ["zlema_dev", "vol_ratio"])

print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "zlema_dev", "forward_5")))
print(ic_summary(cross_section_ic(panel, "vol_ratio", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
df = panel[panel["code"] == "600519.SS"].copy()

# 去滞后价格：2 * 当日价格 - lag 日前价格，lag 取 (n - 1) / 2 向下取整
df["d"] = 2 * df["close"] - df["close"].shift(9)
df["zlema20"] = df["d"].ewm(span=20, adjust=False).mean()
df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
df["zlema_dev"] = df["close"] / df["zlema20"] - 1
df["zl_gap"] = df["zlema20"] / df["ema20"] - 1
# 组合条件：价格在去滞后均线上方，且去滞后量为正
df["cond"] = ((df["zlema_dev"] > 0) & (df["zl_gap"] > 0)).astype(int)

print("--- 组合条件 ---")
print(timing_backtest(df, "cond", "forward_5", entry_q=0.5))

# 单条件对照
df["cond_dev"] = (df["zlema_dev"] > 0).astype(int)
df["cond_gap"] = (df["zl_gap"] > 0).astype(int)

print("\n--- 仅偏离度 ---")
print(timing_backtest(df, "cond_dev", "forward_5", entry_q=0.5))

print("\n--- 仅去滞后量 ---")
print(timing_backtest(df, "cond_gap", "forward_5", entry_q=0.5))
