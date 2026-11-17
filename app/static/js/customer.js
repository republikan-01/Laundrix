const STEP_LABELS = {booking_confirmed:'Booking confirmed',picked_up:'Laundry picked up',received:'Received at facility',washing:'Washing in progress',ironing:'Ironing and folding',ready:'Ready for delivery',out_for_delivery:'Out for delivery',delivered:'Delivered'};
const fmt = s => new Date(s).toLocaleString();

// Start Paystack payment (server creates the transaction; we only redirect)
document.addEventListener('click', async e => {
  const id = e.target.dataset.pay; if (!id) return;
  e.target.disabled = true;
  try { const d = await api('/payments/initialize', 'POST', {booking_id: +id}); location.href = d.authorization_url; }
  catch (err) {
    e.target.disabled = false;
    const el = document.querySelector('[data-pay-error]');
    if (el) el.textContent = err.error || 'Payment could not be started.'; else alert(err.error || 'Payment could not be started.');
  }
});

// Dashboard
const list = document.getElementById('booking-list');
if (list) {
  const label = b => b.status === 'cancelled' ? 'cancelled' : b.paid ? STEP_LABELS[b.order_status] : 'awaiting payment';
  const load = async () => {
    const {bookings} = await api('/bookings');
    list.innerHTML = bookings.length ? bookings.map(b => `
      <div class="panel mb-3"><div class="d-flex justify-content-between flex-wrap gap-2">
        <div><strong>${esc(b.reference)}</strong> <span class="status ${esc(b.status)}">${esc(label(b))}</span>
        <div class="small mt-1">${b.items.map(i => esc(i.service) + ' × ' + i.quantity).join(', ')}</div>
        <div class="small">Pickup ${fmt(b.pickup_at)} · ${esc(b.building_details)}</div></div>
        <div class="text-end"><div class="fw-bold">${naira(b.total_amount)}</div>
        ${b.status === 'pending' ? `<button class="btn btn-sm btn-lx mt-1" data-pay="${b.id}">Pay now</button>
          <button class="btn btn-sm btn-outline-lx mt-1" data-cancel="${b.id}">Cancel</button>` : ''}
        ${b.paid ? `<a class="btn btn-sm btn-lx mt-1" href="/track/${b.id}">Track</a>
          <a class="btn btn-sm btn-outline-lx mt-1" href="/receipt/${b.id}">Receipt</a>
          <button class="btn btn-sm btn-outline-lx mt-1" data-refund-request="${b.id}">Request refund</button>
          ${b.order_status === 'delivered' ? `<button class="btn btn-sm btn-outline-lx mt-1" data-review="${b.id}">Review</button>` : ''}` : ''}</div>
      </div><div class="text-danger small" data-pay-error></div></div>`).join('')
      : '<div class="panel">No bookings yet. Book your first pickup to get started.</div>';
  };
  list.addEventListener('click', async e => {
    const t=e.target;
    if(t.dataset.refundRequest){const reason=prompt('Reason for refund request:');if(reason===null)return;try{const d=await api('/payments/refund-request','POST',{booking_id:+t.dataset.refundRequest,reason});alert(d.message);}catch(err){alert(err.error||'Could not submit refund request.');}return;}
    if(t.dataset.review){const rating=prompt('Rate your order from 1 to 5:');if(rating===null)return;const comment=prompt('Optional comment:')||'';try{const d=await api('/reviews','POST',{booking_id:+t.dataset.review,rating:+rating,comment});alert(d.message);}catch(err){alert(err.error||'Could not submit review.');}return;}
    const id=t.dataset.cancel;if(!id||!confirm('Cancel this booking?'))return;
    try { await api(`/bookings/${id}/cancel`, 'POST'); load(); } catch (err) { alert(err.error); }
  });
  const loadNotifs = async () => {
    const d = await api('/notifications');
    document.getElementById('notif-list').innerHTML = d.notifications.length
      ? d.notifications.map(n => `<div class="mb-2 ${n.is_read ? '' : 'unread'}">${esc(n.message)}<br><small>${fmt(n.at)}</small></div>`).join('')
      : 'No notifications yet.';
  };
  const loadComplaints = async () => {
    const d = await api('/complaints');
    document.getElementById('complaint-list').innerHTML = d.complaints.map(c =>
      `<div class="mb-2"><em>${esc(c.message)}</em><br><span class="status ${c.status === 'resolved' ? 'confirmed' : ''}">${esc(c.status)}</span>${c.reply ? ' ' + esc(c.reply) : ''}</div>`).join('');
  };
  document.getElementById('mark-read').addEventListener('click', async () => { await api('/notifications/read', 'POST'); loadNotifs(); });
  document.getElementById('complaint-form').addEventListener('submit', async e => {
    e.preventDefault(); const f = e.target, a = f.querySelector('[data-alert]');
    try { const d = await api('/complaints', 'POST', {message: f.message.value});
      a.className = 'alert alert-success'; a.textContent = d.message; f.message.value = ''; loadComplaints();
    } catch (err) { a.className = 'alert alert-danger'; a.textContent = err.error; }
  });
  load(); loadNotifs(); loadComplaints(); setInterval(() => { load(); loadNotifs(); }, 20000);
}

