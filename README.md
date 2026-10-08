# Reward Assist

Reward Assist combines a mobile-friendly account and rewards dashboard with a Windows companion for guided Android setup through ADB.

## Repository layout

- The root contains the published landing/mobile web app and current Windows downloads.
- `desktop/` contains the Windows companion, installer, browser helper, local interface, and build scripts.
- `Reward-Assist-Setup.exe` is the current Windows installer.
- `Reward-Assist-Windows.exe` is the current portable Windows companion.

## Privacy

Local profiles and QR snapshots are intentionally excluded from Git. Optional Taco Bell gift card details are entered only for the current checkout. They are excluded from saved profiles, signup tasks, and saved order plans. Credit and debit card details are not automated.

## Building Windows releases

Run `desktop/build.ps1` from PowerShell on Windows. Generated build directories, virtual environments, browser downloads, and user data remain untracked.

## Windows v0.5.22

[Download installer](https://github.com/goforthj76/Reward-Assist/releases/download/v0.5.22/Reward-Assist-Setup.exe) · [Download portable app](https://github.com/goforthj76/Reward-Assist/releases/download/v0.5.22/Reward-Assist-Windows.exe)

Close all older Reward Assist windows before installing. This release corrects the version label and disables caching of the local app UI.
