#!/bin/bash
# 維修接單台 — Mac 安裝程式
set -u
cd "$(dirname "$0")" || exit 1

APP_NAME="維修接單台"
SRC="$(pwd)"
DEST="$HOME/Applications/RepairRadar"
APP_BUNDLE="$HOME/Applications/${APP_NAME}.app"

say()  { printf "  %s\n" "$1"; }
step() { printf "\n  \033[36m%s\033[0m\n" "$1"; }
ok()   { printf "  \033[32m%s\033[0m\n" "$1"; }
die()  { printf "\n  \033[31m安裝失敗：%s\033[0m\n\n" "$1"; read -r -p "  按 Enter 關閉"; exit 1; }

clear
printf "\n  \033[33m┌────────────────────────────────────┐\033[0m\n"
printf "  \033[33m│        維修接單台  安裝程式        │\033[0m\n"
printf "  \033[33m└────────────────────────────────────┘\033[0m\n\n"
say "安裝位置：$DEST"

# ---------- 1. Python ----------
step "[1/4] 檢查 Python…"
PY=""
for c in python3 /usr/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  if command -v "$c" >/dev/null 2>&1; then
    if "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)' 2>/dev/null; then
      PY="$(command -v "$c")"; break
    fi
  fi
done

if [ -z "$PY" ]; then
  say "沒有找到 Python 3.8 以上的版本。"
  say "macOS 通常內建。請在終端機執行這行安裝開發工具："
  printf "\n      xcode-select --install\n\n"
  say "裝完再跑一次這個安裝程式。"
  read -r -p "  按 Enter 關閉"; exit 1
fi
ok "找到 $("$PY" --version 2>&1)"

# ---------- 2. 複製檔案 ----------
step "[2/4] 安裝程式檔案…"
BACKUP=""
if [ -f "$DEST/data.db" ]; then
  BACKUP="$(mktemp -d)"
  cp "$DEST/data.db" "$BACKUP/" 2>/dev/null
  [ -f "$DEST/config.json" ] && cp "$DEST/config.json" "$BACKUP/" 2>/dev/null
  say "偵測到舊資料，已暫存工單與設定"
fi

mkdir -p "$DEST" || die "無法建立 $DEST"
for f in repair_radar.py keywords.json config.example.json README.md; do
  [ -f "$SRC/$f" ] && cp "$SRC/$f" "$DEST/"
done
for d in web tests; do
  [ -d "$SRC/$d" ] && { rm -rf "${DEST:?}/$d"; cp -R "$SRC/$d" "$DEST/"; }
done
find "$DEST" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null
find "$DEST" -name '*.pyc' -delete 2>/dev/null
[ -n "$BACKUP" ] && cp "$BACKUP"/* "$DEST/" 2>/dev/null && ok "舊資料已還原"
[ -f "$DEST/config.json" ] || cp "$DEST/config.example.json" "$DEST/config.json"
ok "檔案安裝完成"

# ---------- 3. 啟動器與 App ----------
step "[3/4] 建立啟動器…"
cat > "$DEST/啟動.command" <<LAUNCH
#!/bin/bash
cd "\$(dirname "\$0")" || exit 1
exec "$PY" repair_radar.py "\$@"
LAUNCH
chmod +x "$DEST/啟動.command"

rm -rf "$APP_BUNDLE"
mkdir -p "$APP_BUNDLE/Contents/MacOS"
cat > "$APP_BUNDLE/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>${APP_NAME}</string>
  <key>CFBundleDisplayName</key><string>${APP_NAME}</string>
  <key>CFBundleIdentifier</key><string>tw.repairradar.app</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleExecutable</key><string>run</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSMinimumSystemVersion</key><string>10.13</string>
</dict></plist>
PLIST
cat > "$APP_BUNDLE/Contents/MacOS/run" <<RUN
#!/bin/bash
open -a Terminal "$DEST/啟動.command"
RUN
chmod +x "$APP_BUNDLE/Contents/MacOS/run"
xattr -dr com.apple.quarantine "$APP_BUNDLE" 2>/dev/null
ok "已建立 $APP_BUNDLE"

ln -sf "$DEST/啟動.command" "$HOME/Desktop/${APP_NAME}.command" 2>/dev/null && ok "桌面捷徑已建立"

# ---------- 4. 開機自動啟動 ----------
step "[4/4] 開機自動啟動"
PLIST_PATH="$HOME/Library/LaunchAgents/tw.repairradar.plist"
say "要開機時自動啟動嗎？（店裡電腦建議開）"
read -r -p "  開機自動啟動？(y/N) " AUTO
if [[ "$AUTO" =~ ^[Yy] ]]; then
  mkdir -p "$HOME/Library/LaunchAgents"
  cat > "$PLIST_PATH" <<AGENT
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>tw.repairradar</string>
  <key>ProgramArguments</key>
  <array><string>$PY</string><string>$DEST/repair_radar.py</string><string>--no-browser</string></array>
  <key>WorkingDirectory</key><string>$DEST</string>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$DEST/run.log</string>
  <key>StandardErrorPath</key><string>$DEST/run.log</string>
</dict></plist>
AGENT
  launchctl unload "$PLIST_PATH" 2>/dev/null
  launchctl load "$PLIST_PATH" 2>/dev/null && ok "已設定開機自動啟動" || say "已寫入設定，下次開機生效"
else
  launchctl unload "$PLIST_PATH" 2>/dev/null
  rm -f "$PLIST_PATH"
  say "沒有設定自動啟動"
fi

# ---------- 移除程式 ----------
cat > "$DEST/移除.command" <<'UNINST'
#!/bin/bash
DEST="$HOME/Applications/RepairRadar"
APP="$HOME/Applications/維修接單台.app"
printf "\n  移除維修接單台\n\n"
if [ -f "$DEST/data.db" ]; then
  read -r -p "  要保留一份工單資料到桌面嗎？(Y/n) " K
  if [[ ! "$K" =~ ^[Nn] ]]; then
    cp "$DEST/data.db" "$HOME/Desktop/維修接單台-資料備份.db"
    printf "  已存到桌面：維修接單台-資料備份.db\n"
  fi
fi
read -r -p "  確定移除？(y/N) " C
[[ "$C" =~ ^[Yy] ]] || { echo "  取消。"; read -r -p "  按 Enter 關閉"; exit 0; }
launchctl unload "$HOME/Library/LaunchAgents/tw.repairradar.plist" 2>/dev/null
rm -f "$HOME/Library/LaunchAgents/tw.repairradar.plist"
rm -f "$HOME/Desktop/維修接單台.command"
rm -rf "$APP"
rm -rf "$DEST"
printf "\n  移除完成。Python 沒有被移除。\n\n"
read -r -p "  按 Enter 關閉"
UNINST
chmod +x "$DEST/移除.command"

printf "\n"
ok "安裝好了。"
printf "\n"
say "• Launchpad 或桌面的「${APP_NAME}」點兩下就能開"
say "• 開起來的終端機視窗不要關，關掉程式就停了"
say "• 要接 LINE、Telegram、粉專、IG："
say "  用文字編輯程式打開 $DEST/config.json 照 README 填"
printf "\n"
say "移除：執行 $DEST/移除.command"
printf "\n"
read -r -p "  現在啟動嗎？(Y/n) " GO
if [[ ! "$GO" =~ ^[Nn] ]]; then open "$APP_BUNDLE"; fi
