#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""不跑章节代码，只按规格重出图。

章节代码跑一轮要十几分钟，改配色这类只影响外观的调整没必要重跑代码。
这里直接按 equant_spec.py 的规格算指标、画图、存盘，与章内代码同函数同参数，
图的结果一致。

用法：python3 scripts/redraw_figures.py [--only 9,21]
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import warnings

import matplotlib
matplotlib.use("Agg")
import pandas as pd

warnings.filterwarnings("ignore")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from equant_spec import SPEC  # noqa: E402

import ettr  # noqa: E402
import efincharts as efc  # noqa: E402
from efincharts import theme  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent

# 中文与 A 股配色：涨红跌绿（efincharts 默认是欧美习惯的涨绿跌红）
theme.efin_style["rc"] = {
    "font.sans-serif": ["PingFang SC", "Heiti SC", "SimHei"],
    "axes.unicode_minus": False,
    "font.family": "sans-serif",
}
_mc = theme.efin_style["marketcolors"]
for _k in ("candle", "edge", "wick", "volume"):
    _mc[_k] = {"up": "#e53935", "down": "#26a69a"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    only = {int(x) for x in args.only.split(",") if x.strip()}

    blue = pd.read_parquet(ROOT / "data/parquet/panel_blue_chip.parquet")
    m = blue[blue["code"] == "600519.SS"].copy()

    ok = 0
    for s in SPEC:
        if only and s["ch"] not in only:
            continue
        d = m.copy()
        for fn, kw in s["py"]:
            d = getattr(ettr, fn)(d, **kw)

        # 转 efincharts 要的宽表
        x = d.sort_values("date").set_index("date")
        x.columns = [c.capitalize() for c in x.columns]

        out = ROOT / "assets" / "figures" / ("ch%03d" % s["ch"])
        out.mkdir(parents=True, exist_ok=True)
        try:
            ch = efc.candlestick(x, volume=True, title="贵州茅台 · %s" % s["name"])
            ch.save(str(out / "indicator.png"))
            ok += 1
            print("第%03d章 %-24s 已重绘" % (s["ch"], s["name"]))
        except Exception as e:
            print("第%03d章 %-24s 失败: %s" % (s["ch"], s["name"], str(e)[:60]))

    print("\n完成 %d 张" % ok)


if __name__ == "__main__":
    main()
