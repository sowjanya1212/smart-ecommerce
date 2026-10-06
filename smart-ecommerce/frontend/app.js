/* Smart Shop - vanilla JS single-page frontend for the FastAPI user panel. */
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const money = (n) => '$' + Number(n).toFixed(2);

const state = { access: localStorage.getItem('access'), refresh: localStorage.getItem('refresh'), user: null,
  config: {}, page: 1, pages: 1, ws: null, view: 'shop', stripe: null };

/* ---------- API helper (auto refresh on 401) ---------- */
async function api(path, { method = 'GET', body, retry = true } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (state.access) headers.Authorization = 'Bearer ' + state.access;
  const res = await fetch('/api' + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  if (res.status === 401 && state.refresh && retry && !path.startsWith('/auth/')) {
    const r = await fetch('/api/auth/refresh', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: state.refresh }) });
    if (r.ok) { setTokens((await r.json()).access_token, state.refresh); return api(path, { method, body, retry: false }); }
    logout(true);
  }
  const data = res.status === 204 ? null : await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data?.detail;
    throw new Error(typeof d === 'string' ? d : Array.isArray(d) ? d.map((x) => x.msg).join('; ') : 'Request failed');
  }
  return data;
}
function setTokens(a, r) {
  state.access = a; state.refresh = r;
  a ? localStorage.setItem('access', a) : localStorage.removeItem('access');
  r ? localStorage.setItem('refresh', r) : localStorage.removeItem('refresh');
}
function toast(msg, kind = '') {
  const el = document.createElement('div');
  el.className = 'toast ' + kind; el.textContent = msg;
  $('#toasts').append(el); setTimeout(() => el.remove(), 5000);
}
const guard = (fn) => async (...a) => { try { return await fn(...a); } catch (e) { toast(e.message, 'err'); } };

/* ---------- views ---------- */
function show(view) {
  state.view = view;
  for (const v of ['shop', 'cart', 'orders', 'notifications']) $('#view-' + v).hidden = v !== view;
  if (view !== 'shop' && !state.user) { openAuth(); return show('shop'); }
  if (view === 'cart') renderCart();
  if (view === 'orders') renderOrders();
  if (view === 'notifications') renderNotifications();
}
document.addEventListener('click', (e) => {
  const v = e.target.closest('[data-view]');
  if (v) { e.preventDefault(); show(v.dataset.view); }
});

/* ---------- catalogue ---------- */
const loadCategories = guard(async () => {
  for (const c of await api('/categories')) $('#f-category').append(new Option(c.name, c.slug));
});
const loadProducts = guard(async () => {
  const p = new URLSearchParams({ page: state.page, page_size: 12, sort: $('#f-sort').value });
  if ($('#f-category').value) p.set('category', $('#f-category').value);
  if ($('#f-min').value) p.set('min_price', $('#f-min').value);
  if ($('#f-max').value) p.set('max_price', $('#f-max').value);
  if ($('#search').value.trim()) p.set('q', $('#search').value.trim());
  const data = await api('/products?' + p);
  state.pages = Math.max(1, Math.ceil(data.total / data.page_size));
  $('#page-info').textContent = `Page ${data.page} / ${state.pages} · ${data.total} items`;
  $('#prev').disabled = state.page <= 1; $('#next').disabled = state.page >= state.pages;
  $('#products').innerHTML = data.items.map((p) => `
    <article class="card">
      ${p.images[0] ? `<img src="${esc(p.images[0])}" alt="${esc(p.name)}" loading="lazy">` : '<div class="ph">📦</div>'}
      <strong>${esc(p.name)}</strong>
      <span class="muted">${esc(p.category?.name ?? '')} · ${p.sold_count} sold</span>
      <p class="muted">${esc(p.description).slice(0, 80)}</p>
      <div class="row" style="justify-content:space-between"><span class="price">${money(p.price)}</span>
        ${p.stock > 0 ? `<button class="primary" data-add="${p.id}">Add to cart</button>` : '<span class="tag failed">Out of stock</span>'}</div>
      ${p.stock > 0 && p.stock <= 5 ? `<span class="muted">Only ${p.stock} left</span>` : ''}
    </article>`).join('') || '<p class="muted">No products match your filters.</p>';
});
document.addEventListener('click', guard(async (e) => {
  const b = e.target.closest('[data-add]'); if (!b) return;
  if (!state.user) return openAuth();
  const cart = await api('/cart', { method: 'POST', body: { product_id: +b.dataset.add, quantity: 1 } });
  setCartCount(cart.count); toast('Added to cart', 'ok');
}));
let debounce;
for (const id of ['#f-category', '#f-sort', '#f-min', '#f-max', '#search'])
  $(id).addEventListener('input', () => { clearTimeout(debounce); debounce = setTimeout(() => { state.page = 1; loadProducts(); }, 250); });
