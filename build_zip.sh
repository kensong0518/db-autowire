#!/bin/bash
# 打包成可散布的 zip：排除資料庫、金鑰與快取
set -e
cd "$(dirname "$0")"
OUT="維修接單台.zip"
rm -f "$OUT"
zip -rq "$OUT" repair-radar \
  -x '*/__pycache__/*' '*/data.db' '*/config.json' '*.pyc' '*/.DS_Store'
# 保留 Unix 執行權限（Mac 的 .command 要能雙擊）
echo "已產生 $OUT"
unzip -l "$OUT" | tail -n +4 | head -n -2
