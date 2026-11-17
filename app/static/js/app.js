const csrf = document.querySelector('meta[name="csrf-token"]').content;
const naira = n => '₦' + Number(n).toLocaleString('en-NG', {minimumFractionDigits: 0, maximumFractionDigits: 2});
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

async function api(path, method = 'GET', body) {
  const res = await fetch('/api' + path, {
    method, credentials: 'same-origin',
    headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf},
    body: body ? JSON.stringify(body) : undefined
  });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && !path.startsWith('/auth/login')) location.href = '/login';
  if (!res.ok) throw data;
  return data;
}

function showErrors(form, err) {
  form.querySelectorAll('.is-invalid').forEach(e => e.classList.remove('is-invalid'));
  form.querySelectorAll('.invalid-feedback.dyn').forEach(e => e.remove());
  const alert = form.querySelector('[data-alert]');
  if (alert) { alert.textContent = err.error || 'Something went wrong. Try again.'; alert.classList.remove('d-none'); }
  let first = null;
  Object.entries(err.fields || {}).forEach(([name, msg]) => {
    const el = form.querySelector(`[data-field="${name}"]`) || form.querySelector(`[name="${name}"]`);
    if (!el) return;
    el.classList.add('is-invalid');
    el.insertAdjacentHTML('afterend', `<div class="invalid-feedback dyn">${esc(msg)}</div>`);
    first = first || el;
  });
  (first || alert)?.scrollIntoView({behavior: 'smooth', block: 'center'});
}

// Auth forms (register / login)
document.querySelectorAll('form[data-auth]').forEach(form => {
  form.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = form.querySelector('button[type=submit]'); btn.disabled = true;
    try {
      const data = await api(form.dataset.auth, 'POST', Object.fromEntries(new FormData(form)));
      if (data.redirect) { location.href = data.redirect; return; }
      const ok = form.querySelector('[data-ok]'); ok.textContent = data.message; ok.classList.remove('d-none'); btn.disabled = false;
    } catch (err) { showErrors(form, err); btn.disabled = false; }
  });
});

document.getElementById('logout')?.addEventListener('click', async () => {
  const d = await api('/auth/logout', 'POST'); location.href = d.redirect;
});

