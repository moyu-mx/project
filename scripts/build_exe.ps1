# Build Windows executable
# Usage: .\scripts\build_exe.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Host "venv not found. Run: python -m venv .venv; pip install -r requirements.txt"
    exit 1
}

if (-not (Test-Path "data\superstore.db")) {
    Write-Warning "data\superstore.db missing. Run: python -m src.etl.load_to_db"
}

Write-Host ">> install build deps..."
& $Python -m pip install -q -r requirements-build.txt

Write-Host ">> clean old build..."
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }

Write-Host ">> pyinstaller..."
& $Python -m PyInstaller --noconfirm packaging\superstore.spec

$OutDir = Join-Path $Root "dist\SuperstoreAnalytics"
if (-not (Test-Path $OutDir)) {
    Write-Error "build failed: dist\SuperstoreAnalytics not found"
}

Write-Host ">> copy runtime data..."
$copyItems = @(
    @{ Src = "data\superstore.db"; Dst = "data\superstore.db" },
    @{ Src = "data\cleaned\superstore_clean.csv"; Dst = "data\cleaned\superstore_clean.csv" },
    @{ Src = "results\forecast_report.json"; Dst = "results\forecast_report.json" },
    @{ Src = "results\charts"; Dst = "results\charts" },
    @{ Src = "config"; Dst = "config" }
)
foreach ($item in $copyItems) {
    $srcPath = Join-Path $Root $item.Src
    $dstPath = Join-Path $OutDir $item.Dst
    if (-not (Test-Path $srcPath)) { continue }
    $dstParent = Split-Path -Parent $dstPath
    if (-not (Test-Path $dstParent)) { New-Item -ItemType Directory -Path $dstParent -Force | Out-Null }
    if (Test-Path $srcPath -PathType Container) {
        if (Test-Path $dstPath) { Remove-Item -Recurse -Force $dstPath }
        Copy-Item -Recurse -Force $srcPath $dstPath
    } else {
        Copy-Item -Force $srcPath $dstPath
    }
}

$readmePath = Join-Path $OutDir "README.txt"
@(
    "Superstore Analytics v1.5"
    ""
    "1. Run SuperstoreAnalytics.exe"
    "2. Browser opens http://127.0.0.1:8000"
    "3. Close console window to stop"
    ""
    "Options:"
    "  SuperstoreAnalytics.exe --port 8001"
    "  SuperstoreAnalytics.exe --no-browser"
) | Set-Content -Path $readmePath -Encoding UTF8

Write-Host ""
Write-Host "Done: $OutDir"
Write-Host "Exe:  $OutDir\SuperstoreAnalytics.exe"
