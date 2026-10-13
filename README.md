# Reward Assist

Reward Assist brings account details, reward QR cards and birthday reminders together with a native iPhone wallet and a Windows companion for supported website and Android setup.

**[Download Reward Assist](https://goforthj76.github.io/Reward-Assist/)** · [Release notes](https://github.com/goforthj76/Reward-Assist/releases/tag/v0.5.42)

## Repository layout

- The root contains the published download website and web wallet.
- `desktop/` contains the Windows companion, installer, browser helper, local interface, and build scripts.
- `ios/` contains the native iPhone app.
- `server/` contains the encrypted phone-request relay.
- Download current binaries from Releases; executable copies in the repository root are legacy builds.

## Privacy

Local profiles and QR snapshots are intentionally excluded from Git. Optional Taco Bell gift card details are entered only for the current checkout. They are excluded from saved profiles, signup tasks, and saved order plans. Credit and debit card details are not automated.

## Building Windows releases

Run `desktop/build.ps1` from PowerShell on Windows. Generated build directories, virtual environments, browser downloads, and user data remain untracked.

## Current preview: Windows 0.5.42 / iPhone 0.3.3 (build 6)

[Download Windows installer](https://github.com/goforthj76/Reward-Assist/releases/download/v0.5.42/Reward-Assist-Setup.exe) · [Download iPhone IPA](https://github.com/goforthj76/Reward-Assist/releases/download/v0.5.42/Reward-Assist.ipa)

1. Close Reward Assist on Windows and run the installer.
2. Reload Rewards Assistant Helper at `chrome://extensions` and confirm **0.5.42**. First-time users should follow the installer's Load unpacked instructions.
3. Import the direct IPA into your compatible sideloading tool. It is a preview, not an App Store installation.
4. Sign into the same Reward Assist account on both devices. Enable **Allow phone requests** in the Windows **Phone connection** tab, then choose your computer on iPhone.

Keep the computer awake, online and running Reward Assist. Android workflows also need an authorized, connected Android device. Remote power-on is not included.

### New in this preview (0.5.42)

- Fixes Nothing Bundt Cakes birthday day selection by waiting for day choices to populate after selecting the month, and validates the full date before submission.
- Independent Bundtastic Rewards enrollment even when bakery dropdown options take time to load.
- Automatically resumes signup from login screen after logout if an account was already signed in.
- Accepts formatted phone numbers on the signup form.
- Actionable feedback and specific attention reasons (birthday, logout, rewards, fields, validation) when human review is required.
- Activity shows recorded computer-task stages and dated account history.
- iPhone wallet sorts by newest known account creation date; historical unknown dates appear last.
- New confirmed Nothing Bundt Cakes signups sync a two-hour countdown and optional local reminder.
- Completed phone tasks sync accounts automatically.

### Recovery improvements

- Fixes incorrect page/service version warnings.
- Adds phone cancellation and **Stop abandoned web tasks and clear queue** on Windows.
- Preserves completed signup status when Chrome closes. Cancellation does not undo submitted accounts or orders; check previous results before retrying.
- Attempts to sign out of an existing Nothing Bundt Cakes session before signup.
- Includes the 7-Eleven logo and its **Set up with Dutch Bot** label.

Validation: 15 Python regression tests and relay checks passed; the iPhone build succeeded. Full restaurant flows still need live testing. See [Terms of Use](https://goforthj76.github.io/Reward-Assist/terms.html).

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
