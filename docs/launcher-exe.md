# Windows one-click launcher

Double-click `XingMuLauncher.exe` in the project root. It runs the existing
`启动项目.bat`, waits for the API and website to become ready, then opens the
site in the default browser. Keep the EXE in the project root beside the BAT
file. The project Python environment, Node.js, web dependencies, and model
files are still required.

If startup fails, the BAT window stays open with the error. Stop the website
with `停止项目.bat`.

To rebuild the EXE after changing its source:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_launcher.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test_launcher.ps1
```

`XingMuLauncher.exe --check` verifies that the adjacent start script exists
without starting services.