// Paystack callback page
const payResult = document.getElementById('pay-result');
if (payResult) {
  const ref = new URLSearchParams(location.search).get('reference') || new URLSearchParams(location.search).get('trxref');
  (async () => {
    try {
      const d = await api('/payments/verify?reference=' + encodeURIComponent(ref || ''));
      payResult.innerHTML = d.success
        ? `<h1 class="h3">Payment confirmed</h1><p>Booking ${esc(d.reference)} is confirmed. We will collect your laundry at the time you chose.</p>
           <a class="btn btn-lx me-2" href="/track/${d.booking_id}">Track order</a><a class="btn btn-outline-lx" href="/receipt/${d.booking_id}">View receipt</a>`
        : `<h1 class="h3">Payment not completed</h1><p>No money was taken for this attempt. You can try again from your dashboard.</p><a class="btn btn-lx" href="/dashboard">Back to dashboard</a>`;
    } catch (err) { payResult.innerHTML = `<h1 class="h3">We could not confirm yet</h1><p>${esc(err.error || 'Try again.')} If you were charged, your booking will confirm automatically within a few minutes.</p><a class="btn btn-lx" href="/dashboard">Go to dashboard</a>`; }
  })();
}

// Tracking timeline (auto-refreshes so admin updates appear)
const tl = document.getElementById('timeline');
if (tl) {
  const draw = async () => {
    try {
      const d = await api(`/bookings/${tl.dataset.booking}/tracking`);
      tl.innerHTML = d.steps.map(s => `<li class="${s.done ? 'done' : ''} ${s.current ? 'current' : ''}">${esc(s.label)}${s.at ? `<small>${fmt(s.at)}</small>` : ''}</li>`).join('');
      const note=document.getElementById('rider-location-note'), mapEl=document.getElementById('rider-map');
      if(d.rider_location && mapEl){
        note.textContent=`Rider: ${d.rider_location.rider_name} · Last update: ${fmt(d.rider_location.updated_at)}`; mapEl.style.display='block';
        if(!window.L && !window._leafletLoading){window._leafletLoading=true;const css=document.createElement('link');css.rel='stylesheet';css.href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';document.head.appendChild(css);const js=document.createElement('script');js.src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';js.onload=()=>drawRiderMap(d.rider_location);document.head.appendChild(js);} else drawRiderMap(d.rider_location);
      }
      function drawRiderMap(loc){if(!window.L)return;let m=window._laundrixMap;if(!m){m=window._laundrixMap=L.map(mapEl).setView([loc.lat,loc.lng],15);L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap'}).addTo(m);window._laundrixMarker=L.marker([loc.lat,loc.lng]).addTo(m).bindPopup('Your delivery rider');}else{m.setView([loc.lat,loc.lng],15);window._laundrixMarker.setLatLng([loc.lat,loc.lng]);}}

    } catch (err) { tl.innerHTML = `<li>${esc(err.error || 'Could not load tracking.')}</li>`; }
  };
  draw(); setInterval(draw, 15000);
}

// Profile
const pf = document.getElementById('profile-form');
if (pf) {
  const say = (form, ok, msg) => { const a = form.querySelector('[data-alert]'); a.className = 'alert ' + (ok ? 'alert-success' : 'alert-danger'); a.textContent = msg; };
  api('/profile').then(p => { pf.email.value = p.email; pf.full_name.value = p.full_name; pf.phone.value = p.phone; pf.saved_location.value = p.saved_location; pf.notifications_enabled.checked = p.notifications_enabled; });
  pf.addEventListener('submit', async e => { e.preventDefault();
    try { say(pf, true, (await api('/profile', 'PUT', {full_name: pf.full_name.value, phone: pf.phone.value, saved_location: pf.saved_location.value, notifications_enabled: pf.notifications_enabled.checked})).message); }
    catch (err) { showErrors(pf, err); } });
  const pw = document.getElementById('password-form');
  pw.addEventListener('submit', async e => { e.preventDefault();
    try { say(pw, true, (await api('/profile/password', 'POST', {current_password: pw.current_password.value, new_password: pw.new_password.value})).message); pw.reset(); }
    catch (err) { showErrors(pw, err); } });
}
