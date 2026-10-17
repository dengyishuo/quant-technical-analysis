#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 anything2explainer 的调研九维框架，对全书做结构化审计。

输出：
  - 控制台汇总
  - 内容审计报告.md（逐章矩阵 + 缺口清单 + 可执行修改建议）

用法：python3 scripts/audit_content.py
"""

from __future__ import annotations

import pathlib
import re
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "内容审计报告.md"

# ---------------- 九维判定规则 ----------------

RE_YEAR = re.compile(r"(?:19|20)\d{2}\s*年")
RE_ORIGIN_VERB = re.compile(r"提出|发明|发表|首次|源于|来自|问世|创立|引入")
RE_ORIGIN_NAME = re.compile(r"(?:由|为)\s*[A-Z][A-Za-z\.\- ]{2,30}(?:于|在)?\s*(?:19|20)\d{2}")

RE_HEAD_PROBLEM = re.compile(r"^##+\s*(?:要解决的问题|为什么|问题)", re.M)
RE_SITUATION = re.compile(
    r"遇到|面对|困境|误以为|以为|常常|往往以为|看上去|直觉上|问题在于|麻烦|痛点|处境"
)
# 新增的结构标记（本轮优化引入）
RE_HEAD_TESTED = re.compile(r"^##+\s*它被检验过吗", re.M)
RE_HEAD_CASE = re.compile(r"^##+\s*真实案例与失败模式", re.M)
RE_HEAD_TERMS = re.compile(r"术语表", re.M)
# 情境段的场景标记：人物 + 动作
RE_SCENE = re.compile(
    r"(?:一位|一个|两名|一名)[^，。]{0,6}(?:交易者|投资者|研究者|分析师|基金经理)"
    r"|收盘后|复盘|盯着|翻开|写下|问自己"
)

RE_HEAD_BOUNDARY = re.compile(r"^##+\s*(?:边界与误区|边界|局限|适用范围)", re.M)
RE_CONTRAST = re.compile(r"区别|差异在于|不同于|容易混淆|不要与|区别于")
RE_HEAD_COMPARE = re.compile(r"^##+\s*.*(?:对比|对照)", re.M)

RE_DISPUTE = re.compile(r"争议|批评|质疑|被证伪|学术研究|实证研究|反例|失效的|不成立的")
RE_RECENT = re.compile(r"近年|最近|2024|2025|2026")

RE_CASE = re.compile(r"案例|实例|真实发生|历史上|典型事件")
RE_CASE_PROPER = re.compile(r"(?:19|20)\d{2}\s*年[^。；\n]{2,24}(?:危机|股灾|事件|崩盘|泡沫|违约|爆仓)")

RE_ANALOGY = re.compile(r"好比|就像|如同|相当于|可以想|打个比方|形象地说")
RE_HEAD_GLOSSARY = re.compile(r"^##+\s*.*术语", re.M)

RE_SENT_SPLIT = re.compile(r"[。！？；]")
RE_URL = re.compile(r"https?://")
RE_PENDING = re.compile(r"待核|待考|未证实|存疑")

# 编造数值嫌疑：IC / ICIR / 夏普 附近 20 字内出现小数
RE_FAKE_IC = re.compile(
    r"(?<![A-Za-z])(?:IC|ICIR|夏普|Sharpe|胜率|年化)(?![A-Za-z])[^\n。，]{0,12}?"
    r"(?:=|为|约|达到|高于)\s*[-−]?\d+(?:\.\d+)?",
    re.I,
)


def split_body(text: str) -> tuple[str, str]:
    """返回 (一级标题行, 正文)。"""
    lines = text.split("\n")
    for i, ln in enumerate(lines):
        if ln.startswith("# "):
            return ln, "\n".join(lines[i + 1:])
    return "", text


def first_para(body: str) -> str:
    """第一个非标题、非空、非代码的段落。"""
    in_code = False
    buf = []
    for ln in body.split("\n"):
        if ln.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        s = ln.strip()
        if not s or s.startswith("#") or s.startswith("|") or s.startswith(">"):
            if buf:
                break
            continue
        buf.append(s)
        if len("".join(buf)) > 120:
            break
    return "".join(buf)


def opening_kind(p: str) -> str:
    """判定开篇类型：定义式 / 处境式 / 其他。"""
    head = p[:60]
    if RE_SCENE.search(p[:200]) or RE_SITUATION.search(p[:160]):
        return "处境式"
    if re.match(r"^[^，。]{2,20}(?:（[^）]*）)?\s*(?:是|指|定义为|的全称)", head):
        return "定义式"
    return "其他"


def prose_only(text: str) -> str:
    """去掉代码块、公式块、行内公式、表格与列表，只留正文段落。"""
    t = re.sub(r"^```.*?^```", "", text, flags=re.S | re.M)
    t = re.sub(r"^\$\$.*?^\$\$", "", t, flags=re.S | re.M)
    t = re.sub(r"\$[^$\n]+\$", "", t)
    keep = []
    for ln in t.split("\n"):
        s = ln.lstrip()
        if not s:
            continue
        if s.startswith(("#", "|", ">", "::", "-", "!", "1.", "2.", "3.")):
            continue
        keep.append(ln)
    return "\n".join(keep)


def audit_file(f: pathlib.Path) -> dict:
    text = f.read_text(encoding="utf-8")
    h1, body = split_body(text)
    paras = [p for p in re.split(r"\n\s*\n", body) if p.strip() and not p.strip().startswith(("```", "|", "#"))]
    sents = [s for s in RE_SENT_SPLIT.split(prose_only(body)) if len(s.strip()) >= 8]
    long_sents = [s for s in sents if len(s) > 60]
    avg_len = sum(len(s) for s in sents) / max(len(sents), 1)

    nums_pct = len(re.findall(r"\d+(?:\.\d+)?\s*%", body))
    nums_all = len(re.findall(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])", body))
    # 排除教学性数值：带「示意 / 假设 / 例如」等标记的行不算嫌疑
    EXEMPT = re.compile(r"示意|假设|假如|例如|举例|我算出来|设 ")
    fake_ic = []
    for ln in body.split("\n"):
        if EXEMPT.search(ln):
            continue
        fake_ic += RE_FAKE_IC.findall(ln)

    d = {
        "file": f.name,
        "module": f.parent.name,
        "words": len(text),
        "h2": len(re.findall(r"^## ", text, re.M)),
        "paras": len(paras),
        "avg_sent": round(avg_len, 1),
        "long_ratio": round(len(long_sents) / max(len(sents), 1), 2),
        "opening": opening_kind(first_para(body)),
        # 九维
        "d_problem": bool(
            RE_HEAD_PROBLEM.search(text)
            or RE_SCENE.search(first_para(body)[:200])
            or RE_SITUATION.search(first_para(body)[:200])
        ),
        "d_origin": bool(RE_YEAR.search(body) and RE_ORIGIN_VERB.search(body)),
        "d_origin_name": bool(RE_ORIGIN_NAME.search(body)),
        "d_mechanism": bool(re.search(r"^##+\s*(?:计算公式|方法细节|核心思想|它怎么运作)", text, re.M)),
        "d_boundary": bool(RE_HEAD_BOUNDARY.search(text)),
        "d_contrast": bool(RE_CONTRAST.search(body) or RE_HEAD_COMPARE.search(text)),
        "d_dispute": bool(RE_HEAD_TESTED.search(text) or RE_DISPUTE.search(body)),
        "d_recent": bool(RE_RECENT.search(body)),
        # 只认独立小节；交叉引用（"见第 8 章的案例"）不算覆盖
        "d_case": bool(RE_HEAD_CASE.search(text)),
        "d_analogy": len(RE_ANALOGY.findall(body)),
        "d_glossary": bool(RE_HEAD_TERMS.search(text)),
        "nums_pct": nums_pct,
        "fake_ic": fake_ic,
        "urls": len(RE_URL.findall(body)),
        "pending": len(RE_PENDING.findall(body)),
    }
    return d


def is_appendix(row: dict) -> bool:
    m = re.match(r"^第(\d+)章", row["file"])
    return bool(m and int(m.group(1)) >= 49)


def main() -> None:
    files = sorted(ROOT.glob("模块*/第*.md"))
    rows = [audit_file(f) for f in files]
    body_rows = [r for r in rows if not is_appendix(r)]
    app_rows = [r for r in rows if is_appendix(r)]

    # ---------- 汇总 ----------
    total_words = sum(r["words"] for r in rows)
    dims = {
        "D1 处境与问题": "d_problem",
        "D2 起源与关键节点": "d_origin",
        "D3 运作方式": "d_mechanism",
        "D4 边界与对比": "d_boundary",
        "D5 争议与局限": "d_dispute",
        "D6 真实案例与失败模式": "d_case",
        "D7 类比": "d_analogy",
    }

    print("=" * 74)
    print("全书审计：%d 章，%d 字（内容章 %d，附录 %d）"
          % (len(rows), total_words, len(body_rows), len(app_rows)))
    print("=" * 74)
    print("%-26s %-10s %s" % ("维度", "内容章覆盖", "缺失章数"))
    for label, key in dims.items():
        if key == "d_analogy":
            hit = sum(1 for r in body_rows if r[key] > 0)
        else:
            hit = sum(1 for r in body_rows if r[key])
        print("%-26s %2d/%d      %d" % (label, hit, len(body_rows), len(body_rows) - hit))
    gloss = [r["file"] for r in rows if r["d_glossary"]]
    print("%-26s %s" % ("D8 术语表（全书）", "有：" + gloss[0] if gloss else "缺"))

    print()
    print("开篇类型分布：", Counter(r["opening"] for r in body_rows).most_common())
    print("行内出处（URL）：", sum(r["urls"] for r in rows))
    print("待核标记：", sum(r["pending"] for r in rows))
    print("编造数值嫌疑（IC/夏普附近带小数）：", sum(len(r["fake_ic"]) for r in rows))
    print("平均句长中位数：", sorted(r["avg_sent"] for r in body_rows)[len(body_rows) // 2], "字")
    print("长句占比中位数：", sorted(r["long_ratio"] for r in body_rows)[len(body_rows) // 2])

    # ---------- 报告 ----------
    lines = []
    A = lines.append
    A("# 内容审计报告")
    A("")
    A("按 `anything2explainer` 的调研简报骨架（执行摘要 / 处境与问题 / 起源与关键节点 / 运作方式 /")
    A("边界与对比 / 争议与局限 / 真实案例与失败模式 / 数字与比喻清单 / 术语表 / 待核清单）")
    A("对全书逐章扫描。判定为关键词与结构信号，属机械筛查，语义质量需人工复核。")
    A("")
    A("## 零、这份报告怎么读")
    A("")
    A("三件事先说明，否则数字会被误读。")
    A("")
    A("**判定是机械的。** D1 到 D7 靠标题结构与关键词识别，没有语义判断能力。例如「边界与对比」只认")
    A("`## 边界与误区` 这类标题，而机器学习各章的「树模型与神经网络的取舍」「三级融合」其实承担了")
    A("同样的功能，却被记为缺失。表格给的是下限，不是评分。")
    A("")
    A("**D6 只认独立小节。** 指标章末尾有「这一类的真实失效案例，见第 008 章」这类交叉引用，")
    A("不算覆盖。案例集中在 5 节里讲（4 个类别总览加机器学习导言），不在 28 个指标章各写一遍：")
    A("同一事件重复出现会让读者跳过，案例分析的价值在事件与机制的对应，不在覆盖章数。")
    A("")
    A("**D7 同理。** 比喻只在能推出可检验结论时才写，没有按章节铺开。一个推不出东西的比喻，")
    A("比没有比喻更糟。")
    A("")
    A("框架本身允许按题材取舍。原始简报写明「小节按题材取舍，不必每节都有，但 0 / 6 / 7 / 8 必须有」，")
    A("其中 0 是执行摘要（对应全书前言），6 是真实案例，7 是数字与比喻清单，8 是术语表。")
    A("")
    A("## 一、总体")
    A("")
    A("- 章节：%d" % len(rows))
    A("- 字数：%s" % format(total_words, ","))
    A("- 行内出处：%d 条" % sum(r["urls"] for r in rows))
    A("- 待核标记：%d 处" % sum(r["pending"] for r in rows))
    A("")
    A("| 维度 | 内容章覆盖 | 缺失 | 判定方式 |")
    A("|---|---|---|---|")
    for label, key in dims.items():
        if key == "d_analogy":
            hit = sum(1 for r in body_rows if r[key] > 0)
            how = "比喻词计数"
        else:
            hit = sum(1 for r in body_rows if r[key])
            how = "结构或关键词"
        A("| %s | %d/%d | %d | %s |" % (label, hit, len(body_rows), len(body_rows) - hit, how))
    A("| D8 术语表 | %d/%d | %d | 章标题含「术语表」 |"
      % (len(gloss), len(rows), len(rows) - len(gloss)))
    A("")
    A("附录章（049 至 054）不计入 D1 至 D7 的分母：框架允许按题材取舍小节，附录不承担处境与案例。")
    A("")
    A("## 二、逐章矩阵")
    A("")
    A("列说明：处=处境/问题，起=起源，机=机制，界=边界，比=对比，争=争议，案=案例，喻=比喻数，%数=百分数个数，疑=数值嫌疑。")
    A("")
    A("| 章 | 字数 | 开篇 | 处 | 起 | 机 | 界 | 比 | 争 | 案 | 喻 | %数 | 疑 |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        name = re.sub(r"^第(\d+)章-", r"\1 ", r["file"].replace(".md", ""))
        A("| %s | %d | %s | %s | %s | %s | %s | %s | %s | %s | %d | %d | %d |" % (
            name, r["words"], r["opening"],
            *["●" if r[k] else "·" for k in
              ("d_problem", "d_origin", "d_mechanism", "d_boundary", "d_contrast", "d_dispute", "d_case")],
            r["d_analogy"], r["nums_pct"], len(r["fake_ic"])))
    A("")
    A("## 三、缺口清单")
    A("")
    for label, key in dims.items():
        miss = [r for r in body_rows if (r[key] == 0 if key == "d_analogy" else not r[key])]
        if not miss:
            continue
        A("### 缺 %s（%d 章）" % (label, len(miss)))
        A("")
        A("、".join(re.sub(r"^第(\d+)章-", r"\1 ", m["file"].replace(".md", "")) for m in miss))
        A("")
    # 数值嫌疑明细
    sus = [(r["file"], v) for r in rows for v in r["fake_ic"]]
    A("### 数值嫌疑明细")
    A("")
    if sus:
        for f, v in sus[:60]:
            A("- `%s`：`%s`" % (f, v))
    else:
        A("无。")
    A("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print()
    print("报告已写入：", OUT)


if __name__ == "__main__":
    main()
