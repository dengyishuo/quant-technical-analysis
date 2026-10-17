#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把书稿里从网络抓数据的代码改成读本地 parquet / CSV。

背景：全书 35 章的数据加载用 yfinance / quantmod 的 getSymbols，依赖联网且
A 股复权质量不可控。本地 data/parquet 已有同一来源（xquant-db）的数据，
改成读本地文件后代码离线可跑，与正文口径一致。

替换是模式化的，只动数据加载那几行，其余代码不动。
列名保持 yfinance 的大写风格（Open/High/Low/Close/Volume），
这样后续所有 `data["Close"]` 之类的引用无需改动。

用法：python3 scripts/switch_to_local_data.py
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# 单个标的的 Python 加载（import 与 download 之间可能夹注释，分两步处理）
PY_DL_ONE = re.compile(
    r'^(?P<indent>[ \t]*)(?P<var>\w+)\s*=\s*yf\.download\('
    r'(?P<sym>"[^"]+")\s*,\s*start="[^"]*"\s*,\s*end="[^"]*"\s*,\s*progress=False\s*\)\s*$',
    re.M,
)

# 循环内按 code 变量加载
PY_DL_LOOP = re.compile(
    r'^(?P<indent>[ \t]*)(?P<var>\w+)\s*=\s*yf\.download\('
    r'(?P<sym>code)\s*,\s*start="[^"]*"\s*,\s*end="[^"]*"\s*,\s*progress=False\s*\)\s*$',
    re.M,
)

PY_IMPORT = re.compile(r'^import yfinance as yf\s*$', re.M)

# 单个标的的 R 加载（getSymbols 之后通常紧跟 data <- `xxx`）
R_ONE = re.compile(
    r'^getSymbols\((?P<sym>"[^"]+")\s*,\s*src\s*=\s*"yahoo"\s*,'
    r'\s*from\s*=\s*"[^"]*"\s*,\s*to\s*=\s*"[^"]*"\s*\)\s*\n'
    r'\s*(?P<var>\w+)\s*<-\s*`[^`]+`\s*$',
    re.M,
)

# 循环内的 R 加载：x <- getSymbols(cd, src = "yahoo", ..., auto.assign = FALSE)
# 实际写法跨行，允许 \s 跨行匹配
R_LOOP = re.compile(
    r'^(?P<indent>[ \t]*)(?P<lhs>\w+)\s*<-\s*getSymbols\((?P<arg>\w+)\s*,\s*src\s*=\s*"yahoo"\s*,'
    r'\s*from\s*=\s*"[^"]*"\s*,\s*to\s*=\s*"[^"]*"\s*,\s*auto\.assign\s*=\s*FALSE\s*\)',
    re.M,
)

PY_SINGLE_TPL = """{indent}_panel = pd.read_parquet("data/parquet/panel_blue_chip.parquet")
{indent}{var} = (_panel[_panel["code"] == {sym}]
{indent}        .set_index("date").sort_index()[["open", "high", "low", "close", "volume"]])
{indent}{var}.columns = ["Open", "High", "Low", "Close", "Volume"]"""

PY_LOOP_TPL = """{indent}_oneday = _panel[_panel["code"] == {sym}].set_index("date").sort_index()
{indent}{var} = _oneday[["open", "high", "low", "close", "volume"]].copy()
{indent}{var}.columns = ["Open", "High", "Low", "Close", "Volume"]"""

PY_IMPORT_TPL = """import pandas as pd

# 本地数据，由 xquant-db 导出，字段见 data/README.md
_panel = pd.read_parquet("data/parquet/panel_blue_chip.parquet")"""

R_SINGLE_TPL = """panel <- read.csv("data/parquet/panel_blue_chip.csv", stringsAsFactors = FALSE)
.sub <- panel[panel$code == "{sym}", ]
{var} <- xts::xts(.sub[, c("open", "high", "low", "close", "volume", "adjusted")],
                 order.by = as.Date(.sub$date))
colnames({var}) <- c("Open", "High", "Low", "Close", "Volume", "Adjusted")"""

R_LOOP_TPL = """{indent}{lhs} <- local({{
{indent}  # 从本地 CSV 取该标的，转成 quantmod 可用的 xts
{indent}  .p <- read.csv("data/parquet/panel_blue_chip.csv", stringsAsFactors = FALSE)
{indent}  .p <- .p[.p$code == {arg}, ]
{indent}  .x <- xts::xts(.p[, c("open", "high", "low", "close", "volume", "adjusted")],
{indent}                     order.by = as.Date(.p$date))
{indent}  colnames(.x) <- c("Open", "High", "Low", "Close", "Volume", "Adjusted")
{indent}  .x
{indent}}})"""


def main() -> None:
    files = sorted(ROOT.glob("模块*/第*.md"))
    stat = {"py_import": 0, "py_single": 0, "py_loop": 0,
            "r_single": 0, "r_loop": 0}
    changed = []

    for f in files:
        t = f.read_text(encoding="utf-8")
        orig = t

        def py_single(m):
            stat["py_single"] += 1
            return PY_SINGLE_TPL.format(indent=m.group("indent"),
                                        var=m.group("var"), sym=m.group("sym"))

        def py_loop(m):
            stat["py_loop"] += 1
            return PY_LOOP_TPL.format(indent=m.group("indent"),
                                      var=m.group("var"), sym=m.group("sym"))

        def r_single(m):
            stat["r_single"] += 1
            return R_SINGLE_TPL.format(var=m.group("var"), sym=m.group("sym").strip(chr(34)))

        def r_loop(m):
            stat["r_loop"] += 1
            return R_LOOP_TPL.format(indent=m.group("indent"), lhs=m.group("lhs"), arg=m.group("arg"))

        # import 先换成 pandas（同一代码块只留一次 _panel 的读取）
        if PY_IMPORT.search(t):
            t = PY_IMPORT.sub(PY_IMPORT_TPL, t, count=1)
            stat["py_import"] += 1
        t = PY_DL_ONE.sub(py_single, t)
        t = PY_DL_LOOP.sub(py_loop, t)
        t = R_ONE.sub(r_single, t)
        t = R_LOOP.sub(r_loop, t)

        if t != orig:
            f.write_text(t, encoding="utf-8")
            changed.append(f.name)

    print("替换统计：")
    for k, v in stat.items():
        print("  %-10s %d" % (k, v))
    print("  合计 %d 处，涉及 %d 个文件" % (sum(stat.values()), len(changed)))

    # 残留检查
    left_py = left_r = 0
    rest = []
    for f in files:
        t = f.read_text(encoding="utf-8")
        a = t.count("yf.download")
        b = t.count('src = "yahoo"')
        if a or b:
            rest.append((f.name, a, b))
        left_py += a
        left_r += b
    print("\n残留：yf.download %d 处，getSymbols %d 处" % (left_py, left_r))
    for n, a, b in rest:
        print("  %s (py=%d, r=%d)" % (n, a, b))
    if left_py or left_r:
        sys.exit(1)


if __name__ == "__main__":
    main()
