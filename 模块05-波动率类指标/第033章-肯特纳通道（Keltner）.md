# 第033章 肯特纳通道（Keltner）

一根跳空长阳之后，布林带的上轨被撑开一大截，随后几天价格只是横着走，通道却迟迟收不回来。一个交易者盯着这条被单日缺口拽宽的边界，判断不了眼前的突破是真还是假。他想要的通道，宽度应当由每日真实波动累积而成，一根 K 线只贡献其中一份，而不是凭一次跳空改写整条界线。他要回答的是：这条边界是市场常态的刻度，还是某一天的残影。

## 名称与来历

肯特纳通道（Keltner Channels，Keltner）。

它由 Chester Keltner 在 1960 年提出，是通道类指标里较早的一位。最初的版本以一条典型价的移动平均线为中轨，上下轨用典型价的固定波动幅度偏移，思路接近后来的价格包络线。这种固定宽度在波动率变化剧烈时明显不够灵活。

1980 年代，Linda Raschke 对原始版本做了改良，用平均真实波幅（ATR）替换固定幅度。改良之后，通道宽度随每日真实波动自动伸缩：波动放大时通道变宽，波动收敛时通道收窄。今天通行的肯特纳通道，多数指的是改良后的 ATR 版本。

## 核心逻辑

通道的宽度该由什么决定，才能既灵敏又不容易误报？

布林带用标准差，对价格围绕均线的偏离非常敏感，单日极端涨跌会迅速把通道撑开。这在多数时候是优点，但在跳空频繁的市场里，一个隔夜缺口就能让标准差跳升，通道被一次非连续的价格变化扭曲。肯特纳通道给出的是另一种答案：用真实波幅来定宽度。真实波幅把当日最高最低差、以及相对昨收的上下缺口都纳入进来，对跳空的处理比标准差更直接，对盘中极端值的反应反而更平滑。

这个替换带来两种不同的敏感度。面对连续的高波动日，布林带扩张得更快，肯特纳通道相对温和；面对一次跳空缺口，肯特纳通道的反应更贴合真实风险，因为它本来就是为刻画缺口设计的。两者在波动率的度量上是互补的，不是谁替代谁。

中轨的选型也体现了这一取向。肯特纳通道的中轨通常用指数移动平均（EMA），而不是简单移动平均。EMA 对近期价格赋予更高权重，中轨更快跟上趋势，与随波动伸缩的轨道配合，整体反应更偏向灵敏。和布林带一样，通道的上下轨严格对称，方向由中轨给出，指标本身不带多空判断。

## 计算公式

肯特纳通道三条线，中轨是指数移动平均，上下轨在中轨基础上加减若干倍真实波幅。

### 中轨

$$Middle_t = EMA(Close,\ n)$$

其中 EMA 的递推形式为 $\mathrm{EMA}_t = \alpha C_t + (1-\alpha)\mathrm{EMA}_{t-1}$，平滑系数 $\alpha = 2/(n+1)$。

### 上轨与下轨

$$Upper_t = Middle_t + k \times ATR_t$$

$$Lower_t = Middle_t - k \times ATR_t$$

其中 ATR 的周期 m 与中轨周期 n 可以不同，典型设置为 n=20、m=10、k=2。

**计算示例。** 设 20 日 EMA 为 100 元，10 日 ATR 为 3 元，倍数 k 取 2，则上轨为 $100+2\times 3=106$ 元，下轨为 $100-2\times 3=94$ 元。若次日价格跳空上涨，ATR 抬升到 4 元，中轨随之上移到 101 元，则上轨变为 $101+2\times 4=109$ 元，下轨变为 $101-2\times 4=93$ 元。可以看到，波动一放大，通道立即变宽。

价格在通道中的相对位置同样可以用 %B 度量：

$$\%K_t = \frac{C_t - Lower_t}{Upper_t - Lower_t}$$

%K 接近 1 表示价格贴近上轨，接近 0 表示贴近下轨。

**参数含义。**

