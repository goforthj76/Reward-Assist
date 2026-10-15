# Reward Assist Wake Relay — local preview

This Android companion receives narrowly scoped wake requests and broadcasts a Wake-on-LAN packet on the tablet's Wi-Fi network. It cannot access the user's vault or restaurant credentials. The PC must already support local Wake-on-LAN.

## Current validation

- Java sources compile; the user built the APK on Windows successfully.
- APK signature verified using v2 and v3 signing.
- Wake packet and server ownership, expiry, replay, rate-limit and revocation tests pass.
- Tablet installation, screen-off reachability, production backend integration and the updated iPhone build are still pending. This is not yet a released working feature.

## Setup after deployment and the updated iPhone build

1. Install `build/Reward-Assist-Wake-Relay.apk` on the Android tablet.
2. Keep the PC awake with Reward Assist phone requests enabled.
3. On iPhone, open Computer tasks → Wake from anywhere. Select the PC and create a pairing key.
4. Enter the key and that PC's Ethernet MAC address in the tablet companion. Enable the relay.
5. Confirm Tablet online on iPhone. Test while the PC is sleeping and the iPhone uses cellular data.
6. Wait for Computer online before starting a task. “Signal sent” alone does not confirm waking.

Keep the tablet powered on, connected to home Wi-Fi and charged. Open and enable the relay again after restarting Android. Android battery restrictions may delay polling; test with the screen off before relying on this remotely. Do not turn the tablet fully off.

The preview signing key stays in ignored `build/preview.jks`. Preserve it for compatible updates. Pairing keys expire after 90 days and can be revoked from iPhone. No router port forwarding is needed.
