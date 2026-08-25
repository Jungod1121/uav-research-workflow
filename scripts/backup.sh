#!/usr/bin/env bash
# backup.sh — 分级备份（restic）。大文件(bags/checkpoints)本地轮转，代码/笔记远端。
# 首次使用: 编辑下方 RESTIC_REPOSITORY / RESTIC_PASSWORD，或 export 到环境。
# 用法: ./backup.sh [--init]
set -euo pipefail

export RESTIC_REPOSITORY="${RESTIC_REPOSITORY:-$HOME/backup/uav-research}"
export RESTIC_PASSWORD="${RESTIC_PASSWORD:-CHANGE_ME_BEFORE_FIRST_RUN}"

WF="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
command -v restic >/dev/null || { echo "请先安装 restic: sudo apt install restic"; exit 1; }
[ "$RESTIC_PASSWORD" = "CHANGE_ME_BEFORE_FIRST_RUN" ] && { echo "ERROR: 请设置真实 RESTIC_PASSWORD"; exit 1; }

if [ "${1:-}" = "--init" ]; then
  restic init --repository-dir "$RESTIC_REPOSITORY" >/dev/null && echo "repo initialized"
fi

echo "[backup] Tier1 代码与轻量资产（每次必备）"
restic backup \
  "$WF" \
  "$HOME/work/uav-research-atlas/data/uav_atlas.db" \
  "$HOME/work/uav-research-atlas/data/seed_taxonomy.json" \
  ~/px4_ros2_ws/src \
  --exclude "*.mcap" --exclude "*.db3" \
  --tag code

echo "[backup] Tier2 实验产物 bags（体积大，仅新增）"
[ -d "$WF/experiments" ] && restic backup "$WF/experiments" --tag experiments || true

echo "[backup] 保留策略: 7日/4周/6月"
restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune

restic snapshots --latest 3
echo "[backup] done. 建议再同步一份到外部盘/云（rsync/rclone），3-2-1 原则。"
