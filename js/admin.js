'use strict';

// ── Utilities ─────────────────────────────────────────────────────────────────

const $ = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));

const money = (v) =>
  new Intl.NumberFormat('es-DO', { style: 'currency', currency: 'DOP', maximumFractionDigits: 0 }).format(v || 0);

const fmt = (iso) => {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('es-DO', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
};

const STATUS_LABELS = {
  borrador: 'Borrador', recibido: 'Nueva', cotizado: 'Cotizada',
  pagado: 'Pagada', en_curso: 'En curso', entregado: 'Entregada', cancelado: 'Cancelada',
};
const STATUS_COLORS = {
  borrador: '#888', recibido: '#D3AB2D', cotizado: '#4A90D9',
  pagado: '#27AE60', en_curso: '#8E44AD', entregado: '#2ECC71', cancelado: '#E74C3C',
};

function badge(status) {
  const label = STATUS_LABELS[status] || escapeHTML(status);
  return `<span class="admin-badge" style="background:${STATUS_COLORS[status] || '#888'}">${label}</span>`;
}

function showToast(msg, error = false) {
  const el = $('#adminToast');
  el.textContent = msg;
  el.className = `admin-toast admin-toast--show${error ? ' admin-toast--error' : ''}`;
  setTimeout(() => el.classList.remove('admin-toast--show'), 3500);
}

// ── Auth ──────────────────────────────────────────────────────────────────────

let AUTH_TOKEN = sessionStorage.getItem('noesis_admin_token') || '';

function getHeaders() {
  return { 'Content-Type': 'application/json', Authorization: `Bearer ${AUTH_TOKEN}` };
}

async function verifyToken(token) {
  const res = await fetch('/api/admin/orders', {
    headers: { Authorization: `Bearer ${token}` },
  });
  return res.ok;
}

// ── API calls ─────────────────────────────────────────────────────────────────

async function apiFetch(url, opts = {}) {
  const res = await fetch(url, {
    ...opts,
    headers: { ...getHeaders(), ...(opts.headers || {}) },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Error ${res.status}`);
  }
  return res.json();
}

// ── State ─────────────────────────────────────────────────────────────────────

let allOrders = [];
let currentOrder = null;
let deliverySelectedFiles = [];

// ── Login ─────────────────────────────────────────────────────────────────────

async function initLogin() {
  const overlay = $('#loginOverlay');
  const panel = $('#adminPanel');
  const btn = $('#loginBtn');
  const input = $('#tokenInput');
  const errEl = $('#loginError');

  async function tryLogin() {
    const token = input.value.trim();
    if (!token) return;
    btn.textContent = 'Verificando...';
    btn.disabled = true;
    const ok = await verifyToken(token);
    if (ok) {
      AUTH_TOKEN = token;
      sessionStorage.setItem('noesis_admin_token', token);
      overlay.hidden = true;
      panel.hidden = false;
      errEl.hidden = true;
      loadOrders();
    } else {
      errEl.hidden = false;
      input.value = '';
      input.focus();
    }
    btn.textContent = 'Ingresar';
    btn.disabled = false;
  }

  btn.addEventListener('click', tryLogin);
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') tryLogin(); });

  if (AUTH_TOKEN) {
    const ok = await verifyToken(AUTH_TOKEN);
    if (ok) {
      overlay.hidden = true;
      panel.hidden = false;
      loadOrders();
      return;
    }
    sessionStorage.removeItem('noesis_admin_token');
    AUTH_TOKEN = '';
  }
}

$('#logoutBtn').addEventListener('click', () => {
  sessionStorage.removeItem('noesis_admin_token');
  location.reload();
});

// ── Orders list ───────────────────────────────────────────────────────────────

function getActiveFilters() {
  return $$('.admin-filter input:checked').map((el) => el.value);
}

function renderOrderCard(order) {
  const c = order.customer || {};
  const q = order.latestQuote;
  const uploads = (order.uploads || []).filter((u) => u.type === 'client_photo');

  return `
    <div class="admin-order-card" data-id="${escapeHTML(order.id)}" role="button" tabindex="0">
      <div class="admin-order-card__header">
        <span class="admin-order-card__id">${escapeHTML(order.id)}</span>
        ${badge(order.status)}
      </div>
      <div class="admin-order-card__body">
        <strong>${escapeHTML(c.name || '—')}</strong>
        <span>${escapeHTML(c.email || '—')}</span>
        <span>${escapeHTML(order.projectType || '—')}</span>
        ${uploads.length ? `<span class="admin-order-card__photos">📷 ${uploads.length} foto${uploads.length !== 1 ? 's' : ''}</span>` : ''}
      </div>
      <div class="admin-order-card__footer">
        <span>${money(q ? q.total : order.total)}</span>
        <span>${fmt(order.createdAt)}</span>
      </div>
    </div>
  `;
}

function renderStats(orders) {
  const count = (s) => orders.filter((o) => o.status === s).length;
  $('#statTotal').textContent = orders.length;
  $('#statRecibido').textContent = count('recibido');
  $('#statPagado').textContent = count('pagado');
  $('#statEntregado').textContent = count('entregado');
}

function renderList() {
  const active = getActiveFilters();
  const filtered = allOrders.filter((o) => active.includes(o.status));
  const container = $('#ordersList');

  if (!filtered.length) {
    container.innerHTML = '<p class="admin-empty">No hay solicitudes con los filtros seleccionados.</p>';
    return;
  }
  container.innerHTML = filtered.map(renderOrderCard).join('');

  $$('.admin-order-card', container).forEach((card) => {
    const open = () => openDetail(card.dataset.id);
    card.addEventListener('click', open);
    card.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') open(); });
  });
}

async function loadOrders() {
  $('#listLoading').style.display = 'block';
  try {
    allOrders = await apiFetch('/api/admin/orders');
    renderStats(allOrders);
    renderList();
  } catch (e) {
    showToast(e.message, true);
  } finally {
    $('#listLoading').style.display = 'none';
  }
}

$$('.admin-filter input').forEach((cb) => cb.addEventListener('change', renderList));
$('#refreshBtn').addEventListener('click', loadOrders);

// ── Views ─────────────────────────────────────────────────────────────────────

function showView(id) {
  $$('.admin-view').forEach((v) => (v.hidden = v.id !== id));
}

$('#navList').addEventListener('click', () => {
  showView('viewList');
  $('#navDetail').hidden = true;
});
$('#backToList').addEventListener('click', () => {
  showView('viewList');
  $('#navDetail').hidden = true;
});

// ── Order detail ──────────────────────────────────────────────────────────────

function infoRow(label, value) {
  return `<div class="admin-info-row"><span>${label}</span><span>${value || '—'}</span></div>`;
}

function renderClientInfo(order) {
  const c = order.customer || {};
  $('#clientInfo').innerHTML = [
    infoRow('Nombre', escapeHTML(c.name)),
    infoRow('Correo', `<a href="mailto:${escapeHTML(c.email)}">${escapeHTML(c.email)}</a>`),
    infoRow('Teléfono', c.phone ? `<a href="tel:${escapeHTML(c.phone)}">${escapeHTML(c.phone)}</a>` : null),
    infoRow('Contacto preferido', escapeHTML(c.contactPreference)),
    infoRow('Fecha de solicitud', fmt(order.createdAt)),
    infoRow('Token de cliente', `<code style="font-size:.75rem">${escapeHTML(order.clientToken || '—')}</code>`),
  ].join('');
}

function renderProjectInfo(order) {
  $('#projectInfo').innerHTML = [
    infoRow('Tipo de proyecto', escapeHTML(order.projectType)),
    infoRow('Área', order.area ? `${escapeHTML(order.area)} m²` : null),
    infoRow('Presupuesto declarado', escapeHTML(order.budget)),
    infoRow('Estado', badge(order.status)),
    infoRow('Total', money(order.total)),
    infoRow('Descripción', order.requirements ? `<em style="white-space:pre-wrap">${escapeHTML(order.requirements)}</em>` : null),
    infoRow('Notas de fotos', order.photoNotes ? escapeHTML(order.photoNotes) : null),
  ].join('');
}

function renderPhotos(order) {
  const photos = (order.uploads || []).filter((u) => u.type === 'client_photo');
  const container = $('#photosList');
  if (!photos.length) {
    container.innerHTML = '<p class="admin-empty-small">Sin fotografías adjuntas.</p>';
    return;
  }
  container.innerHTML = photos.map((f) => `
    <a class="admin-photo-chip" href="/uploads/${escapeHTML(f.storedName)}" target="_blank" rel="noopener">
      📎 ${escapeHTML(f.originalName)}
      <span>${(f.sizeBytes / 1024).toFixed(0)} KB</span>
    </a>
  `).join('');
}

function renderDeliveries(order) {
  const files = (order.uploads || []).filter((u) => u.type === 'delivery');
  const container = $('#deliveryList');
  if (!files.length) {
    container.innerHTML = '<p class="admin-empty-small">Aún no se han entregado diseños.</p>';
    return;
  }
  container.innerHTML = files.map((f) => `
    <a class="admin-photo-chip admin-photo-chip--delivery" href="/uploads/${escapeHTML(f.storedName)}" target="_blank" rel="noopener">
      📦 ${escapeHTML(f.originalName)}
      <span>${(f.sizeBytes / 1024).toFixed(0)} KB</span>
    </a>
  `).join('');
}

function renderCurrentQuote(order) {
  const q = order.latestQuote;
  const container = $('#currentQuote');
  if (!q) {
    container.innerHTML = '<p class="admin-empty-small">Sin cotización enviada aún.</p>';
    return;
  }
  container.innerHTML = `
    <div class="admin-quote-summary">
      <div class="admin-quote-summary__amount">${money(q.total)}</div>
      ${q.scope ? `<p><strong>Alcance:</strong> ${escapeHTML(q.scope)}</p>` : ''}
      ${q.notes ? `<p><strong>Notas:</strong> ${escapeHTML(q.notes)}</p>` : ''}
      ${q.deadlineDays ? `<p><strong>Plazo:</strong> ${escapeHTML(String(q.deadlineDays))} días hábiles</p>` : ''}
      <p class="admin-quote-summary__meta">Enviada ${fmt(q.sentAt || q.createdAt)}</p>
    </div>
  `;
  // Pre-fill form
  $('#qTotal').value = q.total;
  $('#qScope').value = q.scope || '';
  $('#qNotes').value = q.notes || '';
  $('#qDeadline').value = q.deadlineDays || '';
}

async function openDetail(orderId) {
  showView('viewDetail');
  $('#navDetail').hidden = false;
  $('#navDetail').click = null;

  try {
    const order = await apiFetch(`/api/admin/orders/${orderId}`);
    currentOrder = order;

    $('#detailOrderId').textContent = order.id;
    $('#detailStatus').outerHTML = badge(order.status);
    document.getElementById('detailStatus').outerHTML = badge(order.status);

    renderClientInfo(order);
    renderProjectInfo(order);
    renderPhotos(order);
    renderDeliveries(order);
    renderCurrentQuote(order);

    // Set current status in select
    $('#statusSelect').value = order.status;

    // Show/hide quote form based on status
    const canQuote = ['recibido', 'cotizado'].includes(order.status);
    $('#quoteCard').style.opacity = canQuote ? '1' : '.5';
    $('#sendQuoteBtn').disabled = !canQuote;

    // Show/hide delivery form based on status
    const canDeliver = ['pagado', 'en_curso', 'entregado'].includes(order.status);
    $('#deliveryFormCard').style.opacity = canDeliver ? '1' : '.5';
    $('#deliverBtn').disabled = !canDeliver;

  } catch (e) {
    showToast(e.message, true);
    showView('viewList');
  }
}

// ── Quote form ────────────────────────────────────────────────────────────────

$('#quoteForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!currentOrder) return;

  const total = parseInt($('#qTotal').value, 10);
  if (!total || total <= 0) {
    showToast('Ingresa un monto válido para la cotización.', true);
    return;
  }

  const btn = $('#sendQuoteBtn');
  btn.textContent = 'Enviando...';
  btn.disabled = true;

  try {
    await apiFetch(`/api/admin/orders/${currentOrder.id}/quote`, {
      method: 'POST',
      body: JSON.stringify({
        total,
        notes: $('#qNotes').value.trim(),
        scope: $('#qScope').value.trim(),
        deadlineDays: parseInt($('#qDeadline').value, 10) || null,
      }),
    });
    showToast('Cotización enviada al cliente correctamente.');
    await openDetail(currentOrder.id);
    loadOrders();
  } catch (err) {
    showToast(err.message, true);
  } finally {
    btn.textContent = 'Enviar cotización al cliente';
    btn.disabled = false;
  }
});

// ── Status update ─────────────────────────────────────────────────────────────

$('#updateStatusBtn').addEventListener('click', async () => {
  if (!currentOrder) return;
  const status = $('#statusSelect').value;
  try {
    await apiFetch(`/api/admin/orders/${currentOrder.id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    });
    showToast(`Estado actualizado a "${STATUS_LABELS[status]}".`);
    await openDetail(currentOrder.id);
    loadOrders();
  } catch (err) {
    showToast(err.message, true);
  }
});

