# ============================================================
# 第021章 相对强弱指数（RSI）
# 模块 04 震荡类指标
# 源文件：模块04-震荡类指标/第021章-相对强弱指数（RSI）.md
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

# 2. 计算 RSI（Wilder 平滑：alpha = 1/n，不是 2/(n+1)）
def rsi_wilder(series, n=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    avg_loss = loss.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)

df = pd.DataFrame({"close": close})
df["rsi14"] = rsi_wilder(df["close"], 14)
df["rsi6"]  = rsi_wilder(df["close"], 6)

# 3. 识别信号
df["overbought"] = (df["rsi14"] > 70).astype(int)
df["oversold"]   = (df["rsi14"] < 30).astype(int)
df["cross_up"]   = (df["rsi6"] > df["rsi14"]) & (df["rsi6"].shift(1) <= df["rsi14"].shift(1))
print(f"超买天数：{df['overbought'].sum()}  超卖天数：{df['oversold'].sum()}")
print(f"6 日上穿 14 日次数：{df['cross_up'].sum()}")

# 4. 绘图
import matplotlib
matplotlib.rcParams["font.sans-serif"] = ["PingFang SC", "SimHei", "Arial Unicode MS"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                               gridspec_kw={"height_ratios": [2, 1]})
ax1.plot(df.index, df["close"], color="#333", linewidth=1)
ax1.set_title("贵州茅台 收盘价与 RSI")
ax2.plot(df.index, df["rsi14"], label="RSI14", color="#2f6fb5")
ax2.plot(df.index, df["rsi6"], label="RSI6", color="#c0392b", linewidth=1)
ax2.axhline(70, color="#999", linestyle="--", linewidth=0.8)
ax2.axhline(30, color="#999", linestyle="--", linewidth=0.8)
ax2.axhline(50, color="#ccc", linewidth=0.8)
ax2.set_ylim(0, 100)
ax2.legend()
plt.tight_layout()
plt.show()

# 5. 输出统计
extreme = ((df["rsi14"] > 70) | (df["rsi14"] < 30)).sum()
print("处于极端区域的交易日占比：",
      round(extreme / df["rsi14"].notna().sum(), 3))

# ---- 代码块 2：拆解 ----

# 沿用第 007 章的数据准备（panel 含 date / code / close / high / low / volume）
import numpy as np
import pandas as pd

panel = panel.sort_values(["code", "date"]).reset_index(drop=True)

# Wilder 平滑：alpha = 1/n，与 TTR 的 RSI 口径一致
def rsi_wilder(s, n=14):
    d = s.diff()
    g = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    l = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + g / l)

# 极端状态的连续期数：超买侧记正，超卖侧记负，中性段归零
def signed_run(state):
    block = state.ne(state.shift()).cumsum()
    run = state.groupby(block).cumcount() + 1
    return run.where(state != 0, 0) * state

panel["rsi14"] = panel.groupby("code")["close"].transform(rsi_wilder)
# 中轴偏离：读数相对 50 的位置
panel["rsi_dev"] = panel["rsi14"] - 50
# 变化率：五期差分，单位为点
panel["rsi_chg"] = panel["rsi14"] - panel.groupby("code")["rsi14"].shift(5)

state = pd.Series(np.where(panel["rsi14"] > 70, 1,
                           np.where(panel["rsi14"] < 30, -1, 0)), index=panel.index)
panel["rsi_ext_run"] = state.groupby(panel["code"]).transform(signed_run)

print(panel.dropna(subset=["rsi14"]).head(8)[
    ["date", "code", "rsi14", "rsi_dev", "rsi_chg", "rsi_ext_run"]])

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# panel 含 date / code / close / forward_1 / forward_5

def rsi_wilder(s, n=14):
    d = s.diff()
    g = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    l = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + g / l)

panel["rsi14"] = panel.groupby("code")["close"].transform(rsi_wilder)
panel["rsi_dev"] = panel["rsi14"] - 50
panel["rsi_chg"] = panel["rsi14"] - panel.groupby("code")["rsi14"].shift(5)

for h in ["forward_1", "forward_5"]:
    print(f"\n--- 中轴偏离 vs {h} ---")
    print(ic_summary(cross_section_ic(panel, "rsi_dev", h)))
print(layered_returns(panel, "rsi_dev", "forward_5"))

# 变化率作对照
print(ic_summary(cross_section_ic(panel, "rsi_chg", "forward_5")))

# 符号稳定性：按年切分，检查 IC 是否反号
panel["year"] = pd.to_datetime(panel["date"]).dt.year
for y, g in panel.groupby("year"):
    print(y, round(cross_section_ic(g, "rsi_dev", "forward_5").mean(), 4))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df = panel[panel["code"] == "600519.SS"].copy()
df["rsi_low"] = -df["rsi_dev"]

print("--- 上尾：偏离值高于 80 分位 ---")
print(timing_signal_test(df, "rsi_dev", "forward_5", upper=0.8))

print("\n--- 下尾：取负后高于 80 分位，对应原值低于 20 分位 ---")
print(timing_signal_test(df, "rsi_low", "forward_5", upper=0.8))

print("\n--- 条件分位收益 ---")
print(conditional_quantile_return(df, "rsi_dev", "forward_5", q=5))

print("\n--- 择时策略与买入持有对照 ---")
print(timing_backtest(df, "rsi_dev", "forward_5", entry_q=0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal / cross_section_ic / timing_backtest
# 截面路径：RSI 中轴偏离与价格对均线偏离的组合
panel["sma20"] = panel.groupby("code")["close"].transform(lambda s: s.rolling(20).mean())
panel["sma_dev"] = panel["close"] / panel["sma20"] - 1

rho = panel.groupby("date").apply(
    lambda g: g[["rsi_dev", "sma_dev"]].corr(method="spearman").iloc[0, 1])
print("两个特征的平均横截面相关：", round(rho.mean(), 3))

# 方向对齐：若前一步判定 rsi_dev 为负向因子，先执行 panel["rsi_dev"] = -panel["rsi_dev"]
panel = combined_signal(panel, ["rsi_dev", "sma_dev"])

print("\n--- 组合 vs 单特征 ---")
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "rsi_dev", "forward_5")))
print(ic_summary(cross_section_ic(panel, "sma_dev", "forward_5")))

# 择时路径：只在价格位于二十日均线上方时接受超卖信号
df = panel[panel["code"] == "600519.SS"].copy()
df["rsi_up"] = np.where(df["close"] > df["sma20"], df["rsi_dev"], np.nan)

print("\n--- 上升趋势样本内的择时 ---")
print(timing_backtest(df, "rsi_up", "forward_5", entry_q=0.7))

print("\n--- 全样本对照 ---")
print(timing_backtest(df, "rsi_dev", "forward_5", entry_q=0.7))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
# 趋势过滤：价格在 20 日均线上方时，超卖读数才视为持仓条件
df = panel[panel["code"] == "600519.SS"].sort_values("date").copy()
df["sma20"] = df["close"].rolling(20).mean()
df["cond"] = ((df["close"] > df["sma20"]) & (df["rsi14"] < 30)).astype(int)

print(timing_backtest(df, "cond", "forward_5", entry_q=0.5))
