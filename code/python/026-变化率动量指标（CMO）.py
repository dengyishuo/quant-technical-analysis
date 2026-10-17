# ============================================================
# 第026章 变化率动量指标（CMO）
# 模块 04 震荡类指标
# 源文件：模块04-震荡类指标/第026章-变化率动量指标（CMO）.md
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

# 2. 计算 CMO（手写涨跌幅度分离）
def cmo(series, n=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    up_sum = up.rolling(n).sum()
    down_sum = down.rolling(n).sum()
    total = up_sum + down_sum
    return (up_sum - down_sum) / total.replace(0, np.nan) * 100

df = pd.DataFrame({"close": close})
df["cmo14"] = cmo(df["close"], 14)
df["cmo20"] = cmo(df["close"], 20)

# 3. 识别信号
df["strong_long"]  = (df["cmo14"] > 50).astype(int)
df["strong_short"] = (df["cmo14"] < -50).astype(int)
df["cross_up"]   = (df["cmo14"] > -20) & (df["cmo14"].shift(1) <= -20)
df["cross_down"] = (df["cmo14"] < 20) & (df["cmo14"].shift(1) >= 20)
print(f"越过正 50 的交易日：{df['strong_long'].sum()}  跌破负 50 的交易日：{df['strong_short'].sum()}")
print(f"上穿负 20 次数：{df['cross_up'].sum()}  下穿正 20 次数：{df['cross_down'].sum()}")

# 4. 绘图
import matplotlib
matplotlib.rcParams["font.sans-serif"] = ["PingFang SC", "SimHei", "Arial Unicode MS"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                               gridspec_kw={"height_ratios": [2, 1]})
ax1.plot(df.index, df["close"], color="#333", linewidth=1)
ax1.set_title("贵州茅台 收盘价与 CMO")
ax2.plot(df.index, df["cmo14"], label="CMO14", color="#2f6fb5")
ax2.plot(df.index, df["cmo20"], label="CMO20", color="#c0392b", linewidth=1)
for lv in (50, -50, 20, -20, 0):
    ax2.axhline(lv, color="#bbb", linestyle="--", linewidth=0.8)
ax2.legend()
plt.tight_layout()
plt.show()

# 5. 输出统计
print("CMO 均值：", round(df["cmo14"].mean(), 3))
print("CMO 标准差：", round(df["cmo14"].std(), 3))
print("读数落在正负 20 以内的占比：",
      round((df["cmo14"].abs() < 20).sum() / df["cmo14"].notna().sum(), 3))

# ---- 代码块 2：拆解 ----

# 沿用第 007 章的数据准备（panel 含 date / code / close / high / low / volume）
import numpy as np
import pandas as pd

panel = panel.sort_values(["code", "date"]).reset_index(drop=True)


def cmo(s, n=14):
    d = s.diff()
    up = d.clip(lower=0).rolling(n).sum()
    dn = (-d.clip(upper=0)).rolling(n).sum()
    return (up - dn) / (up + dn).replace(0, np.nan) * 100


# 读数：十四日窗口内净动量的相对强度
panel["cmo14"] = panel.groupby("code")["close"].transform(cmo)
# 零轴偏离：减六十日均值后除以六十日标准差，单位为标准差倍数
panel["cmo_z"] = panel.groupby("code")["cmo14"].transform(
    lambda s: (s - s.rolling(60).mean()) / s.rolling(60).std())
# 与自身三日均线的差：平滑后的一阶差分
panel["cmo_bar"] = panel["cmo14"] - panel.groupby("code")["cmo14"].transform(
    lambda s: s.rolling(3).mean())
# 五期读数变化：未平滑的差分
panel["cmo_chg5"] = panel["cmo14"] - panel.groupby("code")["cmo14"].shift(5)

panel[["code", "date", "cmo14", "cmo_z", "cmo_bar", "cmo_chg5"]].head(8)

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
def cmo(s, n=14):
    d = s.diff()
    up, dn = d.clip(lower=0).rolling(n).sum(), (-d.clip(upper=0)).rolling(n).sum()
    return (up - dn) / (up + dn).replace(0, np.nan) * 100

panel["cmo14"] = panel.groupby("code")["close"].transform(cmo)
panel["cmo_bar"] = panel["cmo14"] - panel.groupby("code")["cmo14"].transform(
    lambda s: s.rolling(3).mean())
panel["cmo_z"] = panel.groupby("code")["cmo14"].transform(
    lambda s: (s - s.rolling(60).mean()) / s.rolling(60).std())

# 状态型与边际型：一日与五日两个前向窗口
for h in ["forward_1", "forward_5"]:
    print(ic_summary(cross_section_ic(panel, "cmo14", h)))
print(layered_returns(panel, "cmo14", "forward_5"))
print(ic_summary(cross_section_ic(panel, "cmo_bar", "forward_5")))
print(ic_summary(cross_section_ic(panel, "cmo_z", "forward_5")))

# 与 RSI 的对照：同源构造，平滑方式不同
def rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))

