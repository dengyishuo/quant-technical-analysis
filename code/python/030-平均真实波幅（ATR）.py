# ============================================================
# 第030章 平均真实波幅（ATR）
# 模块 05 波动率类指标
# 源文件：模块05-波动率类指标/第030章-平均真实波幅（ATR）.md
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
high, low, close = data["High"].squeeze(), data["Low"].squeeze(), data["Close"].squeeze()

# 2. 计算真实波幅 TR：三项取最大值
prev_close = close.shift(1)
tr = pd.concat([
    high - low,
    (high - prev_close).abs(),
    (low - prev_close).abs(),
], axis=1).max(axis=1)

# 3. Wilder 平滑等价于 alpha = 1/n 的指数平均
n = 14
atr14 = tr.ewm(alpha=1 / n, adjust=False).mean()
df = pd.DataFrame({"close": close, "atr14": atr14})
df["atr_ratio"] = df["atr14"] / df["close"]

# 4. 识别信号：20 日最高价减 3 倍 ATR 的追踪止损
df["trail_stop"] = df["close"].rolling(20).max() - 3 * df["atr14"]
print("当前追踪止损位：", round(df["trail_stop"].iloc[-1], 2))

# 5. 绘图
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                               gridspec_kw={"height_ratios": [3, 1]})
ax1.plot(df.index, df["close"], label="收盘价", color="#333", linewidth=1)
ax1.plot(df.index, df["trail_stop"], label="ATR 追踪止损", color="#c0392b", linewidth=1)
ax1.set_title("贵州茅台 ATR 追踪止损")
ax1.legend()
ax2.plot(df.index, df["atr14"], color="purple", linewidth=1)
ax2.set_ylabel("ATR14")
plt.tight_layout()
plt.show()

# 6. 输出统计
print("ATR 比率的均值：", round(df["atr_ratio"].mean(), 4))

# ---- 代码块 2：拆解 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
import numpy as np
import pandas as pd

# panel 需包含 date / code / high / low / close
panel = panel.sort_values(["code", "date"]).reset_index(drop=True)

# 真实波幅：日内幅度与两个方向的跳空缺口取最大
prev_close = panel.groupby("code")["close"].shift(1)
panel["tr"] = pd.concat([panel["high"] - panel["low"],
                         (panel["high"] - prev_close).abs(),
                         (panel["low"] - prev_close).abs()], axis=1).max(axis=1)

# Wilder 平滑等价于 alpha = 1/n 的指数平均
panel["atr14"] = panel.groupby("code")["tr"].transform(
    lambda s: s.ewm(alpha=1 / 14, adjust=False).mean())
panel["atr_ratio"] = panel["atr14"] / panel["close"]
panel["atr_chg"] = panel.groupby("code")["atr14"].transform(lambda s: s / s.shift(10) - 1)
panel["atr_pctile"] = panel.groupby("code")["atr14"].transform(
    lambda s: s.rolling(250).apply(lambda x: (x <= x[-1]).mean(), raw=True))

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# 第一组：收益目标
for h in ["forward_1", "forward_5"]:
    print(f"\n--- 收益目标：ATR 比率 vs {h} ---")
    print(ic_summary(cross_section_ic(panel, "atr_ratio", h)))
print(layered_returns(panel, "atr_ratio", "forward_5"))
# 分位版本作稳健性对照，极值影响应明显减弱
print(ic_summary(cross_section_ic(panel, "atr_pctile", "forward_5")))

# 第二组：波动率目标，单独成表，不与上一组的数值比较大小
print("\n--- 波动率目标 ---")
print(ic_summary(cross_section_ic(panel, "atr_ratio", "fwd_vol_20")))
print(layered_returns(panel, "atr_ratio", "fwd_vol_20"))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的 timing_signal_test / conditional_quantile_return / timing_backtest
from scipy import stats

df = panel[panel["code"] == "600519.SS"].sort_values("date").copy()
hi = df["atr_ratio"].quantile(0.8)
lo = df["atr_ratio"].quantile(0.2)
df["state"] = np.where(df["atr_ratio"] >= hi, "高波动",
                       np.where(df["atr_ratio"] <= lo, "低波动", None))

# 分布对照：均值之外，同时看标准差、夏普、胜率与左尾
print(df.dropna(subset=["state"]).groupby("state")["forward_5"].agg(
    样本数="count",
    平均收益=lambda s: round(s.mean() * 100, 3),
    标准差=lambda s: round(s.std() * 100, 3),
    夏普=lambda s: round(s.mean() / s.std() * np.sqrt(252 / 5), 2),
    胜率=lambda s: round((s > 0).mean(), 3),
    左尾=lambda s: round(s.quantile(0.05) * 100, 3)))

# 方差齐性检验：两组的离散程度是否真的不同
hi_r = df.loc[df["state"] == "高波动", "forward_5"].dropna()
lo_r = df.loc[df["state"] == "低波动", "forward_5"].dropna()
print("方差齐性检验 p 值：", round(stats.levene(hi_r, lo_r).pvalue, 4))

print(timing_signal_test(df, "atr_ratio", "forward_5", upper=0.8))
print(conditional_quantile_return(df, "atr_ratio", "forward_5", q=5))
df["low_vol"] = -df["atr_ratio"]
print(timing_backtest(df, "low_vol", "forward_5", entry_q=0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
# 组合的截面验证：先统一符号方向，再做加权
panel["low_vol"] = -panel["atr_ratio"]
panel["mom20"] = panel.groupby("code")["close"].transform(lambda s: s / s.shift(20) - 1)

rho = panel.groupby("date").apply(
    lambda g: g[["low_vol", "mom20"]].corr(method="spearman").iloc[0, 1])
print("两个特征的平均横截面相关：", round(rho.mean(), 3))

panel = combined_signal(panel, ["low_vol", "mom20"])
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "low_vol", "forward_5")))
print(ic_summary(cross_section_ic(panel, "mom20", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 沿用第 007 章定义的 timing_backtest
# 组合的择时验证：低波动与中轨向上同时成立才持仓
df = panel[panel["code"] == "600519.SS"].sort_values("date").copy()
df["sma20"] = df["close"].rolling(20).mean()
df["cond_vol"] = (df["atr_pctile"] < 0.8).astype(int)
df["cond_trend"] = (df["close"] > df["sma20"]).astype(int)
df["cond"] = ((df["cond_vol"] == 1) & (df["cond_trend"] == 1)).astype(int)

print(timing_backtest(df, "cond_vol", "forward_5", entry_q=0.5))
print(timing_backtest(df, "cond_trend", "forward_5", entry_q=0.5))
print(timing_backtest(df, "cond", "forward_5", entry_q=0.5))