$('#prev').onclick = () => { state.page--; loadProducts(); };
$('#next').onclick = () => { state.page++; loadProducts(); };

/* ---------- cart & checkout ---------- */
const setCartCount = (n) => { $('#cart-count').textContent = n; $('#cart-count').dataset.n = n; };
const renderCart = guard(async () => {
  const cart = await api('/cart'); setCartCount(cart.count);
  $('#view-cart').innerHTML = `<h2>Your cart</h2>` + (cart.items.length ? cart.items.map((l) => `
    <div class="line"><div><strong>${esc(l.product.name)}</strong><div class="muted">${money(l.product.price)} each</div></div>
      <div class="row"><button data-qty="${l.product.id}" data-d="-1">−</button><b>${l.quantity}</b>
        <button data-qty="${l.product.id}" data-d="1">+</button><span class="price">${money(l.line_total)}</span>
        <button class="danger" data-rm="${l.product.id}">Remove</button></div></div>`).join('') + `
    <div class="panel"><div class="row" style="justify-content:space-between"><h3>Total: ${money(cart.total)}</h3></div>
      <textarea id="addr" rows="2" style="width:100%" placeholder="Shipping address"></textarea><br><br>
      <button class="primary" id="checkout">Checkout</button></div>` : '<p class="muted">Your cart is empty.</p>');
  window._cart = cart;
});
document.addEventListener('click', guard(async (e) => {
  const q = e.target.closest('[data-qty]'), r = e.target.closest('[data-rm]');
  if (q) {
    const line = window._cart.items.find((l) => l.product.id == q.dataset.qty);
    const n = line.quantity + +q.dataset.d;
    await api(n < 1 ? `/cart/${q.dataset.qty}` : `/cart/${q.dataset.qty}`, n < 1 ? { method: 'DELETE' } : { method: 'PATCH', body: { quantity: n } });
    renderCart();
  }
  if (r) { await api(`/cart/${r.dataset.rm}`, { method: 'DELETE' }); renderCart(); }
  if (e.target.id === 'checkout') {
    const out = await api('/orders/checkout', { method: 'POST', body: { shipping_address: $('#addr').value } });
    setCartCount(0); openPayment(out);
  }
}));

