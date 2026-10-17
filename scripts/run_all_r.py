#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐章执行书稿里的 R 代码块。

由 Python 负责抽取围栏与拼接，写成临时 .R 文件后交给 Rscript 运行，
避免在 R 内部处理多行 UTF-8 字符串的编码问题。

同一章的多个 R 块合并成一个脚本顺序执行（后面的块依赖前面的对象），
与读者的实际运行顺序一致。

产出：assets/run/r_manifest.json，assets/run/r_stdout/chNNN.txt

用法：python3 scripts/run_all_r.py [--only 9,21] [--timeout 180]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUN = ROOT / "assets" / "run"


def r_blocks(text: str):
    out = []
    for m in re.finditer(r"^```r[ \t]*\n(.*?)^```[ \t]*$", text, re.S | re.M):
        out.append(m.group(1))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--timeout", type=int, default=180)
    args = ap.parse_args()

    only = {int(x) for x in args.only.split(",") if x.strip()}
    (RUN / "r_stdout").mkdir(parents=True, exist_ok=True)

    rows = []
    tot_ok = tot_bad = 0

    for f in sorted(ROOT.glob("模块*/第*.md")):
        m = re.match(r"第(\d+)章", f.name)
        if not m:
            continue
        ch = int(m.group(1))
        if only and ch not in only:
            continue

        blocks = r_blocks(f.read_text(encoding="utf-8"))
        if not blocks:
            continue

        # 合并成一份脚本，前面加统一的准备工作
        header = (
            'suppressMessages({library(ettr); library(efactorcraft); '
            'library(efincharts); library(ggplot2); library(xts)})\n'
            'setwd("%s")\n' % ROOT
        )
        body = "\n\n".join(blocks)
        script = header + body

        with tempfile.NamedTemporaryFile("w", suffix=".R", delete=False,
                                         encoding="utf-8") as fh:
            fh.write(script)
            tmp = fh.name

        ok, err = True, ""
        try:
            r = subprocess.run(["Rscript", tmp], capture_output=True, text=True,
                               timeout=args.timeout, cwd=str(ROOT))
            if r.returncode != 0:
                ok = False
                tail = (r.stderr or r.stdout or "").strip().split("\n")
                err = tail[-1][:160] if tail else "未知错误"
            out = (r.stdout or "") + (r.stderr or "")
        except subprocess.TimeoutExpired:
            ok, err, out = False, "超时 %d 秒" % args.timeout, ""
        finally:
            pathlib.Path(tmp).unlink(missing_ok=True)

        (RUN / "r_stdout" / ("ch%03d.txt" % ch)).write_text(out, encoding="utf-8")
        rows.append({"ch": ch, "blocks": len(blocks), "status": "ok" if ok else "error",
                     "error": err})
        tot_ok += ok
        tot_bad += (not ok)
        print("第%03d章  %d 块合并执行  %s%s"
              % (ch, len(blocks), "通过" if ok else "失败", "" if ok else "  " + err))

    (RUN / "r_manifest.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("=" * 56)
    print("合计：%d 章，通过 %d，失败 %d" % (len(rows), tot_ok, tot_bad))


if __name__ == "__main__":
    main()
