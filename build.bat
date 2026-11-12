@echo off
rem Builds the release zip: build\FortniteChestTracker-vX.Y.Z.zip
rem Needs: .NET 10 SDK, Python 3.12 + "pip install pyinstaller pillow"
setlocal
cd /d "%~dp0"
set VERSION=2.0.0

echo [1/3] ChestCounter.exe (replay reader, .NET single file)
rem no debug info / no local paths in the binaries (applies to the vendor projects too)
dotnet publish src\ChestCounter -c Release -o build\cc -p:DebugType=none -p:DebugSymbols=false ^
  -p:ContinuousIntegrationBuild=true -p:Deterministic=true "-p:PathMap=%~dp0=\src\" || exit /b 1

echo [2/3] FortniteChestTracker.exe (window + tracker, PyInstaller)
python -m PyInstaller --noconfirm --onefile --windowed --name FortniteChestTracker ^
  --icon "%~dp0app\icon.ico" --add-data "%~dp0app\icon.ico;." ^
  --add-data "%~dp0app\site_template.html;." --add-data "%~dp0app\i18n.js;." --hidden-import webpage ^
  --distpath build\dist --workpath build\pyi --specpath build app\main.py || exit /b 1

echo [3/3] zip
set OUT=build\release\FortniteChestTracker
if exist build\release rmdir /s /q build\release
mkdir %OUT%
copy /y build\dist\FortniteChestTracker.exe %OUT%\ >nul
copy /y build\cc\ChestCounter.exe %OUT%\ >nul
copy /y LICENSE %OUT%\ >nul
copy /y THIRD_PARTY_NOTICES.md %OUT%\ >nul
powershell -NoProfile -Command "Compress-Archive -Force -Path 'build\release\FortniteChestTracker' -DestinationPath 'build\FortniteChestTracker-v%VERSION%.zip'"
echo Done: build\FortniteChestTracker-v%VERSION%.zip
