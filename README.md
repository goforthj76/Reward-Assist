# Reward Assist

Reward Assist brings account details, reward QR cards and birthday reminders together with a native iPhone wallet and a Windows companion for supported website and Android setup.

**[Download Reward Assist](https://goforthj76.github.io/Reward-Assist/)** · [Release notes](https://github.com/goforthj76/Reward-Assist/releases/tag/v0.5.45)

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

## Current preview: Windows 0.5.45 / iPhone 0.3.9 (build 18)

[Download Windows installer](https://github.com/goforthj76/Reward-Assist/releases/download/v0.5.45/Reward-Assist-Setup.exe) · [Download iPhone IPA](https://github.com/goforthj76/Reward-Assist/releases/download/v0.5.45/Reward-Assist.ipa)

1. Close Reward Assist on Windows and run the installer.
2. Reload Rewards Assistant Helper at `chrome://extensions` and confirm **0.5.45**. First-time users should follow the installer's Load unpacked instructions.
3. Import the direct IPA into your compatible sideloading tool. It is a preview, not an App Store installation.
4. Sign into the same Reward Assist account on both devices. Enable **Allow phone requests** in the Windows **Phone connection** tab, then choose your computer on iPhone.

### Remote Power & Wake (Wake-on-LAN)

- **Wake Computer button on iPhone**: Wake your sleeping Windows PC over local Wi-Fi from both the *Computer Sync* and *Computer Tasks* views.
- **Ethernet MAC Detection**: The Windows app automatically detects and displays your PC's Ethernet MAC address in the *Phone connection* tab for easy entry on iPhone.
- **Automated Android Screen Wake & Sleep**: ADB tasks automatically wake the Android device screen when a task begins, and return it to sleep when finished or cancelled.

### Android Device Configuration

To let Reward Assist wake your phone and automate app tasks:
1. **Developer Options**: Open Android **Settings** → **About phone** → tap **Build number** 7 times until developer options are unlocked.
2. **Enable USB Debugging**: Go to **Settings** → **System** (or Additional Settings) → **Developer options** → toggle **USB debugging** ON.
3. **Authorize Computer**: Plug the Android phone into the Windows PC via USB cable. When the "Allow USB debugging?" dialog appears on the phone, check **"Always allow from this computer"** and tap **Allow**.
4. **Lock Screen Setting**: Change your screen lock to **Swipe** or **None** (Settings → Security / Lock screen), or in Developer options enable **"Stay awake while charging"**. Automated restaurant apps cannot navigate past a PIN, password, or fingerprint lock screen without manual input.

### Wireless / Wi-Fi Wake Instructions (WoWLAN)

If your computer connects via Wi-Fi rather than an Ethernet cable, Wake-on-LAN requires Wake-on-Wireless-LAN (WoWLAN) support:
1. **Device Manager**: Press `Win + X` → open **Device Manager** → expand **Network adapters** → double-click your Wi-Fi adapter (e.g. Intel Wi-Fi 6, Realtek 8821CE).
2. **Power Management**: Click the **Power Management** tab. Check **"Allow this device to wake the computer"** and **"Only allow a magic packet to wake the computer"**.
3. **Advanced Adapter Settings**: Click the **Advanced** tab. Enable **Wake on Magic Packet**, **Wake on Pattern Match**, and **WoWLAN** (if listed).
4. **Turn Off Windows Fast Startup**: Fast Startup hibernates the kernel and turns off Wi-Fi card power. Open **Control Panel** → **Power Options** → **"Choose what the power buttons do"** → click **"Change settings that are currently unavailable"** → uncheck **"Turn on fast startup"** (or run `powercfg -h off` in an administrator command prompt).
5. **BIOS / Motherboard**: During boot, press `Del` or `F2` to enter BIOS. Under **Advanced / ACPI / APM Configuration**, enable **"PCIe / PME Wake"** and **"Wake on LAN / WLAN"**.
6. **Smart Plug Fallback**: If your Wi-Fi card shuts off completely in sleep mode, configure your motherboard BIOS setting **"Restore AC Power Loss"** to **"Power On"** and plug your PC into a smart plug (e.g., Kasa/Tapo). Toggling the smart plug powers the PC on reliably from anywhere.

### Remote Wake Away From Home (Tailscale Setup)

To wake your computer when you are out of the house on cellular data (LTE/5G) using **Tailscale**:

1. **How It Works**: Tailscale creates a secure, encrypted personal network between your devices without opening router ports. Because a sleeping PC's operating system is suspended, you need one device at home on your Wi-Fi to act as a **Subnet Router** to deliver the wake packet to your PC's Ethernet card.
2. **Setting Up the Home Subnet Router**:
   - **Using an Apple TV (Easiest)**: Install the Tailscale app on your Apple TV from the tvOS App Store. Sign in, and enable **"Run as Exit Node / Subnet Router"**.
   - **Using the Connected Android Device**: Install Tailscale from Google Play on your connected Android phone. Sign in with the same account, tap the three dots → **Settings** → enable **Subnet Routing** for your home subnet (e.g., `192.168.4.0/24`).
   - **In Tailscale Admin Console**: Go to [login.tailscale.com/admin/machines](https://login.tailscale.com/admin/machines), click the three dots next to your subnet router device → **Edit route settings** → approve the subnet route.
3. **On Your iPhone**:
   - Install **Tailscale** from the App Store and sign in with the same account.
   - Toggle Tailscale **Connected**.
   - Open **Reward Assist** → tap **Wake computer now**. The wake broadcast packet will route through your home Tailscale subnet router directly to your PC, turning it on from anywhere!

### Recent fixes & improvements (0.5.42 - 0.5.43)

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

