# 維修接單台 — Windows 安裝程式
# 由 安裝-Windows.bat 呼叫。偵測 Python、安裝程式、建立捷徑。
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$APP_NAME  = "維修接單台"
$SRC       = Split-Path -Parent $PSScriptRoot
$DEST      = Join-Path ([Environment]::GetFolderPath("Desktop")) "修手機的"
$PY_VER    = "3.12.7"

function Say($msg, $color = "White") { Write-Host "  $msg" -ForegroundColor $color }
function Step($msg) { Write-Host ""; Write-Host "  $msg" -ForegroundColor Cyan }
function Die($msg) {
    Write-Host ""; Write-Host "  安裝失敗：$msg" -ForegroundColor Red; Write-Host ""
    Read-Host "  按 Enter 關閉"; exit 1
}

Clear-Host
Write-Host ""
Write-Host "  ┌────────────────────────────────────┐" -ForegroundColor Yellow
Write-Host "  │        維修接單台  安裝程式        │" -ForegroundColor Yellow
Write-Host "  └────────────────────────────────────┘" -ForegroundColor Yellow
Write-Host ""
Say "安裝位置：$DEST" "DarkGray"

# ---------- 1. 找 Python ----------
Step "[1/5] 檢查 Python…"

function Find-Python {
    foreach ($cmd in @("py", "python", "python3")) {
        try {
            $exe = (Get-Command $cmd -ErrorAction Stop).Source
            $ver = & $exe -c "import sys;print('%d.%d' % sys.version_info[:2])" 2>$null
            if ($LASTEXITCODE -eq 0 -and [version]$ver -ge [version]"3.8") { return $exe }
        } catch {}
    }
    $roots = @("$env:LOCALAPPDATA\Programs\Python", "$env:ProgramFiles\Python*", "C:\Python*")
    foreach ($r in $roots) {
        $hit = Get-ChildItem -Path $r -Filter "python.exe" -Recurse -ErrorAction SilentlyContinue |
               Sort-Object FullName -Descending | Select-Object -First 1
        if ($hit) { return $hit.FullName }
    }
    return $null
}

$python = Find-Python
if ($python) {
    $v = & $python --version 2>&1
    Say "找到 $v" "Green"
} else {
    Say "沒有找到 Python，要幫你自動安裝嗎？" "Yellow"
    Say "下載約 25 MB，只裝給目前這個使用者，不需要系統管理員權限。" "DarkGray"
    $ans = Read-Host "  安裝 Python？(Y/n)"
    if ($ans -match "^[Nn]") { Die "沒有 Python 就無法執行。請自行安裝後再跑一次。" }

    $arch = if ([Environment]::Is64BitOperatingSystem) { "amd64" } else { "win32" }
    $url  = "https://www.python.org/ftp/python/$PY_VER/python-$PY_VER-$arch.exe"
    $tmp  = Join-Path $env:TEMP "python-$PY_VER.exe"

    Say "下載中…（可能要一兩分鐘）"
    try { Invoke-WebRequest -Uri $url -OutFile $tmp -UseBasicParsing }
    catch { Die "下載失敗：$($_.Exception.Message)`n請手動到 https://www.python.org/downloads/ 安裝。" }

    Say "安裝中…（安裝過程沒有畫面，請耐心等）"
    $p = Start-Process -FilePath $tmp -Wait -PassThru -ArgumentList @(
        "/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_test=0", "Include_launcher=1")
    Remove-Item $tmp -ErrorAction SilentlyContinue

    $python = Find-Python
    if (-not $python) { Die "Python 安裝完成但找不到執行檔（代碼 $($p.ExitCode)）。請重新開機後再試一次。" }
    Say "Python 安裝完成：$(& $python --version 2>&1)" "Green"
}

# ---------- 2. 複製檔案 ----------
Step "[2/5] 安裝程式檔案…"

