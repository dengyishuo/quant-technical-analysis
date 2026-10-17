# ============================================================
# 第015章 多空指数（BBI）
# 模块 03 趋势类指标
# 源文件：模块03-趋势类指标/第015章-多空指数（BBI）.md
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

# 2. 手写 BBI：四个周期 SMA 的算术平均
df = pd.DataFrame({"close": close})
periods = [5, 10, 20, 60]
for p in periods:
    df[f"sma{p}"] = df["close"].rolling(p).mean()
df["bbi"] = df[[f"sma{p}" for p in periods]].mean(axis=1)

# 3. 识别信号
df["above"] = (df["close"] > df["bbi"]).astype(int)
df["break_up"] = (df["above"] == 1) & (df["above"].shift(1) == 0)
df["break_dn"] = (df["above"] == 0) & (df["above"].shift(1) == 1)
print(f"向上突破：{df['break_up'].sum()}  向下跌破：{df['break_dn'].sum()}")

# 4. 绘图
fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(df.index, df["close"], label="收盘价", color="#333", linewidth=1)
ax.plot(df.index, df["sma20"], label="SMA20", color="#999", linewidth=1)
ax.plot(df.index, df["bbi"], label="BBI", color="#d35400", linewidth=2)
ax.set_title("贵州茅台 BBI 多空指数")
ax.legend()
plt.tight_layout()
plt.show()

# 5. 输出统计
print("价格位于 BBI 上方的天数占比：",
      round((df["close"] > df["bbi"]).sum() / df["bbi"].notna().sum(), 3))

# ---- 代码块 2：拆解 ----

# 沿用第 007 章的数据准备（panel 含 date / code / close / high / low / volume）
import pandas as pd

panel = panel.sort_values(["code", "date"]).reset_index(drop=True)

# 四个周期的 SMA 与综合线
for p in (5, 10, 20, 60):
    panel[f"sma{p}"] = panel.groupby("code")["close"].transform(
        lambda s, p=p: s.rolling(p).mean())
panel["bbi"] = panel[["sma5", "sma10", "sma20", "sma60"]].mean(axis=1)

# 价格偏离度：价格相对多周期综合成本的位置
panel["bbi_dev"] = panel["close"] / panel["bbi"] - 1
# 综合线斜率：五日跨度上的相对变化
panel["bbi_slope"] = panel.groupby("code")["bbi"].transform(lambda s: s / s.shift(5) - 1)
# 排列一致性：四条均线相对五日前是否上行，取值 0 至 4
panel["bbi_align"] = sum(
    (panel[f"sma{p}"] > panel.groupby("code")[f"sma{p}"].shift(5)).astype(int)
    for p in (5, 10, 20, 60))
# 综合与单周期之差：综合线相对 20 日均线的偏移
panel["bbi_sma_diff"] = panel["bbi"] / panel["sma20"] - 1

# 前 60 个交易日为均线预热期，用 dropna 略去
print(panel[["date", "code", "bbi_dev", "bbi_slope",
             "bbi_align", "bbi_sma_diff"]].dropna().head())

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
for p in (5, 10, 20, 60):
    panel[f"sma{p}"] = panel.groupby("code")["close"].transform(
        lambda s, p=p: s.rolling(p).mean())
panel["bbi"] = panel[["sma5", "sma10", "sma20", "sma60"]].mean(axis=1)
panel["bbi_dev"] = panel["close"] / panel["bbi"] - 1
panel["sma20_dev"] = panel["close"] / panel["sma20"] - 1
# 四条均线相对五日前是否上行，取值 0 至 4
panel["bbi_align"] = sum(
    (panel[f"sma{p}"] > panel.groupby("code")[f"sma{p}"].shift(5)).astype(int)
    for p in (5, 10, 20, 60))

for h in ["forward_1", "forward_5"]:
    print(f"\n--- BBI 偏离度 vs {h} ---")
    print(ic_summary(cross_section_ic(panel, "bbi_dev", h)))

print(layered_returns(panel, "bbi_dev", "forward_5"))

print(ic_summary(cross_section_ic(panel, "bbi_align", "forward_5")))

# 与单条 20 日均线偏离度对照，判断多周期是否带来增量
print(ic_summary(cross_section_ic(panel, "sma20_dev", "forward_5")))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df = panel[panel["code"] == "600519.SS"].copy()

print("--- 信号触发日检验（偏离度高于 80 分位）---")
print(timing_signal_test(df, "bbi_dev", "forward_5", upper=0.8))

print("\n--- 条件分位收益（偏离度分五档）---")
print(conditional_quantile_return(df, "bbi_dev", "forward_5", q=5))

print("\n--- 择时策略与买入持有对照 ---")
print(timing_backtest(df, "bbi_dev", "forward_5", entry_q=0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
panel["vol_ratio"] = panel["volume"] / panel.groupby("code")["volume"].transform(
    lambda s: s.rolling(20).mean())

# 先看两个特征的横截面相关
rho = panel.groupby("date").apply(
    lambda g: g[["bbi_dev", "vol_ratio"]].corr(method="spearman").iloc[0, 1])
print("两个特征的平均横截面相关：", round(rho.mean(), 3))

panel = combined_signal(panel, ["bbi_dev", "vol_ratio"])

print("\n--- 组合 vs 单特征 ---")
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "bbi_dev", "forward_5")))
print(ic_summary(cross_section_ic(panel, "vol_ratio", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
df = panel[panel["code"] == "600519.SS"].copy()
df["cond"] = ((df["bbi_dev"] > 0) & (df["bbi_align"] == 4)).astype(int)

print(timing_backtest(df, "cond", "forward_5", entry_q=0.5))
