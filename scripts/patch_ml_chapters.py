#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给非指标章（007、040、042–048）补上 eQuant 取数逻辑。

这些章的代码原本直接读 `data/parquet/xxx`，读者没克隆仓库就跑不了。
这里做两件事：

1. 每章第一个代码块顶部插入取数准备代码，定义 load() 并加载 blue / panel。
   后续块依赖这个变量，与原来「顺序运行」的用法一致。
2. 块内形如 `pd.read_parquet("data/parquet/xxx.parquet")` 的调用换成 `load("xxx.parquet")`。

用注释标记包裹插入的准备代码，重跑不会叠加。
用法：python3 scripts/patch_ml_chapters.py [--dry]
"""

from __future__ import annotations

import argparse
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent

CHAPTERS = [7, 40, 42, 43, 44, 45, 46, 47, 48]

MARK_PY = "<!-- data-prep-py:start -->"
MARK_R = "<!-- data-prep-r:start -->"

# 040 章用到四类代表特征，数据里没有预存，用 ettr 现算
PY_FEATS = '''
# 四类代表特征：趋势、震荡、波动率、量价各取一个，与前面各章口径一致
import ettr

panel = ettr.sma(panel, n=20)
panel = ettr.rsi(panel, n=14)
panel = ettr.atr(panel, n=14)
panel = ettr.obv(panel)

panel["sma_dev"]    = panel["close"] / panel["SMA_20"] - 1
panel["rsi_dev"]    = panel["RSI_14"] / 100 - 0.5
panel["atr_rank"]   = panel.groupby("date")["ATR_14"].rank(pct=True)
panel["obv_change"] = panel.groupby("code")["OBV"].pct_change(10)
'''

PY_PREP = '''import pathlib
import urllib.request

import pandas as pd

# 数据随书发布在仓库里，本地没有就下载一次并缓存，之后离线可用
BASE = "https://raw.githubusercontent.com/dengyishuo/quant-technical-analysis/main/data/parquet"
CACHE = pathlib.Path.home() / ".cache" / "qta"


def load(name):
    local = pathlib.Path("data/parquet") / name
    if local.exists():
        path = local
    else:
        CACHE.mkdir(parents=True, exist_ok=True)
        path = CACHE / name
        if not path.exists():
            print("下载 %s ..." % name)
            urllib.request.urlretrieve(BASE + "/" + name, path)
    return pd.read_parquet(path) if name.endswith(".parquet") else pd.read_csv(path)


blue = load("panel_blue_chip.parquet")
panel = load("panel.parquet")
panel = panel[(panel["date"] >= "2023-01-01") & (panel["date"] <= "2025-06-01")]
'''

R_PREP = '''# 数据随书发布在仓库里，本地没有就下载一次并缓存，之后离线可用
BASE <- "https://raw.githubusercontent.com/dengyishuo/quant-technical-analysis/main/data/parquet"

load_data <- function(name) {
  local <- file.path("data", "parquet", name)
  if (file.exists(local)) return(local)
  cache <- file.path(tools::R_user_dir("qta", "cache"), name)
  if (!file.exists(cache)) {
    dir.create(dirname(cache), recursive = TRUE, showWarnings = FALSE)
    message("下载 ", name, " ...")
    download.file(paste0(BASE, "/", name), cache, mode = "wb", quiet = TRUE)
  }
  cache
}

read_data <- function(name) {
  d <- read.csv(load_data(name), stringsAsFactors = FALSE)
  if ("date" %in% names(d)) d$date <- as.Date(d$date)
  d
}

blue  <- read_data("panel_blue_chip.csv")
panel <- read_data("panel_r.csv.gz")
panel <- panel[panel$date >= "2023-01-01" & panel$date <= "2025-06-01", ]
'''

BLOCK_RE = re.compile(r"^```(r|python)[ \t]*\n(.*?)^```[ \t]*$", re.S | re.M)

# 块内读取换成 load()
PY_READ_RE = re.compile(
    r'pd\.read_parquet\(\s*["\']data/parquet/([\w.\-]+)["\']\s*\)')
PY_CSV_RE = re.compile(
    r'pd\.read_csv\(\s*["\']data/parquet/([\w.\-]+)["\']\s*\)')
R_READ_RE = re.compile(
    r'read\.csv\(\s*["\']data/parquet/([\w.\-]+)["\']\s*,?\s*stringsAsFactors\s*=\s*FALSE\s*\)')


def already(block: str) -> bool:
    return "def load(name):" in block or "load_data <- function" in block


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    for ch in CHAPTERS:
        cand = list(ROOT.glob("模块*/第%03d章*.md" % ch))
        if not cand:
            print("第%03d章 找不到文件" % ch)
            continue
        f = cand[0]
        text = f.read_text(encoding="utf-8")

        # 先把块内读取替换掉
        n_py_read = len(PY_READ_RE.findall(text))
        n_py_csv = len(PY_CSV_RE.findall(text))
        n_r_read = len(R_READ_RE.findall(text))
        text = PY_READ_RE.sub(lambda m: 'load("%s")' % m.group(1), text)
        text = PY_CSV_RE.sub(lambda m: 'load("%s")' % m.group(1), text)
        text = R_READ_RE.sub(lambda m: 'read_data("%s")' % m.group(1), text)

        blocks = list(BLOCK_RE.finditer(text))
        if not blocks:
            print("第%03d章 无代码块" % ch)
            continue

        # 每章首个 python / r 块各插一次准备代码
        inserts = []   # (位置, 内容)
        seen = {"python": False, "r": False}
        for b in blocks:
            lang = b.group(1)
            if seen[lang]:
                continue
            seen[lang] = True
            body = b.group(2)
            if already(body):
                continue
            prep = PY_PREP if lang == "python" else R_PREP
            if lang == "python" and ch == 40:
                prep = prep + PY_FEATS
            inserts.append((b.start(2), prep + "\n"))

        if args.dry:
            print("第%03d章 替换读取 py%d+csv%d+r%d，插入准备 %d 处"
                  % (ch, n_py_read, n_py_csv, n_r_read, len(inserts)))
            continue

        for pos, snippet in sorted(inserts, reverse=True):
            text = text[:pos] + snippet + text[pos:]

        f.write_text(text, encoding="utf-8")
        print("第%03d章 %-26s 替换读取 py%d/csv%d/r%d，插入准备 %d 处"
              % (ch, f.name[6:30], n_py_read, n_py_csv, n_r_read, len(inserts)))


if __name__ == "__main__":
    main()
