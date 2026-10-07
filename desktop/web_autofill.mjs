import { createRequire } from "node:module";
import { existsSync, mkdirSync, readFileSync, unlinkSync, writeFileSync } from "node:fs";
import process from "node:process";

const require = createRequire(import.meta.url);
const moduleRoot = process.env.REWARDS_NODE_MODULES;
if (!moduleRoot) throw new Error("REWARDS_NODE_MODULES is not configured");
const { chromium } = require(`${moduleRoot}/playwright`);

let input = "";
for await (const chunk of process.stdin) input += chunk;
const request = JSON.parse(input);
const app = request.app;
const details = request.details;
const statusFile = request.statusFile;
const codeFile = request.codeFile;
const approveFile = request.approveFile;
function setStatus(stage, message) {
  writeFileSync(statusFile, JSON.stringify({ stage, message, updatedAt: new Date().toISOString() }));
}
const urls = {
  "Taco Bell": "https://www.tacobell.com/register/yum",
  "Wendy's": "https://order.wendys.com/us/en/sign-in?lang=en_US&tab=offers",
};
if (!urls[app]) throw new Error("Unsupported web rewards program");

mkdirSync(request.profileDir, { recursive: true });
const context = await chromium.launchPersistentContext(request.profileDir, {
  executablePath: request.browserPath,
  headless: false,
  chromiumSandbox: true,
  viewport: null,
  args: ["--start-maximized"],
});
const pages = context.pages();
const page = pages[0] || await context.newPage();
await page.goto(urls[app], { waitUntil: "domcontentloaded", timeout: 60000 });

async function clickSignupIfPresent() {
  const candidates = [
    page.getByRole("link", { name: /sign up|join rewards|create account/i }),
    page.getByRole("button", { name: /sign up|join rewards|create account/i }),
    page.getByText(/sign up now/i),
  ];
  for (const candidate of candidates) {
    const item = candidate.first();
    if (await item.isVisible().catch(() => false)) {
      await item.click().catch(() => {});
      await page.waitForTimeout(800);
      return;
    }
  }
}

async function dismissCookieBanner() {
  const choices = [
    page.getByRole("button", { name: /reject non-essential/i }),
    page.getByRole("button", { name: /^agree$/i }),
  ];
  for (const choice of choices) {
    const item = choice.first();
    if (await item.isVisible().catch(() => false)) {
      await item.click().catch(() => {});
      await page.waitForTimeout(250);
      return true;
    }
  }
  return false;
}

async function fillFirstVisible(selectors, value) {
  if (!value) return false;
  for (const selector of selectors) {
    const locator = typeof selector === "string" ? page.locator(selector) : selector;
    const count = await locator.count().catch(() => 0);
    for (let index = 0; index < count; index += 1) {
      const field = locator.nth(index);
      if (await field.isVisible().catch(() => false) && await field.isEditable().catch(() => false)) {
        const current = await field.inputValue().catch(() => "");
        if (!current) await field.fill(value);
        await field.press("Tab").catch(() => {});
        await field.evaluate((element) => {
          element.style.outline = "3px solid #35aee4";
          element.style.outlineOffset = "2px";
        }).catch(() => {});
        return true;
      }
    }
  }
  return false;
}

async function fillVisibleFields() {
  await fillFirstVisible([
    page.getByLabel(/email/i), page.getByPlaceholder(/email/i),
    'input[type="email"]', 'input[name*="email" i]', 'input[id*="email" i]'
  ], details.email);
  await fillFirstVisible([
    page.getByLabel(/first name/i), page.getByPlaceholder(/first name/i),
    'input[name*="first" i]', 'input[id*="first" i]'
  ], details.first_name);
  await fillFirstVisible([
    page.getByLabel(/last name/i), page.getByPlaceholder(/last name/i),
    'input[name*="last" i]', 'input[id*="last" i]'
  ], details.last_name);
  await fillFirstVisible([
    page.getByLabel(/zip|postal/i), page.getByPlaceholder(/zip|postal/i),
    'input[name*="zip" i]', 'input[name*="postal" i]', 'input[id*="zip" i]'
  ], details.zip_code);
  await fillFirstVisible([
    page.getByLabel(/birth|birthday|date of birth/i), page.getByPlaceholder(/birth|mm\/dd/i),
    'input[name*="birth" i]', 'input[id*="birth" i]'
  ], details.birthday);
}

async function clickProgress(names = /^(confirm|next|continue|verify)$/i) {
  await dismissCookieBanner();
  const candidates = [
    page.getByRole("button", { name: names }),
    page.locator("button").filter({ hasText: names }),
    page.getByRole("link", { name: names }),
  ];
  for (const candidate of candidates) {
    const item = candidate.first();
    if (await item.isVisible().catch(() => false) && await item.isEnabled().catch(() => false)) {
      await item.click();
      await page.waitForTimeout(700);
      return true;
    }
  }
  return false;
}

async function waitAndClickProgress(names, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await clickProgress(names)) return true;
    await page.waitForTimeout(300);
  }
  return false;
}

