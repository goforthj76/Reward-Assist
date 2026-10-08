// Only the current person's signup goes to the website. Gift cards stay in this window.
let tacoSequence = null;
let tacoSequenceBusy = false;
const sequenceElement = id => document.getElementById(id);

function sequenceMessage(message) {
  sequenceElement('automationPanel').append(sequenceElement('tacoSequencePanel'));
  sequenceElement('tacoSequencePanel').hidden = false;
  sequenceElement('tacoSequenceMessage').textContent = message;
}
function sequenceLock(locked) {
  sequenceElement("manualTacoCheckout").hidden = locked;
  if (!locked) sequenceElement("continueTacoMain").hidden = true;
  for (const selector of ['#detailsBlock', '#tacoBatchBuilder input', '#tacoBatchBuilder button',
      '#tacoBatchBuilder select', '#tacoCheckoutAccount', '#deviceSelect', '.brand']) {
    document.querySelectorAll(selector).forEach(element => element.disabled = locked);
  }
}
async function startTacoSequence() {
  if (tacoSequence || tacoSequenceBusy) return notify('Finish or end the current group first.');
  try {
    const details = tacoBatchText().split(/\nEND(?:\n|$)/).map(text => text.trim()).filter(Boolean);
    const people = parseLooseTacoBlocks();
    if (people.length !== details.length) throw new Error('Import one complete pasted block for each person.');
    if (!sequenceElement('deviceSelect').value) throw new Error('Choose the Android device first.');
    const cards = people.map(person => {
      const number = (person.gift_card_number || '').replace(/[ -]/g, ''), pin = person.gift_card_pin || '';
      if (!number && !pin) return null;
      if (!/^[0-9]{1,32}$/.test(number) || !/^(?:[0-9]{3}|[0-9]{8})$/.test(pin)) throw new Error('Each supplied gift card needs a numeric number and a 3- or 8-digit PIN.');
      return {number, pin};
    });
    tacoSequence = {people, cards, details:details.map(text => text + '\nEND'), index:0,
      serial:sequenceElement('deviceSelect').value, stage:'ready'};
    sequenceLock(true);
    await startSequencePerson();
  } catch (error) {
    sequenceElement('automationPanel').style.display = 'block';
    sequenceElement('automationStatus').textContent = error.message;
    sequenceElement('automationPanel').scrollIntoView({block:'center'});
    notify(error.message);
  }
}
async function startSequencePerson() {
  if (tacoSequenceBusy || !tacoSequence) return;
  tacoSequenceBusy = true;
  const run = tacoSequence, person = run.people[run.index];
  if (statusTimer) clearInterval(statusTimer);
  submissionUrl = '';
  for (const id of ['submissionButton', 'codeControls', 'approveButton']) sequenceElement(id).style.display = 'none';
  sequenceElement('automationPanel').style.display = 'block';
  setProgress(5);
  sequenceElement('automationStatus').textContent = `Starting person ${run.index + 1} of ${run.people.length}: checking Chrome and connecting the verification service. This may take up to a minute…`;
  sequenceElement('automationPanel').scrollIntoView({block:'center'});
  sequenceMessage(`Starting ${person.first_name} (${person.email})…`);
  try {
    sequenceElement('nextTacoPerson').hidden = true;
    sequenceElement('continueTacoMain').hidden = true;
    sequenceElement('confirmTacoCheckout').checked = false;
    sequenceElement('tacoCheckoutAccount').value = person.email;
    const result = await api('/api/web/start', {method:'POST', body:JSON.stringify({app:'Taco Bell', details:run.details[run.index]})});
    run.stage = 'signup';
    submissionUrl = result.submission_url || '';
    sequenceElement('submissionButton').style.display = submissionUrl ? 'block' : 'none';
    sequenceElement('automationPanel').style.display = 'block';
    sequenceMessage(`Person ${run.index + 1} of ${run.people.length}: ${person.first_name} (${person.email}). Complete their website verification and review the terms.`);
    pollStatus();
  } catch (error) {
    run.stage = 'retry';
    sequenceElement('nextTacoPerson').hidden = false;
    sequenceElement('nextTacoPerson').textContent = 'Retry this person';
    setProgress(0);
    sequenceElement('automationStatus').textContent = 'Could not start: ' + error.message + ' Use Retry this person below.';
    sequenceMessage(error.message);
  } finally { tacoSequenceBusy = false; }
}
async function sequenceSignupComplete() {
  if (!tacoSequence || tacoSequence.stage !== 'signup') return;
  tacoSequence.stage = 'checkout';
  submissionUrl = '';
  for (const id of ['submissionButton', 'codeControls', 'approveButton']) sequenceElement(id).style.display = 'none';
  setProgress(70);
  sequenceElement('automationStatus').textContent = 'Website signup finished. Starting Android sign-in…';
  const person = tacoSequence.people[tacoSequence.index];
  sequenceMessage(`${person.first_name} (${person.email}): website setup reported complete. Complete sign-in on Android, then use the button below to prepare this person’s order.`);
  sequenceElement('nextTacoPerson').hidden = false;
  sequenceElement('nextTacoPerson').textContent = 'This person is finished — Next person';
  await retryTacoSignin();
  sequenceElement("continueTacoMain").hidden = false;
}
async function nextTacoPerson() {
  if (!tacoSequence || tacoSequenceBusy || preparingTacoOrder) return;
  if (tacoSequence.stage === 'retry') return startSequencePerson();
  if (!['checkout','review'].includes(tacoSequence.stage)) return;
  if (!confirm('Has this person finished? Verify their order was placed or cancelled in Taco Bell. Before continuing, sign out of their account on the Taco Bell website and Android app.')) return;
  if (tacoSequence.index + 1 === tacoSequence.people.length) {
    if (await endTacoSequence()) notify('Everyone in this group is finished.');
    return;
  }
  tacoSequence.index += 1;
  tacoSequence.stage = 'ready';
  await startSequencePerson();
}
async function endTacoSequence() {
  if (tacoSequenceBusy || preparingTacoOrder) return notify('Wait for the current step to finish.');
  tacoSequenceBusy = true;
  try {
    await api('/api/web/cancel', {method:'POST', body:JSON.stringify({app:'Taco Bell'})});
    if (statusTimer) clearInterval(statusTimer);
    tacoSequence = null;
    sequenceLock(false);
    sequenceElement('confirmTacoCheckout').checked = false;
    sequenceElement('tacoSequencePanel').hidden = true;
    return true;
  } catch (error) { notify(error.message); return false; }
  finally { tacoSequenceBusy = false; }
}
async function prepareTacoOrder() {
  if (preparingTacoOrder || tacoSequenceBusy) return;
  try {
    if (!sequenceElement('confirmTacoCheckout').checked) throw new Error('Confirm the selected account and checkout preparation first.');
    if (tacoSequence && tacoSequence.stage !== 'checkout') throw new Error('Complete this person’s signup first. If checkout is already prepared, review it directly in Taco Bell.');
    if (!tacoSequence) detectTacoBatch(false);
    const plan = tacoPlan(), serial = tacoSequence ? tacoSequence.serial : sequenceElement('deviceSelect').value;
    plan.gift_card = tacoSequence ? tacoSequence.cards[tacoSequence.index] : checkoutGiftCard();
    plan.checkout_confirmed = true;
    if (!serial || !plan.location || !plan.reward) throw new Error('Choose an Android device, reward, and pickup location.');
    if (plan.item) throw new Error('Additional menu items are not supported by this helper. Clear that field first.');
    preparingTacoOrder = true;
    sequenceElement('automationPanel').style.display = 'block';
    sequenceElement('automationStatus').textContent = 'Preparing this person’s checkout…';
    const result = await api('/api/taco/prepare', {method:'POST', body:JSON.stringify({device_serial:serial, plan})});
    sequenceElement('automationStatus').textContent = result.message;
    if (tacoSequence) {
      tacoSequence.stage = 'review';
      sequenceElement('continueTacoMain').hidden = true;
      sequenceMessage('Review the gift card, total, and pickup store in Taco Bell. Place or cancel the order there, then click Next person.');
    }
    notify(result.message);
  } catch (error) { sequenceElement('automationStatus').textContent = error.message; notify(error.message); }
  finally { preparingTacoOrder = false; sequenceElement('confirmTacoCheckout').checked = false; }
}

