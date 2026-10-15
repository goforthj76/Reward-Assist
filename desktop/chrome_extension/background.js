const LOCAL = "http://127.0.0.1:8768";

async function refreshHelpers() {
  const tabs = await chrome.tabs.query({url: ["https://www.tacobell.com/*", "https://order.wendys.com/*"]});
  for (const tab of tabs) {
    if (tab.id) chrome.scripting.executeScript({target: {tabId: tab.id}, files: ["content.js"]}).catch(() => {});
  }
  const bundtTabs = await chrome.tabs.query({url: "https://www.nothingbundtcakes.com/customer/account/*"});
  for (const tab of bundtTabs) {
    if (tab.id) chrome.scripting.executeScript({target:{tabId:tab.id},files:["bundt.js"]}).catch(() => {});
  }
  const cheeseTabs = await chrome.tabs.query({url:"https://www.thecheesecakefactory.com/account/signup*"});
  for (const tab of cheeseTabs) if (tab.id) chrome.scripting.executeScript({target:{tabId:tab.id},files:["cheesecake.js"]}).catch(()=>{});
  const frogTabs = await chrome.tabs.query({url:["https://accounts.spendgo.com/Authenticate/sweetfrog*","https://member.spendgo.com/sweetfrog/*"]});
  for(const tab of frogTabs) if(tab.id) chrome.scripting.executeScript({target:{tabId:tab.id},files:["sweetfrog.js"]}).catch(()=>{});
  const einsteinTabs = await chrome.tabs.query({url:"https://orders.einsteinbros.com/*"});
  for(const tab of einsteinTabs) if(tab.id) chrome.scripting.executeScript({target:{tabId:tab.id},files:["einstein.js"]}).catch(()=>{});
  const localTabs = await chrome.tabs.query({url: "http://127.0.0.1:8768/*"});
  for (const tab of localTabs) {
    if (tab.id) chrome.scripting.executeScript({target: {tabId: tab.id}, files: ["local_bridge.js"]}).catch(() => {});
  }
}

refreshHelpers().catch(() => {});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "open_tab" && /^https:\/\/(www\.tacobell\.com|order\.wendys\.com)\//.test(message.url || "")) {
    chrome.tabs.create({url: message.url, active: false}).then(() => sendResponse({ok: true}));
    return true;
  }
  if (!message || !["task", "status"].includes(message.type)) return false;
  if ((message.app || message.payload?.app) === "Nothing Bundt Cakes" &&
      !/^https:\/\/www\.nothingbundtcakes\.com\/customer\/account\//.test(sender.url || "")) return false;
  if ((message.app || message.payload?.app) === "The Cheesecake Factory" &&
      !/^https:\/\/www\.thecheesecakefactory\.com\/account\/signup(?:[?#]|$)/.test(sender.url || "")) return false;
  if ((message.app || message.payload?.app) === "sweetFrog" &&
      !/^https:\/\/(?:accounts\.spendgo\.com\/Authenticate\/sweetfrog(?:[?#]|$)|member\.spendgo\.com\/sweetfrog\/)/.test(sender.url || "")) return false;
  if ((message.app || message.payload?.app) === "Einstein Bros. Bagels" && !String(sender.url||"").startsWith("https://orders.einsteinbros.com/")) return false;
  const action = message.type === "task"
    ? fetch(`${LOCAL}/api/extension/task?app=${encodeURIComponent(message.app)}`).then(r => r.json())
    : fetch(`${LOCAL}/api/extension/status`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(message.payload),
      }).then(r => r.json());
  action.then(sendResponse).catch(error => sendResponse({error: error.message}));
  return true;
});
