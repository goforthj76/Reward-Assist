(function () {
  function pickupTimes(now) {
    const minutes = now.getHours() * 60 + now.getMinutes() + now.getSeconds() / 60 + now.getMilliseconds() / 60000;
    const first = Math.ceil((minutes + 15) / 15) * 15;
    const times = [];
    for (let minute = first; minute < 1440; minute += 15) {
      const hour = Math.floor(minute / 60);
      times.push(`${hour % 12 || 12}:${String(minute % 60).padStart(2, '0')} ${hour < 12 ? 'AM' : 'PM'}`);
    }
    return times;
  }
  if (typeof module !== 'undefined') { module.exports = pickupTimes; return; }
  const select = document.getElementById('tacoPickupTime');
  function refresh() {
    const previous = select.value || 'ASAP';
    const times = pickupTimes(new Date());
    const choices = ['ASAP', ...times];
    if (Array.from(select.options, option => option.value).join('|') === choices.join('|')) return;
    select.replaceChildren(new Option('ASAP — as soon as possible', 'ASAP'), ...times.map(time => new Option(time, time)));
    select.value = choices.includes(previous) ? previous : 'ASAP';
    if (previous !== select.value) {
      document.getElementById('confirmTacoCheckout').checked = false;
      toastTimeChange();
    }
  }
  function toastTimeChange() { notify('That pickup time is now too soon. Choose a later time or use ASAP.'); }
  refresh();
  select.addEventListener('focus', refresh);
  window.addEventListener('focus', refresh);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
  setInterval(refresh, 15000);
  const originalPlan = tacoPlan;
  tacoPlan = function () { refresh(); return originalPlan(); };
})();
