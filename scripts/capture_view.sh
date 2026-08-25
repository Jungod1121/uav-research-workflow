#!/usr/bin/env bash
# capture_view.sh — 抓取当前屏幕/指定窗口为 PNG（视觉通道原子工具）
# 用法:
#   capture_view.sh out.png              # 全屏
#   capture_view.sh out.png rviz2        # 指定窗口名（模糊匹配）
set -euo pipefail
OUT="${1:?usage: capture_view.sh <out.png> [window_name]}"
WIN="${2:-}"

if [ -z "${DISPLAY:-}" ]; then
  echo "ERROR: DISPLAY 未设置。无桌面会话时请先: xvfb-run 或配置 Xvfb" >&2
  exit 2
fi

if [ -n "$WIN" ]; then
  WID=$(xdotool search --name "$WIN" 2>/dev/null | head -1 || true)
  if [ -n "$WID" ]; then
    import -window "$WID" "$OUT"
  else
    echo "WARN: window '$WIN' not found, fallback to full screen" >&2
    import -window root "$OUT"
  fi
else
  import -window root "$OUT"
fi
echo "saved: $OUT"