// Booking page
const bookForm = document.getElementById('book-form');
if (bookForm) {
  let services = [];
  const rows = document.getElementById('svc-rows'), totalEl = document.getElementById('total'), summary = document.getElementById('summary');
  const rowEls = () => [...rows.querySelectorAll('.svc-row')];
  const qtyOf = r => parseFloat(r.querySelector('input[type=number]').value) || 0;
  const sel = () => rowEls().filter(r => r.querySelector('.svc-check').checked).map(r => ({service_id: +r.dataset.id, quantity: qtyOf(r)}));
  const recalc = () => {
    let total = 0; const items = sel();
    rowEls().forEach(r => r.classList.toggle('selected', r.querySelector('.svc-check').checked));
    summary.innerHTML = items.length ? items.map(i => {
      const s = services.find(x => x.id === i.service_id), line = i.quantity * s.price; total += line;
      return `<div class="sum-line"><span>${esc(s.name)} <small>× ${i.quantity} ${s.unit}</small></span><strong>${naira(line)}</strong></div>`;
    }).join('') : '<p class="mb-0">Select a service to see your total.</p>';
    totalEl.textContent = naira(total);
  };
  const today = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  const f = bookForm.elements;
  f.pickup_date.min = today; f.delivery_date.min = today;
  f.pickup_date.addEventListener('change', () => { f.delivery_date.min = f.pickup_date.value || today; });
  api('/services').then(({services: s, locations}) => {
    services = s;
    rows.innerHTML = s.map(x => `<div class="svc-row" data-id="${x.id}">
      <label class="svc-pick"><input type="checkbox" class="svc-check" aria-label="Select ${esc(x.name)}">
        <span class="svc-info"><strong>${esc(x.name)}</strong><small>${esc(x.description)}</small><em>${naira(x.price)} per ${x.unit}</em></span></label>
      <div class="stepper" data-unit="${x.unit}"><button type="button" data-step="-1" aria-label="Less">−</button>
        <input type="number" inputmode="decimal" min="${x.unit === 'kg' ? 0.5 : 1}" max="100" step="${x.unit === 'kg' ? 0.5 : 1}" value="1" aria-label="Quantity in ${x.unit}">
        <button type="button" data-step="1" aria-label="More">+</button></div></div>`).join('');
    document.getElementById('loc-options').innerHTML = locations.map(l => `<label class="chip"><input type="radio" name="pickup_location" value="${esc(l)}"><span>${esc(l)}</span></label>`).join('');
    const pre = new URLSearchParams(location.search).get('service');
    const row = pre && rows.querySelector(`[data-id="${CSS.escape(pre)}"]`);
    if (row) { row.querySelector('.svc-check').checked = true; recalc(); }
  });
  rows.addEventListener('input', recalc); rows.addEventListener('change', recalc);
  rows.addEventListener('click', e => {
    const b = e.target.closest('[data-step]'); if (!b) return;
    const box = b.closest('.stepper'), inp = box.querySelector('input'), step = box.dataset.unit === 'kg' ? 0.5 : 1;
    inp.value = Math.min(100, Math.max(step, (parseFloat(inp.value) || 0) + step * +b.dataset.step)); recalc();
  });
  bookForm.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = bookForm.querySelector('button[type=submit]'); btn.disabled = true;
    document.getElementById('items-error').textContent = '';
    try {
      const {booking} = await api('/bookings', 'POST', {
        items: sel(), discount_code: f.discount_code.value, pickup_location: (bookForm.querySelector('[name=pickup_location]:checked') || {}).value || '',
        building_details: f.building_details.value,
        pickup_at: f.pickup_date.value && f.pickup_time.value ? `${f.pickup_date.value}T${f.pickup_time.value}` : '',
        delivery_date: f.delivery_date.value, instructions: f.instructions.value});
      document.getElementById('confirm-ref').textContent = booking.reference;
      document.getElementById('confirm-total').textContent = naira(booking.total_amount);
      document.getElementById('pay-now').dataset.pay = booking.id;
      bookForm.classList.add('d-none'); document.getElementById('confirmation').classList.remove('d-none'); scrollTo({top: 0, behavior: 'smooth'});
    } catch (err) {
      if (err.fields && err.fields.pickup_at) { err.fields.pickup_date = err.fields.pickup_at; delete err.fields.pickup_at; }
      if (err.fields && err.fields.items) { document.getElementById('items-error').textContent = err.fields.items; delete err.fields.items; }
      showErrors(bookForm, err); btn.disabled = false;
    }
  });
}

// "Install app" button (Android/Chrome). On iPhone: Share > Add to Home Screen.
let installEvt;
addEventListener('beforeinstallprompt', e => { e.preventDefault(); installEvt = e; document.getElementById('install-app')?.classList.remove('d-none'); });
document.getElementById('install-app')?.addEventListener('click', async ev => {
  if (!installEvt) return; installEvt.prompt(); await installEvt.userChoice; installEvt = null; ev.target.classList.add('d-none');
});

// Mobile menu and header shadow
const menuBtn = document.getElementById('menu-btn'), navEl = document.getElementById('nav');
if (menuBtn) {
  menuBtn.addEventListener('click', () => { const o = navEl.classList.toggle('open'); menuBtn.setAttribute('aria-expanded', o); });
  navEl.addEventListener('click', e => { if (e.target.closest('a')) { navEl.classList.remove('open'); menuBtn.setAttribute('aria-expanded', false); } });
}
const closeMenu = () => { if (navEl && menuBtn) { navEl.classList.remove('open'); menuBtn.setAttribute('aria-expanded', false); } };
addEventListener('keydown', e => { if (e.key === 'Escape') closeMenu(); });
document.addEventListener('click', e => { if (navEl && navEl.classList.contains('open') && !e.target.closest('.lx-nav')) closeMenu(); });
const navBar = document.querySelector('.lx-nav');
addEventListener('scroll', () => navBar && navBar.classList.toggle('scrolled', scrollY > 8), {passive: true});
