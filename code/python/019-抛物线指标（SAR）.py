# ============================================================
# 第019章 抛物线指标（SAR）
# 模块 03 趋势类指标
# 源文件：模块03-趋势类指标/第019章-抛物线指标（SAR）.md
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
high = data["High"].squeeze()
low = data["Low"].squeeze()
close = data["Close"].squeeze()

# 2. 手写 SAR
def parabolic_sar(high, low, af0=0.02, af_max=0.2):
    n = len(high)
    sar = np.zeros(n)
    trend = np.ones(n, dtype=int)          # 1 上升，-1 下降
    ep = np.zeros(n)                        # 极值点
    af = np.zeros(n)
    # 用前两根 K 线判定初始方向
    trend[0] = 1
    ep[0] = high.iloc[0]
    af[0] = af0
    sar[0] = low.iloc[0]
    for i in range(1, n):
        prev_sar = sar[i - 1]
        if trend[i - 1] == 1:
            candidate = prev_sar + af[i - 1] * (ep[i - 1] - prev_sar)
            if low.iloc[i] < candidate:      # 反转为下降
                trend[i] = -1
                sar[i] = ep[i - 1]
                ep[i] = low.iloc[i]
                af[i] = af0
            else:
                trend[i] = 1
                sar[i] = candidate
                if high.iloc[i] > ep[i - 1]:
                    ep[i] = high.iloc[i]
                    af[i] = min(af[i - 1] + af0, af_max)
                else:
                    ep[i] = ep[i - 1]
                    af[i] = af[i - 1]
        else:
            candidate = prev_sar - af[i - 1] * (prev_sar - ep[i - 1])
            if high.iloc[i] > candidate:     # 反转为上升
                trend[i] = 1
                sar[i] = ep[i - 1]
                ep[i] = high.iloc[i]
                af[i] = af0
            else:
                trend[i] = -1
                sar[i] = candidate
                if low.iloc[i] < ep[i - 1]:
                    ep[i] = low.iloc[i]
                    af[i] = min(af[i - 1] + af0, af_max)
                else:
                    ep[i] = ep[i - 1]
                    af[i] = af[i - 1]
    return pd.Series(sar, index=high.index), pd.Series(trend, index=high.index)

sar, trend = parabolic_sar(high, low)
df = pd.DataFrame({"close": close, "sar": sar, "trend": trend})

# 3. 识别信号
df["above"] = (df["close"] > df["sar"]).astype(int)
df["flip_multi"] = (df["above"] == 1) & (df["above"].shift(1) == 0)
df["flip_short"] = (df["above"] == 0) & (df["above"].shift(1) == 1)
print(f"转多信号：{df['flip_multi'].sum()}  转空信号：{df['flip_short'].sum()}")

# 4. 绘图
fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(df.index, df["close"], label="收盘价", color="#333", linewidth=1)
ax.scatter(df.index, df["sar"], s=4,
           c=np.where(df["trend"] == 1, "#27ae60", "#c0392b"), label="SAR")
ax.set_title("贵州茅台 SAR(0.02, 0.2)")
ax.legend()
plt.tight_layout()
plt.show()

# 5. 输出统计
print("价格位于 SAR 上方的天数占比：",
      round((df["close"] > df["sar"]).sum() / df["sar"].notna().sum(), 3))

# ---- 代码块 2：拆解 ----

# 沿用第 007 章的数据准备（panel 含 date / code / close / high / low / volume）
import pandas as pd

panel = panel.sort_values(["code", "date"]).reset_index(drop=True)

# parabolic_sar 见本章代码实现小节的递推实现，按标的逐段计算
panel["sar"] = panel.groupby("code", group_keys=False).apply(
    lambda g: parabolic_sar(g["high"], g["low"])[0])

# 偏离度：价格相对止损位的距离
panel["sar_dev"] = panel["close"] / panel["sar"] - 1
# 方向状态：价格在 SAR 上方记 1，下方记 0
panel["sar_state"] = (panel["close"] > panel["sar"]).astype(int)

