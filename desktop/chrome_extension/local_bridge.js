const BRIDGE_VERSION = "0.5.3";
if (window.__rewardsBridgeVersion !== BRIDGE_VERSION) {
  window.__rewardsBridgeVersion = BRIDGE_VERSION;
document.addEventListener("rewards-open-tab", () => {
  const url = document.documentElement.dataset.rewardsOpenUrl || "";
  try {
    if (url && globalThis.chrome?.runtime?.id) {
      chrome.runtime.sendMessage({type: "open_tab", url}, () => void chrome.runtime.lastError);
    }
  } catch (_) {
    // A newly reloaded extension reinjects a fresh bridge automatically.
  }
});
}
