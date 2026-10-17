# ============================================================
# 第033章 肯特纳通道（Keltner）
# 模块 05 波动率类指标
# 源文件：模块05-波动率类指标/第033章-肯特纳通道（Keltner）.md
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

# 2. 真实波幅与 ATR（Wilder 平滑）
prev_close = close.shift(1)
tr = pd.concat([
    high - low,
    (high - prev_close).abs(),
    (low - prev_close).abs(),
], axis=1).max(axis=1)

n, m, k = 20, 10, 2
df = pd.DataFrame({"close": close})
df["atr"] = tr.ewm(alpha=1 / m, adjust=False).mean()

# 3. 中轨 EMA 与上下轨
df["mid"] = df["close"].ewm(span=n, adjust=False).mean()
df["up"] = df["mid"] + k * df["atr"]
df["dn"] = df["mid"] - k * df["atr"]

# 4. 宽度与 %K
df["kc_width"] = (df["up"] - df["dn"]) / df["mid"]
df["kc_pct"] = (df["close"] - df["dn"]) / (df["up"] - df["dn"])
print("当前通道宽度：", round(df["kc_width"].iloc[-1], 4))
print("当前 %K：", round(df["kc_pct"].iloc[-1], 4))

# 5. 绘图
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                               gridspec_kw={"height_ratios": [3, 1]})
ax1.plot(df.index, df["close"], label="收盘价", color="#333", linewidth=1)
ax1.plot(df.index, df["up"], label="上轨", color="#c0392b", linewidth=1)
ax1.plot(df.index, df["mid"], label="中轨", color="#2f6fb5", linewidth=1)
ax1.plot(df.index, df["dn"], label="下轨", color="#27ae60", linewidth=1)
ax1.set_title("贵州茅台肯特纳通道")
ax1.legend()
ax2.plot(df.index, df["kc_width"], color="#8e44ad", linewidth=1)
ax2.set_ylabel("通道宽度")
plt.tight_layout()
plt.show()

# 6. 输出统计
thr = df["kc_width"].quantile(0.2)
print("通道宽度处于低 20 百分位的天数占比：",
      round((df["kc_width"] < thr).mean(), 3))

# ---- 代码块 2：拆解 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
import numpy as np
import pandas as pd

# panel 需包含 date / code / high / low / close
panel = panel.sort_values(["code", "date"]).reset_index(drop=True)
prev_close = panel.groupby("code")["close"].shift(1)
panel["tr"] = pd.concat([panel["high"] - panel["low"],
                         (panel["high"] - prev_close).abs(),
                         (panel["low"] - prev_close).abs()], axis=1).max(axis=1)

# ATR(10) 与 EMA(20) 中轨，上下轨为中轨加减 2 倍 ATR
panel["atr10"] = panel.groupby("code")["tr"].transform(
    lambda s: s.ewm(alpha=1 / 10, adjust=False).mean())
panel["kc_mid"] = panel.groupby("code")["close"].transform(
    lambda s: s.ewm(span=20, adjust=False).mean())
panel["kc_up"] = panel["kc_mid"] + 2 * panel["atr10"]
panel["kc_dn"] = panel["kc_mid"] - 2 * panel["atr10"]
panel["kc_width"] = (panel["kc_up"] - panel["kc_dn"]) / panel["kc_mid"]
panel["kc_pct"] = (panel["close"] - panel["kc_dn"]) / (panel["kc_up"] - panel["kc_dn"])
panel["kc_dev"] = panel["close"] / panel["kc_mid"] - 1
panel["kc_width_chg"] = panel.groupby("code")["kc_width"].transform(
    lambda s: s / s.shift(5) - 1)

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# 第一组：%K 对收益目标
print(ic_summary(cross_section_ic(panel, "kc_pct", "forward_1")))
print(ic_summary(cross_section_ic(panel, "kc_pct", "forward_5")))
print(layered_returns(panel, "kc_pct", "forward_5"))

# 第二组：宽度对波动率目标，单独成表
print(ic_summary(cross_section_ic(panel, "kc_width", "fwd_vol_20")))

# 第三组：双通道宽度比，先补布林带宽度再检验
bb_sd = panel.groupby("code")["close"].transform(lambda s: s.rolling(20).std())
bb_mid = panel.groupby("code")["close"].transform(lambda s: s.rolling(20).mean())
panel["bb_width"] = 4 * bb_sd / bb_mid
panel["bw_ratio"] = panel["bb_width"] / panel["kc_width"]

print(ic_summary(cross_section_ic(panel, "bw_ratio", "fwd_vol_20")))
rho = panel.groupby("date").apply(
    lambda g: g[["kc_width", "bw_ratio"]].corr(method="spearman").iloc[0, 1])
print("宽度与比值的平均横截面相关：", round(rho.mean(), 3))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的 timing_signal_test / conditional_quantile_return / timing_backtest
df = panel[panel["code"] == "600519.SS"].sort_values("date").copy()

# 突破事件：%K 高于 95 分位视为站上上轨
print(timing_signal_test(df, "kc_pct", "forward_5", upper=0.95))

# 条件分位收益：%K 分五档
print(conditional_quantile_return(df, "kc_pct", "forward_5", q=5))

# 收窄与常态的收益分布对照
df["narrow"] = (df["kc_width"] < df["kc_width"].quantile(0.2)).astype(int)
print(df.groupby("narrow")["forward_5"].agg(
    样本数="count",
    平均收益=lambda s: round(s.mean() * 100, 3),
    标准差=lambda s: round(s.std() * 100, 3),
    夏普=lambda s: round(s.mean() / s.std() * np.sqrt(252 / 5), 2),
    左尾=lambda s: round(s.quantile(0.05) * 100, 3)))

print(timing_backtest(df, "kc_pct", "forward_5", entry_q=0.8))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
# 组合的截面验证：两条通道的宽度都反向，合成双通道低波动得分
panel["low_bb"] = -panel["bb_width"]
panel["low_kc"] = -panel["kc_width"]

rho = panel.groupby("date").apply(
    lambda g: g[["low_bb", "low_kc"]].corr(method="spearman").iloc[0, 1])
print("两条通道宽度的平均横截面相关：", round(rho.mean(), 3))

panel = combined_signal(panel, ["low_bb", "low_kc"])
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "low_bb", "forward_5")))
print(ic_summary(cross_section_ic(panel, "low_kc", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 沿用第 007 章定义的 timing_backtest
# 组合的择时验证：突破上轨且中轨向上才持仓
df = panel[panel["code"] == "600519.SS"].sort_values("date").copy()
df["kc_slope"] = df["kc_mid"] / df["kc_mid"].shift(5) - 1
df["cond_break"] = (df["kc_pct"] > 0.9).astype(int)
df["cond_trend"] = (df["kc_slope"] > 0).astype(int)
df["cond"] = ((df["cond_break"] == 1) & (df["cond_trend"] == 1)).astype(int)

print(timing_backtest(df, "cond_break", "forward_5", entry_q=0.5))
print(timing_backtest(df, "cond_trend", "forward_5", entry_q=0.5))
print(timing_backtest(df, "cond", "forward_5", entry_q=0.5))
