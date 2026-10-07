# Rewards Assistant

A Windows desktop dashboard for consent-based setup of Dutch Bros, Taco Bell,
and Wendy's reward accounts on one USB-connected Android device.

## Run from source

```powershell
& 'C:\Users\gofor\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' 'C:\Users\gofor\Documents\Codex\2026-08-06\wh\outputs\rewards_assistant\rewards_assistant.py'
```

Profiles are encrypted with Windows DPAPI and stored for the current Windows
account under `%LOCALAPPDATA%\RewardsAssistant`. Verification codes are never
stored. Dutch Bros uses the existing guided automation. Taco Bell and Wendy's
currently provide verified install/open support and await supervised UI mapping.

## Build the executable

Run `build.ps1`. The executable is written to `dist\Rewards Assistant.exe`.
