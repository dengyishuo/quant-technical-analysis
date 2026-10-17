#!/usr/bin/env bash
# 下载 MathJax，供 build_ebook.py 内联进单文件电子书。
#
# 为什么需要：电子书是自包含的单文件，读者可能断网阅读，或所在网络访问
# cdn.jsdelivr.net 受限。MathJax 从 CDN 加载时，一旦拿不到脚本，全书
# 公式都会退回 $$...$$ 原始源码。内联后与网络无关。
#
# 选 tex-svg 而非 tex-chtml：SVG 把字形直接画成路径，不依赖额外下载的
# woff 字体文件；CHTML 需要字体，离线时字形会退化。
#
# 用法：bash 电子书/fetch_mathjax.sh

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$HERE/vendor/tex-svg.js"
URL="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"

mkdir -p "$HERE/vendor"

if [ -f "$OUT" ] && [ "$(wc -c < "$OUT")" -gt 1000000 ]; then
  echo "已存在：$(du -h "$OUT" | cut -f1)  $OUT"
  echo "如需重新下载，先删除该文件。"
  exit 0
fi

echo "下载 MathJax tex-svg.js ..."
curl -fsSL -o "$OUT" "$URL"

size=$(wc -c < "$OUT")
if [ "$size" -lt 1000000 ]; then
  echo "下载异常，文件只有 $size 字节" >&2
  exit 1
fi

echo "完成：$(du -h "$OUT" | cut -f1)  $OUT"
echo "现在可以运行：python3 电子书/build_ebook.py"
