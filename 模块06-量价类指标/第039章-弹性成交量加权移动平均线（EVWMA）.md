# 第039章 弹性成交量加权移动平均线（EVWMA）

同一段行情，一个交易者把二十日简单均线和一条按成交量加权的均线画在一起，两条线在放量那几天分得最开。他据此判断趋势已经转向，另一条线却给出相反的位置。他意识到差别不在参数，而在权重：等权均线把二十天前的成交和昨天的成交看成一样重。如果让成交密集的日子在均线里多占一份话语权，这条成本线会不会更贴近持仓者的真实处境。

## 名称与来历

弹性成交量加权移动平均线（Elastic Volume-Weighted Moving Average，EVWMA）。

它没有公认的单一提出者。把成交量引入移动平均权重的想法在二十世纪九十年代逐步成形，随后的开源量化库把它整理成固定的递推形式，EVWMA 才成为一个有明确公式的标准指标。在 R 的 TTR 包中，EVWMA 是一个独立函数，需要同时传入价格和成交量两个序列 [@ulrich2020]。中文资料中它也译作弹性量价均线，名称中的"弹性"指均线的有效窗口长度会随成交量伸缩。

EVWMA 要解决的问题是传统均线的一个盲点：所有移动平均线都只用价格，把成交量信息完全丢弃。现实中的经验是，放量突破比无量拉升可靠，缩量回调比放量杀跌安全。既然成交量代表市场参与度，那么均线的窗口长度就应该与参与度挂钩：量大时窗口收窄，紧跟价格；量小时窗口拉宽，保持平滑。EVWMA 就是这个想法的直接实现。

## 核心逻辑

考虑一个对比：缩量横盘和放量突破这两种行情，同一条 20 日均线的反应速度应该一样吗？

传统均线的答案是"一样"，因为窗口固定为 20 天，不区分这 20 天里成交是活跃还是清淡。这在量能稳定的市场里问题不大，但在量能剧烈变化时会产生偏差。放量突破的当天，价格跳空上行，20 日均线因为要等 20 天的数据更新，反应迟缓，等到均线确认时价格可能已经走远。缩量横盘时，价格在窄幅区间内微小波动，20 日均线却因为等权处理，把二十天前的旧价格也计入，反而显得迟钝。

EVWMA 的思路是让窗口长度由成交量决定。它设定一个成交量阈值，从当日开始向左累积成交量，直到累计值达到阈值为止，实际涵盖的天数就是有效窗口。交投活跃时，几天就能累积到阈值，窗口自动缩短，均线更快跟随价格；交投清淡时，需要十几二十天才能累积到阈值，窗口自动拉长，均线更平滑。

这个机制的效果可以这样理解：EVWMA 的每一点，都是"最近足够多的成交"所对应的加权平均价格。成交量大的日子，在窗口里占的权重大，对均线的影响也大。因此 EVWMA 更接近真实成交成本的概念。同样一条均线，在放量期它贴近最新成交，在缩量期它保持稳定，这种自适应让它在量价配合明显的品种上比普通均线更敏感地反映趋势变化。

把均线的权重想成股东投票：等权均线是一人一票，成交量加权则按持股数计票，放量的日子票多，说话更算数。这个类比能推出一个可检验的判断：若按成交量分配投票权真的带来新信息，EVWMA 与等权均线之差就应当对后续收益有解释力，并且在剔除普通均线偏离之后仍然存在；若残差归零，说明多出来的是计算，不是信息。

## 计算公式

EVWMA 的递推形式是理解它的关键。先定义成交量窗口之和与均线初值，再用递推式更新。

### 第一步：确定成交量窗口

$$W_t = \sum_{i=0}^{n-1} v_{t-i}$$

其中 $v_t$ 为第 t 日成交量，n 为周期参数。需要注意，这里的 n 与传统均线的 n 语义不同：它不是固定取 n 根 K 线，而是取最近 n 日的成交量之和作为权重基数。TTR 的 EVWMA 函数中，n 的默认取值为 20。

### 第二步：计算初值

