#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 chapters/*.Rmd 转换为模块目录下的纯 Markdown 书稿。

一次性的迁移脚本，迁移完成后可保留作记录。

用法：
    python3 scripts/rmd_to_markdown.py
"""

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = ROOT / "chapters"
DST = ROOT

# 模块定义：(模块号, 模块名, 模块说明, [(源文件, 章标题关键词)])
MODULES = [
    (
        1, "技术分析总论",
        "技术分析从何处来，解决了什么问题，有哪些主要流派，这些流派共享什么假设、各自有什么局限。",
        ["01-what-is-technical-analysis", "02-history", "03-methods",
         "04-critique-and-quant", "05-indicator-taxonomy"],
    ),
    (
        2, "趋势类指标",
        "通过平滑价格提取方向。含总览与 11 个指标：SMA、EMA、WMA、DEMA、ZLEMA、DMA、BBI、MACD、DMI、ADX、SAR。",
        ["10-trend-overview", "11-sma", "12-ema", "13-wma", "14-dema",
         "15-zlema", "16-dma", "17-bbi", "18-macd", "19-dmi", "20-adx", "21-sar"],
    ),
    (
        3, "震荡类指标",
        "把价格位置或力量对比标准化到有界刻度。含总览与 8 个指标：RSI、KDJ、CCI、WPR、ROC、CMO、DPO、SMI。",
        ["30-oscillator-overview", "31-rsi", "32-kdj", "33-cci", "34-wpr",
         "35-roc", "36-cmo", "37-dpo", "38-smi"],
    ),
    (
        4, "波动率类指标",
        "度量价格的离散程度，不带方向。含总览与 5 个指标：ATR、HV、布林带、肯特纳通道、价格包络线。",
        ["40-volatility-overview", "41-atr", "42-hv", "43-bbands", "44-keltner", "45-envelope"],
    ),
    (
        5, "量价类指标",
        "把成交量与价格变化结合，刻画资金流向。含总览与 4 个指标：OBV、CMF、VO、EVWMA。",
        ["50-volume-overview", "51-obv", "52-cmf", "53-vo", "54-evwma"],
    ),
    (
        6, "因子检验方法",
        "以单个指标为单位做检验的统一方法论：先拆解成特征，再检验截面选股能力与择时能力。",
        ["56-part3-overview", "57-dual-test-methodology"],
    ),
    (
        7, "逐指标因子检验",
        "按四步流程把 28 个指标逐个检验一遍，最后做跨类别组合的量化验证。",
        ["60-trend-tests", "65-oscillator-tests", "70-volatility-tests",
         "75-volume-tests", "78-combination-tests"],
    ),
    (
        8, "机器学习挖掘与融合",
        "用机器学习处理人工特征与线性加权触及的三个天花板：特征交互、权重自适应、特征充分性。",
        ["80-ml-overview", "81-feature-mining", "82-tree-models", "83-sequence-models",
         "84-state-models", "85-factor-fusion", "86-robustness", "87-end-to-end-case"],
    ),
    (
        9, "附录",
        "全书 AI 引导词索引、公式速查表与参考文献。",
        ["90-appendix-prompts", "91-appendix-formulas", "99-references"],
    ),
]

# 引导词容器 -> 简洁的 ::: prompt 块
PROMPT_RE = re.compile(
    r"^::::: ai-prompt\s*\n"
    r"::: ai-prompt-label\s*\n"
    r"(.+?)\s*\n"
    r":::\s*\n"
    r"\n"
    r"(.*?)\n"
    r":::::\s*$",
    re.S | re.M,
)

FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n", re.S)
ANCHOR_RE = re.compile(r"\s*\{#[^}]*\}\s*")
FENCE_RE = re.compile(r"^```\{(r|python)[^}]*\}\s*$", re.M)


def clean_title(raw_title: str) -> str:
    """去掉标题里的锚点，去掉"附录 X：""这类前缀之外的编号。"""
    t = ANCHOR_RE.sub("", raw_title).strip()
    return t


def convert(text: str) -> str:
    """Rmd 正文 -> 纯 Markdown。"""
    text = FRONTMATTER_RE.sub("", text, count=1)
    text = PROMPT_RE.sub(lambda m: "::: prompt %s\n\n%s\n\n:::" % (
        m.group(1).strip(), m.group(2).strip()), text)
    text = FENCE_RE.sub(lambda m: "```" + m.group(1), text)
    return text.strip() + "\n"


def main():
    total = 0
    chapter_no = 0
    lines_out = []

    for mod_no, mod_name, mod_desc, files in MODULES:
        mod_dir = DST / ("模块%02d-%s" % (mod_no, mod_name))
        mod_dir.mkdir(exist_ok=True)
        lines_out.append("模块 %02d %s：%d 章" % (mod_no, mod_name, len(files)))

        for stem in files:
            src = SRC / (stem + ".Rmd")
            if not src.exists():
                raise SystemExit("缺少源文件：%s" % src)
            chapter_no += 1
            raw = src.read_text(encoding="utf-8")
            body = convert(raw)

            # 从正文的一级标题里取章标题
            m = re.search(r"^#\s+(.+)$", body, re.M)
            title = clean_title(m.group(1)) if m else stem
            # 正文的一级标题替换为带章号的标题
            body = re.sub(
                r"^#\s+.+$",
                "# 第%03d章 %s" % (chapter_no, title),
                body, count=1, flags=re.M,
            )

            safe = re.sub(r"[/\\:*?\"<>|]", "·", title)
            out = mod_dir / ("第%03d章-%s.md" % (chapter_no, safe))
            out.write_text(body, encoding="utf-8")
            total += 1

        # 模块说明写入 _module.md，供编译脚本读取
        (mod_dir / "_module.md").write_text(
            "# 模块%02d %s\n\n%s\n" % (mod_no, mod_name, mod_desc), encoding="utf-8")

    print("\n".join(lines_out))
    print("---")
    print("共转换 %d 章" % total)


if __name__ == "__main__":
    main()