panel["rsi14"] = panel.groupby("code")["close"].transform(rsi)
rho = panel.groupby("date").apply(
    lambda g: g[["cmo14", "rsi14"]].corr(method="spearman").iloc[0, 1])
print("与 RSI 的平均横截面相关：", round(rho.mean(), 3))
print(ic_summary(cross_section_ic(panel, "rsi14", "forward_5")))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的三种择时检验
df = panel[panel["code"] == "600519.SS"].copy()
df["cmo_neg"] = -df["cmo14"]   # 取负后上分位即对应强空头端

# 顺势写法：强多头端
print(timing_signal_test(df, "cmo14", "forward_5", upper=0.8))
# 反向写法：把读数取负，再看强空头端的后续收益
print(timing_signal_test(df, "cmo_neg", "forward_5", upper=0.8))

# 五档条件收益：重点看首末档与中间档的差，而不是单调性
print(conditional_quantile_return(df, "cmo14", "forward_5", q=5))

print(timing_backtest(df, "cmo14", "forward_5", entry_q=0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal / cross_section_ic / ic_summary / timing_backtest
# 先看 CMO 与 ROC 的横截面相关，再决定是否值得组合
panel["roc12"] = panel.groupby("code")["close"].transform(
    lambda s: (s / s.shift(12) - 1) * 100)
rho = panel.groupby("date").apply(
    lambda g: g[["cmo14", "roc12"]].corr(method="spearman").iloc[0, 1])
print("两个特征的平均横截面相关：", round(rho.mean(), 3))

# 组合的截面验证：加权型与乘积型各算一次
panel = combined_signal(panel, ["cmo14", "roc12"])
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
panel["cmo_weight"] = panel["roc12"] * (panel["cmo14"] + 100) / 200
print(ic_summary(cross_section_ic(panel, "cmo_weight", "forward_5")))

# 组合的择时验证：读数转正且站上二十日均线才持仓
df = panel[panel["code"] == "600519.SS"].copy()
df["cond"] = ((df["cmo14"] > 0) &
              (df["close"] > df["close"].rolling(20).mean())).astype(int)
print(timing_backtest(df, "cond", "forward_5", entry_q=0))

# ---- 代码块 6：组合使用与验证 ----

# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
# 事件型写法：CMO 上穿自身三日均线且价格站上二十日均线才持仓
df = panel[panel["code"] == "600519.SS"].copy()
df["sma20"] = df["close"].rolling(20).mean()
# cmo_bar 是读数与自身三日均线之差，由负转正即金叉
cross_up = (df["cmo_bar"] > 0) & (df["cmo_bar"].shift(1) <= 0)
df["cond"] = ((df["close"] > df["sma20"]) & cross_up.fillna(False)).astype(int)

print(timing_backtest(df, "cond", "forward_5", entry_q=0.5))