| 参数 | 含义 | 常见取值 | 影响 |
|------|------|---------|------|
| n | 中轨 EMA 周期 | 10、20（默认）、30 | n 越大，中轨越平滑，方向确认越慢 |
| m | ATR 周期 | 5、10（默认）、20 | m 越大，宽度越稳定，对波动突变越迟钝 |
| k | ATR 倍数 | 1.5、2（默认）、2.5 | k 越大，通道越宽，突破信号越少 |

三个参数需要协同，短线场景都调小，中长线场景都放大。ATR 周期与倍数共同决定通道宽度，具体取多少取决于品种波动率与容忍的误报率。

## 用法与信号

**突破。** 价格上穿上轨且中轨向上，说明多头突破了正常波动范围的上沿，可能标志上升趋势启动。突破时成交量放大，可靠性更高。价格下穿下轨且中轨向下，同理适用于下行方向。突破后若价格快速回落到通道内，通常视为假突破，应及时了结。

**通道收窄。** 通道宽度持续缩小到近期最低水平，意味着波动率被极度压缩，进入蓄力阶段。此时多空分歧小，价格在一个越来越窄的区间里运行。一旦价格带量突破收窄后的上轨或下轨，往往伴随一段较大的波动。收窄本身不提示方向，是一个待突破的状态。

**通道扩张。** 通道由窄变宽说明波动率从低位向高位切换。扩张时若价格持续贴近通道一侧（例如始终靠上轨运行），说明趋势力量强；若扩张但价格在两侧来回穿越，说明市场进入高波动震荡，突破的信噪比下降。

**中轨的支撑与阻力。** 上升趋势中价格回调至中轨附近止跌反弹，说明趋势健康；直接跌破中轨则趋势可能转弱。下降趋势中价格反弹至中轨遇阻回落是健康信号，上穿中轨则需警惕反转。中轨的方向本身也是判断多空的依据，价格与中轨的相对位置给出了通道内的偏向。

## 边界与误区

**ATR 的滞后会让通道短暂偏窄。** 波动率从低位突然跃升时，ATR 需要若干个交易日才能吸收新的波动水平，这段窗口里通道可能仍然偏窄，产生一连串假突破。极端行情中不宜只依赖通道信号，应结合成交量与市场状态再判断。

**极端行情下通道容易被贯穿。** 连续涨跌停或恐慌抛售中，价格可能被钉在通道外侧多日，ATR 短期内难以追上。此时通道的边界失去约束意义，把价格在上轨之外停留当作反转信号会连续做错方向。

**三个参数增加了优化空间。** 中轨周期、ATR 周期、倍数各有取值，组合多，容易在历史数据上挑出一组看起来最优的参数。合理的做法是先固定标准参数（20、10、2），在较长样本外验证其稳定性，再考虑调整，而不是在样本内反复搜索。

**震荡市中反复穿越。** 通道被价格一周内多次穿越、中轨走平、宽度极低时，突破信号基本无效。可先用平均趋向指数判断市场是否处于趋势状态，在支撑不足时降低对通道信号的依赖。

## 它被检验过吗

肯特纳通道没有针对它本身的独立同行评议检验。它的两个构件各有出处：中轨属于均线族，均线规则在整族层面被检验过，但结论无法归因到某一个周期或某一种加权方式；宽度来自 ATR，ATR 本身也没有单独检验。

合起来看，这条通道的绩效证据是空的。宽度与位置两种读数的用法，只能靠构造逻辑与样本内的分层结果支撑，不宜称为已经验证。完整证据链见第 007 章。

这一类的真实失效案例，见第 029 章的「真实案例与失败模式」。

## 代码实现

TTR 中的肯特纳通道实现并不稳定，这里直接手写，逻辑更透明。

### R

