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

## Windows v0.5.34

[Download installer](https://github.com/goforthj76/Reward-Assist/releases/download/v0.5.34/Reward-Assist-Setup.exe) · [Download portable app](https://github.com/goforthj76/Reward-Assist/releases/download/v0.5.34/Reward-Assist-Windows.exe)

Close all older Reward Assist windows before installing. This release corrects the version label and disables caching of the local app UI.

### Nothing Bundt Cakes website signup

MAIN fills one signup form, including both passwords and Bundtastic Rewards enrollment. Clicks Create Account once and waits for the official registration confirmation. Verification challenges or errors stop for attention. SMS marketing is not changed. Reload the updated Chrome helper after installing.

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

### Cheesecake Factory website beta

Use one details block with first_name, last_name, email, phone, zip_code, birthday (YYYY-MM-DD), password, and restaurant. Example restaurant: `The Shops at Highland Village (Highland Village, TX)`. MAIN requests one SMS code; enter it in Assistant status. The helper fills the profile and selects the exact restaurant. Review the official terms and promotional email/SMS consent before approving creation. Sign Up is clicked once; a 400 error stops for attention. Account completion is not automatically confirmed or saved yet. Password and SMS code remain in a short-lived memory session, not session files. Reload the updated Chrome extension after installation.
