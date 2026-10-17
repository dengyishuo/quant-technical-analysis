# ============================================================
# 第032章 布林带（BBands）
# 模块 05 波动率类指标
# 源文件：模块05-波动率类指标/第032章-布林带（BBands）.md
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

# 2. 中轨与标准差（pandas 的 std 默认样本无偏估计）
df = pd.DataFrame({"close": close})
n, k = 20, 2
df["mid"] = df["close"].rolling(n).mean()
sd = df["close"].rolling(n).std()
df["up"] = df["mid"] + k * sd
df["dn"] = df["mid"] - k * sd

# 3. 带宽与 %B
df["band_width"] = (df["up"] - df["dn"]) / df["mid"]
df["pctB"] = (df["close"] - df["dn"]) / (df["up"] - df["dn"])
print("当前带宽：", round(df["band_width"].iloc[-1], 4))
print("当前 %B：", round(df["pctB"].iloc[-1], 4))

# 4. 识别信号：带宽低于 20 百分位视为挤压
thr = df["band_width"].quantile(0.2)
df["squeeze"] = df["band_width"] < thr
print("带宽处于低 20 百分位的天数占比：", round(df["squeeze"].mean(), 3))

# 5. 绘图
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                               gridspec_kw={"height_ratios": [3, 1]})
ax1.plot(df.index, df["close"], label="收盘价", color="#333", linewidth=1)
ax1.plot(df.index, df["up"], label="上轨", color="#c0392b", linewidth=1)
ax1.plot(df.index, df["mid"], label="中轨", color="#2f6fb5", linewidth=1)
ax1.plot(df.index, df["dn"], label="下轨", color="#27ae60", linewidth=1)
ax1.set_title("贵州茅台布林带")
ax1.legend()
ax2.plot(df.index, df["band_width"], color="#8e44ad", linewidth=1)
ax2.set_ylabel("带宽")
plt.tight_layout()
plt.show()

# 6. 输出统计
print("收盘价位于上轨之上的天数占比：",
      round((df["close"] > df["up"]).mean(), 3))

# ---- 代码块 2：拆解 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
import numpy as np
import pandas as pd

# panel 需包含 date / code / close
panel = panel.sort_values(["code", "date"]).reset_index(drop=True)
panel["bb_mid"] = panel.groupby("code")["close"].transform(lambda s: s.rolling(20).mean())
bb_sd = panel.groupby("code")["close"].transform(lambda s: s.rolling(20).std())
panel["bb_up"] = panel["bb_mid"] + 2 * bb_sd
panel["bb_dn"] = panel["bb_mid"] - 2 * bb_sd
panel["bb_pctb"] = ((panel["close"] - panel["bb_dn"])
                    / (panel["bb_up"] - panel["bb_dn"]))
panel["bb_width"] = (panel["bb_up"] - panel["bb_dn"]) / panel["bb_mid"]
panel["bb_width_chg"] = panel.groupby("code")["bb_width"].transform(
    lambda s: s / s.shift(4) - 1)
# 挤压：带宽低于全样本 20 分位，实盘须改滚动分位
panel["squeeze"] = (panel["bb_width"] < panel["bb_width"].quantile(0.2)).astype(int)

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# 第一组：%B 对收益目标
print(ic_summary(cross_section_ic(panel, "bb_pctb", "forward_1")))
print(ic_summary(cross_section_ic(panel, "bb_pctb", "forward_5")))
print(layered_returns(panel, "bb_pctb", "forward_5"))

# 第二组：带宽对波动率目标，单独成表
print(ic_summary(cross_section_ic(panel, "bb_width", "fwd_vol_20")))

# 挤压是二值状态，用分组对照而不是 IC
print(panel.groupby("squeeze").agg(
    样本数=("fwd_vol_20", "count"),
    未来波动=("fwd_vol_20", lambda s: round(s.mean(), 4)),
    未来收益=("forward_5", lambda s: round(s.mean() * 100, 3)),
    收益标准差=("forward_5", lambda s: round(s.std() * 100, 3))))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的 timing_signal_test / conditional_quantile_return / timing_backtest
df = panel[panel["code"] == "600519.SS"].sort_values("date").copy()

# 触轨事件：%B 高于 95 分位视为触及上轨
print(timing_signal_test(df, "bb_pctb", "forward_5", upper=0.95))

# 条件分位收益：%B 分五档
print(conditional_quantile_return(df, "bb_pctb", "forward_5", q=5))

# 挤压与非挤压的收益分布对照
print(df.groupby("squeeze")["forward_5"].agg(
    样本数="count",
    平均收益=lambda s: round(s.mean() * 100, 3),
    标准差=lambda s: round(s.std() * 100, 3),
    夏普=lambda s: round(s.mean() / s.std() * np.sqrt(252 / 5), 2),
    左尾=lambda s: round(s.quantile(0.05) * 100, 3)))

df["low_b"] = -df["bb_pctb"]
print(timing_backtest(df, "low_b", "forward_5", entry_q=0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
# 组合的截面验证：两个维度都反向使用，符号先摆正
panel["low_pos"] = -panel["bb_pctb"]
panel["low_bw"] = -panel["bb_width"]

rho = panel.groupby("date").apply(
    lambda g: g[["low_pos", "low_bw"]].corr(method="spearman").iloc[0, 1])
print("两个维度的平均横截面相关：", round(rho.mean(), 3))

panel = combined_signal(panel, ["low_pos", "low_bw"])
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "low_pos", "forward_5")))
print(ic_summary(cross_section_ic(panel, "low_bw", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 沿用第 007 章定义的 timing_backtest
# 组合的择时验证：挤压状态下价格上穿中轨才持仓
df = panel[panel["code"] == "600519.SS"].sort_values("date").copy()
df["cond_sq"] = (df["bb_width"] < df["bb_width"].quantile(0.3)).astype(int)
df["cond_up"] = (df["close"] > df["bb_mid"]).astype(int)
df["cond"] = ((df["cond_sq"] == 1) & (df["cond_up"] == 1)).astype(int)

print(timing_backtest(df, "cond_sq", "forward_5", entry_q=0.5))
print(timing_backtest(df, "cond_up", "forward_5", entry_q=0.5))
print(timing_backtest(df, "cond", "forward_5", entry_q=0.5))