```r
# 1. 加载包
library(quantmod)
library(TTR)

# 2. 获取数据
panel <- read.csv("data/parquet/panel_blue_chip.csv", stringsAsFactors = FALSE)
.sub <- panel[panel$code == "600519.SS", ]
data <- xts::xts(.sub[, c("open", "high", "low", "close", "volume", "adjusted")],
                 order.by = as.Date(.sub$date))
colnames(data) <- c("Open", "High", "Low", "Close", "Volume", "Adjusted")
close_price <- Cl(data)

# 3. 计算指标：EMA 中轨与 ATR 宽度（手写）
n <- 20; m <- 10; k <- 2
kc_mid <- EMA(close_price, n = n)
atr_m  <- ATR(HLC(data), n = m)[, "atr"]
kc_up  <- kc_mid + k * atr_m
kc_dn  <- kc_mid - k * atr_m

# 4. 识别信号：通道宽度与 %K
kc_width <- (kc_up - kc_dn) / kc_mid
kc_pct   <- (close_price - kc_dn) / (kc_up - kc_dn)
cat("当前通道宽度：", round(tail(kc_width, 1), 4), "\n")
cat("当前 %K：", round(tail(kc_pct, 1), 4), "\n")

# 5. 绘图
chartSeries(data, theme = "white", name = "贵州茅台")
addTA(merge(kc_up, kc_mid, kc_dn), col = c("red", "blue", "green"),
      legend = "KC upper / mid / lower")

# 6. 输出统计：通道宽度处于低 20 百分位的天数占比
sq <- kc_width < quantile(kc_width, 0.2, na.rm = TRUE)
cat("通道宽度处于低 20 百分位的天数占比：",
    round(mean(sq, na.rm = TRUE), 3), "\n")
```

### Python

```python
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
high, low, close = data["High"].squeeze(), data["Low"].squeeze(), data["Close"].squeeze()

# 2. 真实波幅与 ATR（Wilder 平滑）
prev_close = close.shift(1)
tr = pd.concat([
    high - low,
    (high - prev_close).abs(),
    (low - prev_close).abs(),
], axis=1).max(axis=1)

n, m, k = 20, 10, 2
df = pd.DataFrame({"close": close})
df["atr"] = tr.ewm(alpha=1 / m, adjust=False).mean()

# 3. 中轨 EMA 与上下轨
df["mid"] = df["close"].ewm(span=n, adjust=False).mean()
df["up"] = df["mid"] + k * df["atr"]
df["dn"] = df["mid"] - k * df["atr"]

# 4. 宽度与 %K
df["kc_width"] = (df["up"] - df["dn"]) / df["mid"]
df["kc_pct"] = (df["close"] - df["dn"]) / (df["up"] - df["dn"])
print("当前通道宽度：", round(df["kc_width"].iloc[-1], 4))
print("当前 %K：", round(df["kc_pct"].iloc[-1], 4))

# 5. 绘图
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                               gridspec_kw={"height_ratios": [3, 1]})
ax1.plot(df.index, df["close"], label="收盘价", color="#333", linewidth=1)
ax1.plot(df.index, df["up"], label="上轨", color="#c0392b", linewidth=1)
ax1.plot(df.index, df["mid"], label="中轨", color="#2f6fb5", linewidth=1)
ax1.plot(df.index, df["dn"], label="下轨", color="#27ae60", linewidth=1)
ax1.set_title("贵州茅台肯特纳通道")
ax1.legend()
ax2.plot(df.index, df["kc_width"], color="#8e44ad", linewidth=1)
ax2.set_ylabel("通道宽度")
plt.tight_layout()
plt.show()

# 6. 输出统计
thr = df["kc_width"].quantile(0.2)
print("通道宽度处于低 20 百分位的天数占比：",
      round((df["kc_width"] < thr).mean(), 3))
```

## 拆解

肯特纳通道的三条轨与价格同量纲，直接排序没有意义。它的两个派生读数与布林带同名，构造却不同，差异正是检验时最需要说清的地方：宽度由真实波幅驱动，位置的分母也随波动变化。这两处决定了它的因子行为与布林带并不重合。

