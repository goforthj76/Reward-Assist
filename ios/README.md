# Native iPhone plan and build status

The source preview is SwiftUI, not a web-page wrapper. It now includes an encrypted local account/QR wallet, password reveal with device authentication, app lock, favorites pinned on Home, search, a birthday calendar, expiration dates, local expiration reminders, full-screen QR images and undoable used markers. Activity and Computer remain clearly unavailable placeholders. Cloud wallet sync and computer pairing are not connected. No IPA has been compiled or device-tested yet.

## Build
The manual GitHub Actions workflow in `.github/workflows/ios-preview.yml` uses a hosted Mac, Xcode and XcodeGen to produce `Reward-Assist-unsigned.ipa`. SideStore must sign it during installation. A Windows machine alone cannot run Xcode. GitHub authorization needs permission to add workflows before this build configuration can be pushed. Run the manual workflow and download its artifact, then extract the IPA.

## Implementation sequence
1. Build and sideload the native preview; test launch, tabs and local notification permission on the actual installation method.
2. Implement account sign-in with Keychain session storage and encrypted vault compatibility tests against the existing browser format. Never overwrite desktop data with an incompatible model. Add QR import, full-screen QR display, favorites, search, biometric reveal, and deletion.
3. Add a versioned Cloudflare queue and a Windows companion. Pair devices with a short-lived single-use approval code. Validate ownership on every request. Show last-seen and readiness, not a guessed online status.
4. Queue only allowlisted actions with immutable IDs, expiration, cancellation, leases, acknowledgement and duplicate-submission protection. Do not expose a remote shell. Require specific order authorization and preserve third-party verification checks.
5. Stream progress while the phone is open; prompt for a code tied to its exact task. Never put codes, credentials or profile details in diagnostic reports or notification previews.
6. Add remote notifications only with supported signing/APNs entitlement and server credentials. Keep in-app activity reliable independently of push delivery. LiveContainer explicitly does not support remote push.

## Useful features
- Phone-only: saved QR wallet, search/favorites, local birthday/expiry reminders, pickup preferences, restaurant links and manual account management.
- Paired computer: start a supported workflow, view status, supply a verification code, cancel queued work, inspect sanitized errors and retry safely.
- Later: share-sheet QR import, widgets, Siri shortcuts, purchase summaries, optional nearby-place discovery, native accessibility and dark mode.

## Power and execution limits
An online computer with the companion active can start a queued task promptly. A logged-out or locked desktop may not be usable for browser automation. Offline requests wait until reconnection. Sleep wakeup requires separately configured supported hardware and a reachable wake mechanism. A fully off machine cannot execute a task; cloud execution would be a separate service and cannot use a locally connected Android phone.

Keep the working Home Screen web app until a replacement IPA passes real-device testing. Do not advertise planned features as implemented. Local reminders need testing under both SideStore and LiveContainer; native cross-app automation is not permitted by ordinary iOS sandboxing.

Sources:
- https://github.com/LiveContainer/LiveContainer
- https://docs.sidestore.io/docs/faq
- https://developer.apple.com/documentation/usernotifications/pushing-background-updates-to-your-app
- https://support.apple.com/en-au/guide/security/sec15bfe098e/web
