#!/bin/bash
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then
  exec python3 repair_radar.py
fi
echo
echo "  找不到 python3。macOS 通常內建，若沒有請執行： xcode-select --install"
echo
read -r -p "按 Enter 關閉…"
