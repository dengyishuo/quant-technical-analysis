# ============================================================
# 第028章 随机动量指数（SMI）
# 模块 04 震荡类指标
# 源文件：模块04-震荡类指标/第028章-随机动量指数（SMI）.md
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
high, low, close = (data["High"].squeeze(), data["Low"].squeeze(), data["Close"].squeeze())

# 2. 计算 SMI（手写：以区间中点为基准）
def smi(high, low, close, n=14, m=3):
    hh = high.rolling(n).max()
    ll = low.rolling(n).min()
    mid = (hh + ll) / 2
    max_dev = np.maximum(hh - mid, mid - ll)
    line = (close - mid) / max_dev * 100
    return line, line.rolling(m).mean()

df = pd.DataFrame({"high": high, "low": low, "close": close})
df["smi"], df["signal"] = smi(df["high"], df["low"], df["close"], 14, 3)

# 3. 识别信号
df["golden"] = (df["smi"] > df["signal"]) & (df["smi"].shift(1) <= df["signal"].shift(1))
df["low_golden"] = df["golden"] & (df["smi"] < 40)
df["cross_zero_up"] = (df["smi"] > 0) & (df["smi"].shift(1) <= 0)
print(f"金叉次数：{df['golden'].sum()}  其中中低位金叉：{df['low_golden'].sum()}")
print(f"读数越过 80 的交易日：{(df['smi'] > 80).sum()}  跌破负 80 的交易日：{(df['smi'] < -80).sum()}")

# 4. 绘图
import matplotlib
matplotlib.rcParams["font.sans-serif"] = ["PingFang SC", "SimHei", "Arial Unicode MS"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                               gridspec_kw={"height_ratios": [2, 1]})
ax1.plot(df.index, df["close"], color="#333", linewidth=1)
ax1.set_title("贵州茅台 收盘价与 SMI")
ax2.plot(df.index, df["smi"], label="SMI", color="#2f6fb5")
ax2.plot(df.index, df["signal"], label="信号线", color="#c0392b")
for lv in (80, 40, -40, -80, 0):
    ax2.axhline(lv, color="#bbb", linestyle="--", linewidth=0.8)
ax2.legend()
plt.tight_layout()
plt.show()

# 5. 输出统计
print("SMI 均值：", round(df["smi"].mean(), 3))
print("SMI 标准差：", round(df["smi"].std(), 3))
print("读数落在正负 40 以内的占比：",
      round((df["smi"].abs() < 40).sum() / df["smi"].notna().sum(), 3))

# ---- 代码块 2：拆解 ----

# 沿用第 007 章的数据准备（panel 含 date / code / close / high / low / volume）
import numpy as np
import pandas as pd

panel = panel.sort_values(["code", "date"]).reset_index(drop=True)

g = panel.groupby("code")
hh14 = g["high"].transform(lambda s: s.rolling(14).max())
ll14 = g["low"].transform(lambda s: s.rolling(14).min())
mid14, half = (hh14 + ll14) / 2, (hh14 - ll14) / 2
# 读数：偏离中点除以半个区间高度，区间高度为零时置空
panel["smi14"] = (panel["close"] - mid14) / half.replace(0, np.nan) * 100
# 零轴偏离：相对自身六十日均值的位置，单位为点
panel["smi_center"] = panel["smi14"] - panel.groupby("code")["smi14"].transform(
    lambda s: s.rolling(60).mean())
# 与信号线的差：即柱状值，读数减去三日均线
panel["smi_diff"] = panel["smi14"] - panel.groupby("code")["smi14"].transform(
    lambda s: s.rolling(3).mean())
# 极值状态：读数在正负 80 之外取符号，其余为零
panel["smi_ext"] = np.sign(panel["smi14"]) * (panel["smi14"].abs() > 80).astype(int)

panel[["code", "date", "smi14", "smi_center", "smi_diff", "smi_ext"]].head(8)

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
g = panel.groupby("code")
hh14 = g["high"].transform(lambda s: s.rolling(14).max())
ll14 = g["low"].transform(lambda s: s.rolling(14).min())
mid14, half = (hh14 + ll14) / 2, (hh14 - ll14) / 2
panel["smi14"] = ((panel["close"] - mid14) / half.replace(0, np.nan) * 100)
panel["smi_diff"] = panel["smi14"] - panel.groupby("code")["smi14"].transform(
    lambda s: s.rolling(3).mean())
panel["rsv_c"] = ((panel["close"] - ll14) / (hh14 - ll14).replace(0, np.nan)
                  * 100 - 50)

for h in ["forward_1", "forward_5"]:
    print(ic_summary(cross_section_ic(panel, "smi14", h)))
print(layered_returns(panel, "smi14", "forward_5"))
print(ic_summary(cross_section_ic(panel, "smi_diff", "forward_5")))

# 与 KDJ 的区间位置对照：同源，SMI 多一层中点偏离
print(ic_summary(cross_section_ic(panel, "rsv_c", "forward_5")))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df = panel[panel["code"] == "600519.SS"].copy()
df["smi_neg"] = -df["smi14"]

print(timing_signal_test(df, "smi14", "forward_5", upper=0.8))
print(timing_signal_test(df, "smi_neg", "forward_5", upper=0.8))
print(conditional_quantile_return(df, "smi14", "forward_5", q=5))

# 反向写法：读数越低越持仓；顺势写法取原读数，两条对照
print(timing_backtest(df, "smi_neg", "forward_5", entry_q=0.7))
print(timing_backtest(df, "smi14", "forward_5", entry_q=0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / timing_backtest
# 正交化：SMI 对区间位置取横截面残差
g = panel.groupby("date")
x, y = panel["rsv_c"], panel["smi14"]
mx, my = g["rsv_c"].transform("mean"), g["smi14"].transform("mean")
sxy = ((x - mx) * (y - my)).groupby(panel["date"]).transform("sum")
sxx = ((x - mx) ** 2).groupby(panel["date"]).transform("sum")
panel["smi_resid"] = (y - my) - sxy / sxx * (x - mx)

print(ic_summary(cross_section_ic(panel, "smi14", "forward_5")))
print(ic_summary(cross_section_ic(panel, "rsv_c", "forward_5")))
print(ic_summary(cross_section_ic(panel, "smi_resid", "forward_5")))

# 组合的择时验证：超卖且价格站上二十日均线
df = panel[panel["code"] == "600519.SS"].copy()
df["cond"] = ((df["smi14"] < -20) &
              (df["close"] > df["close"].rolling(20).mean())).astype(int)
print(timing_backtest(df, "cond", "forward_5", entry_q=0))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
# 事件型写法：SMI 上穿信号线且价格站上二十日均线才持仓
df = panel[panel["code"] == "600519.SS"].copy()
df["sma20"] = df["close"].rolling(20).mean()
# smi_diff 是读数与信号线之差，由负转正即金叉
cross_up = (df["smi_diff"] > 0) & (df["smi_diff"].shift(1) <= 0)
df["cond"] = ((df["close"] > df["sma20"]) & cross_up.fillna(False)).astype(int)

print(timing_backtest(df, "cond", "forward_5", entry_q=0.5))
