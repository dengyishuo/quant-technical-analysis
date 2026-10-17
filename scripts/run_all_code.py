#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把书稿里的 Python 代码块逐章跑一遍，保存图表与控制台输出。

设计要点：
- 同一章内的代码块按顺序在同一个命名空间里执行，模拟读者的实际运行顺序
  （后面的块依赖前面的 `panel`）。
- 拦掉 plt.show()，改成存文件。原代码里 plt.show() 只是为了让读者看图，
  这里把它转成 assets/figures/<章>/<块>_<序号>.png。
- 中文字体在 preamble 里先设好，避免图里出现方框。
- 每块单独超时，一块失败不影响后续块。

产出：
  assets/figures/            图片
  assets/run/manifest.json   每章每块的执行记录（状态、耗时、输出、图）
  assets/run/stdout/<章>.txt 完整控制台输出

用法：python3 scripts/run_all_code.py [--only 9,21,30] [--timeout 180]
"""

from __future__ import annotations

import argparse
import io
import json
import os
import pathlib
import re
import sys
import time
import traceback
import contextlib
import signal

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIG_DIR = ROOT / "assets" / "figures"
RUN_DIR = ROOT / "assets" / "run"

# 每章 preamble：只设置环境，不引入业务变量
PREAMBLE = r"""
import os, sys, math, json, warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
matplotlib.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti SC", "SimHei", "Arial Unicode MS"]
matplotlib.rcParams["axes.unicode_minus"] = False
matplotlib.rcParams["figure.dpi"] = 130
matplotlib.rcParams["savefig.dpi"] = 130
matplotlib.rcParams["figure.figsize"] = (9, 4.2)
matplotlib.rcParams["axes.grid"] = True
matplotlib.rcParams["grid.alpha"] = 0.25

_FIG = {"n": 0, "dir": None}

# 同一进程内反复读同一份 parquet 很慢，这里做一次读取缓存。
# 返回副本，避免被调用方就地修改后污染下一次读取。
import functools as _ft
_ORIG_READ = pd.read_parquet

@_ft.lru_cache(maxsize=8)
def _cached_read(path, *a, **k):
    return _ORIG_READ(path, *a, **k)

def _read_parquet(path, *a, **k):
    return _cached_read(str(path), *a, **k).copy()

pd.read_parquet = _read_parquet

def _save_show(*a, **k):
    # 把 plt.show() 换成落盘，文件名带自增序号
    if not plt.get_fignums():
        return
    _FIG["n"] += 1
    p = os.path.join(_FIG["dir"], "fig%02d.png" % _FIG["n"])
    fig = plt.gcf()
    fig.tight_layout()
    fig.savefig(p, bbox_inches="tight")
    plt.close("all")
    print("[图已保存] " + p)

