# ============================================================
# 第027章 去趋势价格震荡器（DPO）
# 模块 04 震荡类指标
# 源文件：模块04-震荡类指标/第027章-去趋势价格震荡器（DPO）.md
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

# 2. 计算 DPO（手写：短窗均线扣减 + 位移对齐）
def dpo(series, n=20, align=True):
    k = n // 2 + 1
    sma_k = series.rolling(k).mean()
    raw = series - sma_k
    # align=True 时整体左移 k-1 期，末尾留空
    return raw.shift(-(k - 1)) if align else raw

df = pd.DataFrame({"close": close})
df["dpo20"] = dpo(df["close"], 20)          # 图上对齐，末尾空白
df["dpo20_raw"] = dpo(df["close"], 20, align=False)  # 研究用，不位移
df["dpo10"] = dpo(df["close"], 10)

# 3. 识别信号（用未位移的原始差值判断，避免使用未来信息）
df["up"]   = (df["dpo20_raw"] > 0) & (df["dpo20_raw"].shift(1) <= 0)
df["down"] = (df["dpo20_raw"] < 0) & (df["dpo20_raw"].shift(1) >= 0)
print(f"上穿零轴次数：{df['up'].sum()}  下穿零轴次数：{df['down'].sum()}")
print(f"端部空白交易日：{df['dpo20'].tail(20).isna().sum()}")

# 4. 绘图
import matplotlib
matplotlib.rcParams["font.sans-serif"] = ["PingFang SC", "SimHei", "Arial Unicode MS"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                               gridspec_kw={"height_ratios": [2, 1]})
ax1.plot(df.index, df["close"], color="#333", linewidth=1)
ax1.set_title("贵州茅台 收盘价与 DPO")
ax2.plot(df.index, df["dpo20"], label="DPO20", color="#2f6fb5")
ax2.plot(df.index, df["dpo10"], label="DPO10", color="#c0392b", linewidth=1)
ax2.axhline(0, color="#888", linewidth=0.8)
ax2.legend()
plt.tight_layout()
plt.show()

# 5. 输出统计
print("DPO 均值：", round(df["dpo20_raw"].mean(), 3))
print("DPO 标准差：", round(df["dpo20_raw"].std(), 3))
print("正值天数与负值天数之比：",
      round((df["dpo20_raw"] > 0).sum() / (df["dpo20_raw"] < 0).sum(), 3))

# ---- 代码块 2：拆解 ----

# 沿用第 007 章的数据准备（panel 含 date / code / close / high / low / volume）
import numpy as np
import pandas as pd

# n = 20 时 k = 20 // 2 + 1 = 11，位移长度 k - 1 = 10 期
panel = panel.sort_values(["code", "date"]).reset_index(drop=True)

panel["sma11"] = panel.groupby("code")["close"].transform(
    lambda s: s.rolling(11).mean())
# 未位移的原始差值：t 时刻只用到 t 及之前的收盘价，因子取自这一列
panel["dpo_raw"] = panel["close"] - panel["sma11"]
# 相对化差值：除以同一期的均线，消除价格量纲
panel["dpo_rel"] = panel["dpo_raw"] / panel["sma11"]
# 分位值：近 120 日窗口内的经验百分位，含当日，映射到 0 到 100
panel["dpo_pct"] = panel.groupby("code")["dpo_rel"].transform(
    lambda s: s.rolling(120).apply(lambda x: (x <= x[-1]).mean(), raw=True) * 100)
# 相位状态：周期处在基线之上为 1，之下为 0
panel["dpo_sign"] = (panel["dpo_raw"] > 0).astype(int)
# 位移版：t 时刻取 dpo_raw 在 t + 10 时刻的值，含未来十期信息
# 仅作诊断，因子不得使用位移版本
panel["dpo_shift"] = panel.groupby("code")["dpo_raw"].shift(-10)

panel[["code", "date", "dpo_raw", "dpo_rel", "dpo_pct", "dpo_sign", "dpo_shift"]].head(8)

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# k = 20 // 2 + 1 = 11；因子取未位移的原始差值
panel["sma11"] = panel.groupby("code")["close"].transform(
    lambda s: s.rolling(11).mean())
panel["dpo_raw"] = panel["close"] - panel["sma11"]
panel["dpo_rel"] = panel["dpo_raw"] / panel["sma11"]
panel["dpo_pct"] = panel.groupby("code")["dpo_rel"].transform(
    lambda s: s.rolling(120).apply(lambda x: (x <= x[-1]).mean(), raw=True))
panel["dpo_shift"] = panel.groupby("code")["dpo_raw"].shift(-10)  # 仅作诊断

for h in ["forward_1", "forward_5"]:
    print(ic_summary(cross_section_ic(panel, "dpo_rel", h)))
print(layered_returns(panel, "dpo_rel", "forward_5"))
print(ic_summary(cross_section_ic(panel, "dpo_pct", "forward_5")))

# 诊断：位移版含未来十期信息，IC 会明显偏高，不可用于实盘
print(ic_summary(cross_section_ic(panel, "dpo_shift", "forward_5")))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df = panel[panel["code"] == "600519.SS"].copy()
df["dpo_neg"] = -df["dpo_pct"]

print(timing_signal_test(df, "dpo_pct", "forward_5", upper=0.8))
print(timing_signal_test(df, "dpo_neg", "forward_5", upper=0.8))
print(conditional_quantile_return(df, "dpo_pct", "forward_5", q=5))

# 状态即仓位：未位移差值在零轴上方时持仓
df["dpo_pos"] = (df["dpo_raw"] > 0).astype(int)
print(timing_backtest(df, "dpo_pos", "forward_5", entry_q=0))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal / cross_section_ic / ic_summary / timing_backtest
panel["roc12"] = panel.groupby("code")["close"].transform(
    lambda s: (s / s.shift(12) - 1) * 100)

# 剥离趋势的 DPO 与保留趋势的 ROC，相关性通常不高
rho = panel.groupby("date").apply(
    lambda g: g[["dpo_rel", "roc12"]].corr(method="spearman").iloc[0, 1])
print("两个特征的平均横截面相关：", round(rho.mean(), 3))

panel = combined_signal(panel, ["dpo_rel", "roc12"])
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "dpo_rel", "forward_5")))
print(ic_summary(cross_section_ic(panel, "roc12", "forward_5")))

# 组合的择时验证：周期在零轴上方且站上二十日均线才持仓
df = panel[panel["code"] == "600519.SS"].copy()
df["cond"] = ((df["dpo_raw"] > 0) &
              (df["close"] > df["close"].rolling(20).mean())).astype(int)
print(timing_backtest(df, "cond", "forward_5", entry_q=0))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
# 事件型写法：未位移的差值由负转正且价格站上二十日均线才持仓
df = panel[panel["code"] == "600519.SS"].copy()
df["sma20"] = df["close"].rolling(20).mean()
# 相位转换：当日为正、前一日非正，取值一律来自 dpo_raw
turn_up = (df["dpo_raw"] > 0) & (df["dpo_raw"].shift(1) <= 0)
df["cond"] = ((df["close"] > df["sma20"]) & turn_up.fillna(False)).astype(int)

print(timing_backtest(df, "cond", "forward_5", entry_q=0.5))
