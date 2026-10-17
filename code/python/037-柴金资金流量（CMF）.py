# ============================================================
# 第037章 柴金资金流量（CMF）
# 模块 06 量价类指标
# 源文件：模块06-量价类指标/第037章-柴金资金流量（CMF）.md
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
data = (_panel[_panel["code"] == "300750.SZ"]
        .set_index("date").sort_index()[["open", "high", "low", "close", "volume"]])
data.columns = ["Open", "High", "Low", "Close", "Volume"]
high = data["High"].squeeze()
low = data["Low"].squeeze()
close = data["Close"].squeeze()
volume = data["Volume"].squeeze()

# 2. 计算资金流向乘数与资金流量
rng = (high - low).replace(0, np.nan)
mfm = ((close - low) - (high - close)) / rng
mfv = mfm * volume

# 3. 计算 20 期 CMF（求和之比）
n = 20
df = pd.DataFrame({"close": close})
df["cmf20"] = mfv.rolling(n).sum() / volume.rolling(n).sum()

# 4. 识别信号
df["above_zero"] = (df["cmf20"] > 0).astype(int)
df["cross_up"] = (df["above_zero"] == 1) & (df["above_zero"].shift(1) == 0)
print(f"CMF 上穿零轴次数：{df['cross_up'].sum()}")
print(f"CMF 高于 0.05 的天数：{(df['cmf20'] > 0.05).sum()}")

# 5. 绘图
fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
axes[0].plot(df.index, df["close"], color="#333", linewidth=1)
axes[0].set_title("宁德时代 收盘价与 CMF")
axes[1].plot(df.index, df["cmf20"], color="#2f6fb5", label="CMF(20)")
axes[1].axhline(0.05, color="#c0392b", linestyle="--", linewidth=0.8)
axes[1].axhline(-0.05, color="#c0392b", linestyle="--", linewidth=0.8)
axes[1].axhline(0, color="#999", linewidth=0.8)
axes[1].legend()
plt.tight_layout()
plt.show()

# 6. 输出统计
print("CMF 均值：", round(df["cmf20"].mean(), 4))
print("CMF 标准差：", round(df["cmf20"].std(), 4))
print("CMF 取值范围：", round(df["cmf20"].min(), 3), "至", round(df["cmf20"].max(), 3))

# ---- 代码块 2：拆解 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
import numpy as np
import pandas as pd

# panel 已含 date / code / high / low / close / volume / forward_1 / forward_5
panel = panel.sort_values(["code", "date"]).reset_index(drop=True)
grp = panel.groupby("code")

# 资金流向乘数：区间高度为零时（一字板）记为缺失
rng = (panel["high"] - panel["low"]).replace(0, np.nan)
mfm = ((panel["close"] - panel["low"]) - (panel["high"] - panel["close"])) / rng
panel["mfv"] = mfm * panel["volume"]

# 20 期 CMF 为求和之比，有界于 -1 到 1
panel["cmf20"] = (grp["mfv"].transform(lambda s: s.rolling(20).sum())
                  / grp["volume"].transform(lambda s: s.rolling(20).sum()))
panel["cmf_state"] = np.sign(panel["cmf20"])

# 5 日均值：压掉日频锯齿，保留方向
panel["cmf_ma5"] = grp["cmf20"].transform(lambda s: s.rolling(5).mean())
panel["cmf_chg"] = panel["cmf20"] - grp["cmf20"].shift(10)

# 零轴上方持续期，带符号
panel["above"] = (panel["cmf20"] > 0).astype(int)
run_id = panel.groupby("code")["above"].transform(lambda s: (s != s.shift()).cumsum())
run_len = panel.groupby(["code", run_id])["above"].cumcount() + 1
panel["cmf_dur"] = run_len * np.where(panel["above"] > 0, 1, -1)
panel.loc[panel["cmf20"].isna(), "cmf_dur"] = np.nan

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# 平滑读数与变化量分别检验
for f in ["cmf_ma5", "cmf_chg"]:
    print(f"\n--- {f} vs forward_5 ---")
    print(ic_summary(cross_section_ic(panel, f, "forward_5")))

print(layered_returns(panel, "cmf_ma5", "forward_5"))

# 对同期动量取残差，看是否还有独立信息
panel["mom20"] = panel["close"] / grp["close"].shift(20) - 1

def _resid(g):
    g = g.dropna(subset=["cmf_ma5", "mom20"])
    if len(g) < 10:
        return pd.Series(np.nan, index=g.index)
    beta = np.polyfit(g["mom20"], g["cmf_ma5"], 1)
    return pd.Series(g["cmf_ma5"] - np.polyval(beta, g["mom20"]), index=g.index)

panel["cmf_resid"] = panel.groupby("date", group_keys=False).apply(_resid)

print("\n--- 动量残差 ---")
print(ic_summary(cross_section_ic(panel, "cmf_resid", "forward_5")))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df = panel[panel["code"] == "600519.SS"].sort_values("date").copy()

print("--- 信号触发日检验（读数高于 80 分位）---")
print(timing_signal_test(df, "cmf_ma5", "forward_5", upper=0.8))

print("\n--- 条件分位收益（读数分五档）---")
print(conditional_quantile_return(df, "cmf_ma5", "forward_5", q=5))

print("\n--- 择时策略与买入持有对照 ---")
print(timing_backtest(df, "cmf_ma5", "forward_5", entry_q=0.6))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
panel["vol_ratio"] = panel["volume"] / grp["volume"].transform(
    lambda s: s.rolling(20).mean())

rho = panel.groupby("date").apply(
    lambda g: g[["cmf_ma5", "vol_ratio"]].corr(method="spearman").iloc[0, 1])
print("两个特征的平均横截面相关：", round(rho.mean(), 3))

panel = combined_signal(panel, ["cmf_ma5", "vol_ratio"])

print("\n--- 组合 vs 单特征 ---")
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "cmf_ma5", "forward_5")))
print(ic_summary(cross_section_ic(panel, "vol_ratio", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
df2 = panel[panel["code"] == "600519.SS"].sort_values("date").copy()
df2["sma20"] = df2["close"].rolling(20).mean()
df2["cond"] = ((df2["cmf_ma5"] > 0.05) & (df2["close"] > df2["sma20"])).astype(int)

print(timing_backtest(df2, "cond", "forward_5", entry_q=0.5))
