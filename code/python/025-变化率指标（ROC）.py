# ============================================================
# 第025章 变化率指标（ROC）
# 模块 04 震荡类指标
# 源文件：模块04-震荡类指标/第025章-变化率指标（ROC）.md
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

# 2. 计算 ROC
df = pd.DataFrame({"close": close})
df["roc12"] = (df["close"] / df["close"].shift(12) - 1) * 100
df["roc24"] = (df["close"] / df["close"].shift(24) - 1) * 100

# 3. 识别信号
df["cross_up"]   = (df["roc12"] > 0) & (df["roc12"].shift(1) <= 0)
df["cross_down"] = (df["roc12"] < 0) & (df["roc12"].shift(1) >= 0)
print(f"上穿零轴次数：{df['cross_up'].sum()}  下穿零轴次数：{df['cross_down'].sum()}")
print(f"越过正 20 的交易日：{(df['roc12'] > 20).sum()}  跌破负 20 的交易日：{(df['roc12'] < -20).sum()}")

# 4. 绘图
import matplotlib
matplotlib.rcParams["font.sans-serif"] = ["PingFang SC", "SimHei", "Arial Unicode MS"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                               gridspec_kw={"height_ratios": [2, 1]})
ax1.plot(df.index, df["close"], color="#333", linewidth=1)
ax1.set_title("贵州茅台 收盘价与 ROC")
ax2.plot(df.index, df["roc12"], label="ROC12", color="#2f6fb5")
ax2.plot(df.index, df["roc24"], label="ROC24", color="#c0392b", linewidth=1)
ax2.axhline(0, color="#888", linewidth=0.8)
ax2.axhline(20, color="#bbb", linestyle="--", linewidth=0.8)
ax2.axhline(-20, color="#bbb", linestyle="--", linewidth=0.8)
ax2.legend()
plt.tight_layout()
plt.show()

# 5. 输出统计
print("ROC 均值：", round(df["roc12"].mean(), 3))
print("ROC 标准差：", round(df["roc12"].std(), 3))
print("读数落在正负 20 以内的占比：",
      round((df["roc12"].abs() < 20).sum() / df["roc12"].notna().sum(), 3))

# ---- 代码块 2：拆解 ----

# 沿用第 007 章的数据准备（panel 含 date / code / close / high / low / volume）
import numpy as np
import pandas as pd

panel = panel.sort_values(["code", "date"]).reset_index(drop=True)

panel["ret1"] = panel.groupby("code")["close"].pct_change()
# 变化率读数：十二个交易日的累计变化，单位为百分比
panel["roc12"] = panel.groupby("code")["close"].transform(
    lambda s: (s / s.shift(12) - 1) * 100)
# 分位标准化值：近 120 日窗口内的经验百分位，含当日，映射到 0 到 100
panel["roc_pct"] = panel.groupby("code")["roc12"].transform(
    lambda s: s.rolling(120).apply(lambda x: (x <= x[-1]).mean(), raw=True) * 100)
# 符号状态：方向单独提出，幅度归零
panel["roc_sign"] = (panel["roc12"] > 0).astype(int)
# 波动调整值：读数除以收益率的滚动标准差，换算成倍数
panel["vol20"] = panel.groupby("code")["ret1"].transform(
    lambda s: s.rolling(20).std() * 100)
panel["roc_std"] = panel["roc12"] / panel["vol20"]

panel[["code", "date", "roc12", "roc_pct", "roc_sign", "roc_std"]].head(8)

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
panel["ret1"] = panel.groupby("code")["close"].pct_change()
panel["roc12"] = panel.groupby("code")["close"].transform(
    lambda s: (s / s.shift(12) - 1) * 100)
panel["roc60"] = panel.groupby("code")["close"].transform(
    lambda s: (s / s.shift(60) - 1) * 100)
panel["vol20"] = panel.groupby("code")["ret1"].transform(
    lambda s: s.rolling(20).std() * 100)
