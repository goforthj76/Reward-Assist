(() => {
  const SCRIPT_VERSION = "0.5.8";
  if (window.__rewardsAssistantRunning === SCRIPT_VERSION) return;
  window.__rewardsAssistantRunning = SCRIPT_VERSION;

  const app = location.hostname.includes("tacobell") ? "Taco Bell" : "Wendy's";
  const ask = message => new Promise(resolve => {
    try {
      if (!chrome.runtime?.id) {
        resolve({error: "Extension was reloaded; refresh this restaurant tab."});
        return;
      }
      chrome.runtime.sendMessage(message, response => {
        const runtimeError = chrome.runtime.lastError;
        resolve(runtimeError ? {error: runtimeError.message} : response);
      });
    } catch (error) {
      resolve({error: error.message});
    }
  });
  const report = (stage, message) => ask({type: "status", payload: {app, stage, message}});
  const visible = element => !!element && element.getClientRects().length > 0;
  const text = element => (element?.textContent || "").replace(/\s+/g, " ").trim();

  function setField(field, value) {
    if (!field || !value || field.value === value) return false;
    const prototype = field instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
    setter ? setter.call(field, value) : (field.value = value);
    field.dispatchEvent(new Event("input", {bubbles: true}));
    field.dispatchEvent(new Event("change", {bubbles: true}));
    field.dispatchEvent(new Event("blur", {bubbles: true}));
    field.style.outline = "3px solid #35aee4";
    return true;
  }

  function field(pattern, extras = "") {
    const inputs = [...document.querySelectorAll(`input${extras}`)];
    return inputs.find(input => {
      const labels = [input.name, input.id, input.placeholder, input.type, input.autocomplete,
        input.getAttribute("aria-label"), document.querySelector(`label[for="${CSS.escape(input.id || "-")}"]`)?.textContent];
      return visible(input) && labels.some(value => pattern.test(value || ""));
    });
  }

  function button(pattern) {
    return [...document.querySelectorAll("button, [role='button'], input[type='submit']")]
      .find(item => {
        const label = `${text(item)} ${item.value || ""}`.trim();
        return visible(item) && !item.disabled && pattern.test(label);
      });
  }

  function dismissCookies() {
    const choice = button(/reject non-essential|^agree$/i);
    if (choice) choice.click();
  }

  function deliveryError() {
    const body = document.body?.innerText || "";
    return /email didn't send|email did not send|connection issue|unable to send|could not send|something went wrong/i.test(body);
  }

  function fillDetails(details) {
    setField(field(/email/i, "[type='email']"), details.email);
    setField(field(/first.?name/i), details.first_name);
    setField(field(/last.?name/i), details.last_name);
    setField(field(/zip|postal/i), details.zip_code);
    const birthday = field(/birth|birthday|date.?of.?birth/i);
    if (birthday && details.birthday) {
      const parts = details.birthday.split("-");
      const hint = `${birthday.placeholder || ""} ${birthday.getAttribute("aria-label") || ""}`;
      const formatted = birthday.type === "date" || parts.length !== 3
        ? details.birthday
        : /MM\s*\/\s*DD/i.test(hint) && !/YYYY/i.test(hint)
          ? `${parts[1]}/${parts[2]}`
          : `${parts[1]}/${parts[2]}/${parts[0]}`;
      setField(birthday, formatted);
    }
  }

  function checkSecondCheckbox() {
    const formCheckboxes = [...document.querySelectorAll("form input[type='checkbox']")];
    const requiredBox = document.querySelector("input#agreement, input[name='agreement']") || formCheckboxes[1];
    if (!requiredBox || requiredBox.checked) return !!requiredBox;
    requiredBox.click();
    if (!requiredBox.checked) {
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "checked")?.set;
      setter ? setter.call(requiredBox, true) : (requiredBox.checked = true);
      requiredBox.dispatchEvent(new Event("input", {bubbles: true}));
      requiredBox.dispatchEvent(new Event("change", {bubbles: true}));
    }
    const label = requiredBox.id
      ? document.querySelector(`label[for="${CSS.escape(requiredBox.id)}"]`)
      : null;
    if (label) label.style.outline = "3px solid #35aee4";
    return requiredBox.checked;
  }

  let emailClicked = false;
  let codeUsed = "";
  let lastFinalSubmit = 0;
  let finalSubmitAttempts = 0;
  let emailLoginContinued = false;
  let completed = false;
  async function tick() {
    const task = await ask({type: "task", app});
    if (task?.error) return;
    if (!task?.active || !task.details) return;
    dismissCookies();
    fillDetails(task.details);

    if (deliveryError()) {
      await report("attention", "The restaurant could not send the email. Use Retry once in normal Chrome or wait before trying again.");
      return;
    }

    const continueEmail = [...document.querySelectorAll("a, button, [role='button']")]
      .find(item => visible(item) && /continue using email to log in/i.test(text(item)));
    if (continueEmail && !emailLoginContinued) {
      emailLoginContinued = true;
      continueEmail.click();
      await report("finishing_login", "Skipped the optional phone number and continued using email to log in.");
      return;
    }

    const authPage = /register|authenticate|sign-in|signup|login\/yum/i.test(location.href);
    if (!authPage && !completed) {
      completed = true;
      const completion = await ask({type: "status", payload: {
        app, stage: "complete", details: task.details,
        message: `${app} setup completed. Login details were encrypted and saved locally.`,
      }});
      if (completion?.next_url) {
        location.assign(completion.next_url);
      }
      return;
    }

    const firstName = field(/first.?name/i);
    if (firstName) {
      fillDetails(task.details);
      checkSecondCheckbox();
      if (!task.approved) {
        await report("review_required", "Birthday is filled as MM/DD and the required second checkbox is selected. Review the official terms, then approve creation in Rewards Assistant.");
        return;
      }
      if (finalSubmitAttempts < 3 && Date.now() - lastFinalSubmit > 4000) {
        const finish = button(/create account|complete sign up|sign up|confirm|finish/i);
        if (finish) {
          lastFinalSubmit = Date.now();
          finalSubmitAttempts += 1;
          finish.scrollIntoView({block: "center"});
          finish.click();
          await report("submitted", "Final Confirm clicked. The assistant will retry if the official page does not advance.");
        }
      } else if (finalSubmitAttempts >= 3) {
        await report("attention", "Final Confirm was clicked three times but the official page did not advance. Check the highlighted form for a validation message.");
      }
      return;
    }

    const codeField = field(/code|otp|one.?time/i);
    if (!codeField && !emailClicked) {
      const next = button(/^(confirm|next|continue)$/i);
      if (next) {
        emailClicked = true;
        next.click();
        await report("sending_email", "Confirm/Next clicked in normal Chrome. Waiting for the verification screen.");
      } else {
        await report("filling_email", "Email filled. Waiting for Confirm/Next to become available.");
      }
      return;
    }

    if (codeField) {
      if (!task.verification_code) {
        await report("waiting_code", "Verification email sent. Enter the code in Rewards Assistant.");
        return;
      }
      if (codeUsed !== task.verification_code) {
        setField(codeField, task.verification_code);
        codeUsed = task.verification_code;
        const verify = button(/^(confirm|next|continue|verify|submit)$/i);
        if (verify) verify.click();
        await report("filling_details", "Verification code entered. Filling the remaining details.");
      }
      return;
    }

  }

  const run = () => tick().catch(error => report("attention", `Extension waiting: ${error.message}`));
  setInterval(run, 700);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) run(); });
  window.addEventListener("focus", run);
  run();
})();