async function openPayment(out) {
  const dlg = $('#pay-dialog'), body = $('#pay-body');
  $('#pay-title').textContent = `Pay for order #${out.order.id} — ${money(out.order.total)}`;
  if (out.mock) {
    body.innerHTML = `<p class="muted">Demo mode (no Stripe keys configured). Simulate the gateway result:</p>
      <div class="row"><button class="primary" id="pay-ok">✅ Pay successfully</button><button id="pay-fail">❌ Simulate failure</button>
      <button id="pay-later">Later</button></div>`;
    const confirm = (success) => guard(async () => {
      await api(`/payments/${out.order.id}/mock-confirm`, { method: 'POST', body: { success } });
      dlg.close(); show('orders');
    });
    $('#pay-ok').onclick = confirm(true); $('#pay-fail').onclick = confirm(false);
    $('#pay-later').onclick = () => { dlg.close(); show('orders'); };
  } else {
    if (!window.Stripe) await new Promise((res) => { const s = document.createElement('script'); s.src = 'https://js.stripe.com/v3/'; s.onload = res; document.head.append(s); });
    state.stripe = state.stripe || Stripe(out.publishable_key);
    body.innerHTML = `<div id="card-element"></div><div class="row"><button class="primary" id="pay-now">Pay ${money(out.order.total)}</button><button id="pay-later">Later</button></div><p class="muted" id="pay-msg"></p>`;
    const card = state.stripe.elements().create('card'); card.mount('#card-element');
    $('#pay-later').onclick = () => { dlg.close(); show('orders'); };
    $('#pay-now').onclick = async () => {
      $('#pay-now').disabled = true;
      const { error } = await state.stripe.confirmCardPayment(out.client_secret, { payment_method: { card } });
      if (error) { $('#pay-msg').textContent = error.message; $('#pay-now').disabled = false; }
      else { dlg.close(); toast('Payment submitted - waiting for confirmation…'); show('orders'); }
    };
  }
  dlg.showModal();
}

/* ---------- orders & notifications ---------- */
const renderOrders = guard(async () => {
  const orders = await api('/orders');
  $('#view-orders').innerHTML = '<h2>Order history</h2>' + (orders.map((o) => `
    <div class="panel"><div class="row" style="justify-content:space-between">
      <strong>Order #${o.id}</strong><span class="muted">${new Date(o.created_at).toLocaleString()}</span></div>
      <div class="row"><span class="tag ${o.order_status}">${o.order_status}</span><span class="tag ${o.payment_status}">payment: ${o.payment_status}</span>
        <b>${money(o.total)}</b></div>
      <ul>${o.items.map((i) => `<li>${i.quantity} × ${esc(i.product_name)} <span class="muted">(${money(i.unit_price)})</span></li>`).join('')}</ul>
      <div class="row">${['pending', 'failed'].includes(o.payment_status) && o.order_status !== 'cancelled' ? `<button class="primary" data-pay="${o.id}">Pay now</button>` : ''}
        ${o.payment_status !== 'paid' && o.order_status === 'pending' ? `<button class="danger" data-cancel="${o.id}">Cancel</button>` : ''}</div>
    </div>`).join('') || '<p class="muted">No orders yet.</p>');
});
document.addEventListener('click', guard(async (e) => {
  const p = e.target.closest('[data-pay]'), c = e.target.closest('[data-cancel]');
  if (p) openPayment(await api(`/orders/${p.dataset.pay}/pay`, { method: 'POST' }));
  if (c) { await api(`/orders/${c.dataset.cancel}/cancel`, { method: 'POST' }); renderOrders(); }
}));

const renderNotifications = guard(async () => {
  const list = await api('/notifications');
  $('#view-notifications').innerHTML = `<div class="row" style="justify-content:space-between"><h2>Notifications</h2>
    <button id="read-all">Mark all read</button></div>` + (list.map((n) => `
    <div class="panel ${n.is_read ? '' : 'unread'}"><span class="tag">${esc(n.type.replace('_', ' '))}</span>
      <p>${esc(n.message)}</p><span class="muted">${new Date(n.created_at).toLocaleString()}</span></div>`).join('') || '<p class="muted">Nothing yet.</p>');
  refreshUnread();
});
document.addEventListener('click', guard(async (e) => {
  if (e.target.id === 'read-all') { await api('/notifications/read-all', { method: 'POST' }); renderNotifications(); }
}));
const setUnread = (n) => { $('#notif-count').textContent = n; $('#notif-count').dataset.n = n; };
const refreshUnread = guard(async () => setUnread((await api('/notifications/unread-count')).unread));