panel["roc_std"] = panel["roc12"] / panel["vol20"]      # 波动调整值
panel["roc_sign"] = (panel["roc12"] > 0).astype(int)    # 符号状态

# 原始读数：一日与五日两个前向窗口
for h in ["forward_1", "forward_5"]:
    print(ic_summary(cross_section_ic(panel, "roc12", h)))

print(layered_returns(panel, "roc12", "forward_5"))

# 符号状态与波动调整值作对照
print(ic_summary(cross_section_ic(panel, "roc_sign", "forward_5")))
print(ic_summary(cross_section_ic(panel, "roc_std", "forward_5")))

# 按年份切分，检查 IC 符号是否稳定
ic = cross_section_ic(panel, "roc12", "forward_5").rename("ic").reset_index()
ic["date"] = pd.to_datetime(ic["date"])
ic["year"] = ic["date"].dt.year
print(ic.groupby("year")["ic"].agg(["mean", "count"]).round(4))

# 对照回归：对 60 日读数取横截面残差，看短周期项是否还有增量
g = panel.groupby("date")
x, y = panel["roc60"], panel["roc12"]
mx, my = g["roc60"].transform("mean"), g["roc12"].transform("mean")
sxy = ((x - mx) * (y - my)).groupby(panel["date"]).transform("sum")
sxx = ((x - mx) ** 2).groupby(panel["date"]).transform("sum")
panel["roc_resid"] = (y - my) - sxy / sxx * (x - mx)

print(ic_summary(cross_section_ic(panel, "roc_resid", "forward_5")))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df = panel[panel["code"] == "600519.SS"].copy()
df["roc_neg"] = -df["roc12"]   # 取负后上分位即对应超卖端

print("--- 信号触发日检验（读数高于 80 分位）---")
print(timing_signal_test(df, "roc12", "forward_5", upper=0.8))

print("\n--- 超卖端（读数低于 20 分位）---")
print(timing_signal_test(df, "roc_neg", "forward_5", upper=0.8))

print("\n--- 条件分位收益（读数分五档）---")
print(conditional_quantile_return(df, "roc12", "forward_5", q=5))

print("\n--- 择时策略与买入持有对照 ---")
print(timing_backtest(df, "roc12", "forward_5", entry_q=0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal / cross_section_ic / ic_summary / timing_backtest
panel["vol_ratio"] = panel["volume"] / panel.groupby("code")["volume"].transform(
    lambda s: s.rolling(20).mean())

# 组合的截面验证：先看相关，再看加权后的 ICIR
rho = panel.groupby("date").apply(
    lambda g: g[["roc12", "vol_ratio"]].corr(method="spearman").iloc[0, 1])
print("两个特征的平均横截面相关：", round(rho.mean(), 3))

panel = combined_signal(panel, ["roc12", "vol_ratio"])
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "roc12", "forward_5")))
print(ic_summary(cross_section_ic(panel, "vol_ratio", "forward_5")))

# 组合的择时验证：读数转正且站上二十日均线才持仓
df = panel[panel["code"] == "600519.SS"].copy()
df["cond"] = ((df["roc12"] > 0) &
              (df["close"] > df["close"].rolling(20).mean())).astype(int)

# 条件信号为 0 或 1，阈值取 0 等价于条件成立即持仓
print(timing_backtest(df, "cond", "forward_5", entry_q=0))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
# 二值条件经 entry_q = 0.5 转成仓位，并与单用读数大于零的对照组并列
# 条件成立的交易日若超过半数，中位数升到 1，仓位会恒为零，此时改用 entry_q = 0
df = panel[panel["code"] == "600519.SS"].copy()
df["sma20"] = df["close"].rolling(20).mean()
df["cond"] = ((df["close"] > df["sma20"]) & (df["roc12"] > 0)).astype(int)
df["cond_base"] = (df["roc12"] > 0).astype(int)

print(timing_backtest(df, "cond", "forward_5", entry_q=0.5))
print(timing_backtest(df, "cond_base", "forward_5", entry_q=0.5))
