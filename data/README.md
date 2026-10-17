# data 目录说明

书稿中所有示例数据都在这里。数据来自本地 MySQL 库 `strategy_monitor`（仓库 `XQuant-DB`），
不再从网络抓取。这样代码离线可跑，复权与可交易性口径也和正文一致。

## 一眼看懂

```python
import pandas as pd
panel = pd.read_parquet("data/parquet/panel_blue_chip.parquet")
panel.head()
```

```r
panel <- read.csv("data/parquet/panel_blue_chip.csv", stringsAsFactors = FALSE)
head(panel)
```

Python 读 parquet，R 读 CSV。两份内容相同，CSV 是为了让 R 不必安装 arrow。

## 文件

| 文件 | 行数 | 内容 |
|---|---|---|
| `panel_blue_chip.parquet` | 2,905 | **正文示例用**。5 只蓝筹，2023-01-01 至 2025-06-01 |
| `panel_blue_chip.csv` | 2,905 | 同上，CSV 版，供 R 读取 |
| `panel.parquet` | 302,757 | **真实横截面用**。287 只，2021-06 至 2025-12 |
| `daily_prices.parquet` | 302,757 | 原始日线，未做衍生计算 |
| `index_daily.parquet` | 6,690 | 6 只宽基 ETF，择时检验的市场载体 |
| `industry.parquet` | 5,571 | 全市场行业分类与市值快照，31 个申万一级行业 |
| `universe.parquet` | 300 | 扩展股票池清单 |
| `corp_action_flagged.parquet` | 10 | 被自动识别并修补的除权日 |

`panel_blue_chip` 的 5 只是正文反复引用的示例：`600519.SS` 贵州茅台、`600036.SS` 招商银行、
`601318.SS` 中国平安、`300750.SZ` 宁德时代、`000858.SZ` 五粮液。

## 字段

| 字段 | 类型 | 含义 |
|---|---|---|
| `date` | date | 交易日 |
| `code` | str | 标的代码，`600519.SS` 这种 yfinance 风格 |
| `name` | str | 中文简称 |
| `industry` | str | 申万一级行业（快照，见下文） |
| `board` | str | 板块：main / gem / star / bse，决定涨跌停幅度 |
| `open` `high` `low` `close` | float | **已做除权修补**的价格（送转复权后） |
| `open_raw` `high_raw` `low_raw` `close_raw` | float | 数据库原始价格，未经修补 |
| `volume` | int | 成交量（股） |
| `adjusted` | float | 复权价，用于计算收益 |
| `ret` | float | 当日收益率 |
| `forward_1` `forward_5` `forward_20` | float | 未来 1 / 5 / 20 日收益率，末若干行为空 |
| `fwd_vol_20` | float | 未来 20 日已实现波动率（年化） |
| `corp_action` | 0/1 | 该日被判定为送转除权日并做了修补 |
| `resume_day` | 0/1 | 停牌后复牌首日，通常不设涨跌幅 |
| `new_listing` | 0/1 | 次新股（上市未满一年，且首日晚于窗口起点） |
| `limit_up` `limit_down` | 0/1 | 触及涨停 / 跌停 |
| `suspended` | 0/1 | 当日无成交，价格由前值填充 |
| `price_valid` | 0/1 | 价格是否为真实成交（停牌日为 0） |
| `tradable` | 0/1 | 可交易：非涨跌停、非停牌 |

## 三个必须知道的数据处理

**一、送转除权是自动修补的。** 数据库的 `adjusted` 字段做了现金分红复权，但没有做送股与转增复权。
表现为除权日开盘价直接低于前一日最低价，单日收益出现负 30% 这类不可能的值。全样本共 10 处，
涉及 10 只标的，例如 `300308.SZ` 在 2024-05-06、`688072.SS` 同日。

修补方式：把开盘价与前一日收盘价的比例当作复权系数，向后累乘放大价格。假设隔夜无真实跳空，
这是 A 股集合竞价下的近似。代价是除权当日的真实涨跌被并入复权系数，误差只影响当日。
被修补的日期在 `corp_action` 列标 1，原始价格保留在 `*_raw` 列，可随时核对。

修补前后 `ret` 的最小值从负 32% 变为负 20%，与创业板跌停幅度一致。

**二、涨跌停按板块分别判定。** 主板 9.8%、创业板与科创板 19.8%、北交所 29.8%，留了 0.2 个百分点的余量。
不用 10% 整，是因为四舍五入会让真实涨停落在 9.97% 这类位置。

**三、行业分类是快照，不是历史。** 来自 `a_share_industry_cap` 的 2026-09-30 单一快照，全市场 31 个申万一级行业。`panel.parquet` 的 287 只落在其中 27 个行业里，另外 4 个行业没有标的进入市值前 300。
用它做行业中性化会有幸存者偏差与行业变更的问题。这一点在第 053 章的待核清单里列为第 5 项。

## 没有的东西

数据库里**没有指数本身的日线**，只有跟踪指数的 ETF。所以 `index_daily.parquet` 里是
510300（沪深300）、510500（中证500）、510050（上证50）、159915（创业板）、159845（中证1000）、
588000（科创50）六只 ETF，用它们代替指数做择时检验的市场载体。

也**没有**分红送转的明细数据，所以除权修补只能靠价格反推，无法用真实送转比例。

## 重新生成

数据不是手改的，任何时候都能从数据库重新拉一遍：

```bash
# 1. 从 MySQL 导出到 data/staging/（需要 R + DBI + RMySQL）
Rscript scripts/export_from_db.R

# 2. 转 parquet 并派生研究面板（需要 pandas + pyarrow + numpy）
python3 scripts/csv_to_parquet.py
```

第一步按 `XQuant-DB/config/config.yml` 里的连接参数读库。`data/staging/` 是中间件，当前已清空，这一步会自动重建它，产出的 CSV 只用于下一步转换。

第二步在控制台打印每个文件的行数与体积，以及除权修补、可交易性占比等质量指标。两步共约 30 秒。转换完成后 staging 可以再清掉，省下 28MB。

## 关于规模

正文的所有示例都用 `panel_blue_chip`，也就是 5 只标的。这个规模只够把流程跑通，不足以支撑任何横截面结论。
实测过这件事：同一份数据、同一个 20 日偏离度因子、同一段区间，5 只标的与 287 只标的算出的 IC 均值几乎一样
（负 0.018 与 负 0.019），但 IC 标准差差了一倍多（0.559 与 0.218），t 统计量从负 0.76 变成负 2.08。

也就是说，5 只标的时这个因子被判为"不显著"，287 只时被判为"临界显著"。样本量改变的不是结论的方向，
而是能否下结论。要做真实研究，请用 `panel.parquet`。
