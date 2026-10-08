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

## Optional Taco Bell gift card (0.5.10)

In the Windows Taco Bell paste box, put these fields before END:

```text
first_name: Scott
last_name: Smith
email: scott@example.com
zip_code: 75022
birthday: 2000-10-08
gift_card_number: YOUR_CARD_NUMBER
gift_card_pin: YOUR_PIN
END
```

Replace the placeholders with a Taco Bell gift card number and its 3- or 8-digit
PIN. Spaces and hyphens in the number are accepted; leading zeroes are preserved.
Select the connected Android device, choose the account currently signed in on
that device, select the reward and pickup plan, and click **Prepare order on Android**.
For multiple pasted accounts, select the matching account explicitly. Reward Assist
cannot independently verify which account owns the current Android checkout.

The helper also handles an already-open checkout or gift card form. It enters the
card and presses ADD GIFT CARD, then asks you to verify the selected payment method
and remaining total in Taco Bell. It never presses PLACE ORDER. If Taco Bell changes
its form or rejects the card, review the official app before retrying. A submitted
card is not a guarantee that it was accepted or selected for payment.

Gift card fields stay in the paste box for the current session, but are not included
in saved profiles, signup tasks, cloud requests, or saved order plans. Close the
window or clear the paste box when finished. Taco Bell may save a card you add there.

Validation: five Python tests cover validation, field verification, rejection, and
wrong-app protection. JavaScript checks cover parsing, account selection, leading
zeroes, and exclusion from saved plans. Live ADB inspection confirmed the form and
dummy field entry. The final retry-clearing revision and actual card acceptance
still need a connected-device check; no real gift card or order was submitted.


# Reward Assist 0.5.12 — one person at a time

1. Close the previous Reward Assist window and open Reward-Assist-GiftCard.exe.
2. Choose Taco Bell and paste a complete block for each person, with END after each block. Each person keeps their own name, birthday, and different email.
3. Optional gift cards go in that person's block before END:

```text
gift_card_number: YOUR_CARD_NUMBER
gift_card_pin: YOUR_PIN
END
```

4. Select the connected Android device and reward. Click Start guided setup. Only the first person's signup starts.
5. Complete their website verification and terms review. Then sign into that same account in the Android app.
6. Choose the pickup details, check the account/checkout confirmation box, and click Prepare order on Android. The helper enters that person's gift card, if supplied.
7. Review the gift card, pickup store, and total in Taco Bell. Place or cancel the order there.
8. Sign out of the previous person's account on the website and Android app. Click **This person is finished — Next person** to start the next signup. After the last person, this button finishes the group.

**End group** stops the website helper and unlocks the paste box. Card details stay in the current window but are excluded from saved signup tasks, profiles, and saved order plans. Clear the box or close the window when finished.

The app does not automatically place orders or clear Android app data. MAIN now starts Android email sign-in; verification remains manual. The different-email requirement remains. Taco Bell controls account eligibility and gift-card acceptance.

Validation: seven Python tests and JavaScript checks pass. A headless Chrome test verified two sequential people, separate gift cards, checkout confirmation, no automatic advancement, and group completion using mocked API responses. Actual restaurant signup, gift-card acceptance, and order submission were not exercised. ADB access to both devices was restored.


## MAIN and pickup location (0.5.13)

Click MAIN to start the current person's website signup. After website completion, the app opens Taco Bell on the selected Android device, fills the same email on the observed email Sign In form, and presses NEXT. Complete verification or other authentication prompts on the Android device. This is not a guarantee of completed sign-in. If the form is not available, sign out of the previous person, open email Sign In, and click Retry Android sign-in. Gift cards and the manual Next person flow remain available.

Location formats: a street address with city/state, a city/state such as Flower Mound, TX, or a ZIP such as 75022. This is search text, not a verified store ID. The existing helper can select a search result; always verify the actual pickup address in Taco Bell before placing the order. No in-app store dropdown was added.

Nine Python tests and the browser sequence test passed. The Android email form was inspected live, but a real authentication attempt and final verification were not performed. No real gift card or order was submitted.


## Simpler pickup layout (0.5.14)

The Taco Bell section now uses three numbered steps. The When list scrolls through ASAP and 96 quarter-hour times. Choose the restaurant’s local time; listed times are choices, not confirmed availability. Gift-card instructions and recovery actions are expandable. The unsupported additional-menu-item field is hidden and no longer restored from old saved plans. Browser checks verify 97 options and that 3:15 PM reaches the order plan. The updated layout was visually inspected.