// ── Delivery upload ───────────────────────────────────────────────────────────

const deliveryDropZone = $('#deliveryDropZone');
const deliveryInput = $('#deliveryFiles');
const deliveryFileList = $('#deliveryFileList');

function renderDeliveryFileChips() {
  deliveryFileList.innerHTML = deliverySelectedFiles.map((f, i) => `
    <div class="admin-file-chip">
      📄 ${escapeHTML(f.name)} <span>(${(f.size / 1024).toFixed(0)} KB)</span>
      <button type="button" data-idx="${i}" aria-label="Quitar ${escapeHTML(f.name)}">×</button>
    </div>
  `).join('');

  $$('[data-idx]', deliveryFileList).forEach((btn) => {
    btn.addEventListener('click', () => {
      deliverySelectedFiles.splice(parseInt(btn.dataset.idx, 10), 1);
      renderDeliveryFileChips();
    });
  });
}

deliveryDropZone.addEventListener('click', () => deliveryInput.click());
deliveryDropZone.addEventListener('dragover', (e) => { e.preventDefault(); deliveryDropZone.classList.add('admin-upload-zone--over'); });
deliveryDropZone.addEventListener('dragleave', () => deliveryDropZone.classList.remove('admin-upload-zone--over'));
deliveryDropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  deliveryDropZone.classList.remove('admin-upload-zone--over');
  deliverySelectedFiles = [...deliverySelectedFiles, ...Array.from(e.dataTransfer.files)];
  renderDeliveryFileChips();
});
deliveryInput.addEventListener('change', () => {
  deliverySelectedFiles = [...deliverySelectedFiles, ...Array.from(deliveryInput.files)];
  renderDeliveryFileChips();
  deliveryInput.value = '';
});

$('#deliveryForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!currentOrder) return;
  if (!deliverySelectedFiles.length) {
    showToast('Selecciona al menos un archivo para entregar.', true);
    return;
  }

  const btn = $('#deliverBtn');
  btn.textContent = 'Subiendo archivos...';
  btn.disabled = true;

  const form = new FormData();
  deliverySelectedFiles.forEach((f) => form.append('files', f));
  form.append('notes', $('#deliveryNotes').value.trim());

  try {
    await fetch(`/api/admin/orders/${currentOrder.id}/deliver`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${AUTH_TOKEN}` },
      body: form,
    }).then(async (res) => {
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `Error ${res.status}`);
      }
      return res.json();
    });

    showToast('Diseños entregados y cliente notificado.');
    deliverySelectedFiles = [];
    renderDeliveryFileChips();
    await openDetail(currentOrder.id);
    loadOrders();
  } catch (err) {
    showToast(err.message, true);
  } finally {
    btn.textContent = 'Enviar diseños y notificar cliente';
    btn.disabled = false;
  }
});

// ── Init ──────────────────────────────────────────────────────────────────────

initLogin();