$$EVWMA_n = \frac{\sum_{i=0}^{n-1} v_{n-i}\, p_{n-i}}{\sum_{i=0}^{n-1} v_{n-i}}$$

即前 n 日的成交量加权平均价格。这一步与普通的成交量加权均线相同，区别出现在后续的递推更新。

### 第三步：递推更新

$$EVWMA_t = \frac{v_t\, p_t + EVWMA_{t-1}\,(W_t - v_t)}{W_t}$$

递推式写成加权平均的形式更容易看出权重分配：

$$EVWMA_t = \underbrace{\frac{v_t}{W_t}}_{\text{当日权重}} \times p_t + \underbrace{\frac{W_t - v_t}{W_t}}_{\text{历史权重}} \times EVWMA_{t-1}$$

当日的权重是 $v_t / W_t$，即当日成交量占窗口成交量之和的比例。当日放量时，这个比例上升，新价格对均线的影响加大，均线向价格靠近得更快；当日缩量时，比例下降，均线基本保持原来的位置。这就是"弹性"的数学来源：权重不是固定的 1/n，而是随成交量浮动。

**计算示例。** 设 n = 3，前三日价格与成交量为：

| 交易日 | 价格 p | 成交量 v |
|--------|--------|---------|
| 1 | 10.0 | 100 |
| 2 | 11.0 | 200 |
| 3 | 12.0 | 100 |
| 4 | 13.0 | 400 |

初值取前三日的加权平均：

$$EVWMA_3 = \frac{10\times100 + 11\times200 + 12\times100}{400} = \frac{4400}{400} = 11.0$$

第四日放量，窗口之和 $W_4 = 200 + 100 + 400 = 700$，当日权重为 $400/700 \approx 0.571$。递推得

$$EVWMA_4 = \frac{400\times13 + 11.0\times(700 - 400)}{700} = \frac{5200 + 3300}{700} \approx 12.14$$

第四日成交放大到前两日的两到四倍，当日权重超过一半，均线从 11.0 快速上移到 12.14，明显向 13.0 靠近。如果第四日成交量只有 50，则当日权重仅约 0.14，均线几乎不动。权重的差异完全由成交量决定。

**参数含义。**

| n | 弹性窗口常态长度 | 灵敏度 | 适用品种 |
|---|----------------|--------|---------|
| 10 到 15 | 较短 | 高 | 高换手率的活跃个股 |
| 20 | 中等，约 15 到 25 根 K 线 | 中 | 蓝筹股、主流指数 |
| 30 到 50 | 较长 | 低 | 低换手率的银行股、债券 |

参数调整的原则是让常态下的弹性窗口覆盖 15 到 25 根 K 线。n 太小，成交量基数小的品种上阈值过低，窗口可能只有一两天，失去平滑意义；n 太大，成交量基数大的品种上窗口过长，失去灵敏度。

## 用法与信号

**拐头。** EVWMA 的拐头不仅需要价格变化，还需要累积成交量达到阈值，因此比普通均线的拐头带有量能验证。EVWMA 由下转上时，近期放量上涨使弹性窗口缩短，均线快速向上跟进，属于量价齐升的格局；由上转下时，近期放量下跌使窗口缩短，均线快速向下，属于量价齐跌。拐头信号适合作为趋势方向的切换提示。

**价格与均线的相对位置。** EVWMA 作为动态支撑或阻力时，天然带有成交量信息。放量突破 EVWMA，说明有资金进场推动，突破的可信度相对较高；缩量回踩 EVWMA 后止跌，说明抛压不大，支撑有效。放量跌破 EVWMA 说明资金加速离场；缩量反弹至 EVWMA 遇阻，说明买盘不足。同样的位置，成交量的大小给出不同强度的解读。

**与同周期均线的距离。** 把 EVWMA 与同周期的 EMA 或 SMA 并列观察。EVWMA 明显高于 EMA，说明近期成交量放大且价格在上涨，量能推动价格上行；明显低于 EMA，说明近期放量且价格在下跌，量能推动价格下行。两者接近时说明成交量在均值附近，EVWMA 退化为普通均线，此时它相对 EMA 没有额外信息。

