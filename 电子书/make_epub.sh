#!/usr/bin/env bash
# 从 Markdown 源生成 EPUB。
#
# 说明书在网页版用交互图，但 EPUB 阅读器只认静态内容（图片 + XHTML），
# 所以这里不用网页那份 HTML，而是直接拿 Markdown 源重新拼。
# 好处是章节顺序、图片路径、公式都与源文件一致，不受网页结构影响。
#
# 依赖：pandoc（brew install pandoc）
# 产出：电子书/量化投资视角的技术分析.epub
#
# 用法：bash 电子书/make_epub.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

OUT="电子书/量化投资视角的技术分析.epub"
TITLE="量化投资视角的技术分析"
AUTHOR="邓一硕（MatrixSpk）"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

if ! command -v pandoc >/dev/null 2>&1; then
  echo "需要 pandoc：brew install pandoc" >&2
  exit 1
fi

# ── 1. 按模块与章号顺序拼出单一 Markdown ──────────────────────
MERGED="$TMP/book.md"
: > "$MERGED"

for mod in 模块*; do
  [ -d "$mod" ] || continue

  # 模块标题：优先用 _module.md 的一级标题
  mod_title=""
  if [ -f "$mod/_module.md" ]; then
    mod_title="$(grep -m1 '^# ' "$mod/_module.md" | sed 's/^# //')"
  fi
  [ -n "$mod_title" ] || mod_title="$mod"

  first=1
  for ch in "$mod"/第*章-*.md; do
    [ -f "$ch" ] || continue

    # 章节里的一级标题已自带章号，不再重复加模块名，
    # 模块信息通过分节符体现
    if [ "$first" = "1" ]; then
      printf '\n\\newpage\n\n# %s {.unnumbered}\n\n' "$mod_title" >> "$MERGED"
      first=0
    fi
    cat "$ch" >> "$MERGED"
    printf '\n\n\\newpage\n\n' >> "$MERGED"
  done
done

# ── 2. 图片路径改成相对仓库根，pandoc 才能找到 ────────────────
# 章节里的引用是 ../assets/figures/...，从根目录看应去掉 ../
# 不用 sed -i：BSD 与 GNU 的写法不兼容，本机装的是 GNU sed
python3 - "$MERGED" <<'PYFIX'
import sys, pathlib
f = pathlib.Path(sys.argv[1])
s = f.read_text(encoding="utf-8").replace("](../assets/", "](assets/")
f.write_text(s, encoding="utf-8")
PYFIX

# ── 3. EPUB 样式 ─────────────────────────────────────────────
CSS="$TMP/epub.css"
cat > "$CSS" <<'EOF'
body { font-family: serif; line-height: 1.7; }
h1 { font-size: 1.5em; margin: 1.2em 0 .8em; }
h2 { font-size: 1.15em; margin: 1.4em 0 .6em; }
img { max-width: 100%; height: auto; display: block; margin: 1em auto; }
p.figcap { text-align: center; font-size: .85em; color: #666; margin: .2em 0 1.4em; }
pre { font-size: .72em; white-space: pre-wrap; word-wrap: break-word;
      background: #f6f8fa; padding: .7em; border-radius: 4px; }
code { font-family: monospace; font-size: .9em; }
table { border-collapse: collapse; font-size: .8em; margin: 1em 0; }
th, td { border: 1px solid #ddd; padding: .35em .5em; }
.math.display { font-size: .95em; }
EOF

# ── 4. 生成 ─────────────────────────────────────────────────
# --mathml：EPUB3 阅读器（Apple Books、Kobo、Calibre）都支持 MathML，
# 比塞图片清晰，也能被检索。
pandoc "$MERGED" \
  -f markdown+pipe_tables+tex_math_dollars+fenced_code_blocks \
  -t epub3 \
  --toc --toc-depth=2 \
  --mathml \
  --css "$CSS" \
  --metadata title="$TITLE" \
  --metadata author="$AUTHOR" \
  --metadata lang=zh-CN \
  --metadata date="$(date +%Y-%m-%d)" \
  --resource-path="$ROOT" \
  -o "$OUT"

echo "已生成：${OUT}（$(du -h "$OUT" | cut -f1)）"
echo "图片：$(unzip -l "$OUT" | grep -c '\.png$' || true) 张"
