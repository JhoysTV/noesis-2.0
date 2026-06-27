'use strict';

const STATUS_ORDER = ['recibido', 'cotizado', 'pagado', 'en_curso', 'entregado'];

const STATUS_LABELS = {
  borrador: 'Borrador', recibido: 'En revisión', cotizado: 'Cotización lista',
  pagado: 'Pago recibido', en_curso: 'En proceso', entregado: 'Entregado', cancelado: 'Cancelado',
};
const STATUS_COLORS = {
  borrador: '#888', recibido: '#D3AB2D', cotizado: '#4A90D9',
  pagado: '#27AE60', en_curso: '#8E44AD', entregado: '#2ECC71', cancelado: '#E74C3C',
};

const money = (v) =>
  new Intl.NumberFormat('es-DO', { style: 'currency', currency: 'DOP', maximumFractionDigits: 0 }).format(v || 0);

function qs(sel, ctx = document) { return ctx.querySelector(sel); }
function show(el) { if (el) el.hidden = false; }
function hide(el) { if (el) el.hidden = true; }

// ── URL params ────────────────────────────────────────────────────────────────

const params = new URLSearchParams(location.search);
const TOKEN = params.get('token') || '';
const PAYMENT_RESULT = params.get('payment') || '';

// ── Timeline ──────────────────────────────────────────────────────────────────

function renderTimeline(status) {
  const steps = Array.from(document.querySelectorAll('.os-timeline__step'));
  const currentIdx = STATUS_ORDER.indexOf(status);
  steps.forEach((step, i) => {
    step.classList.remove('os-timeline__step--done', 'os-timeline__step--active', 'os-timeline__step--pending');
    if (i < currentIdx) step.classList.add('os-timeline__step--done');
    else if (i === currentIdx) step.classList.add('os-timeline__step--active');
    else step.classList.add('os-timeline__step--pending');
  });
}

// ── Order summary ─────────────────────────────────────────────────────────────

function renderSummary(order) {
  const c = order.customer || {};
  const rows = [
    ['Cliente', c.name],
    ['Correo', c.email],
    ['Teléfono', c.phone || '—'],
    ['Tipo de proyecto', order.projectType],
    ['Área', order.area ? `${order.area} m²` : '—'],
    ['Presupuesto estimado', order.budget || '—'],
    ['Descripción', order.requirements || '—'],
  ];

  if (order.items?.length) {
    rows.push(['Servicios', order.items.map((i) => i.name).join(', ')]);
  }

  qs('#orderSummary').innerHTML = rows.map(([k, v]) => `
    <div class="os-info-row">
      <span class="os-info-row__key">${k}</span>
      <span>${escapeHTML(v) || '—'}</span>
    </div>
  `).join('');
}

// ── Quote panel ───────────────────────────────────────────────────────────────

function renderQuote(order, quote) {
  if (!quote) return;
  qs('#quoteAmount').textContent = money(quote.total);

  const details = [];
  if (quote.scope) details.push(`<p><strong>Alcance:</strong> ${escapeHTML(quote.scope)}</p>`);
  if (quote.notes) details.push(`<p><strong>Notas del arquitecto:</strong> ${escapeHTML(quote.notes)}</p>`);
  if (quote.deadlineDays) details.push(`<p><strong>Plazo estimado:</strong> ${escapeHTML(String(quote.deadlineDays))} días hábiles</p>`);
  qs('#quoteDetails').innerHTML = details.join('') || '';
}

// ── Pay button ────────────────────────────────────────────────────────────────

function initPayButton(order) {
  const btn = qs('#payBtn');
  if (!btn) return;

  btn.addEventListener('click', async () => {
    btn.textContent = 'Redirigiendo a pago seguro...';
    btn.disabled = true;
    try {
      const res = await fetch('/api/order/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: TOKEN }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'No se pudo iniciar el pago.');
      }
      const data = await res.json();
      if (data.url) {
        window.location.href = data.url;
      } else {
        throw new Error('El servidor no devolvió la URL de pago.');
      }
    } catch (e) {
      alert(e.message);
      btn.textContent = 'Aceptar y pagar ahora';
      btn.disabled = false;
    }
  });
}

// ── Delivery files ────────────────────────────────────────────────────────────

function renderDeliveryFiles(files) {
  const list = qs('#deliveryFileList');
  if (!files?.length) {
    list.innerHTML = '<p>Los archivos serán listados aquí cuando sean entregados.</p>';
    return;
  }
  list.innerHTML = files.map((f) => `
    <a class="os-file-chip" href="/uploads/${escapeHTML(f.storedName)}" download="${escapeHTML(f.originalName)}" target="_blank" rel="noopener">
      <span class="os-file-chip__icon" aria-hidden="true">📦</span>
      <span class="os-file-chip__name">${escapeHTML(f.originalName)}</span>
      <span class="os-file-chip__size">${(f.sizeBytes / 1024).toFixed(0)} KB</span>
      <span class="os-file-chip__dl" aria-hidden="true">↓</span>
    </a>
  `).join('');
}

// ── Status badge ──────────────────────────────────────────────────────────────

function renderStatusBadge(status) {
  const el = qs('#osStatusBadge');
  el.textContent = STATUS_LABELS[status] || status;
  el.style.background = STATUS_COLORS[status] || '#888';
}

// ── Panel visibility ──────────────────────────────────────────────────────────

function showPanel(status) {
  hide(qs('#pendingPanel'));
  hide(qs('#quotePanel'));
  hide(qs('#paidPanel'));
  hide(qs('#inProgressPanel'));
  hide(qs('#deliveryPanel'));

  switch (status) {
    case 'recibido':
      show(qs('#pendingPanel'));
      break;
    case 'cotizado':
      show(qs('#quotePanel'));
      break;
    case 'pagado':
      show(qs('#paidPanel'));
      break;
    case 'en_curso':
      show(qs('#inProgressPanel'));
      break;
    case 'entregado':
      show(qs('#deliveryPanel'));
      break;
    default:
      show(qs('#pendingPanel'));
  }
}

// ── Main init ─────────────────────────────────────────────────────────────────

async function init() {
  if (!TOKEN) {
    hide(qs('#osLoading'));
    show(qs('#osError'));
    return;
  }

  try {
    const res = await fetch(`/api/order/${TOKEN}`);
    if (!res.ok) throw new Error('not_found');
    const { order, quote, deliveryFiles } = await res.json();

    hide(qs('#osLoading'));
    show(qs('#osContent'));

    // Payment result banner
    if (PAYMENT_RESULT === 'success') show(qs('#paymentSuccessBanner'));

    // Populate UI
    qs('#osOrderId').textContent = order.id;
    renderStatusBadge(order.status);
    renderTimeline(order.status);
    renderSummary(order);
    renderQuote(order, quote);
    renderDeliveryFiles(deliveryFiles);
    showPanel(order.status);

    if (order.status === 'cotizado') {
      initPayButton(order);
    }

  } catch (_) {
    hide(qs('#osLoading'));
    show(qs('#osError'));
  }
}

init();
