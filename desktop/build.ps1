$ErrorActionPreference = 'Stop'
$Python = 'C:\Users\gofor\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$Project = Split-Path -Parent $MyInvocation.MyCommand.Path
$Venv = Join-Path $Project '.venv'

if (-not (Test-Path -LiteralPath (Join-Path $Venv 'Scripts\python.exe'))) {
    & $Python -m venv $Venv
}

$VenvPython = Join-Path $Venv 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath (Join-Path $Venv 'Scripts\pyinstaller.exe'))) {
    & $VenvPython -m pip install --disable-pip-version-check pyinstaller
}
& $Python -c "from PIL import Image; Image.open(r'$(Join-Path $Project '..\icon-512.png')').save(r'$(Join-Path $Project 'reward-assist.ico')', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"
& $VenvPython -m PyInstaller --noconfirm --clean --onefile --console `
    --name 'Dutch Bros Setup' `
    --distpath (Join-Path $Project 'dist') `
    --workpath (Join-Path $Project 'build-dutch') `
    --specpath $Project `
    (Join-Path $Project 'dutch_bros_signup_assistant.py')
& $VenvPython -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name 'Rewards Assistant' `
    --icon (Join-Path $Project 'reward-assist.ico') `
    --distpath (Join-Path $Project 'dist') `
    --workpath (Join-Path $Project 'build') `
    --specpath $Project `
    --add-data "$(Join-Path $Project 'demo');demo" `
    --add-data "$(Join-Path $Project '..\icon-192.png');demo" `
    --add-data "$(Join-Path $Project 'chrome_extension');chrome_extension" `
    --add-binary "$(Join-Path $Project 'dist\Dutch Bros Setup.exe');." `
    (Join-Path $Project 'local_app.py')
& $VenvPython -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name 'Reward Assist Setup' `
    --icon (Join-Path $Project 'reward-assist.ico') `
    --distpath (Join-Path $Project 'dist') `
    --workpath (Join-Path $Project 'build-setup') `
    --specpath $Project `
    --add-data "$(Join-Path $Project 'chrome_extension');chrome_extension" `
    --add-binary "$(Join-Path $Project 'dist\Rewards Assistant.exe');." `
    (Join-Path $Project 'setup_app.py')
