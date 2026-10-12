# Phone requests — private test preview

This preview starts signup workflows, reports stages and forwards verification codes. It does not remotely complete Taco Bell pickup/payment, approve review screens, or wake a sleeping computer.

1. Run the matching desktop preview and sign into Reward Assist. Finish any local task, then enable **Phone requests** at the bottom. Keep this window open and the computer awake.
2. Install the matching iPhone IPA as an update in your existing sideload environment. Preserve the existing app data.
3. Open Computer, sign in with the same Reward Assist account and sync. Choose **Start a computer task**.
4. Choose the computer whose short ID matches the desktop. Paste one authorized person's details and explicitly authorize setup.
5. Start once. When prompted, send the verification code. Review-required means continue on the computer.
6. Sync the wallet after completion. Only accounts actually saved by the desktop can be downloaded.

Requests expire after 15 minutes before starting. Interrupted active jobs do not automatically restart. The computer must stay open and signed in; remote push notifications are not supported under LiveContainer. New tasks are disabled each time the desktop window opens. Disabling requests does not cancel an already-running signup.

Validation: relay unit checks cover account isolation, offline rejection, retry IDs, claim-once behavior, one active job per computer, code consumption and ciphertext cleanup. End-to-end phone testing remains required; no live signup was submitted during development.
