const body = document.getElementById('tab-body'), msg = document.getElementById('admin-msg');
const flash = (t, ok = true) => { msg.className = 'alert ' + (ok ? 'alert-success' : 'alert-danger'); msg.textContent = t; };
const tbl = (head, rows) => `<table class="table align-middle"><thead><tr>${head.map(h => `<th>${h}</th>`).join('')}</tr></thead><tbody>${rows.join('') || `<tr><td colspan="${head.length}">Nothing here yet.</td></tr>`}</tbody></table>`;
const call = async (path, method, data, after) => { try { const d = await api('/admin' + path, method, data); flash(d.message || 'Saved.'); if (after) after(); } catch (e) { flash(e.error || 'Something went wrong.', false); } };
let current = 'orders';

async function stats() {
  const s = await api('/admin/stats');
  const cards = [['Customers', s.customers], ['Bookings', s.bookings], ['Awaiting payment', s.awaiting_payment], ['Ongoing orders', s.ongoing], ['Delivered', s.completed], ['Revenue', naira(s.revenue)]];
  document.getElementById('stats').innerHTML = cards.map(([l, v]) => `<div class="col-6 col-md-2"><div class="panel"><div class="stat">${v}</div>${l}</div></div>`).join('');
}

const views = {
  async orders() {
    const [{orders, steps}, {staff}] = await Promise.all([api('/admin/orders'), api('/admin/staff')]);
    const keys = steps.map(s => s[0]), opt = (id) => '<option value="">Unassigned</option>' + staff.filter(p => p.active || p.id === id).map(p => `<option value="${p.id}" ${p.id === id ? 'selected' : ''}>${esc(p.name)}</option>`).join('');
    body.innerHTML = tbl(['Order', 'Customer', 'Pickup', 'Status', 'Pickup staff', 'Delivery staff', ''], orders.map(o => `<tr data-id="${o.id}">
      <td><strong>${esc(o.reference)}</strong><br><small>${naira(o.total)}</small></td>
      <td>${esc(o.customer)}<br><small>${esc(o.phone)}</small></td>
      <td><small>${esc(o.where)}<br>${fmt(o.pickup_at)}<br>Deliver by ${esc(o.delivery_date)}</small></td>
      <td><select class="form-select form-select-sm" data-f="status"><option value="">${esc(steps[keys.indexOf(o.status)][1])} (current)</option>${steps.slice(keys.indexOf(o.status) + 1).map(s => `<option value="${s[0]}">${esc(s[1])}</option>`).join('')}</select></td>
      <td><select class="form-select form-select-sm" data-f="pickup_staff_id">${opt(o.pickup_staff_id)}</select></td>
      <td><select class="form-select form-select-sm" data-f="delivery_staff_id">${opt(o.delivery_staff_id)}</select></td>
      <td><button class="btn btn-sm btn-lx" data-save-order="${o.id}">Save</button></td></tr>`));
  },
  async customers() {
    const {customers} = await api('/admin/customers');
    body.innerHTML = tbl(['Name', 'Email', 'Phone', 'Type', 'Bookings', ''], customers.map(c => `<tr><td>${esc(c.name)}</td><td>${esc(c.email)}</td><td>${esc(c.phone)}</td><td>${esc(c.type)}</td><td>${c.bookings}</td>
      <td><button class="btn btn-sm btn-outline-lx" data-toggle-customer="${c.id}">${c.active ? 'Deactivate' : 'Activate'}</button></td></tr>`));
  },
  async payments() {
    const {payments} = await api('/admin/payments');
    body.innerHTML = tbl(['Reference', 'Booking', 'Customer', 'Amount', 'Status', 'Channel', 'Date'], payments.map(p => `<tr><td>${esc(p.reference)}</td><td>${esc(p.booking)}</td><td>${esc(p.customer)}</td><td>${naira(p.amount)}</td><td><span class="status ${p.status === 'success' ? 'confirmed' : ''}">${esc(p.status)}</span></td><td>${esc(p.channel || '')}</td><td>${fmt(p.at + 'Z')}</td></tr>`));
  },
  async services() {
    const {services} = await api('/admin/services');
    const row = (s) => `<tr data-sid="${s.id || ''}"><td><input class="form-control form-control-sm" data-f="name" value="${esc(s.name)}" aria-label="Name"></td>
      <td><input class="form-control form-control-sm" data-f="description" value="${esc(s.description)}" aria-label="Description"></td>
      <td><select class="form-select form-select-sm" data-f="unit"><option ${s.unit === 'kg' ? 'selected' : ''}>kg</option><option ${s.unit === 'item' ? 'selected' : ''}>item</option></select></td>
      <td><input class="form-control form-control-sm" data-f="price" type="number" min="1" step="50" value="${s.price}" aria-label="Price"></td>
      <td><input type="checkbox" class="form-check-input" data-f="is_active" ${s.is_active !== false ? 'checked' : ''} aria-label="Active"></td>
      <td><button class="btn btn-sm btn-lx" data-save-service>${s.id ? 'Save' : 'Add service'}</button></td></tr>`;
    body.innerHTML = tbl(['Name', 'Description', 'Unit', 'Price (₦)', 'Active', ''], [...services.map(row), row({name: '', description: '', unit: 'kg', price: ''})]);
  },
  async staff() {
    const {staff} = await api('/admin/staff');
    body.innerHTML = tbl(['Name', 'Phone', 'Status', ''], [...staff.map(p => `<tr><td>${esc(p.name)}</td><td>${esc(p.phone)}</td><td>${p.active ? 'Active' : 'Inactive'}<br><small>${p.tracking_url ? `<a target="_blank" rel="noopener" href="${esc(p.tracking_url)}">Rider GPS link</a>` : 'Run seed.py to create link'}</small></td><td><button class="btn btn-sm btn-outline-lx" data-toggle-staff="${p.id}">${p.active ? 'Deactivate' : 'Activate'}</button></td></tr>`),
      `<tr id="new-staff"><td><input class="form-control form-control-sm" data-f="name" placeholder="Full name" aria-label="Name"></td><td><input class="form-control form-control-sm" data-f="phone" placeholder="Phone" aria-label="Phone"></td><td></td><td><button class="btn btn-sm btn-lx" data-add-staff>Add staff</button></td></tr>`]);
  },
  async analytics() {
    const d = await api('/admin/analytics');
    const rows = d.daily.map(x => `<tr><td>${esc(x.date)}</td><td>${naira(x.revenue)}</td></tr>`);
    body.innerHTML = `<h3 class="h5">Revenue – last 30 days</h3>${tbl(['Date','Revenue'], rows)}<h3 class="h5 mt-4">Orders by stage</h3>${tbl(['Stage','Orders'], d.order_statuses.map(x=>`<tr><td>${esc(x.status.replaceAll('_',' '))}</td><td>${x.count}</td></tr>`))}`;
  },
  async promotions() {
    const {promotions} = await api('/admin/promotions');
    body.innerHTML = `<h3 class="h5">Create discount code</h3><div class="row g-2 mb-3"><div class="col"><input id="promo-code" class="form-control" placeholder="CODE"></div><div class="col"><input id="promo-percent" type="number" min="1" max="100" class="form-control" placeholder="Discount %"></div><div class="col"><input id="promo-uses" type="number" min="1" class="form-control" placeholder="Max uses"></div><div class="col-auto"><button class="btn btn-lx" id="promo-add">Add</button></div></div>${tbl(['Code','Discount','Uses','Status',''], promotions.map(p=>`<tr><td>${esc(p.code)}</td><td>${p.discount_percent}%</td><td>${p.uses}/${p.max_uses||'∞'}</td><td>${p.active?'Active':'Inactive'}</td><td><button class="btn btn-sm btn-outline-lx" data-toggle-promo="${p.id}">Toggle</button></td></tr>`))}`;
  },
  async refunds() {
    const {refunds} = await api('/admin/refunds');
    body.innerHTML = tbl(['Booking','Customer','Amount','Reason','Status','Actions'], refunds.map(r=>`<tr><td>${esc(r.booking)}</td><td>${esc(r.customer)}</td><td>${naira(r.amount)}</td><td>${esc(r.note)}</td><td>${esc(r.status)}</td><td>${r.status==='requested'?`<button class="btn btn-sm btn-lx" data-refund="${r.id}" data-status="approved">Approve</button> <button class="btn btn-sm btn-outline-lx" data-refund="${r.id}" data-status="rejected">Reject</button>`:r.status==='approved'?`<button class="btn btn-sm btn-lx" data-refund="${r.id}" data-status="refunded">Mark refunded</button>`:''}</td></tr>`));
    body.insertAdjacentHTML('beforeend','<p class="small text-muted">Approving or marking a refund here does not move money. Process the actual refund in Paystack first.</p>');
  },
  async reviews() {
    const {reviews} = await api('/admin/reviews');
    body.innerHTML = tbl(['Customer','Booking','Rating','Comment','Date'], reviews.map(r=>`<tr><td>${esc(r.customer)}</td><td>${esc(r.booking)}</td><td>${'★'.repeat(r.rating)}${'☆'.repeat(5-r.rating)}</td><td>${esc(r.comment)}</td><td>${fmt(r.at+'Z')}</td></tr>`));
  },
  async complaints() {
    const {complaints} = await api('/admin/complaints');
    body.innerHTML = tbl(['Customer', 'Complaint', 'Status', 'Reply'], complaints.map(c => `<tr data-cid="${c.id}"><td>${esc(c.customer)}<br><small>${fmt(c.at + 'Z')}</small></td><td>${esc(c.message)}</td><td>${esc(c.status)}</td>
      <td>${c.reply ? esc(c.reply) : `<textarea class="form-control form-control-sm mb-1" rows="2" aria-label="Reply"></textarea><button class="btn btn-sm btn-lx" data-reply>Send reply</button>`}</td></tr>`));
  }
};