| 特征名 | 计算式 | 量纲 | 经济含义 |
|--------|--------|------|----------|
| %K | $(p_t-L_t)/(U_t-L_t)$ | 无量纲，可越界 | 价格在通道中的相对位置 |
| 通道宽度 | $(U_t-L_t)/M_t=2k\,\mathrm{ATR}_t/M_t$ | 无量纲比例 | 由真实波幅驱动的波动水平 |
| 宽度变化率 | $W_t/W_{t-5}-1$ | 无量纲比例 | 通道张开或收拢的速度 |
| 中轨偏离 | $p_t/M_t-1$ | 无量纲比例 | 价格相对中轨的位置，分母不含波动 |

宽度与 ATR 比率几乎同源。上下轨之差等于 $2k$ 倍 ATR，宽度再除以中轨，与 ATR 除以收盘价只差一个常数和一个分母。这意味着宽度因子的排序与 ATR 因子高度一致，把它当作独立的波动因子放进模型，增量会很有限。检验时应先算两者的相关，或直接对 ATR 取残差，看剩余部分还有没有信息。

%K 与 %B 的差别在分母。%B 的分母是四倍标准差，%K 的分母是四倍 ATR，后者在跳空频繁的标的上更大。后果是，同样的价格偏离，在高波动期给出的 %K 比 %B 更温和。两者在平静期排序接近，在波动剧烈时明显分叉。若模型里同时有布林带与肯特纳，需要检查这两个位置因子是否重复。

中轨偏离与 %K 也不等价。%K 的分母随波动变化，中轨偏离的分母是价格本身，不受波动影响。前者把偏离按当前波动标准化，后者只按价格水平标准化。前者更适合判断"这次偏离相对当前波动算不算极端"，后者更适合判断"价格相对成本走了多远"。两者可以分别使用，混用会让结论含混。

中轨用 EMA，记忆比 SMA 短，对近期价格更敏感。这带来两个后果：中轨偏离的持续性弱于均线偏离，转向更快；价格与中轨的交叉更频繁，作为事件检验时样本更多，噪音也更多。宽度变化率则继承了 ATR 的滞后，波动突然跃升时，宽度需要几个交易日才能跟上，这段窗口里的突破信号信噪比偏低。

### R

```r
# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
library(dplyr)
library(TTR)

# panel 需包含 date / code / high / low / close
panel <- panel |> group_by(code) |> arrange(date, .by_group = TRUE) |>
  mutate(kc_mid = as.numeric(TTR::EMA(close, n = 20)),
         atr10 = as.numeric(TTR::ATR(
           cbind(High = high, Low = low, Close = close), n = 10)[, "atr"]),
         kc_up = kc_mid + 2 * atr10,
         kc_dn = kc_mid - 2 * atr10,
         kc_width = (kc_up - kc_dn) / kc_mid,
         kc_pct = (close - kc_dn) / (kc_up - kc_dn),
         kc_dev = close / kc_mid - 1,
         kc_width_chg = kc_width / dplyr::lag(kc_width, 5) - 1) |> ungroup()
```

### Python

```python
# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
import numpy as np
import pandas as pd

# panel 需包含 date / code / high / low / close
panel = panel.sort_values(["code", "date"]).reset_index(drop=True)
prev_close = panel.groupby("code")["close"].shift(1)
panel["tr"] = pd.concat([panel["high"] - panel["low"],
                         (panel["high"] - prev_close).abs(),
                         (panel["low"] - prev_close).abs()], axis=1).max(axis=1)

# ATR(10) 与 EMA(20) 中轨，上下轨为中轨加减 2 倍 ATR
panel["atr10"] = panel.groupby("code")["tr"].transform(
    lambda s: s.ewm(alpha=1 / 10, adjust=False).mean())
panel["kc_mid"] = panel.groupby("code")["close"].transform(
    lambda s: s.ewm(span=20, adjust=False).mean())
panel["kc_up"] = panel["kc_mid"] + 2 * panel["atr10"]
panel["kc_dn"] = panel["kc_mid"] - 2 * panel["atr10"]
panel["kc_width"] = (panel["kc_up"] - panel["kc_dn"]) / panel["kc_mid"]
panel["kc_pct"] = (panel["close"] - panel["kc_dn"]) / (panel["kc_up"] - panel["kc_dn"])
panel["kc_dev"] = panel["close"] / panel["kc_mid"] - 1
panel["kc_width_chg"] = panel.groupby("code")["kc_width"].transform(
    lambda s: s / s.shift(5) - 1)
```