async function retryTacoSignin() {
  if (!tacoSequence || tacoSequenceBusy || preparingTacoOrder || tacoSequence.stage !== 'checkout') return;
  tacoSequenceBusy = true;
  const person = tacoSequence.people[tacoSequence.index];
  sequenceElement('confirmTacoCheckout').checked = false;
  try {
    setProgress(70);
    sequenceElement('automationStatus').textContent = 'Opening Taco Bell on Android and entering this person’s email…';
    sequenceMessage('Opening Android sign-in for ' + person.email + '…');
    const result = await api('/api/taco/signin', {method:'POST', body:JSON.stringify({device_serial:tacoSequence.serial,email:person.email})});
    sequenceElement('automationStatus').textContent = 'Complete verification on your Android device. Website signup is finished; Android sign-in is still waiting for you.';
    sequenceMessage(person.email + ': ' + result.message);
    sequenceElement('automationPanel').scrollIntoView({block:'center'});
  } catch (error) {
    sequenceElement('automationStatus').textContent = 'Android sign-in needs attention: ' + error.message;
    sequenceMessage(error.message);
  }
  finally { tacoSequenceBusy = false; }
}

async function continueTacoMain() {
  if (!tacoSequence || tacoSequence.stage !== 'checkout' || preparingTacoOrder || tacoSequenceBusy) return;
  const button = sequenceElement('continueTacoMain');
  button.disabled = true;
  sequenceElement('confirmTacoCheckout').checked = true;
  try { await prepareTacoOrder(); }
  finally { button.disabled = false; }
}