/* ---------- real-time (WebSocket) ---------- */
function connectWS() {
  if (!state.access) return;
  state.ws?.close();
  const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/notifications?token=${state.access}`);
  state.ws = ws;
  const ping = setInterval(() => ws.readyState === 1 && ws.send('ping'), 25000);
  ws.onmessage = (m) => {
    if (m.data === 'pong') return;
    const ev = JSON.parse(m.data);
    if (ev.event === 'notification') {
      toast('🔔 ' + ev.notification.message, ev.notification.type === 'payment_failed' ? 'err' : 'ok');
      refreshUnread();
      if (state.view === 'orders') renderOrders();
      if (state.view === 'notifications') renderNotifications();
    } else if (ev.event === 'cart_updated') {
      setCartCount(ev.count); if (state.view === 'cart') renderCart();
    }
  };
  ws.onclose = () => { clearInterval(ping); if (state.ws === ws && state.access) setTimeout(connectWS, 3000); };
}

/* ---------- auth ---------- */
let signup = false;
function openAuth() { $('#auth-dialog').showModal(); }
function setAuthMode(s) {
  signup = s;
  $('#auth-title').textContent = s ? 'Create account' : 'Log in';
  $('#a-name').hidden = !s; $('#a-name').required = s;
  $('#a-toggle').textContent = s ? 'Have an account? Log in' : 'Need an account? Sign up';
}
$('#a-toggle').onclick = (e) => { e.preventDefault(); setAuthMode(!signup); };
$('#auth-btn').onclick = () => (state.user ? logout() : openAuth());
$('#auth-form').addEventListener('submit', (e) => {
  if (e.submitter?.value !== 'submit') return;
  e.preventDefault();
  guard(async () => {
    const body = { email: $('#a-email').value, password: $('#a-pass').value };
    if (signup) body.name = $('#a-name').value;
    const t = await api(signup ? '/auth/register' : '/auth/login', { method: 'POST', body });
    onLoggedIn(t); $('#auth-dialog').close();
  })();
});
function onLoggedIn(t) {
  setTokens(t.access_token, t.refresh_token); state.user = t.user;
  $('#auth-btn').textContent = `Log out (${t.user.name.split(' ')[0]})`;
  connectWS(); refreshUnread(); api('/cart').then((c) => setCartCount(c.count)).catch(() => {});
}
function logout(silent) {
  state.ws?.close(); state.ws = null; setTokens(null, null); state.user = null;
  $('#auth-btn').textContent = 'Log in'; setCartCount(0); setUnread(0); show('shop');
  if (!silent) toast('Logged out');
}
// Auth0 social login (implicit flow -> id_token in URL hash -> exchanged for our own JWT)
document.querySelectorAll('.social').forEach((b) => b.onclick = () => {
  const a = state.config.auth0, nonce = crypto.randomUUID();
  sessionStorage.setItem('nonce', nonce);
  const q = new URLSearchParams({ response_type: 'id_token', client_id: a.client_id, connection: b.dataset.conn,
    redirect_uri: location.origin + '/', scope: 'openid profile email', nonce });
  location.href = `https://${a.domain}/authorize?${q}`;
});
async function handleAuth0Callback() {
  const h = new URLSearchParams(location.hash.slice(1));
  if (!h.get('id_token')) return;
  history.replaceState(null, '', location.pathname);
  await guard(async () => onLoggedIn(await api('/auth/auth0', { method: 'POST',
    body: { id_token: h.get('id_token'), nonce: sessionStorage.getItem('nonce') } })))();
}

/* ---------- boot ---------- */
(async function init() {
  state.config = await fetch('/api/config').then((r) => r.json()).catch(() => ({}));
  if (state.config.auth0) $('#social').hidden = false;
  await handleAuth0Callback();
  if (state.access && !state.user) {
    try { const user = await api('/auth/me'); onLoggedIn({ access_token: state.access, refresh_token: state.refresh, user }); }
    catch { logout(true); }
  }
  loadCategories(); loadProducts();
})();
