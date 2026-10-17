#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 Markdown 书稿中提取代码块，生成可直接运行的 R 与 Python 文件。

用法：
    python3 scripts/extract_code.py

产物：
    code/R/          R 代码（按章聚合，附公共函数与数据准备）
    code/python/     Python 代码（同上）
    code/README.md   索引与运行说明
"""

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "code"

MODULE_DIR_RE = re.compile(r"^模块\s*(\d+)\s*[-—－]\s*(.+)$")
CHAPTER_FILE_RE = re.compile(r"^第\s*(\d+)\s*章\s*[-—－]\s*(.+)\.md$")
H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.M)
H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.M)

# 公共函数与数据准备所在的章
COMMON_CHAPTER = 7

# 需要提示"先加载公共函数"的章（检验类与建模类）
# 需要提示"先加载公共函数"的章：04x 检验四段、07x 跨类组合、08x 机器学习的后半段
# 指标章（009–039）的检验代码同样依赖公共函数，也一并提示
DEPENDS_COMMON = set(range(9, 40)) | {40, 42, 43, 44, 45, 46, 47, 48}

PY_HEADER = """\
# ============================================================
# {title}
# 模块 {mod_no:02d} {mod_name}
# 源文件：{src}
# ============================================================
# 本文件由 scripts/extract_code.py 自动生成，请勿直接编辑。
# 修改代码请改 Markdown 源稿，再重新运行提取脚本。
{depends}# ------------------------------------------------------------
"""

R_HEADER = """\
# ============================================================
# {title}
# 模块 {mod_no:02d} {mod_name}
# 源文件：{src}
# ============================================================
# 本文件由 scripts/extract_code.py 自动生成，请勿直接编辑。
# 修改代码请改 Markdown 源稿，再重新运行提取脚本。
{depends}# ------------------------------------------------------------
"""

DEPENDS_R = """\
#
# 依赖：先加载同目录下的公共函数与数据准备
#   source("code/R/00-common.R")
#   source("code/R/00-data.R")
#
"""

DEPENDS_PY = """\
#
# 依赖：先加载同目录下的公共函数与数据准备
#   exec(open("code/python/00-common.py").read())
#   exec(open("code/python/00-data.py").read())
#
"""


def collect(path: Path):
    """从一章的 Markdown 中提取 (语言, 代码, 所属小节标题) 列表。"""
    text = path.read_text(encoding="utf-8")
    blocks = []
    # 记录每个代码块之前最近的 ## 标题，作为用途说明
    marks = [(m.start(), m.group(1).strip()) for m in H2_RE.finditer(text)]
    for m in re.finditer(r"^```(r|python)\s*$(.*?)^```\s*$", text, re.S | re.M):
        lang, body = m.group(1), m.group(2)
        # 归属小节
        section = ""
        for pos, title in marks:
            if pos < m.start():
                section = title
            else:
                break
        blocks.append((lang, body.strip("\n"), section))
    return blocks


def slug(title: str) -> str:
    """标题 -> 文件名安全片段。"""
    t = title.strip()
    t = re.sub(r"^第\s*\d+\s*章\s*", "", t)
    t = re.sub(r"[/\\:*?\"<>|\s]+", "-", t)
    t = re.sub(r"-{2,}", "-", t).strip("-")
    return t or "chapter"


def main():
    (OUT / "R").mkdir(parents=True, exist_ok=True)
    (OUT / "python").mkdir(parents=True, exist_ok=True)

    # 清理上次生成的代码文件，避免章节重编号后留下旧文件
    stale = []
    for sub, suffix in (("R", "*.R"), ("python", "*.py")):
        for f in (OUT / sub).glob(suffix):
            f.unlink()
            stale.append(f.name)
    if stale:
        print("清理旧文件：%d 个" % len(stale))

    index = []           # (章号, 标题, 模块号, 模块名, R 块数, Py 块数, R 文件名, Py 文件名)

    for mod_dir in sorted(ROOT.glob("模块*")):
        m = MODULE_DIR_RE.match(mod_dir.name)
        if not m or not mod_dir.is_dir():
            continue
        mod_no, mod_name = int(m.group(1)), m.group(2).strip()

        for f in sorted(mod_dir.glob("第*章-*.md")):
            hit = CHAPTER_FILE_RE.match(f.name)
            if not hit:
                continue
            no = int(hit.group(1))
            raw = f.read_text(encoding="utf-8")
            h1 = H1_RE.search(raw)
            title = h1.group(1).strip() if h1 else f.stem
            title = re.sub(r"^第\s*\d+\s*章\s*", "", title).strip()

            blocks = collect(f)
            r_blocks = [(c, s) for lang, c, s in blocks if lang == "r"]
            p_blocks = [(c, s) for lang, c, s in blocks if lang == "python"]

            stem = "%03d-%s" % (no, slug(title))
            rel = f.relative_to(ROOT).as_posix()

            write_file(OUT / "R", stem + ".R", r_blocks, "r",
                       no, title, mod_no, mod_name, rel)
            write_file(OUT / "python", stem + ".py", p_blocks, "python",
                       no, title, mod_no, mod_name, rel)

            # 公共函数与数据准备单独出文件
            if no == COMMON_CHAPTER:
                if r_blocks:
                    write_plain(OUT / "R" / "00-common.R",
                                r_blocks[0][0],
                                "第007章 定义的 R 公共函数（IC 汇总 / 分层回测 / 择时检验 / 组合合成）")
                if len(r_blocks) > 1:
                    write_plain(OUT / "R" / "00-data.R",
                                r_blocks[1][0],
                                "R 示例数据准备（5 只 A 股蓝筹面板，含因子与未来收益列）")
                if p_blocks:
                    write_plain(OUT / "python" / "00-common.py",
                                p_blocks[0][0],
                                "第007章 定义的 Python 公共函数（IC 汇总 / 分层回测 / 择时检验 / 组合合成）")
                if len(p_blocks) > 1:
                    write_plain(OUT / "python" / "00-data.py",
                                p_blocks[1][0],
                                "Python 示例数据准备（5 只 A 股蓝筹面板，含因子与未来收益列）")

            index.append((no, title, mod_no, mod_name,
                          len(r_blocks), len(p_blocks),
                          stem + ".R", stem + ".py"))

    write_readme(index)
    tot_r = sum(i[4] for i in index)
    tot_p = sum(i[5] for i in index)
    n_r_files = len(list((OUT / "R").glob("*.R")))
    n_p_files = len(list((OUT / "python").glob("*.py")))
    print("章数：%d   生成文件：R %d 个 / Python %d 个（块数 %d / %d）"
          % (len(index), n_r_files, n_p_files, tot_r, tot_p))
    print("输出目录：%s" % OUT)


def write_file(dirpath: Path, name: str, blocks, lang,
               no, title, mod_no, mod_name, src):
    if not blocks:
        return
    header_tpl = R_HEADER if lang == "r" else PY_HEADER
    depends = ""
    if no in DEPENDS_COMMON and blocks:
        depends = DEPENDS_R if lang == "r" else DEPENDS_PY
    comment = "#" if lang == "r" else "#"

    parts = [header_tpl.format(
        title="第%03d章 %s" % (no, title), mod_no=mod_no, mod_name=mod_name,
        src=src, depends=depends)]

    for i, (code, section) in enumerate(blocks, 1):
        label = section or "代码"
        parts.append("%s ---- 代码块 %d：%s ----" % (comment, i, label))
        parts.append("")
        parts.append(code.rstrip())
        parts.append("")

    path = dirpath / name
    path.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")


def write_plain(path: Path, code: str, desc: str):
    comment = "#"
    head = [
        "%s ============================================================" % comment,
        "%s %s" % (comment, desc),
        "%s" % comment,
        "%s 本文件由 scripts/extract_code.py 自动生成，请勿直接编辑。" % comment,
        "%s 修改代码请改 Markdown 源稿（模块02-因子检验方法/第007章），再重新运行提取脚本。" % comment,
        "%s ============================================================" % comment,
        "",
    ]
    path.write_text("\n".join(head) + code.rstrip() + "\n", encoding="utf-8")


def write_readme(index):
    lines = [
        "# 代码索引",
        "",
        "本书全部代码从 Markdown 书稿自动提取，按章聚合。修改代码请改源稿后重新运行：",
        "",
        "```bash",
        "python3 scripts/extract_code.py",
        "```",
        "",
        "## 公共文件",
        "",
        "| 文件 | 内容 |",
        "|---|---|",
        "| `R/00-common.R` | 第 007 章定义的 R 公共函数：`cross_section_ic`、`ic_summary`、`layered_returns`、`timing_signal_test`、`conditional_quantile_return`、`timing_backtest`、`combined_signal` |",
        "| `R/00-data.R` | R 示例数据准备：5 只 A 股蓝筹面板，含因子与未来收益列 |",
        "| `python/00-common.py` | 与 R 版功能等价的 Python 公共函数 |",
        "| `python/00-data.py` | Python 示例数据准备 |",
        "",
        "## 运行方式",
        "",
        "### R",
        "",
        "```r",
        'setwd("code")',
        'source("R/00-common.R")',
        'source("R/00-data.R")        # 生成 panel',
        'source("R/009-简单移动平均线（SMA）.R")',
        "```",
        "",
        "依赖：`quantmod`、`TTR`、`xts`、`dplyr`、`zoo`（`zoo` 是 `xts` 的依赖）。",
        "机器学习章节另需 `xgboost`、`ranger`、`depmixS4`、`glmnet`；",
        "序列模型章节的 R 版用 `keras3`，需先运行 `keras3::install_keras()` 安装 TensorFlow 后端。",
        "",
        "### Python",
        "",
        "```python",
        'import os',
        'os.chdir("code/python")',
        'exec(open("00-common.py").read())',
        'exec(open("00-data.py").read())     # 生成 panel',
        'exec(open("009-简单移动平均线（SMA）.py").read())',
        "```",
        "",
        "依赖：`pandas`、`numpy`、`scipy`、`yfinance`、`matplotlib`。",
        "机器学习章节另需 `scikit-learn`、`xgboost`、`lightgbm`、`torch`、`hmmlearn`。",
        "",
        "## 重要提醒",
        "",
        "- 示例数据只有 5 只标的、约两年半的区间，**只够验证流程能否跑通**。",
        "  真实的横截面研究需要 50 只以上标的、更长的历史区间，并做行业中性化处理。",
        "- 波动率类指标（ATR、HV）的检验目标不是未来收益，而是未来实现波动率，",
        "  代码中会同时构造收益目标与波动率目标两套列，不要放进同一张表比较。",
        "- R 与 Python 的 Wilder 平滑口径存在差异（R 侧 TTR 默认 `alpha = 2/(n+1)`，",
        "  Python 侧手写采用 `alpha = 1/n`），两边的数值不会逐点对齐，这是口径差异而非错误。",
        "",
        "## 章节代码清单",
        "",
        "| 章 | 标题 | 模块 | R | Python | 文件 |",
        "|---|---|---|---:|---:|---|",
    ]
    for no, title, mod_no, mod_name, nr, np_, rname, pname in index:
        cells = "%d" % nr if nr else "–"
        cellp = "%d" % np_ if np_ else "–"
        lines.append("| %03d | %s | %02d %s | %s | %s | `%s` / `%s` |"
                     % (no, title, mod_no, mod_name, cells, cellp, rname, pname))
    lines.append("")
    lines.append("总计：R %d 块，Python %d 块。"
                 % (sum(i[4] for i in index), sum(i[5] for i in index)))
    lines.append("")
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