## 截面选股能力

肯特纳进入截面检验，位置因子取 %K：

$$f^{\%K}_t=\frac{p_t-L_t}{U_t-L_t}$$

波动因子取通道宽度：

$$f^{w}_t=\frac{U_t-L_t}{M_t}$$

第三个候选是双通道宽度比，分母用肯特纳宽度，分子用同参数的布林带宽度：

$$R_t=\frac{BW^{BB}_t}{W^{KC}_t}=\frac{4\sigma_t/M_t}{2k\,\mathrm{ATR}_t/M_t}=\frac{2\sigma_t}{k\,\mathrm{ATR}_t}$$

比值大于一，说明标准差口径的波动高于真实波幅口径，通常对应连续大阴大阳而少有跳空；比值小于一，说明跳空较多，真实波幅相对更大。这个比值不是宽度，而是两种波动估计的分歧程度，它携带的信息与单一宽度不同。

预期表现上，%K 属于均值回归型，方向多为负，但在趋势中会减弱甚至反号。宽度对未来波动率通常为正，波动聚类使高宽度状态延续。双通道比值的方向更不确定：比值高说明价格在连续交易中剧烈摆动，这类标的后续波动可能继续偏高；比值低说明波动集中在缺口，缺口之后往往进入整理。方向由数据给出，不宜先验设定。

检验时有三点值得注意。第一，宽度与 ATR 比率高度共线。若模型里已有 ATR 类因子，宽度因子的增量有限，判断时应先取残差，或直接只保留一个。第二，%K 与布林带的 %B 在两个指标同时出现时会重复，二者的相关在平静期很高，在跳空频繁期下降，需要用分段相关确认是否真的提供了新信息。第三，比值的分母在宽度极小时不稳定，低波动样本里读数会剧烈跳动，计算前应剔除宽度低于某一分位的观测。

### R

```r
# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# 第一组：%K 对收益目标
print(ic_summary(cross_section_ic(panel, "kc_pct", "forward_1")))
print(ic_summary(cross_section_ic(panel, "kc_pct", "forward_5")))
print(layered_returns(panel, "kc_pct", "forward_5"))

# 第二组：宽度对波动率目标，单独成表
print(ic_summary(cross_section_ic(panel, "kc_width", "fwd_vol_20")))

# 第三组：双通道宽度比，先补布林带宽度再检验
panel <- panel |> group_by(code) |>
  mutate(bb_width = 4 * zoo::rollapply(close, 20, sd, fill = NA, align = "right") /
           zoo::rollmean(close, 20, fill = NA, align = "right"),
         bw_ratio = bb_width / kc_width) |> ungroup()

print(ic_summary(cross_section_ic(panel, "bw_ratio", "fwd_vol_20")))
panel |> filter(!is.na(kc_width), !is.na(bw_ratio)) |> group_by(date) |>
  summarise(rho = cor(kc_width, bw_ratio, method = "spearman"), .groups = "drop") |>
  summarise(平均相关 = round(mean(rho, na.rm = TRUE), 3)) |> print()
```

### Python

```python
# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# 第一组：%K 对收益目标
print(ic_summary(cross_section_ic(panel, "kc_pct", "forward_1")))
print(ic_summary(cross_section_ic(panel, "kc_pct", "forward_5")))
print(layered_returns(panel, "kc_pct", "forward_5"))

# 第二组：宽度对波动率目标，单独成表
print(ic_summary(cross_section_ic(panel, "kc_width", "fwd_vol_20")))

# 第三组：双通道宽度比，先补布林带宽度再检验
bb_sd = panel.groupby("code")["close"].transform(lambda s: s.rolling(20).std())
bb_mid = panel.groupby("code")["close"].transform(lambda s: s.rolling(20).mean())
panel["bb_width"] = 4 * bb_sd / bb_mid
panel["bw_ratio"] = panel["bb_width"] / panel["kc_width"]

print(ic_summary(cross_section_ic(panel, "bw_ratio", "fwd_vol_20")))
rho = panel.groupby("date").apply(
    lambda g: g[["kc_width", "bw_ratio"]].corr(method="spearman").iloc[0, 1])
print("宽度与比值的平均横截面相关：", round(rho.mean(), 3))
```