**跳跃。** 当成交量出现极端变化，比如单日爆出数倍均量，EVWMA 的当日权重会瞬间接近 1，均线随之出现明显跳跃。向上跳跃说明单日超大量推动价格上行，是极强的短期信号，但需要警惕量能能否延续；向下跳跃同理。跳跃本身不是买卖建议，而是一个需要进一步核实量能持续性的提示。

## 边界与误区

**低量时段接近僵化。** 成交量极度萎缩时，弹性窗口会拉得很长，EVWMA 几乎不动，任何价格变化都难以触发拐头。节假日前后的缩量期是典型的例子。这段时间的 EVWMA 信号可以参考，但不宜作为主要依据，应结合其他量价指标共同判断。

**跨品种使用同一参数会失真。** 不同品种的日均成交量差异巨大，同样的 n 在活跃个股上可能是三天的窗口，在低换手品种上可能是四十天的窗口。跨品种使用时，应以换手率而非绝对成交量作为参考，让常态窗口长度落在合理的区间内。

**成交量季节性变化会系统性影响窗口。** A 股存在明显的成交量季节规律，比如春节前缩量、季末调仓放量。这些周期性的量能变化会系统性地改变 EVWMA 的弹性窗口长度，使指标的灵敏度随季节波动。在已知的缩量期，对 EVWMA 信号的要求应适当放宽。

**在无量涨跌停的极端行情中失效。** 涨停或跌停时成交量可能极度萎缩或极度放大，成交明细失真，EVWMA 的权重分配失去意义。这类极端行情下，EVWMA 应与 EMA 并列使用，两者信号矛盾时以更稳健的 EMA 为准。EVWMA 不能替代传统均线，只能作为补充。

## 它被检验过吗

EVWMA 没有针对它本身的独立同行评议检验。它属于均线族的一个变体，而均线族的证据只到规则族这一层：Brock、Lakonishok 与 LeBaron（1992）、Sullivan、Timmermann 与 White（1999）检验的是均线规则的集合，结论不区分具体变体，也无法归因到成交量加权这一改动上。

可引的关系层面证据是 Karpoff（1987）的综述，量价正相关且不对称，但它同样不是对 EVWMA 的绩效检验。完整证据链见第 007 章。

这一类的真实失效案例，见第 035 章的「真实案例与失败模式」。

## 代码实现

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
volume <- Vo(data)

# 3. 计算指标：手写 EVWMA 递推（n 为成交量窗口天数）
my_evwma <- function(price, volume, n = 20) {
  p <- as.numeric(price); v <- as.numeric(volume)
  N <- length(p)
  out <- rep(NA_real_, N)
  if (N < n) return(xts::xts(out, order.by = index(price)))
  # 初值：前 n 日的成交量加权平均价
  w <- sum(v[1:n])
  out[n] <- sum(p[1:n] * v[1:n]) / w
  # 递推：当日权重为 v[t] / W[t]
  for (t in (n + 1):N) {
    w <- w - v[t - n] + v[t]
    out[t] <- (v[t] * p[t] + out[t - 1] * (w - v[t])) / w
  }
  xts::xts(out, order.by = index(price))
}

evwma20 <- my_evwma(close_price, volume, n = 20)
ema20   <- EMA(close_price, n = 20)

# 4. 识别信号：EVWMA 上穿 EMA 视为量能推动转强
cross_up   <- crossover(evwma20, ema20)
cross_down <- crossover(ema20, evwma20)
cat("EVWMA 上穿 EMA 次数：", sum(cross_up, na.rm = TRUE), "\n")
cat("EVWMA 下穿 EMA 次数：", sum(cross_down, na.rm = TRUE), "\n")

