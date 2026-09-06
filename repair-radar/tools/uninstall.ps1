# 維修接單台 — 移除
$ErrorActionPreference = "SilentlyContinue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$APP_NAME = "維修接單台"
$DEST = Join-Path ([Environment]::GetFolderPath("Desktop")) "修手機的"

Write-Host ""
Write-Host "  移除 $APP_NAME" -ForegroundColor Yellow
Write-Host ""

$db = Join-Path $DEST "data.db"
$keep = $null
if (Test-Path $db) {
    Write-Host "  你有工單資料（data.db）。" -ForegroundColor Cyan
    $ans = Read-Host "  要保留一份到桌面嗎？(Y/n)"
    if ($ans -notmatch "^[Nn]") {
        $keep = Join-Path ([Environment]::GetFolderPath("Desktop")) "維修接單台-資料備份.db"
        Copy-Item $db $keep -Force
        Write-Host "  已存到：$keep" -ForegroundColor Green
    }
}

$confirm = Read-Host "  確定要移除嗎？(y/N)"
if ($confirm -notmatch "^[Yy]") { Write-Host "  取消。"; Read-Host "  按 Enter 關閉"; exit }

foreach ($f in @(
    (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\$APP_NAME.lnk"),
    (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup\$APP_NAME.lnk")
)) { Remove-Item $f -Force }
Write-Host "  捷徑已移除" -ForegroundColor Green

Start-Process powershell -ArgumentList @(
    "-NoProfile", "-WindowStyle", "Hidden", "-Command",
    "Start-Sleep -Seconds 2; Remove-Item -Recurse -Force '$DEST'"
)
Write-Host "  程式檔案將在幾秒後移除" -ForegroundColor Green
Write-Host ""
Write-Host "  移除完成。Python 沒有被移除（其他程式可能會用到）。" -ForegroundColor DarkGray
if ($keep) { Write-Host "  你的資料備份在：$keep" -ForegroundColor Cyan }
Write-Host ""
Read-Host "  按 Enter 關閉"
