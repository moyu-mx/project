# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置。"""
from pathlib import Path

block_cipher = None
root = Path(SPECPATH).resolve().parent

datas = [
    (str(root / "web" / "templates"), "web/templates"),
    (str(root / "web" / "static"), "web/static"),
    (str(root / "config"), "config"),
    (str(root / "prompts"), "prompts"),
    (str(root / "sql" / "schema.sql"), "sql"),
]

for optional, dest in [
    (root / "data" / "superstore.db", "data"),
    (root / "data" / "cleaned" / "superstore_clean.csv", "data/cleaned"),
    (root / "results" / "forecast_report.json", "results"),
]:
    if optional.is_file():
        datas.append((str(optional), dest))

charts_dir = root / "results" / "charts"
if charts_dir.is_dir():
    datas.append((str(charts_dir), "results/charts"))

hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.importer",
    "multipart",
    "sqlalchemy.dialects.sqlite",
    "sklearn.utils._cython_blas",
    "sklearn.neighbors._partition_nodes",
    "sklearn.tree._utils",
    "web.app",
    "web.chart_insights",
    "web.dashboard_charts",
    "src.agents.anomaly_detect",
    "src.agents.config",
    "src.agents.insight_builder",
    "src.agents.insight_data",
    "src.agents.insight_engine",
    "src.agents.report_builder",
    "src.agents.report_data",
    "src.llm.chat_engine",
    "src.llm.chat_pipeline",
    "src.analysis.forecast",
]

a = Analysis(
    [str(root / "run_app.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "tkinter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SuperstoreAnalytics",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SuperstoreAnalytics",
)