三组结果分别回答三个问题。%K 是否有选股能力，宽度是否是合格的波动代理，比值是否在宽度之外还有增量。第三组最后那一行相关是关键：若宽度与比值的横截面相关很低，说明比值确实是独立信息；若相关很高，比值只是宽度的另一种刻度，不值得单独保留。两组目标列的结果仍要分开看，%K 那一组的目标是收益，后两组是波动率。

## 择时能力

时序上肯特纳的读法有三层。第一层是突破，价格上穿上轨且中轨向上，属于离散事件。第二层是收窄，通道宽度落到历史低位，属于状态。第三层是中轨的方向与支撑，价格回调至中轨止跌是趋势健康的确认，跌破则趋势转弱。

检验方法要与形态匹配。突破是事件，适合信号触发日检验，比较突破日与其余交易日的后续收益。%K 是连续变量，适合条件分位收益，观察各档是否单调。收窄是状态，适合分组对照，比较收窄期与常态期未来收益的分布。

这里要强调分布而非均值。ATR 存在滞后，波动从低位跃升时，通道往往还偏窄，价格容易被连续突破，产生一串看似有效的信号。这些信号集中在波动跃升的初期，对应的是收益分布整体变宽，而不是均值抬升。只看均值，容易得出突破无用的结论；看标准差与左尾，才会看到真正发生的变化是风险的重估。

三个陷阱。第一，突破事件在波动跃升期高度重叠，连续多日站在上轨外侧会被计为多次触发，样本不独立，显著性被高估。第二，收窄阈值若用全样本分位，等于提前知道未来的宽度分布，回测应改为滚动分位。第三，三个参数（中轨周期、ATR 周期、倍数）共同决定宽度，在同一段样本里同时优化会让结果变成拟合，稳健做法是固定标准参数，检查邻近取值的表现是否平稳。

### R

```r
# 沿用第 007 章定义的 timing_signal_test / conditional_quantile_return / timing_backtest
df <- panel |> filter(code == "600519.SS") |> arrange(date)

# 突破事件：%K 高于 95 分位视为站上上轨
print(timing_signal_test(df, "kc_pct", "forward_5", upper = 0.95))

# 条件分位收益：%K 分五档
print(conditional_quantile_return(df, "kc_pct", "forward_5", q = 5))

# 收窄与常态的收益分布对照
df <- df |> mutate(narrow = as.integer(kc_width < quantile(kc_width, 0.2, na.rm = TRUE)))
df |> group_by(narrow) |>
  summarise(样本数 = n(),
            平均收益 = round(mean(forward_5, na.rm = TRUE) * 100, 3),
            标准差 = round(sd(forward_5, na.rm = TRUE) * 100, 3),
            夏普 = round(mean(forward_5, na.rm = TRUE) /
                           sd(forward_5, na.rm = TRUE) * sqrt(252 / 5), 2),
            左尾 = round(quantile(forward_5, 0.05, na.rm = TRUE) * 100, 3),
            .groups = "drop") |> print()

print(timing_backtest(df, "kc_pct", "forward_5", entry_q = 0.8))
```

### Python

