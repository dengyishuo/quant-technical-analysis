# ============================================================
# 第038章 成交量震荡器（VO）
# 模块 06 量价类指标
# 源文件：模块06-量价类指标/第038章-成交量震荡器（VO）.md
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

# 2. 计算短期与长期成交量均线
df = pd.DataFrame({"close": close, "volume": volume})
df["v_s"] = df["volume"].rolling(10).mean()
df["v_l"] = df["volume"].rolling(20).mean()

# 3. 计算 VO：差值型与比值型
df["vo_abs"] = df["v_s"] - df["v_l"]
df["vo_pct"] = (df["v_s"] - df["v_l"]) / df["v_l"] * 100

# 4. 识别信号：比值型 VO 穿越零轴
df["above_zero"] = (df["vo_pct"] > 0).astype(int)
df["cross_up"] = (df["above_zero"] == 1) & (df["above_zero"].shift(1) == 0)
print(f"VO 上穿零轴次数：{df['cross_up'].sum()}")
print(f"VO 高于 30% 的天数：{(df['vo_pct'] > 30).sum()}")

# 5. 绘图
fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
axes[0].plot(df.index, df["close"], color="#333", linewidth=1)
axes[0].set_title("贵州茅台 收盘价与成交量震荡器")
axes[1].bar(df.index, df["vo_pct"], color="#9bb8d8", width=1.0, label="VO 比值型")
axes[1].axhline(0, color="#999", linewidth=0.8)
axes[1].axhline(30, color="#c0392b", linestyle="--", linewidth=0.8)
axes[1].axhline(-30, color="#c0392b", linestyle="--", linewidth=0.8)
axes[1].legend()
plt.tight_layout()
plt.show()

# 6. 输出统计
print("VO 均值：", round(df["vo_pct"].mean(), 2))
print("VO 标准差：", round(df["vo_pct"].std(), 2))
price_up = close.diff() > 0
vo_up = df["vo_pct"].diff() > 0
print("价格与 VO 同向比例：", round((price_up == vo_up).mean(), 3))

# ---- 代码块 2：拆解 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
import numpy as np
import pandas as pd

# panel 已含 date / code / close / volume / forward_1 / forward_5
# 比值型 VO 按本章公式手写：(SMA10 - SMA20) / SMA20，输出为小数
panel = panel.sort_values(["code", "date"]).reset_index(drop=True)
grp = panel.groupby("code")

panel["v_s"] = grp["volume"].transform(lambda s: s.rolling(10).mean())
panel["v_l"] = grp["volume"].transform(lambda s: s.rolling(20).mean())
panel["vo_ratio"] = (panel["v_s"] - panel["v_l"]) / panel["v_l"]
panel["vo_state"] = np.sign(panel["vo_ratio"])

# 阈值取 0.5，对应正文的 50%
panel["vo_thr"] = (panel["vo_ratio"].abs() > 0.5).astype(int)
panel["vo_chg"] = panel["vo_ratio"] - grp["vo_ratio"].shift(5)

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
for h in ["forward_1", "forward_5"]:
    print(f"\n--- VO 比值 vs {h} ---")
    print(ic_summary(cross_section_ic(panel, "vo_ratio", h)))

print(layered_returns(panel, "vo_ratio", "forward_5"))

# 缩尾：分母偏小的标的会给出极端读数
panel["vo_w"] = panel.groupby("date")["vo_ratio"].transform(
    lambda s: s.clip(s.quantile(0.01), s.quantile(0.99)))

print("\n--- 缩尾后 ---")
print(ic_summary(cross_section_ic(panel, "vo_w", "forward_5")))

# 按成交额分位分组，检查是否只是市值暴露
panel["size_grp"] = panel.groupby("date")["volume"].transform(
    lambda s: pd.qcut(s.rank(method="first"), 3, labels=False))
for g, sub in panel.groupby("size_grp"):
    print("成交额组", g, round(cross_section_ic(sub, "vo_w", "forward_5").mean(), 4))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df = panel[panel["code"] == "600519.SS"].sort_values("date").copy()

print("--- 信号触发日检验（读数高于 80 分位）---")
print(timing_signal_test(df, "vo_w", "forward_5", upper=0.8))

print("\n--- 条件分位收益（读数分五档）---")
print(conditional_quantile_return(df, "vo_w", "forward_5", q=5))

print("\n--- 择时策略与买入持有对照 ---")
print(timing_backtest(df, "vo_w", "forward_5", entry_q=0.7))

# 把价格方向作为前置条件，比较四组组合的收益
df["价涨"] = (df["close"] > df["close"].rolling(20).mean()).astype(int)
df["组合"] = "价" + df["价涨"].astype(str) + "量" + (df["vo_w"] > 0).astype(int).astype(str)
print(df.groupby("组合")["forward_5"].agg(["count", "mean"]).round(4))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
panel["mom20"] = panel["close"] / grp["close"].shift(20) - 1

rho = panel.groupby("date").apply(
    lambda g: g[["vo_w", "mom20"]].corr(method="spearman").iloc[0, 1])
print("两个特征的平均横截面相关：", round(rho.mean(), 3))

panel = combined_signal(panel, ["vo_w", "mom20"])

print("\n--- 组合 vs 单特征 ---")
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "vo_w", "forward_5")))
print(ic_summary(cross_section_ic(panel, "mom20", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
df2 = panel[panel["code"] == "600519.SS"].sort_values("date").copy()
df2["sma20"] = df2["close"].rolling(20).mean()
df2["cond"] = ((df2["vo_w"] > 0) & (df2["close"] > df2["sma20"])).astype(int)

print(timing_backtest(df2, "cond", "forward_5", entry_q=0.5))
