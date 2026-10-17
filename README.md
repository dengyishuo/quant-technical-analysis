# 量化投资视角的技术分析

> AI 时代技术分析新视角

**[在线读](https://dengyishuo.github.io/quant-technical-analysis/)** · 54 章 · 80 万字 · 231 组 R/Python 双语代码

一本按"讲原理 → 拆解特征 → 检验能力 → 建模融合"四层递进组织的中文技术分析书稿。源稿为纯 Markdown，编译为**单文件 HTML 电子书**（封面／目录／逐章阅读／夜间模式／键盘翻页）。

- **规模**：9 个模块 · 54 章 · 141 条 AI 引导词 · 231 组 R/Python 双语代码 · 28 幅指标图 · 约 82 万字
- **电子书**：`docs/index.html`（自包含单文件，1.62 MB，也可直接在线看，见下方「在线阅读」）
- **代码库**：`code/R/` 与 `code/python/` 各 39 个可运行文件，从书稿自动提取
- **数据**：`data/parquet/` 两级面板（5 只示例 / 287 只真实横截面），从本地 MySQL 导出

**结构上的一个关键决定**：检验不集中成一部分，而是并入每个指标章。读完一个指标的公式与信号，紧接着就走完拆解、截面检验、择时检验、组合验证四步。方法论前置在模块 02，指标章只调用、不重复推导。

---

## 在线阅读

电子书是单文件 HTML，三种看法：

1. 直接打开 `docs/index.html`
2. 已开启 GitHub Pages（`main` 分支的 `/docs`），地址为 <https://dengyishuo.github.io/quant-technical-analysis/>
3. 克隆后自己编译一份（见下）

在线版：<https://dengyishuo.github.io/quant-technical-analysis/>

---

## 快速开始

```bash
git clone https://github.com/dengyishuo/quant-technical-analysis.git
cd quant-technical-analysis

# 编译电子书（源稿改动后重新运行即可）
python3 电子书/build_ebook.py

# 从书稿提取代码到 code/（代码改动后运行）
python3 scripts/extract_code.py

# 重建数据（改了本地库之后运行，两步约 30 秒）
export DB_USER=... DB_PASSWORD=...     # 或写进 ~/.Renviron
Rscript scripts/export_from_db.R       # MySQL → data/staging/
python3 scripts/csv_to_parquet.py      # staging → data/parquet/
```

电子书与数据这两条链路互不依赖。只想读，克隆下来打开 `docs/index.html` 即可；只想跑代码，`data/parquet/` 与 `code/` 已经备好。

依赖分三类：

| 用途 | 依赖 |
|---|---|
| 编译电子书 | Python `markdown` |
| 读写数据 | Python `pandas` `pyarrow` |
| 跑书里的代码 | Python 见下「eQuant 生态」；R 用 `ettr` `efactorcraft` `efincharts` 等 |

公式与图片都已内联进 HTML，不依赖网络。

### eQuant 生态

书中全部代码调用 eQuant 系列包，不自己手写指标。两套实现同源同口径：

| 语言 | 包 | 仓库 |
|---|---|---|
| Python | `ettr` `efactorcraft` `eclassic` `efincharts` | github.com/dengyishuo/equant-py |
| R | `ettr` `efactorcraft` `eclassic` `efincharts` | github.com/dengyishuo/equant-r |

```r
# R：一次装齐
pak::pak(c("dengyishuo/ettr", "dengyishuo/efactorcraft",
           "dengyishuo/eclassic", "dengyishuo/efincharts"))
```

```bash
# Python：从源码装（各子包独立仓库）
git clone https://github.com/dengyishuo/equant-py
pip install -e equant-py/ettr-py -e equant-py/efactorcraft-py \
            -e equant-py/eclassic-py -e equant-py/efincharts-py
```

**统一数据规范**：长格式面板，一行一个「标的-日」，含 `date` / `code` / OHLCV。所有指标函数都是「进来一个面板、追加若干列」的形态，天然适配横截面与时间序列两种检验。

```
ettr.sma(df, n=[5, 20, 60])          # Python：追加 SMA_5 / SMA_20 / SMA_60
add_sma(df, n = 20)                  # R：追加 SMA_20
efc.ic_analysis(d, factor_cols="f")  # 横截面 IC
ic_analysis(d, factor_cols = "f")    # R 同口径
```

产物四个：

| 路径 | 用途 |
|---|---|
| `docs/index.html` | 电子书成品。GitHub Pages 直接指向这里，本地也可双击打开 |
| `电子书/build_ebook.py` | 编译脚本。运行时会在 `电子书/` 下另存一份同名 HTML（不入库，避免与 docs 重复 1.6 MB） |
| `code/` | 全部代码的独立可运行版本，`code/README.md` 是索引 |
| `data/parquet/` | 书中全部示例数据，`data/README.md` 是字段与口径说明 |
| `assets/figures/` | 各章指标图，编译时内联进 HTML |

### 数据

**每段代码都自带取数逻辑，复制就能跑，不需要先准备数据。** 取数函数按「本地 → 缓存 → 远程」的顺序查找：

```
1. ./data/parquet/xxx       有就直接用，不联网
2. ~/.cache/qta/xxx         有就用缓存（R 走 tools::R_user_dir("qta","cache")）
3. 都没有                    从 GitHub 下载一次，写入缓存
```

| 情形 | 行为 | 首次耗时 |
|---|---|---|
| 克隆了整个仓库 | 读本地文件 | 即时 |
| 只复制了代码片段 | 自动下载（约 25 MB） | 约 20 秒 |
| 跑过一次 | 命中缓存，断网可用 | 即时 |

想彻底离线，可以只拉 40 MB 的数据而不拉正文：

```bash
git clone --depth 1 --filter=blob:none --sparse \
  https://github.com/dengyishuo/quant-technical-analysis.git qta
cd qta && git sparse-checkout set data
```

拿到数据后的本地读取写法、字段对照、常见坑（`date` 必须转 Date、路径相对工作目录等）见 **[数据使用说明.md](数据使用说明.md)**。

数据从本地 MySQL 库 `strategy_monitor`（仓库 `XQuant-DB`）导出，两级规模：

| 文件 | 规模 | 用途 |
|---|---|---|
| `panel_blue_chip.parquet` | 5 只 · 2,905 行 · 2023-01 至 2025-06 | 正文示例 |
| `panel.parquet` | 287 只 · 302,757 行 · 2021-06 至 2025-12 | 真实横截面 |
| `index_daily.parquet` | 6 只宽基 ETF | 择时检验的市场载体 |
| `panel_r.csv.gz` | 287 只 · 9 列 · 6.8 MB | 供 R 读取（read.csv 直接支持 gz） |

除常规 OHLCV 外，面板里还带 `forward_1` / `forward_5` / `forward_20`（前向收益）、`fwd_vol_20`（未来 20 日已实现波动率）、`limit_up` / `limit_down` / `suspended` / `tradable`（可交易性）、`industry`（申万一级）、`corp_action`（送转除权修补标记）。

送转除权已自动修补。库里的复权字段只做了现金分红，没做送股转增，会导致除权日出现负 30% 这类假收益；全样本 10 处，按开盘价比例重建复权因子，原始价格保留在 `*_raw` 列。细节见 `data/README.md`。

---

## 全书结构

### 模块 01 · 技术分析总论（001–005，5 章）

技术分析从何处来，解决了什么问题，有哪些主要流派，这些流派共享什么假设、各自有什么局限。

| 章 | 标题 |
|---|---|
| 001 | 技术分析是什么 |
| 002 | 技术分析的历史脉络 |
| 003 | 主要方法流派 |
| 004 | 从质疑到量化视角 |
| 005 | 指标分类总览 |

### 模块 02 · 因子检验方法（006–007，2 章）

检验一个指标是否有效的统一方法论，前置在这里，供后续 28 个指标章反复调用。

| 章 | 标题 | 内容 |
|---|---|---|
| 006 | 从指标到可检验的因子 | 为什么逐个检验、四步流程、截面与择时的区别、检验纪律 |
| 007 | 双重检验方法论 | **全书的检验口径权威章**：全部公式、7 个公共函数、判读阈值、常见陷阱 |

### 模块 03 至 06 · 28 个指标章

每个指标章十一节：前六节讲原理，后四节走检验。

| 模块 | 章 | 指标 |
|---|---|---|
| 03 趋势类 | 008–019（12 章） | 总览 + SMA、EMA、WMA、DEMA、ZLEMA、DMA、BBI、MACD、DMI、ADX、SAR |
| 04 震荡类 | 020–028（9 章） | 总览 + RSI、KDJ、CCI、WPR、ROC、CMO、DPO、SMI |
| 05 波动率类 | 029–034（6 章） | 总览 + ATR、HV、BBands、Keltner、Envelope |
| 06 量价类 | 035–039（5 章） | 总览 + OBV、CMF、VO、EVWMA |

每个模块的总览章末尾有一张「检验结果对照表」，把本类各指标的拆解维度、截面能力、择时能力、推荐搭档并排放在一起。

### 模块 07 · 跨类组合（040，1 章）

把四类特征放在一起做跨类别组合，判定组合是否带来增益，以及增益属于信息互补、风险分散还是样本内拟合。

### 模块 08 · 机器学习挖掘与融合（041–048，8 章）

处理人工特征与线性加权触及的三个天花板：特征交互、权重自适应、特征充分性。

| 章 | 标题 |
|---|---|
| 041 | 第四部分导言：机器学习能做什么 |
| 042 | 特征挖掘：从人工构造到自动生成 |
| 043 | 树模型：捕捉非线性与特征交互 |
| 044 | 序列模型：时间结构的建模 |
| 045 | 状态模型：市场状态与自适应 |
| 046 | 因子融合：把多个模型与多类特征合成一个信号 |
| 047 | 稳健性：过拟合识别与模型衰减 |
| 048 | 端到端案例：从指标到可交易信号 |

### 模块 09 · 附录（049–054，6 章）

| 章 | 标题 |
|---|---|
| 049 | 附录 A：全书 AI 引导词索引 |
| 050 | 附录 B：公式速查表 |
| 051 | 附录 C：术语表 |
| 052 | 附录 D：关键数字的读法 |
| 053 | 附录 E：待核清单与数据说明 |
| 054 | 参考文献 |

## 指标章十二节

模块 03 至 06 的 28 个指标章，严格按以下顺序（标题用 `##`）：

| 段落 | 要求 |
|------|------|
| `## 名称与来历` | 中文全称、英文全称、缩写；提出者姓名与年份；当时的原始动机 |
| `## 核心逻辑` | 它测量什么，为什么这样测量有意义 |
| `## 计算公式` | 分步推导 + 参数含义表 + 数值算例 |
| `## 用法与信号` | 3–4 个信号形态 |
| `## 边界与误区` | 4 条失效条件与误用 |
| `## 它被检验过吗` | 该指标有没有被单独检验过；绝大多数没有，如实写明 |
| `## 代码实现` | `### R` + `### Python` 各一份完整实现 |
| `## 拆解` | 拆成 3–5 个无量纲特征（表格），说明各自量纲与经济含义；配 `### R` + `### Python` 展示计算 |
| `## 截面选股能力` | 构造式、符号方向、预期表现、检验注意；配 `### R` + `### Python` |
| `## 择时能力` | 时序逻辑、方法选择理由、关键陷阱；配 `### R` + `### Python` |
| `## 组合使用与验证` | 搭档、组合的截面验证与择时验证、增益判读；`### R` 与 `### Python` 下各两个代码块 |
| `## AI 引导词` | 3 条具体研究任务 |

每章共 **6 组 R + 6 组 Python**，合计 231 组，两两配对。

---

## 代码库（`code/`）

全部代码从书稿自动提取，与书中内容严格一致。改代码请改 Markdown 源稿，再重新运行 `scripts/extract_code.py`。

```
code/
├── README.md          # 索引表：每章的文件名、代码块数、依赖
├── R/
│   ├── 00-common.R    # 第 039 章的 7 个公共函数
│   ├── 00-data.R      # 示例数据准备
│   └── 007-*.R … 052-*.R   # 43 个章节文件
└── python/
    ├── 00-common.py
    ├── 00-data.py
    └── 007-*.py … 052-*.py
```

**公共函数**（第 039 章定义，检验类章节共用）：

| 函数 | 作用 |
|---|---|
| `cross_section_ic(panel, factor, ret)` | 横截面 IC 序列（Spearman），返回带日期名的数值向量 |
| `ic_summary(ic)` | IC 均值、标准差、ICIR、t 统计量、IC 大于零比例 |
| `layered_returns(panel, factor, ret, q)` | 分层回测各组均收益与单调性 |
| `timing_signal_test(df, factor, ret, upper)` | 触发日与非触发日的收益差异检验 |
| `conditional_quantile_return(df, factor, ret, q)` | 条件分位收益 |
| `timing_backtest(df, factor, ret, entry_q)` | 择时策略与买入持有的对照 |
| `combined_signal(panel, cols, weights)` | 横截面标准化后加权合成 |

**运行方式**：

```r
setwd("code")
source("R/00-common.R")
source("R/00-data.R")            # 生成 panel
source("R/007-简单移动平均线（SMA）.R")
```

```python
import os
os.chdir("code/python")
exec(open("00-common.py").read())
exec(open("00-data.py").read())   # 生成 panel
exec(open("007-简单移动平均线（SMA）.py").read())
```

**依赖**：

| 语言 | 包 |
|---|---|
| R | `quantmod` `TTR` `xts` `dplyr` `zoo`；建模章另需 `xgboost` `ranger` `glmnet` `depmixS4`；序列模型用 `keras3`（需 `keras3::install_keras()`） |
| Python | `pandas` `numpy` `scipy` `yfinance` `matplotlib`；建模章另需 `scikit-learn` `xgboost` `lightgbm` `torch` `hmmlearn` |

**三点要注意**：

1. 示例数据只有 5 只标的、约两年半的区间，只够验证流程跑通。真实横截面研究需 50 只以上标的、更长区间，并做行业中性化。
2. R 与 Python 的 Wilder 平滑口径不同（TTR 默认 `alpha = 2/(n+1)`，Python 手写用 `alpha = 1/n`），两边数值不会逐点对齐，这是口径差异而非错误。
3. 波动率类（ATR、HV、BBands、Keltner）同时构造收益目标与波动率目标两套列，不要放进同一张表比较。

---

## AI 引导词写法

源稿里用 fenced div 标记，编译时转成带标签的卡片：

```markdown
::: prompt 引导词 1：参数敏感性检验

我在研究简单移动平均线（SMA）作为趋势因子。请帮我设计……

:::
```

规则：`::: prompt <标签>` 开头，正文与标签之间空一行，`:::` 单独一行收尾。相邻块之间要留空行。

---

## 写作规范

### 语言

- 简洁、专业、有叙述感。句子短而直接，一句一个意思。
- 用**流畅段落**，非必要不用列表。表格与代码块除外。
- 人称用"投资者／交易者／研究者／读者"，不用"你"。
- 概率性表述优先（"通常""倾向于""大概率"），避免绝对化断言。

### 禁用

| 类别 | 示例 |
|------|------|
| 营销用语 | 堪称、神器、必备工具、顶尖、令人惊叹、独辟蹊径 |
| 过度比喻 | 堆叠三层比喻 |
| 夸大断言 | 覆盖 90% 场景、新手可直接套用、100% 有效 |
| 绝对化 | 一定、必须、永远、必然、保证 |
| 中文破折号 | `——`，用逗号或冒号替代 |
| 标题中符号 | `+`、`-`，用中文描述（"正向 DI"而非"+DI"） |

### 格式

- 加粗：首次出现的关键术语与信号名称。
- 引号：中文双引号用于比喻性称呼，反引号用于代码与包名。
- 每个文件**只有一个一级标题**（章标题），其余用 `##` / `###`。标题**不手写编号**（章号由文件名与阅读器呈现）。
- 行间公式用 `$$...$$` 独占一段；编译时会被保护，不会与 Markdown 的强调符号冲突。
- 代码块内注释用中文，变量名 `snake_case`。

---

## 代码约定

### R

依赖：`quantmod`（指标与绘图接口）、`TTR`（指标计算）、`xts`（时间序列）、`dplyr`、`zoo`（滚动统计）。数据不通过 `quantmod` 获取，改由本地 CSV 构造 `xts` 对象。

六步结构，每步一个注释块：

```r
# 1. 加载包
# 2. 获取数据
# 3. 计算指标
# 4. 识别信号
# 5. 绘图
# 6. 输出统计
```

数据一律读本地 `data/parquet/`，不联网。R 侧读同内容的 CSV（`panel_blue_chip.csv`），用 `xts` 转成时间序列后交给 `quantmod` 与 `TTR`，绘图 `chartSeries(..., theme = "white")`。

### Python

指标计算层：`pandas`、`numpy`、`scipy`、`matplotlib`。**只用这些**，不依赖 `ta` / `pandas_ta` / `talib`，也不依赖 `yfinance`（数据已在本地）。

机器学习层追加：`scikit-learn`、`xgboost`、`lightgbm`、`torch`（或 `tensorflow`）、`hmmlearn`。

含绘图的代码块开头必须有中文字体设置：

```python
import matplotlib
matplotlib.rcParams["font.sans-serif"] = ["PingFang SC", "SimHei", "Arial Unicode MS"]
matplotlib.rcParams["axes.unicode_minus"] = False
```

### 示例数据

5 只 A 股蓝筹：`600519.SS` 贵州茅台、`600036.SS` 招商银行、`601318.SS` 中国平安、`300750.SZ` 宁德时代、`000858.SZ` 五粮液。区间 `2023-01-01` 至 `2025-06-01`，对应 `data/parquet/panel_blue_chip`。

**每次给代码都要提醒**：这 5 只只够验证流程跑通。真实横截面研究请改用 `data/parquet/panel.parquet`（287 只），或自行扩充到 50 只以上并做行业中性处理。

---

## 目录结构

```
quant-technical-analysis/
├── README.md                      # 本文档
├── LICENSE                        # 正文与代码分别授权
├── 模块01-技术分析总论/            # 001–005，5 章
├── 模块02-因子检验方法/            # 006–007，2 章（方法论前置）
├── 模块03-趋势类指标/              # 008–019，12 章
├── 模块04-震荡类指标/              # 020–028，9 章
├── 模块05-波动率类指标/            # 029–034，6 章
├── 模块06-量价类指标/              # 035–039，5 章
├── 模块07-跨类组合/               # 040，1 章
├── 模块08-机器学习挖掘与融合/       # 041–048，8 章
├── 模块09-附录/                   # 049–054，6 章
├── 电子书/
│   └── build_ebook.py             # 编译脚本
├── docs/
│   └── index.html                 # 电子书成品，GitHub Pages 入口
├── scripts/
│   ├── export_from_db.R           # MySQL → data/staging/
│   ├── csv_to_parquet.py          # staging → data/parquet/（含清洗与派生）
│   ├── switch_to_local_data.py    # 一次性迁移：联网抓取 → 读本地
│   ├── audit_content.py           # 九维框架逐章审计
│   ├── rmd_to_markdown.py         # 一次性迁移：Rmd → Markdown
│   └── extract_code.py            # 代码提取：Markdown → code/
├── code/
│   ├── README.md                  # 代码索引
│   ├── R/                         # 39 个 .R 文件
│   └── python/                    # 39 个 .py 文件
├── data/
│   ├── README.md                  # 字段、口径、复现方式
│   └── parquet/                   # 书中全部示例数据
└── assets/                        # 图片等素材
```

`.gitignore` 排除了几类不入库的内容：`data/staging/`（导出中间件，可重建）、`电子书/*.html`（与 `docs/` 重复）、`.Renviron`（数据库凭据）、`__pycache__`、`.DS_Store`、`Rplots.pdf`。

### 命名约定

- 模块目录：`模块NN-模块名/`（两位数字，便于排序）
- 章节文件：`第NNN章-章标题.md`（三位数字，跨模块连续编号）
- 模块说明：`模块NN-模块名/_module.md`（第一行标题，第二段说明，供编译脚本读取）
- 代码文件：`NNN-章标题.R` / `.py`（与章节编号对应，`00-` 前缀为公共文件）
- 编号从 001 连续到 054，**改动章节顺序需同步改文件名、首行章号、正文里的交叉引用**（当前有 100 余处「第 NNN 章」引用）

---

## 双语代码的对应关系

全书 231 组 R/Python 代码遵循同一套配对规则：

| 位置 | 代码分布 |
|---|---|
| 指标章的六处 | 代码实现、拆解、截面选股能力、择时能力、组合使用与验证（两块），每处一对 |
| 方法章（模块 02、07、08） | 每段 Python 后紧跟功能等价的 R 块 |

两侧的因子列名、函数名、参数值保持一致，只有语法不同。差异集中在四处：Wilder 平滑系数、深度学习框架（PyTorch 对 `keras3`）、中文字体设置、MAD 的常数因子（R 的 `mad()` 默认乘 1.4826，书中统一用 `constant = 1` 与 Python 对齐）。

---

## 与旧版的关系

早期用 R Markdown + bookdown 写过一版，全部内容已迁移到本 Markdown 版，旧源文件留在本地归档，不入库。新稿不再依赖 R 环境，只需 Python 与 `markdown` 包就能编译。

---

## 授权

正文与图表采用 **CC BY-NC-SA 4.0**（署名-非商业-相同方式共享），代码采用 **MIT**。出版、付费课程、商业培训等商业用途需另行取得授权。详见 [LICENSE](LICENSE)。

## 关于准确性

书中的判读全部是方法层面的：在什么条件下该看什么、看到什么算通过、通过之后还要防什么。全书只有一组实测数字，在附录 E，证明的是样本量如何决定结论能不能下，不是某个因子能赚钱。

数据区间截至 2025 年 6 月。市场结构在变化，任何关于「当前有效」的判断都应加上时间限定，并在新数据上重做一遍。所有内容不构成投资建议。