```python
# 沿用第 007 章定义的 timing_signal_test / conditional_quantile_return / timing_backtest
df = panel[panel["code"] == "600519.SS"].sort_values("date").copy()

# 突破事件：%K 高于 95 分位视为站上上轨
print(timing_signal_test(df, "kc_pct", "forward_5", upper=0.95))

# 条件分位收益：%K 分五档
print(conditional_quantile_return(df, "kc_pct", "forward_5", q=5))

# 收窄与常态的收益分布对照
df["narrow"] = (df["kc_width"] < df["kc_width"].quantile(0.2)).astype(int)
print(df.groupby("narrow")["forward_5"].agg(
    样本数="count",
    平均收益=lambda s: round(s.mean() * 100, 3),
    标准差=lambda s: round(s.std() * 100, 3),
    夏普=lambda s: round(s.mean() / s.std() * np.sqrt(252 / 5), 2),
    左尾=lambda s: round(s.quantile(0.05) * 100, 3)))

print(timing_backtest(df, "kc_pct", "forward_5", entry_q=0.8))
```

三组输出分别对应事件、形态与状态。突破检验若显著且方向为正，说明通道突破具备动量特征；条件分位若在高端单调抬升，说明突破越强后续越强，这与均值回归类的 %B 正好相反。这一层与截面结论看似矛盾，其实不冲突：截面比较的是同一时点不同标的的位置，极端位置多对应短期过度延伸；时序检验的是同一标的突破的那几天，位置偏高往往伴随趋势启动。同一个读数在两个维度上含义不同，这正是两条检验线要分开跑的理由。收窄分布表看标准差与左尾，若均值相近而这两列更高，说明收窄预测的是波动的展开，方向仍需另找依据。

## 组合使用与验证

肯特纳的常见搭档有三个。与布林带搭配，两条通道的宽度比是判断波动来源的现成工具，一个用标准差，一个用真实波幅，分歧本身就带信息。与平均趋向指数搭配，ADX 补市况前提，趋势弱时突破多为噪音。与成交量搭配，突破放量提高可靠性，缩量突破多属假信号。

**组合的截面验证。** 把布林带宽度与肯特纳宽度都取负，转成低波动得分，标准化后相加，得到一个双通道低波动因子。它要回答的问题是：两把尺子合起来，是否比任何一把单独使用更准。若两把尺子的横截面相关很高，组合只是平均；若相关中等，组合可能略优于两者。这一检验的价值不在得出一个更强的因子，而在确认两条通道是否重复。若组合明显优于任一单通道，说明标准差与真实波幅捕捉的是波动的不同侧面，两条通道值得同时保留。

**组合的择时验证。** 条件型组合更贴近实务：价格突破上轨且中轨向上才持仓，两者缺一即空仓。回测时与两个单条件并排跑，比较年化、夏普与最大回撤。中轨方向的加入会减少持仓天数，作用在于滤掉波动跃升初期的假突破。改进通常体现在最大回撤与胜率上，年化收益未必提高。

增益的判读沿用方法论章的标准：组合的 ICIR 高于两个单特征，才说明存在互补性。同族通道的宽度相关性很高，组合多半只是平均，此时更该做的是二选一，而不是叠加。真正有增量的是宽度与位置这两个不同维度，以及宽度比这类刻画分歧的构造。把同源因子反复叠加，是通道类指标最容易犯的错误。

### R

```r
# 沿用第 007 章定义的 combined_signal
# 组合的截面验证：两条通道的宽度都反向，合成双通道低波动得分
panel <- panel |> group_by(code) |>
  mutate(low_bb = -bb_width, low_kc = -kc_width) |> ungroup()

panel |> filter(!is.na(low_bb), !is.na(low_kc)) |> group_by(date) |>
  summarise(rho = cor(low_bb, low_kc, method = "spearman"), .groups = "drop") |>
  summarise(平均相关 = round(mean(rho, na.rm = TRUE), 3)) |> print()

panel <- combined_signal(panel, c("low_bb", "low_kc"))
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "low_bb", "forward_5")))
print(ic_summary(cross_section_ic(panel, "low_kc", "forward_5")))
```

```r
# 沿用第 007 章定义的 timing_backtest
# 组合的择时验证：突破上轨且中轨向上才持仓
df <- panel |> filter(code == "600519.SS") |> arrange(date) |>
  mutate(kc_slope = kc_mid / dplyr::lag(kc_mid, 5) - 1,
         cond_break = as.integer(kc_pct > 0.9),
         cond_trend = as.integer(kc_slope > 0),
         cond = as.integer(cond_break == 1 & cond_trend == 1))

print(timing_backtest(df, "cond_break", "forward_5", entry_q = 0.5))
print(timing_backtest(df, "cond_trend", "forward_5", entry_q = 0.5))
print(timing_backtest(df, "cond", "forward_5", entry_q = 0.5))
```

