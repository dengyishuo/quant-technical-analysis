# ============================================================
# 第039章 弹性成交量加权移动平均线（EVWMA）
# 模块 06 量价类指标
# 源文件：模块06-量价类指标/第039章-弹性成交量加权移动平均线（EVWMA）.md
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

# 2. 手写 EVWMA 递推
def evwma(price, volume, n=20):
    p = price.to_numpy(dtype=float)
    v = volume.to_numpy(dtype=float)
    N = len(p)
    out = np.full(N, np.nan)
    if N < n:
        return pd.Series(out, index=price.index)
    w = v[:n].sum()
    out[n - 1] = (p[:n] * v[:n]).sum() / w
    for t in range(n, N):
        w = w - v[t - n] + v[t]
        out[t] = (v[t] * p[t] + out[t - 1] * (w - v[t])) / w
    return pd.Series(out, index=price.index)

# 3. 计算 EVWMA 与 EMA
df = pd.DataFrame({"close": close})
df["evwma20"] = evwma(close, volume, n=20)
df["ema20"] = close.ewm(span=20, adjust=False).mean()

# 4. 识别信号：EVWMA 上穿 EMA
df["above"] = (df["evwma20"] > df["ema20"]).astype(int)
df["cross_up"] = (df["above"] == 1) & (df["above"].shift(1) == 0)
print(f"EVWMA 上穿 EMA 次数：{df['cross_up'].sum()}")

# 5. 绘图
fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(df.index, df["close"], label="收盘价", color="#333", linewidth=1)
ax.plot(df.index, df["evwma20"], label="EVWMA20", color="#2f6fb5")
ax.plot(df.index, df["ema20"], label="EMA20", color="#c0392b")
ax.set_title("贵州茅台 EVWMA 与 EMA 对比")
ax.legend()
plt.tight_layout()
plt.show()

# 6. 输出统计
print("价格位于 EVWMA20 上方的比例：",
      round((df["close"] > df["evwma20"]).sum() / df["evwma20"].notna().sum(), 3))

# ---- 代码块 2：拆解 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
import numpy as np
import pandas as pd

# EVWMA 递推：当日权重为 v_t / W_t，W_t 为 n 日成交量之和
def evwma(price, volume, n=20):
    p = price.to_numpy(dtype=float)
    v = volume.to_numpy(dtype=float)
    out = np.full(len(p), np.nan)
    if len(p) < n:
        return pd.Series(out, index=price.index)
    w = v[:n].sum()
    out[n - 1] = (p[:n] * v[:n]).sum() / w
    for t in range(n, len(p)):
        w = w - v[t - n] + v[t]
        out[t] = (v[t] * p[t] + out[t - 1] * (w - v[t])) / w
    return pd.Series(out, index=price.index)

# panel 已含 date / code / close / volume / forward_1 / forward_5
panel = panel.sort_values(["code", "date"]).reset_index(drop=True)
grp = panel.groupby("code")
panel["evwma20"] = np.nan
for code, g in panel.groupby("code"):
    panel.loc[g.index, "evwma20"] = evwma(g["close"], g["volume"], n=20)

panel["sma20"] = grp["close"].transform(lambda s: s.rolling(20).mean())
panel["evwma_dev"] = panel["close"] / panel["evwma20"] - 1

# 成交集中度：量价加权均线相对等权均线的位移
panel["conc"] = panel["evwma20"] / panel["sma20"] - 1
panel["conc_abs"] = panel["conc"].abs()

# 当日成交占 20 日成交量之和的比例
panel["w_now"] = panel["volume"] / grp["volume"].transform(lambda s: s.rolling(20).sum())
panel["evwma_slope"] = panel["evwma20"] / grp["evwma20"].shift(10) - 1

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# 集中度与偏离度并列检验
for f in ["conc", "evwma_dev"]:
    print(f"\n--- {f} vs forward_5 ---")
    print(ic_summary(cross_section_ic(panel, f, "forward_5")))

print(layered_returns(panel, "conc", "forward_5"))

# 集中度的绝对值版本：只保留集中程度，剥掉方向
print("\n--- 集中度绝对值 ---")
print(ic_summary(cross_section_ic(panel, "conc_abs", "forward_5")))

# 对偏离度取残差，看集中度是否还有独立信息
def _resid(g):
    g = g.dropna(subset=["conc", "evwma_dev"])
    if len(g) < 10:
        return pd.Series(np.nan, index=g.index)
    beta = np.polyfit(g["evwma_dev"], g["conc"], 1)
    return pd.Series(g["conc"] - np.polyval(beta, g["evwma_dev"]), index=g.index)

panel["conc_resid"] = panel.groupby("date", group_keys=False).apply(_resid)

print("\n--- 剔除偏离度后的残差 ---")
print(ic_summary(cross_section_ic(panel, "conc_resid", "forward_5")))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df = panel[panel["code"] == "600519.SS"].sort_values("date").copy()

print("--- 信号触发日检验（偏离度高于 80 分位）---")
print(timing_signal_test(df, "evwma_dev", "forward_5", upper=0.8))

print("\n--- 条件分位收益（偏离度分五档）---")
print(conditional_quantile_return(df, "evwma_dev", "forward_5", q=5))

print("\n--- 择时策略与买入持有对照 ---")
print(timing_backtest(df, "evwma_dev", "forward_5", entry_q=0.7))

# 集中度极值日的后续收益，与其余交易日对照
print(df.assign(集中=(df["conc_abs"] > df["conc_abs"].quantile(0.9)).astype(int))
      .groupby("集中")["forward_5"].agg(["count", "mean"]).round(4))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
panel["mom20"] = panel["close"] / grp["close"].shift(20) - 1

rho = panel.groupby("date").apply(
    lambda g: g[["conc", "mom20"]].corr(method="spearman").iloc[0, 1])
print("两个特征的平均横截面相关：", round(rho.mean(), 3))

panel = combined_signal(panel, ["conc", "mom20"])

print("\n--- 组合 vs 单特征 ---")
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "conc", "forward_5")))
print(ic_summary(cross_section_ic(panel, "mom20", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
df2 = panel[panel["code"] == "600519.SS"].sort_values("date").copy()
df2["ema20"] = df2["close"].ewm(span=20, adjust=False).mean()
df2["cond"] = ((df2["evwma20"] > df2["ema20"]) & (df2["close"] > df2["evwma20"])).astype(int)

print(timing_backtest(df2, "cond", "forward_5", entry_q=0.5))
