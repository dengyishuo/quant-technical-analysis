# ============================================================
# 第031章 历史波动率（HV）
# 模块 05 波动率类指标
# 源文件：模块05-波动率类指标/第031章-历史波动率（HV）.md
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

# 2. 对数收益率
log_ret = np.log(close / close.shift(1))

# 3. 滚动标准差并按平方根法则年化
df = pd.DataFrame({"close": close})
df["hv20"] = log_ret.rolling(20).std() * np.sqrt(252)
df["hv60"] = log_ret.rolling(60).std() * np.sqrt(252)

# 4. 识别信号：HV20 上穿 HV60 视为波动扩张
df["above"] = (df["hv20"] > df["hv60"]).astype(int)
df["expand"] = (df["above"] == 1) & (df["above"].shift(1) == 0)
print("波动扩张信号次数：", int(df["expand"].sum()))

# 5. 绘图
fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(df.index, df["hv20"], label="HV20", color="#2f6fb5")
ax.plot(df.index, df["hv60"], label="HV60", color="#c0392b")
ax.set_title("贵州茅台历史波动率 HV20 / HV60")
ax.set_ylabel("年化波动率")
ax.legend()
plt.tight_layout()
plt.show()

# 6. 输出统计：当前 HV20 的历史百分位
current = df["hv20"].iloc[-1]
pctile = (df["hv20"] <= current).mean()
print("当前 HV20 的历史百分位：", round(pctile, 3))

# ---- 代码块 2：拆解 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
import numpy as np
import pandas as pd

# panel 需包含 date / code / close
panel = panel.sort_values(["code", "date"]).reset_index(drop=True)
panel["log_ret"] = panel.groupby("code")["close"].transform(lambda s: np.log(s / s.shift(1)))

# 20 日与 60 日对数收益率标准差，按 252 个交易日年化
panel["hv20"] = panel.groupby("code")["log_ret"].transform(
    lambda s: s.rolling(20).std() * np.sqrt(252))
panel["hv60"] = panel.groupby("code")["log_ret"].transform(
    lambda s: s.rolling(60).std() * np.sqrt(252))
panel["hv_chg"] = panel.groupby("code")["hv20"].transform(lambda s: s / s.shift(5) - 1)
panel["hv_ratio"] = panel["hv20"] / panel["hv60"]
panel["hv_pctile"] = panel.groupby("code")["hv20"].transform(
    lambda s: s.rolling(250).apply(lambda x: (x <= x[-1]).mean(), raw=True))

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# 收益目标：一日与五日两个前向窗口
print(ic_summary(cross_section_ic(panel, "hv20", "forward_1")))
print(ic_summary(cross_section_ic(panel, "hv20", "forward_5")))
print(layered_returns(panel, "hv20", "forward_5"))
# 长短周期之比作第二个候选
print(ic_summary(cross_section_ic(panel, "hv_ratio", "forward_5")))

# 波动率目标：单独成表，不与上一组的数值比较大小
print(ic_summary(cross_section_ic(panel, "hv20", "fwd_vol_20")))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的 timing_signal_test / conditional_quantile_return / timing_backtest
from scipy import stats

df = panel[panel["code"] == "600519.SS"].sort_values("date").copy()
df["state"] = np.where(df["hv_pctile"] >= 0.67, "高波动",
                       np.where(df["hv_pctile"] <= 0.33, "低波动", None))

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

# 长短周期之比落到九成分位以上，视为波动扩张事件
print(timing_signal_test(df, "hv_ratio", "forward_5", upper=0.9))
print(conditional_quantile_return(df, "hv_pctile", "forward_5", q=5))
df["low_vol"] = -df["hv20"]
print(timing_backtest(df, "low_vol", "forward_5", entry_q=0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
# 组合的截面验证：先统一符号方向，再做加权
panel["low_vol"] = -panel["hv20"]
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
# 组合的择时验证：中低波动与中期均线之上同时成立才持仓
df = panel[panel["code"] == "600519.SS"].sort_values("date").copy()
df["sma60"] = df["close"].rolling(60).mean()
df["cond_vol"] = (df["hv_pctile"] < 0.67).astype(int)
df["cond_trend"] = (df["close"] > df["sma60"]).astype(int)
df["cond"] = ((df["cond_vol"] == 1) & (df["cond_trend"] == 1)).astype(int)

print(timing_backtest(df, "cond_vol", "forward_5", entry_q=0.5))
print(timing_backtest(df, "cond_trend", "forward_5", entry_q=0.5))
print(timing_backtest(df, "cond", "forward_5", entry_q=0.5))
