# ============================================================
# 第009章 简单移动平均线（SMA）
# 模块 03 趋势类指标
# 源文件：模块03-趋势类指标/第009章-简单移动平均线（SMA）.md
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
close = data["Close"].squeeze()

# 2. 计算 SMA（rolling 默认等权，与 R 的 SMA 一致）
df = pd.DataFrame({"close": close})
df["sma20"] = df["close"].rolling(20).mean()
df["sma60"] = df["close"].rolling(60).mean()
df["sma200"] = df["close"].rolling(200).mean()

# 3. 识别信号
df["above_sma60"] = (df["sma20"] > df["sma60"]).astype(int)
df["cross_up"] = (df["above_sma60"] == 1) & (df["above_sma60"].shift(1) == 0)
df["cross_down"] = (df["above_sma60"] == 0) & (df["above_sma60"].shift(1) == 1)
print(f"金叉次数：{df['cross_up'].sum()}  死叉次数：{df['cross_down'].sum()}")

# 4. 绘图
import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(df.index, df["close"], label="收盘价", color="#333", linewidth=1)
ax.plot(df.index, df["sma20"], label="SMA20", color="#2f6fb5")
ax.plot(df.index, df["sma60"], label="SMA60", color="#c0392b")
ax.set_title("贵州茅台 SMA20 / SMA60")
ax.legend()
plt.tight_layout()
plt.show()

# 5. 输出统计
print("价格位于 200 日均线上方的比例：",
      round((df["close"] > df["sma200"]).sum() / df["sma200"].notna().sum(), 3))

# ---- 代码块 2：拆解 ----

# 沿用第 007 章口径，拆解四个特征
import numpy as np

panel = panel.sort_values(["code", "date"]).reset_index(drop=True)

panel["sma20"] = panel.groupby("code")["close"].transform(
    lambda s: s.rolling(20).mean())
# 价格偏离度：价格相对二十日均线的位置
panel["sma_dev"] = panel["close"] / panel["sma20"] - 1
# 均线斜率：均线五期的推进速度
panel["sma_slope"] = panel["sma20"] / panel.groupby("code")["sma20"].shift(5) - 1
# 斜率加速度：斜率相对五期前的变化
panel["slope_acc"] = panel["sma_slope"] - panel.groupby("code")["sma_slope"].shift(5)

# 状态久期：连续位于均线同侧的期数，上方为正、下方为负
def _state_dur(s):
    sgn = np.sign(s.fillna(0)).astype(int)
    seg = (sgn != sgn.shift()).cumsum()
    dur = sgn.groupby(seg).transform("size") * sgn
    return dur.where(s.notna())

panel["state_dur"] = (panel["close"] - panel["sma20"]).groupby(
    panel["code"]).transform(_state_dur)

print(panel[["date", "code", "sma_dev", "sma_slope", "slope_acc", "state_dur"]].dropna().head(8))

# ---- 代码块 3：截面选股能力 ----

# 沿用「双重检验方法论」一章定义的 cross_section_ic / ic_summary / layered_returns
panel["sma20"] = panel.groupby("code")["close"].transform(lambda s: s.rolling(20).mean())
panel["sma_dev"] = panel["close"] / panel["sma20"] - 1
panel["sma_slope"] = panel.groupby("code")["sma20"].transform(lambda s: s / s.shift(5) - 1)

# 偏离度因子：一日与五日两个前向窗口对照
for h in ["forward_1", "forward_5"]:
    print(f"\n--- 偏离度 vs {h} ---")
    print(ic_summary(cross_section_ic(panel, "sma_dev", h)))

print(layered_returns(panel, "sma_dev", "forward_5"))

# 斜率因子作对照
print(ic_summary(cross_section_ic(panel, "sma_slope", "forward_5")))

# 对标的中立性做一次检查：偏离度与股价水平的相关
rho = panel.groupby("date").apply(
    lambda g: g[["sma_dev", "close"]].corr(method="spearman").iloc[0, 1])
print("偏离度与股价水平的平均相关：", round(rho.mean(), 3))

# ---- 代码块 4：择时能力 ----

# 沿用「双重检验方法论」一章的三种择时检验
df = panel[panel["code"] == "600519.SS"].copy()

print("--- 信号触发日检验（偏离度高于 80 分位）---")
print(timing_signal_test(df, "sma_dev", "forward_5", upper=0.8))

print("\n--- 条件分位收益（偏离度分五档）---")
print(conditional_quantile_return(df, "sma_dev", "forward_5", q=5))

print("\n--- 择时策略与买入持有对照 ---")
print(timing_backtest(df, "sma_dev", "forward_5", entry_q=0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用「双重检验方法论」一章的 combined_signal
# 先看两个特征的横截面相关，再决定是否值得组合
panel["vol_ratio"] = panel["volume"] / panel.groupby("code")["volume"].transform(
    lambda s: s.rolling(20).mean())

rho = panel.groupby("date").apply(
    lambda g: g[["sma_dev", "vol_ratio"]].corr(method="spearman").iloc[0, 1])
print("两个特征的平均横截面相关：", round(rho.mean(), 3))

# 加权型组合：等权
panel = combined_signal(panel, ["sma_dev", "vol_ratio"])

print("\n--- 组合 vs 单特征 ---")
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "sma_dev", "forward_5")))
print(ic_summary(cross_section_ic(panel, "vol_ratio", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
df = panel[panel["code"] == "600519.SS"].copy()
df["sma20"] = df["close"].rolling(20).mean()
df["sma_dev"] = df["close"] / df["sma20"] - 1
df["vol_ratio"] = df["volume"] / df["volume"].rolling(20).mean()
# 组合条件：价格在均线上方且成交量高于二十日均量
df["cond"] = ((df["sma_dev"] > 0) & (df["vol_ratio"] > 1)).astype(int)

print("--- 组合条件 ---")
print(timing_backtest(df, "cond", "forward_5", entry_q=0.5))

# 单条件对照
df["cond_dev"] = (df["sma_dev"] > 0).astype(int)
df["cond_vol"] = (df["vol_ratio"] > 1).astype(int)

print("\n--- 仅偏离度 ---")
print(timing_backtest(df, "cond_dev", "forward_5", entry_q=0.5))

print("\n--- 仅量能 ---")
print(timing_backtest(df, "cond_vol", "forward_5", entry_q=0.5))
