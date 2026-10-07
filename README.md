# Reward Assist

Reward Assist combines a mobile-friendly account and rewards dashboard with a Windows companion for guided Android setup through ADB.

## Repository layout

- The root contains the published landing/mobile web app and current Windows downloads.
- `desktop/` contains the Windows companion, installer, browser helper, local interface, and build scripts.
- `Reward-Assist-Setup.exe` is the current Windows installer.
- `Reward-Assist-Windows.exe` is the current portable Windows companion.

## Privacy

Local profiles and QR snapshots are intentionally excluded from Git. Payment credentials are never stored or automated by Reward Assist.

## Building Windows releases

Run `desktop/build.ps1` from PowerShell on Windows. Generated build directories, virtual environments, browser downloads, and user data remain untracked.
