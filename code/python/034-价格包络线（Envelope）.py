# ============================================================
# 第034章 价格包络线（Envelope）
# 模块 05 波动率类指标
# 源文件：模块05-波动率类指标/第034章-价格包络线（Envelope）.md
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

# 2. 中轨与固定百分比上下轨
n, pct = 20, 0.03
df = pd.DataFrame({"close": close})
df["mid"] = df["close"].rolling(n).mean()
df["up"] = df["mid"] * (1 + pct)
df["dn"] = df["mid"] * (1 - pct)

# 3. 触轨与相对位置
df["pct_e"] = (df["close"] - df["dn"]) / (df["up"] - df["dn"])
touch_up = (df["close"] > df["up"]).sum()
touch_dn = (df["close"] < df["dn"]).sum()
print(f"触上轨次数：{touch_up}  触下轨次数：{touch_dn}")

# 4. 识别信号：价格连续在外侧运行视为趋势加速
df["outside"] = (df["close"] > df["up"]) | (df["close"] < df["dn"])

# 5. 绘图
fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(df.index, df["close"], label="收盘价", color="#333", linewidth=1)
ax.plot(df.index, df["up"], label="上轨", color="#c0392b", linewidth=1)
ax.plot(df.index, df["mid"], label="中轨", color="#2f6fb5", linewidth=1)
ax.plot(df.index, df["dn"], label="下轨", color="#27ae60", linewidth=1)
ax.set_title("贵州茅台价格包络线")
ax.legend()
plt.tight_layout()
plt.show()

# 6. 输出统计
print("价格处于通道内的天数占比：", round(1 - df["outside"].mean(), 3))

# ---- 代码块 2：拆解 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
import numpy as np
import pandas as pd

# panel 需包含 date / code / close
pct = 0.03
panel = panel.sort_values(["code", "date"]).reset_index(drop=True)
panel["env_mid"] = panel.groupby("code")["close"].transform(lambda s: s.rolling(20).mean())
panel["env_up"] = panel["env_mid"] * (1 + pct)
panel["env_dn"] = panel["env_mid"] * (1 - pct)
panel["env_pct"] = ((panel["close"] - panel["env_dn"])
                    / (panel["env_up"] - panel["env_dn"]))
panel["env_dev"] = panel["close"] / panel["env_mid"] - 1
panel["env_width"] = (panel["env_up"] - panel["env_dn"]) / panel["env_mid"]
panel["outside"] = ((panel["close"] > panel["env_up"])
                    | (panel["close"] < panel["env_dn"])).astype(int)
panel["out_share"] = panel.groupby("code")["outside"].transform(
    lambda s: s.rolling(20).mean())

# ---- 代码块 3：截面选股能力 ----

# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# 第一组：%E 对收益目标
print(ic_summary(cross_section_ic(panel, "env_pct", "forward_1")))
print(ic_summary(cross_section_ic(panel, "env_pct", "forward_5")))
print(layered_returns(panel, "env_pct", "forward_5"))

# %E 与均线偏离的秩相关，理论上等于 1，偏离说明数据对齐有问题
rho = panel.groupby("date").apply(
    lambda g: g[["env_pct", "env_dev"]].corr(method="spearman").iloc[0, 1])
print("%E 与均线偏离的平均横截面相关：", round(rho.mean(), 3))

# 第二组：波动率目标。带宽是常数，横截面标准差应为 0；穿透占比才有信息
print("带宽的平均横截面标准差：",
      round(panel.groupby("date")["env_width"].std().mean(), 6))
print(ic_summary(cross_section_ic(panel, "out_share", "fwd_vol_20")))

# ---- 代码块 4：择时能力 ----

# 沿用第 007 章定义的 timing_signal_test / conditional_quantile_return / timing_backtest
df = panel[panel["code"] == "600519.SS"].sort_values("date").copy()

# 触轨事件：%E 高于 95 分位视为触及上轨
print(timing_signal_test(df, "env_pct", "forward_5", upper=0.95))

# 条件分位收益：%E 分五档
print(conditional_quantile_return(df, "env_pct", "forward_5", q=5))

# 连续穿透与通道内的收益分布对照
df["deep"] = (df["out_share"] > 0.2).astype(int)
print(df.groupby("deep")["forward_5"].agg(
    样本数="count",
    平均收益=lambda s: round(s.mean() * 100, 3),
    标准差=lambda s: round(s.std() * 100, 3),
    夏普=lambda s: round(s.mean() / s.std() * np.sqrt(252 / 5), 2),
    左尾=lambda s: round(s.quantile(0.05) * 100, 3)))

df["low_e"] = -df["env_pct"]
print(timing_backtest(df, "low_e", "forward_5", entry_q=0.7))

# ---- 代码块 5：组合使用与验证 ----

# 沿用第 007 章定义的 combined_signal
# 组合的截面验证：位置取负，带宽取负，先补布林带宽度
bb_sd = panel.groupby("code")["close"].transform(lambda s: s.rolling(20).std())
bb_mid = panel.groupby("code")["close"].transform(lambda s: s.rolling(20).mean())
panel["bb_width"] = 4 * bb_sd / bb_mid
panel["low_e"] = -panel["env_pct"]
panel["low_bw"] = -panel["bb_width"]

rho = panel.groupby("date").apply(
    lambda g: g[["low_e", "low_bw"]].corr(method="spearman").iloc[0, 1])
print("两个特征的平均横截面相关：", round(rho.mean(), 3))

panel = combined_signal(panel, ["low_e", "low_bw"])
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "low_e", "forward_5")))
print(ic_summary(cross_section_ic(panel, "low_bw", "forward_5")))

# ---- 代码块 6：组合使用与验证 ----

# 沿用第 007 章定义的 timing_backtest
# 组合的择时验证：触轨且带宽处于低位才做回归
df = panel[panel["code"] == "600519.SS"].sort_values("date").copy()
df["cond_touch"] = (df["env_pct"] < 0.1).astype(int)
df["cond_calm"] = (df["bb_width"] < df["bb_width"].quantile(0.5)).astype(int)
df["cond"] = ((df["cond_touch"] == 1) & (df["cond_calm"] == 1)).astype(int)

print(timing_backtest(df, "cond_touch", "forward_5", entry_q=0.5))
print(timing_backtest(df, "cond_calm", "forward_5", entry_q=0.5))
print(timing_backtest(df, "cond", "forward_5", entry_q=0.5))