# 5. 绘图
chartSeries(data, theme = "white", name = "贵州茅台",
  TA = "addTA(EVWMA(Cl(.), Vo(.), n = 20), col = 'blue');
        addTA(EMA(Cl(.), n = 20), col = 'red')")

# 6. 输出统计：价格位于 EVWMA 上方的比例
above <- sum(close_price > evwma20, na.rm = TRUE) / sum(!is.na(evwma20))
cat("价格位于 EVWMA20 上方的比例：", round(above, 3), "\n")
```

### Python

```python
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
```

## 拆解

EVWMA 与价格同量纲，直接排序排的是股价。偏离度虽无量纲，信息却与同周期均线偏离度重叠，区别只在权重。拆解的重点因此不在偏离度，而在普通均线没有的那层信息：成交量在时间上的分布。

| 特征名 | 计算式 | 量纲 | 经济含义 |
|--------|--------|------|----------|
| 价格偏离度 | $(p_t-EVWMA_t)/EVWMA_t$ | 无量纲比例 | 价格相对量价加权成本的位置 |
| EVWMA 斜率 | $(EVWMA_t-EVWMA_{t-k})/EVWMA_{t-k}$ | 无量纲比例 | 加权成本的变化方向与速度 |
| 成交集中度 | $EVWMA_t/SMA_t^{(n)}-1$ | 无量纲比例 | 近期成交相对早期成交的价格位移，是本章的独有特征 |
| 当日权重 | $v_t/W_t$ | 0 到 1 | 当日成交量占窗口成交量的比例，弹性强弱的直接读数 |

成交集中度是本指标相对普通均线的增量所在。EVWMA 的权重按成交量分配，SMA 的权重按天数平均分配。若近期的成交明显大于早期，EVWMA 会更贴近近期价格；若价格在近期上行，EVWMA 就会高于 SMA，读数为正。因此这个差值的符号由价格方向决定，绝对值才反映成交集中的程度。

带符号的集中度把"集中"与"方向"揉在一起，正值可能是放量推升，也可能是缩量下跌后的反弹；绝对值剥掉方向，只留集中程度。两种版本对应两个问题：前者问"资金是不是在推着价格走"，后者问"最近的成交是不是异常集中"，检验时应分开处理。

集中度还有一个测量上的困难。EVWMA 的参数 $n$ 是成交量窗口，不是天数窗口，有效长度等于 $W_t/\bar v_t$，随换手率浮动。高换手标的的 20 日成交量之和可能三天就攒够，有效窗口只有三五天；低换手标的要一个多月。用固定 20 日的 SMA 对照，差值里混进了窗口长度差异。严格的做法是先估计有效窗口，再用同等长度的 SMA 对照；实务上常简化为固定 $n$，把换手率作为控制变量。成交量口径也要一致，权重完全由成交量决定，口径不同会直接改变有效窗口的长度。

### R

```r
# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
library(dplyr)

# EVWMA 递推：当日权重为 v_t / W_t，W_t 为 n 日成交量之和
evwma_calc <- function(p, v, n = 20) {
  p <- as.numeric(p); v <- as.numeric(v)
  N <- length(p); out <- rep(NA_real_, N)
  if (N < n) return(out)
  w <- sum(v[1:n])
  out[n] <- sum(p[1:n] * v[1:n]) / w
  for (t in (n + 1):N) {
    w <- w - v[t - n] + v[t]
    out[t] <- (v[t] * p[t] + out[t - 1] * (w - v[t])) / w
  }
  out
}

# panel 已含 date / code / close / volume / forward_1 / forward_5
panel <- panel |>
  group_by(code) |>
  arrange(date, .by_group = TRUE) |>
  mutate(
    evwma20 = evwma_calc(close, volume, 20),
    sma20 = zoo::rollmean(close, 20, fill = NA, align = "right"),
    evwma_dev = close / evwma20 - 1,
    # 成交集中度：量价加权均线相对等权均线的位移
    conc = evwma20 / sma20 - 1,
    conc_abs = abs(conc),
    # 当日成交占 20 日成交量之和的比例
    w_now = volume / zoo::rollsum(volume, 20, fill = NA, align = "right"),
    evwma_slope = evwma20 / dplyr::lag(evwma20, 10) - 1
  ) |>
  ungroup()
```

### Python

```python
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
```

四个特征的信息量递减：偏离度与斜率是均线的常规派生量，集中度与当日权重才带着成交量的痕迹。

## 截面选股能力

EVWMA 的横截面因子有两个候选。第一个是集中度：

$$f^{conc}_t=\frac{EVWMA_t^{(n)}}{SMA_t^{(n)}}-1$$

第二个是偏离度：

$$f^{dev}_t=\frac{p_t-EVWMA_t^{(n)}}{EVWMA_t^{(n)}}$$

前者是本章要检验的主角，后者作为对照。两者的经济含义不同：集中度为正说明近期的成交价格高于窗口早期的成交价格，资金在更高的位置换手；偏离度为正说明现价高于加权平均成本，持仓者整体浮盈。前者描述成交的分布，后者描述盈亏的位置。

预期表现上，集中度属于量价配合型，方向通常偏正但依赖价格趋势。集中度为正且价格上行，说明放量推升；集中度为正而价格下行，说明下跌过程中在低位换手，可能是恐慌抛售，也可能是承接，两种情形在读数上区分不开。这种模糊性意味着集中度单独使用时 IC 不会很稳定，与价格方向组合之后才有较清晰的解释。

偏离度的价值在于它的"基准"作用。若集中度的表现与它接近，说明 EVWMA 没有提供超出普通均线的信息，多付出的成交量数据与递推计算没有回报。若集中度在剔除偏离度之后仍有解释力，说明成交分布这一层确实被定价。判断方法是对偏离度做横截面回归，取残差再算一次 IC。

检验时有三点值得注意。

第一，$n$ 与换手率的匹配在拆解里已经说明，检验上有两个处理：按换手率调整 $n$，或者对集中度取自身的时间序列分位。

第二，初值的影响不能忽略。递推从第 $n$ 日开始，初值是前 $n$ 日的成交量加权均价，之后每步都依赖前一步。序列开头几十个点尚未稳定，计算因子时应丢掉暖机段，长度取 $n$ 的三到五倍。

第三，与偏离度的共线性要做显式检查。两者的横截面相关通常不低，直接放进同一个模型会产生多重共线性，系数不稳。稳健的做法是先算两者的秩相关，再决定是取残差还是只保留一个。

### R

```r
# 沿用第 007 章定义的 cross_section_ic / ic_summary / layered_returns
# 集中度与偏离度并列检验
for (f in c("conc", "evwma_dev")) {
  cat("\n---", f, "vs forward_5 ---\n")
  print(ic_summary(cross_section_ic(panel, f, "forward_5")))
}

print(layered_returns(panel, "conc", "forward_5"))

# 集中度的绝对值版本：只保留集中程度，剥掉方向
cat("\n--- 集中度绝对值 ---\n")
print(ic_summary(cross_section_ic(panel, "conc_abs", "forward_5")))

# 对偏离度取残差，看集中度是否还有独立信息
panel <- panel |>
  group_by(date) |>
  mutate(conc_resid = {
    ok <- !is.na(conc) & !is.na(evwma_dev)
    r <- rep(NA_real_, dplyr::n())
    if (sum(ok) >= 10) r[ok] <- residuals(lm(conc[ok] ~ evwma_dev[ok]))
    r
  }) |>
  ungroup()

cat("\n--- 剔除偏离度后的残差 ---\n")
print(ic_summary(cross_section_ic(panel, "conc_resid", "forward_5")))
```

### Python

```python
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
```

几行结果有明确的阅读顺序。先看集中度与偏离度谁更强，两者接近说明增量有限；再看残差，残差的 IC 接近零，说明集中度的信息已被偏离度包含，EVWMA 相对 SMA 的优势没有落到预测上；最后看绝对值版本，它与带符号版本的方向可能不同。

## 择时能力

时序上 EVWMA 的择时逻辑分三层。第一层是价格与 EVWMA 的相对位置，站上加权成本视为偏多。第二层是 EVWMA 与同周期 EMA 的交叉，上穿说明近期成交的推动力强于时间加权的结果。第三层是集中度的极值，读数突然放大说明成交在短期内高度集中，往往对应突破或恐慌。

方法与信号形态要匹配。位置是状态量，适合条件分位收益与阈值回测。交叉是事件，一年十几次，适合触发日检验。集中度是连续量，适合分位检验，重点看两端，因极值对应异常换手，中间区间没有特别含义。

EVWMA 在时序上的优势比在截面上明显。均线信息本身就是时序概念，量的加权只是调整了反应速度。对单只标的而言，EVWMA 相对 EMA 的差异含义清楚：差异大说明近期成交集中，差异小说明成交均匀。这个含义在截面上会被标的之间的换手率差异淹没。

陷阱有两处。第一，低量时段的僵化。成交量萎缩时有效窗口拉长，EVWMA 几乎不动，价格上下穿越都不会触发信号，这段时间的检验结果实际上是"没有信号"，不能算作"信号失败"。第二，初值与暖机段。递推起点不同，前几十个点的路径会不同，若把这段纳入检验，结果依赖于数据起点。

### R

```r
# 沿用第 007 章定义的三种择时检验
df <- panel |> filter(code == "600519.SS") |> arrange(date)

cat("--- 信号触发日检验（偏离度高于 80 分位）---\n")
print(timing_signal_test(df, "evwma_dev", "forward_5", upper = 0.8))

cat("\n--- 条件分位收益（偏离度分五档）---\n")
print(conditional_quantile_return(df, "evwma_dev", "forward_5", q = 5))

cat("\n--- 择时策略与买入持有对照 ---\n")
print(timing_backtest(df, "evwma_dev", "forward_5", entry_q = 0.7))

# 集中度极值日的后续收益，与其余交易日对照
df |>
  mutate(集中 = as.integer(conc_abs > quantile(conc_abs, 0.9, na.rm = TRUE))) |>
  group_by(集中) |>
  summarise(样本数 = n(),
            平均未来五日收益 = round(mean(forward_5, na.rm = TRUE), 4),
            .groups = "drop") |>
  print()
```

### Python

```python
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
```

最后一行最值得看。集中度处于高位的那批交易日，若后续收益明显不同于其余日子，说明成交集中本身带有预测信息；若两者接近，说明它只是对已发生行情的描述。前者支持把集中度做成因子，后者只支持做成状态标签。

## 组合使用与验证

EVWMA 的搭档有三个。与价格动量搭配最自然：动量给方向，集中度给成交分布，两者相乘或分组，回答"放量推升是否比缩量推升更持久"。与 EMA 偏离度搭配属于同族对照，用于确认增量是否来自成交量权重。与换手率搭配用于控制规模，因为集中度的分布尺度本身就被换手率影响。

**组合的截面验证。** 加权型做法是把集中度与二十日动量各自标准化后等权相加，再走一遍截面检验。两者相关通常不高，一个是成交分布，一个是价格位移。组合的 ICIR 若能高于两者，说明量价两个维度互补；若落在中间，说明集中度的信息与动量重叠。条件型做法是只取"集中度为正且动量为正"的样本，比较触发样本内的收益。

**组合的择时验证。** 把"EVWMA 高于同周期 EMA 且价格高于 EVWMA"设为持仓条件，与单条件、买入持有对照。两个条件分别确认成交集中与价格站上加权成本，同时成立时仓位的含义最清楚。这类双重条件会把持仓比例压得较低，比较时应报告持仓天数占比。

增益的判读依据方法论章的标准：**组合的 ICIR 高于两个单特征，才说明存在互补性；介于两者之间，说明只是平均；低于两者，说明信号在某些时段互相抵消。** EVWMA 的增量本来就该体现在集中度上，若组合的改善主要来自动量那一侧，说明集中度没有贡献，evwma 的成交量权重可以省略。

### R

```r
# 沿用第 007 章定义的 combined_signal
panel <- panel |>
  group_by(code) |>
  mutate(mom20 = close / dplyr::lag(close, 20) - 1) |>
  ungroup()

panel |>
  group_by(date) |>
  filter(!is.na(conc), !is.na(mom20)) |>
  summarise(rho = cor(conc, mom20, method = "spearman",
                      use = "complete.obs"), .groups = "drop") |>
  summarise(平均相关 = round(mean(rho, na.rm = TRUE), 3)) |>
  print()

panel <- combined_signal(panel, c("conc", "mom20"))

cat("\n--- 组合 vs 单特征 ---\n")
print(ic_summary(cross_section_ic(panel, "combined", "forward_5")))
print(ic_summary(cross_section_ic(panel, "conc", "forward_5")))
print(ic_summary(cross_section_ic(panel, "mom20", "forward_5")))
```

```r
# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
df2 <- panel |>
  filter(code == "600519.SS") |>
  arrange(date) |>
  mutate(ema20 = as.numeric(TTR::EMA(close, 20)),
         cond = as.integer(evwma20 > ema20 & close > evwma20))

print(timing_backtest(df2, "cond", "forward_5", entry_q = 0.5))
```

### Python

```python
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
```

```python
# 组合的择时验证（沿用第 007 章定义的 timing_backtest）
df2 = panel[panel["code"] == "600519.SS"].sort_values("date").copy()
df2["ema20"] = df2["close"].ewm(span=20, adjust=False).mean()
df2["cond"] = ((df2["evwma20"] > df2["ema20"]) & (df2["close"] > df2["evwma20"])).astype(int)

print(timing_backtest(df2, "cond", "forward_5", entry_q=0.5))
```

三行输出并排读：组合高于两者说明互补，落在中间说明只是平均，低于两者说明信号冲突。择时那一组再看持仓比例，双重条件往往只覆盖两三成交易日，夏普的提升要折算到同等仓位后再比较。

## AI 引导词

::: prompt 引导词 1：与普通均线的增量信息检验

我在研究弹性成交量加权移动平均线（EVWMA）作为因子。核心疑问是成交量加权是否带来了超出普通均线的信息。请帮我设计一个检验方案：1）对同一批标的，分别构造"价格相对 EVWMA 的偏离度"和"价格相对同周期 EMA 的偏离度"两个因子；2）计算两个因子各自的 IC 均值和 ICIR，以及两者之间的相关系数；3）构造一个回归，用 EMA 偏离度对收益回归，取残差作为 EVWMA 的增量部分，检验残差与未来收益的相关性；4）用文字说明如何判断 EVWMA 是否值得在普通均线之上额外付出计算和数据成本。请输出可直接运行的 Python 代码。

:::
::: prompt 引导词 2：窗口参数的稳健性检验

请帮我写一段 Python 代码，检验 EVWMA 窗口参数的稳健性。具体要求：1）用 Python 手写 EVWMA 递推函数，n 取 10、15、20、30、50；2）对每个 n，统计弹性窗口的实际长度分布（当日权重超过 0.5 的天数占比、均线单日变动的幅度分布）；3）用价格相对 EVWMA 的偏离度作为因子，计算每个 n 下的 IC 均值和 ICIR；4）输出一个表格；5）用文字说明 n 的取值如何影响均线的灵敏度和信号质量，以及"常态窗口覆盖 15 到 25 根 K 线"这一原则在不同换手率品种上如何落地。请只使用 pandas、numpy、yfinance、matplotlib。

:::
::: prompt 引导词 3：放量突破形态的规则化

我观察到"价格放量突破 EVWMA"可能是一个可信度较高的信号。请帮我把这个条件写成可回测的规则，包括：1）如何量化"放量"（用当日成交量与窗口均量的比值，还是用 EVWMA 当日权重超过某个值）；2）如何定义"突破"（收盘价上穿 EVWMA，还是盘中最高价，确认时点如何设定）；3）如何在回测中对比"放量突破"与"缩量突破"的收益差异；4）如何计入 A 股的成本。请给出带中文注释的 Python 实现，并说明如何避免前视偏差和生存者偏差。

:::
