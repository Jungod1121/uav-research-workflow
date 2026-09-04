#!/bin/bash
# capture_view.sh — 证据截图工具
# 用法: capture_view.sh <out.png> [窗口名正则] [mode]
#   mode: window(默认,只截目标窗口) | monitor(目标窗口所在显示器) | full(全桌面,仅调试)
# 依赖: xdotool + ImageMagick(import) + python3-PIL
set -e
OUT="$1"; NAME="${2:-}"; MODE="${3:-window}"
[ -z "$OUT" ] && { echo "usage: capture_view.sh <out.png> [window_name] [window|monitor|full]"; exit 1; }
export DISPLAY="${DISPLAY:-:0}"

if [ "$MODE" = "full" ] || [ -z "$NAME" ]; then
  import -window root "$OUT"
  echo "captured: $OUT (full)"
  exit 0
fi

# 取匹配窗口中几何有效且面积最大者(避开托盘/隐藏/已销毁窗口)
WID=$(xdotool search --name "$NAME" 2>/dev/null | while read -r w; do
  g=$(xdotool getwindowgeometry "$w" 2>/dev/null | awk '/Geometry:/ {gsub(/x/," "); print $2, $3}')
  [ -z "$g" ] && continue
  read -r ww hh <<< "$g"
  [ "$ww" -ge 500 ] 2>/dev/null && [ "$hh" -ge 300 ] 2>/dev/null && echo "$((ww*hh)) $w"
done | sort -rn | head -1 | awk '{print $2}')
[ -z "$WID" ] && { echo "window not found: $NAME (无有效窗口)"; exit 1; }

GEO=$(xdotool getwindowgeometry "$WID" | awk '
  /Position:/ {gsub(/[,:]/, " "); x=$2; y=$3}
  /Geometry:/ {gsub(/x/, " "); w=$2; h=$3}
  END {print x, y, w, h}')
read -r X Y W H <<< "$GEO"

if [ "$MODE" = "monitor" ] || [ "$W" -lt 50 ] 2>/dev/null; then
  # 含窗口中心的显示器矩形 (python 解析 xrandr, 避开 gawk/mawk 差异)
  RECT=$(xrandr --query | grep " connected" | python3 -c "
import sys, re
cx, cy = $((X + W / 2)), $((Y + H / 2))
for line in sys.stdin:
    m = re.search(r'(\d+)x(\d+)\+(\d+)\+(\d+)', line)
    if not m: continue
    w, h, x, y = map(int, m.groups())
    if x <= cx < x + w and y <= cy < y + h:
        print(w, h, x, y); break
")
  [ -z "$RECT" ] && RECT="$W $H 0 0"
  read -r W H X Y <<< "$RECT"
  MODE=monitor
fi

import -window root "$OUT"
python3 - "$OUT" "$X" "$Y" "$W" "$H" <<'EOF'
import sys
from PIL import Image
p, x, y, w, h = sys.argv[1], *map(int, sys.argv[2:])
im = Image.open(p)
im.crop((x, y, min(x + w, im.width), min(y + h, im.height))).save(p)
EOF
echo "captured: $OUT (mode=$MODE ${W}x${H}+${X}+${Y})"