async function show(tab) {
  current = tab;
  document.querySelectorAll('[data-tab]').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  body.textContent = 'Loading…'; await views[tab](); stats();
}
const fields = el => Object.fromEntries([...el.querySelectorAll('[data-f]')].map(i => [i.dataset.f, i.type === 'checkbox' ? i.checked : i.value]));

document.addEventListener('click', e => {
  const t = e.target, d = t.dataset, row = t.closest('tr'), reload = () => show(current);
  if (d.tab) show(d.tab);
  else if (t.id === 'promo-add') call('/promotions','POST',{code:document.getElementById('promo-code').value,discount_percent:document.getElementById('promo-percent').value,max_uses:document.getElementById('promo-uses').value||null},reload);
  else if (d.togglePromo) call(`/promotions/${d.togglePromo}/toggle`,'POST',null,reload);
  else if (d.refund) call(`/refunds/${d.refund}`,'PATCH',{status:d.status},reload);
  else if (d.saveOrder) { const f = fields(row), p = {pickup_staff_id: f.pickup_staff_id ? +f.pickup_staff_id : null, delivery_staff_id: f.delivery_staff_id ? +f.delivery_staff_id : null}; if (f.status) p.status = f.status; call('/orders/' + d.saveOrder, 'PATCH', p, reload); }
  else if (d.toggleCustomer) call(`/customers/${d.toggleCustomer}/toggle`, 'POST', null, reload);
  else if (d.toggleStaff) call(`/staff/${d.toggleStaff}/toggle`, 'POST', null, reload);
  else if ('saveService' in d) { const f = fields(row), id = row.dataset.sid; call(id ? '/services/' + id : '/services', id ? 'PUT' : 'POST', f, reload); }
  else if ('addStaff' in d) call('/staff', 'POST', fields(row), reload);
  else if ('reply' in d) call(`/complaints/${row.dataset.cid}/reply`, 'POST', {reply: row.querySelector('textarea').value}, reload);
});
show('orders');