# 真实波幅按标的取昨收，再做 Wilder 平滑得到 ATR
prev_close = panel.groupby("code")["close"].shift(1)
panel["tr"] = pd.concat([panel["high"] - panel["low"],
                         (panel["high"] - prev_close).abs(),
                         (panel["low"] - prev_close).abs()], axis=1).max(axis=1)
panel["atr"] = panel.groupby("code")["tr"].transform(
    lambda s: s.ewm(alpha=1 / 14, adjust=False).mean())
# 归一化止损距离：以 ATR 倍数衡量的缓冲空间
panel["sar_atr"] = (panel["close"] - panel["sar"]) / panel["atr"]

# 状态段编号在标的内部累计，翻转一次加一
panel["flip"] = panel.groupby("code")["sar_state"].diff().ne(0)
panel["run"] = panel.groupby("code")["flip"].cumsum()
# 趋势年龄：段内计数，翻转后从 1 重新开始，不跨标的累加
panel["sar_age"] = panel.groupby(["code", "run"]).cumcount() + 1

# 展示四个特征的取值形状
print(panel[["date", "code", "sar_dev", "sar_state",
             "sar_age", "sar_atr"]].dropna().head())

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# parabolic_sar 见本章代码实现小节的递推实现
panel["sar"] = panel.groupby("code", group_keys=False).apply(
    lambda g: parabolic_sar(g["high"], g["low"])[0])
panel["sar_dev"] = panel["close"] / panel["sar"] - 1
panel["tr"] = pd.concat([panel["high"] - panel["low"],
                         (panel["high"] - panel["close"].shift()).abs(),
                         (panel["low"] - panel["close"].shift()).abs()], axis=1).max(axis=1)
panel["sar_atr"] = (panel["close"] - panel["sar"]) / panel.groupby("code")["tr"].transform(
    lambda s: s.ewm(alpha=1/14, adjust=False).mean())
panel["sar_state"] = (panel["close"] > panel["sar"]).astype(int)
panel["flip"] = panel.groupby("code")["sar_state"].diff().ne(0)
panel["run"] = panel.groupby("code")["flip"].cumsum()
panel["sar_age"] = panel.groupby(["code", "run"]).cumcount() + 1

for h in ["forward_1", "forward_5"]:
    print(ic_summary(cross_section_ic(panel, "sar_dev", h)))

print(layered_returns(panel, "sar_dev", "forward_5"))
print(ic_summary(cross_section_ic(panel, "sar_atr", "forward_5")))

# 剔除翻转日，检查跳变对 IC 的影响
print(ic_summary(cross_section_ic(panel[~panel["flip"].fillna(False)], "sar_dev", "forward_5")))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df = panel[panel["code"] == "600519.SS"].copy()

print("--- 信号触发日检验（偏离度高于 80 分位）---")
print(timing_signal_test(df, "sar_dev", "forward_5", upper=0.8))

print("\n--- 条件分位收益（趋势年龄分五档）---")
print(conditional_quantile_return(df, "sar_age", "forward_5", q=5))

# 状态即仓位：价格在 SAR 上方持有，翻转即出场
print("\n--- 状态策略与买入持有对照 ---")
print(timing_backtest(df, "sar_state", "forward_5", entry_q=0.5))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
panel["vol_ratio"] = panel["volume"] / panel.groupby("code")["volume"].transform(
    lambda s: s.rolling(20).mean())

rho = panel.groupby("date").apply(
    lambda g: g[["sar_dev", "vol_ratio"]].corr(method="spearman").iloc[0, 1])
print("两个特征的平均横截面相关：", round(rho.mean(), 3))

panel = combined_signal(panel, ["sar_dev", "vol_ratio"])

print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "sar_dev", "forward_5")))
print(ic_summary(cross_section_ic(panel, "vol_ratio", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
df = panel[panel["code"] == "600519.SS"].copy()
df["cond"] = ((df["sar_state"] == 1) & (df["close"] > df["close"].rolling(20).mean())).astype(int)

print(timing_backtest(df, "cond", "forward_5", entry_q=0.5))