$keepDb = Join-Path $DEST "data.db"
$keepCfg = Join-Path $DEST "config.json"
$backup = $null
if (Test-Path $keepDb) {
    $backup = Join-Path $env:TEMP "rr_backup_$(Get-Date -Format yyyyMMddHHmmss)"
    New-Item -ItemType Directory -Path $backup -Force | Out-Null
    Copy-Item $keepDb $backup -Force
    if (Test-Path $keepCfg) { Copy-Item $keepCfg $backup -Force }
    Say "偵測到舊資料，已暫存工單與設定" "DarkGray"
}

New-Item -ItemType Directory -Path $DEST -Force | Out-Null
foreach ($item in @("repair_radar.py", "keywords.json", "config.example.json", "README.md")) {
    $p = Join-Path $SRC $item
    if (Test-Path $p) { Copy-Item $p $DEST -Force }
}
foreach ($dir in @("web", "tests")) {
    $p = Join-Path $SRC $dir
    if (Test-Path $p) { Copy-Item $p (Join-Path $DEST $dir) -Recurse -Force }
}
Get-ChildItem $DEST -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
if ($backup) {
    Get-ChildItem $backup | ForEach-Object { Copy-Item $_.FullName $DEST -Force }
    Say "舊資料已還原" "Green"
}
$cfg = Join-Path $DEST "config.json"
if (-not (Test-Path $cfg)) { Copy-Item (Join-Path $DEST "config.example.json") $cfg -Force }
Say "檔案安裝完成" "Green"

# ---------- 3. 產生啟動器 ----------
Step "[3/5] 建立啟動器…"

$launcher = Join-Path $DEST "啟動.bat"
@"
@echo off
chcp 65001 >nul
title $APP_NAME
cd /d "%~dp0"
"$python" repair_radar.py %*
if errorlevel 1 pause
"@ | Set-Content -Path $launcher -Encoding UTF8
Say "啟動器已建立" "Green"

# ---------- 4. 捷徑 ----------
Step "[4/5] 建立捷徑…"

function New-Shortcut($path, $target, $desc) {
    $ws = New-Object -ComObject WScript.Shell
    $sc = $ws.CreateShortcut($path)
    $sc.TargetPath = $target
    $sc.WorkingDirectory = Split-Path -Parent $target
    $sc.Description = $desc
    $sc.IconLocation = "$env:SystemRoot\System32\shell32.dll,167"
    $sc.Save()
}

Say "全部檔案都在桌面的「修手機的」資料夾裡" "Green"

$startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
New-Shortcut (Join-Path $startMenu "$APP_NAME.lnk") $launcher "店面接單與維修需求雷達"
Say "開始功能表已建立" "Green"

$startup = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$startupLnk = Join-Path $startup "$APP_NAME.lnk"
Write-Host ""
Say "要開機時自動啟動嗎？（店裡電腦建議開）" "Yellow"
$auto = Read-Host "  開機自動啟動？(Y/n)"
if ($auto -notmatch "^[Nn]") {
    New-Shortcut $startupLnk $launcher "店面接單與維修需求雷達"
    Say "已設定開機自動啟動" "Green"
} else {
    Remove-Item $startupLnk -ErrorAction SilentlyContinue
    Say "沒有設定自動啟動" "DarkGray"
}

# ---------- 5. 完成 ----------
Step "[5/5] 完成"
Write-Host ""
Say "安裝好了。" "Green"
Write-Host ""
Say "• 桌面的「修手機的」資料夾，雙擊裡面的「啟動」就能開" "White"
Say "• 開起來的黑色視窗不要關，關掉程式就停了" "White"
Say "• 要接 LINE、Telegram、粉專、IG：" "White"
Say "  記事本打開 $DEST\config.json 照 README 填" "DarkGray"
Write-Host ""
Say "移除：執行 $DEST\移除.bat（工單資料會問你要不要留）" "DarkGray"
Write-Host ""

Copy-Item (Join-Path $PSScriptRoot "uninstall.ps1") $DEST -Force -ErrorAction SilentlyContinue
@"
@echo off
chcp 65001 >nul
title $APP_NAME - 移除
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1"
"@ | Set-Content -Path (Join-Path $DEST "移除.bat") -Encoding UTF8

$go = Read-Host "  現在啟動嗎？(Y/n)"
if ($go -notmatch "^[Nn]") { Start-Process -FilePath $launcher }