async function fillVerificationCode(code) {
  const single = page.locator('input[autocomplete="one-time-code"], input[name*="code" i], input[id*="code" i], input[name*="otp" i], input[id*="otp" i]').first();
  if (await single.isVisible().catch(() => false) && await single.isEditable().catch(() => false)) {
    await single.fill(code);
    return true;
  }
  const segments = page.locator('input[inputmode="numeric"], input[type="tel"]');
  const visible = [];
  for (let index = 0; index < await segments.count(); index += 1) {
    const item = segments.nth(index);
    if (await item.isVisible().catch(() => false) && await item.isEditable().catch(() => false)) visible.push(item);
  }
  if (visible.length >= code.length) {
    for (let index = 0; index < code.length; index += 1) await visible[index].fill(code[index]);
    return true;
  }
  return false;
}

async function verificationFieldVisible() {
  return await page.locator(
    'input[autocomplete="one-time-code"], input[name*="code" i], input[id*="code" i], input[name*="otp" i], input[id*="otp" i]'
  ).first().isVisible().catch(() => false);
}

async function visibleDeliveryError() {
  const errors = page.getByText(
    /email didn't send|email did not send|connection issue|unable to send|could not send|something went wrong|try again/i
  );
  const count = await errors.count().catch(() => 0);
  for (let index = 0; index < count; index += 1) {
    const item = errors.nth(index);
    if (await item.isVisible().catch(() => false)) {
      const message = (await item.innerText().catch(() => "")).replace(/\s+/g, " ").trim();
      if (message) return message;
    }
  }
  return "";
}

async function waitForEmailOutcome(timeoutMs = 25000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const error = await visibleDeliveryError();
    if (error) return { ok: false, error };
    if (await verificationFieldVisible() || await detailsFormVisible()) return { ok: true };
    await page.waitForTimeout(350);
  }
  return { ok: false, error: "The restaurant did not confirm that a verification email was sent." };
}

async function detailsFormVisible() {
  return await page.getByLabel(/first name/i).first().isVisible().catch(() => false)
    || await page.locator('input[name*="first" i], input[id*="first" i]').first().isVisible().catch(() => false);
}

await clickSignupIfPresent();
await dismissCookieBanner();
await fillVisibleFields();
setStatus("email_filled", `Email filled for ${app}; requesting the verification code.`);
const requestedCode = await waitAndClickProgress(/^(confirm|next|continue)$/i);
let stage = "attention";
if (requestedCode) {
  setStatus("sending_email", "Confirm clicked. Waiting for the restaurant to send the verification email.");
  const outcome = await waitForEmailOutcome();
  if (outcome.ok) {
    stage = "waiting_code";
    setStatus(stage, "Verification email sent. Enter the code in Rewards Assistant.");
  } else {
    setStatus(stage, `The restaurant could not send the email: ${outcome.error} Use Retry in the official browser.`);
  }
} else {
  setStatus(stage, "Email was filled, but the Confirm button did not become clickable. Open the assisted browser and review the highlighted field.");
}
console.log(JSON.stringify({ status: stage, app }));

const timer = setInterval(async () => {
  try {
    if (stage === "waiting_code" && existsSync(codeFile)) {
      const code = readFileSync(codeFile, "utf8").trim();
      unlinkSync(codeFile);
      if (!/^\d{4,8}$/.test(code)) {
        setStatus("waiting_code", "The code must contain 4 to 8 digits.");
        return;
      }
      if (!await fillVerificationCode(code)) {
        setStatus("waiting_code", "The verification-code field is not visible yet; retrying.");
        return;
      }
      await waitAndClickProgress(/^(confirm|next|continue|verify|submit)$/i, 10000);
      stage = "filling_details";
      setStatus(stage, "Code entered. Filling the remaining account details.");
    }
    if (stage === "filling_details") {
      await fillVisibleFields();
      if (await detailsFormVisible()) {
        stage = "review_required";
        setStatus(stage, "Details are filled. Review the terms, then approve final account creation here.");
      }
    }
    if (stage === "review_required" && existsSync(approveFile)) {
      unlinkSync(approveFile);
      const boxes = page.locator('input[type="checkbox"]');
      for (let index = 0; index < await boxes.count(); index += 1) {
        const box = boxes.nth(index);
        if (await box.isVisible().catch(() => false) && await box.isEnabled().catch(() => false)) {
          await box.setChecked(true).catch(() => {});
        }
      }
      const submitted = await clickProgress(/^(create account|complete sign up|sign up|confirm|finish)$/i);
      if (submitted) {
        stage = "submitted";
        setStatus(stage, "Final account creation submitted. Waiting for completion.");
      } else {
        setStatus(stage, "The final button is not ready. Review any highlighted required fields.");
      }
    }
    if (stage === "submitted") {
      const url = page.url();
      if (!/register|sign-in|signup/i.test(url)) {
        stage = "complete";
        setStatus(stage, `${app} account setup completed.`);
      }
    }
  } catch (error) {
    setStatus(stage, `Waiting: ${error.message}`);
  }
}, 500);
context.on("close", () => {
  clearInterval(timer);
  process.exit(0);
});
await new Promise(() => {});
