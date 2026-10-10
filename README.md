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

## Windows v0.5.31

[Download installer](https://github.com/goforthj76/Reward-Assist/releases/download/v0.5.31/Reward-Assist-Setup.exe) · [Download portable app](https://github.com/goforthj76/Reward-Assist/releases/download/v0.5.31/Reward-Assist-Windows.exe)

Close all older Reward Assist windows before installing. This release corrects the version label and disables caching of the local app UI.

### Nothing Bundt Cakes website test

MAIN fills one signup form, including both passwords and Bundtastic Rewards enrollment. Review and submit in Chrome; successful account creation is not yet detected. SMS marketing is not changed. Reload the updated Chrome helper after installing.

```text
first_name: Test
last_name: Example
email: YOUR_EMAIL
phone: YOUR_10_DIGIT_PHONE
zip_code: 75022
birthday: 2000-01-15
password: YOUR_PASSWORD
country: United States
state: Texas
bakery: Flower Mound, TX
END
```

Use the exact country, state and bakery names from the official website. Password is held temporarily in memory for this flow, not written to its session files.