### Python

```python
# 沿用第 007 章定义的 combined_signal
# 组合的截面验证：两条通道的宽度都反向，合成双通道低波动得分
panel["low_bb"] = -panel["bb_width"]
panel["low_kc"] = -panel["kc_width"]

rho = panel.groupby("date").apply(
    lambda g: g[["low_bb", "low_kc"]].corr(method="spearman").iloc[0, 1])
print("两条通道宽度的平均横截面相关：", round(rho.mean(), 3))

panel = combined_signal(panel, ["low_bb", "low_kc"])
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "low_bb", "forward_5")))
print(ic_summary(cross_section_ic(panel, "low_kc", "forward_5")))
```

```python
# 沿用第 007 章定义的 timing_backtest
# 组合的择时验证：突破上轨且中轨向上才持仓
df = panel[panel["code"] == "600519.SS"].sort_values("date").copy()
df["kc_slope"] = df["kc_mid"] / df["kc_mid"].shift(5) - 1
df["cond_break"] = (df["kc_pct"] > 0.9).astype(int)
df["cond_trend"] = (df["kc_slope"] > 0).astype(int)
df["cond"] = ((df["cond_break"] == 1) & (df["cond_trend"] == 1)).astype(int)

print(timing_backtest(df, "cond_break", "forward_5", entry_q=0.5))
print(timing_backtest(df, "cond_trend", "forward_5", entry_q=0.5))
print(timing_backtest(df, "cond", "forward_5", entry_q=0.5))
```

截面三行要看相关那一个数字先。相关接近一时，组合的 ICIR 只会落在两者之间，说明两条通道在说同一件事，保留一个即可；相关中等时，组合才有可能高于两者。择时那一组看持仓天数与回撤的取舍：条件变严后交易次数下降，若夏普上升而年化基本持平，说明中轨过滤确实滤掉了波动跃升初期的假突破。

## AI 引导词

::: prompt 引导词 1：与布林带的对照实验

请帮我写一段 Python 代码，在同一段数据上对比肯特纳通道与布林带对同一段行情的反应差异。要求：1）肯特纳通道用 EMA(20) 加上 2 倍 ATR(10)，布林带用 SMA(20) 加上 2 倍标准差；2）计算两条通道的宽度序列与 %B 序列；3）找出一次明显的跳空或单日大涨，比较两种宽度在事件前后的变化幅度；4）用文字总结在跳空行情中两者为何反应不同。数据用 yfinance 获取，代码需可直接运行，只使用 pandas、numpy、yfinance、matplotlib。

:::
::: prompt 引导词 2：三个参数的敏感性检验

我在研究肯特纳通道的三个参数（中轨周期、ATR 周期、倍数）对信号的影响。请帮我设计一个敏感性检验方案：1）中轨周期取 10、20、30，ATR 周期取 5、10、20，倍数固定为 2；2）对每种组合统计通道被价格穿越的次数与挤压天数占比；3）输出一个表格，行是中轨周期、列是 ATR 周期；4）说明哪个参数对信号密度的影响最大，以及为什么不应同时优化三个参数。请输出可直接运行的 Python 代码。

:::
::: prompt 引导词 3：宽度因子的规则化回测

我打算把"肯特纳通道宽度处于低位后突破"写成可回测的规则。请帮我把规则细化：1）如何定义宽度低位（用多少窗口的历史百分位）；2）如何定义突破（收盘价穿越上轨还是盘中穿越）；3）建仓与清仓的条件，以及换手率的计算方式；4）A 股回测需要扣除的费率与印花税取值。请给出 R 和 Python 两版实现，并说明如何避免用未来数据判定宽度低位与挤压状态。

:::