plt.show = _save_show
"""


def split_blocks(text: str):
    """按围栏代码块切分，返回 [(lang, body, 起始行号)]。"""
    out = []
    for m in re.finditer(r"^```(\w*)[ \t]*\n(.*?)^```[ \t]*$", text, re.S | re.M):
        lang = m.group(1).lower()
        line_no = text[: m.start()].count("\n") + 2
        out.append((lang, m.group(2), line_no))
    return out


def section_of(text: str, line_no: int) -> str:
    """代码块属于哪个二级小节。"""
    cur = ""
    for m in re.finditer(r"^##\s+(.+)$", text, re.M):
        ln = text[: m.start()].count("\n") + 1
        if ln < line_no:
            cur = m.group(1).strip()
        else:
            break
    return cur


def run_chapter(path: pathlib.Path, timeout: int, verbose: bool):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"第(\d+)章", path.name)
    if not m:
        return None
    ch = int(m.group(1))

    fig_dir = FIG_DIR / ("ch%03d" % ch)
    fig_dir.mkdir(parents=True, exist_ok=True)
    for old in fig_dir.glob("*.png"):
        old.unlink()

    blocks = [(lang, body, ln) for lang, body, ln in split_blocks(text) if lang == "python"]
    if not blocks:
        return None

    ns = {"__name__": "__main__"}
    exec(compile(PREAMBLE, "<preamble>", "exec"), ns)
    ns["_FIG"]["dir"] = str(fig_dir)

    records = []
    buf_all = io.StringIO()

    for k, (lang, body, ln) in enumerate(blocks, 1):
        sec = section_of(text, ln)
        rec = {"block": k, "line": ln, "section": sec, "status": "ok",
               "seconds": 0.0, "stdout": "", "figures": [], "error": ""}
        buf = io.StringIO()
        t0 = time.time()

        class _Timeout(Exception):
            pass

        def _alarm(signum, frame):
            raise _Timeout("单块超过 %d 秒" % timeout)

        old_handler = signal.signal(signal.SIGALRM, _alarm)
        signal.alarm(timeout)
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                exec(compile(body, "<ch%d-b%d>" % (ch, k), "exec"), ns)
        except _Timeout as e:
            rec["status"] = "timeout"
            rec["error"] = str(e)
        except Exception as e:
            rec["status"] = "error"
            rec["error"] = "%s: %s" % (type(e).__name__, str(e)[:200])
            if verbose:
                rec["trace"] = traceback.format_exc()[-800:]
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
            # 块结束时若还有未 show 的图，也存下来
            if plt.get_fignums():
                try:
                    ns["plt"].show()
                except Exception:
                    plt.close("all")
        rec["seconds"] = round(time.time() - t0, 2)
        rec["stdout"] = buf.getvalue()[:4000]
        buf_all.write("\n===== 块 %d（第 %d 行，%s）=====\n" % (k, ln, sec))
        buf_all.write(rec["stdout"])
        if rec["status"] == "error":
            buf_all.write("[错误] %s\n" % rec["error"])
        rec["figures"] = sorted(p.name for p in fig_dir.glob("fig%02d.png" % k))

        records.append(rec)

    (RUN_DIR / "stdout").mkdir(parents=True, exist_ok=True)
    (RUN_DIR / "stdout" / ("ch%03d.txt" % ch)).write_text(buf_all.getvalue(), encoding="utf-8")

    n_fig = len(list(fig_dir.glob("*.png")))
    return {"ch": ch, "file": path.name, "blocks": len(blocks),
            "ok": sum(1 for r in records if r["status"] == "ok"),
            "error": sum(1 for r in records if r["status"] != "ok"),
            "figures": n_fig, "records": records}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="只跑指定章号，逗号分隔")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    only = {int(x) for x in args.only.split(",") if x.strip()}
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(ROOT.glob("模块*/第*.md"))
    manifest = []
    tot_ok = tot_err = tot_fig = 0

    for f in files:
        chm = re.match(r"第(\d+)章", f.name)
        if not chm:
            continue
        ch = int(chm.group(1))
        if only and ch not in only:
            continue
        r = run_chapter(f, args.timeout, args.verbose)
        if r is None:
            continue
        manifest.append(r)
        tot_ok += r["ok"]
        tot_err += r["error"]
        tot_fig += r["figures"]
        flag = "" if r["error"] == 0 else "  <%d 块失败>" % r["error"]
        print("第%03d章  %2d 块  成功 %2d  失败 %d  图 %d%s"
              % (ch, r["blocks"], r["ok"], r["error"], r["figures"], flag))
        for rec in r["records"]:
            if rec["status"] == "error":
                print("      ! 块%d @%s  %s" % (rec["block"], rec["section"], rec["error"][:90]))

    (RUN_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    print()
    print("=" * 60)
    print("合计：%d 章，代码块 %d，成功 %d，失败 %d，生成图 %d"
          % (len(manifest), tot_ok + tot_err, tot_ok, tot_err, tot_fig))
    print("清单：assets/run/manifest.json")


if __name__ == "__main__":
    main()
