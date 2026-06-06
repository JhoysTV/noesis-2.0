/**
 * form.js — Multi-step quote form logic
 * Handles step navigation, validation, file upload and API submission.
 */

'use strict';

const QuoteForm = (() => {

  let currentStep = 1;
  const TOTAL_STEPS = 4;

  // ── DOM references ─────────────────────────────────────────

  const getStep  = (n) => qs(`#step-${n}`);
  const getProg  = (n) => qs(`#prog-${n}`);

  // ── Step transitions ───────────────────────────────────────

  const showStep = (n) => {
    getStep(currentStep)?.classList.remove('form-step--active');
    getProg(currentStep)?.classList.remove('form-progress__step--active');
    getProg(currentStep)?.classList.add('form-progress__step--done');

    currentStep = n;
    getStep(n)?.classList.add('form-step--active');

    for (let i = 1; i <= TOTAL_STEPS; i++) {
      const prog = getProg(i);
      if (!prog) continue;
      prog.classList.remove('form-progress__step--active', 'form-progress__step--done');
      if (i < n) prog.classList.add('form-progress__step--done');
      if (i === n) {
        prog.classList.add('form-progress__step--active');
        prog.setAttribute('aria-current', 'step');
      } else {
        prog.removeAttribute('aria-current');
      }
    }

    if (n === 4) buildReview();
    qs('.form-card')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  // ── Basic validation ───────────────────────────────────────

  const validateStep = (n) => {
    if (n === 1) {
      const nombre = qs('#f-nombre')?.value.trim();
      const email  = qs('#f-email')?.value.trim();
      const tipo   = qs('#f-tipo')?.value;
      if (!nombre || !email || !tipo) {
        alert('Por favor completa Nombre, Correo electrónico y Tipo de proyecto.');
        return false;
      }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        alert('Por favor ingresa un correo electrónico válido.');
        return false;
      }
    }
    if (n === 2) {
      const area = qs('#f-area')?.value;
      if (!area || Number(area) <= 0) {
        alert('Por favor indica el área total del espacio.');
        return false;
      }
    }
    return true;
  };

  // ── Build review summary ───────────────────────────────────

  const buildReview = () => {
    const container = qs('#reviewContent');
    if (!container) return;

    const ambientes = qsa('#ambientesGroup input:checked')
      .map((cb) => cb.value)
      .join(', ') || '—';

    const data = {
      'Nombre':      `${qs('#f-nombre')?.value || ''} ${qs('#f-apellido')?.value || ''}`.trim() || '—',
      'Correo':      qs('#f-email')?.value || '—',
      'Teléfono':    qs('#f-tel')?.value || '—',
      'Proyecto':    qs('#f-tipo')?.value || '—',
      'Área':        qs('#f-area')?.value ? `${qs('#f-area').value} m²` : '—',
      'Ambientes':   ambientes,
      'Presupuesto': qs('#f-presupuesto')?.value || '—',
    };

    container.innerHTML = Object.entries(data)
      .map(
        ([key, val]) => `
        <div class="review-row">
          <span class="review-row__key">${key}</span>
          <span>${val}</span>
        </div>`
      )
      .join('');

    Orders.renderOrderReview();
  };

  // ── Collect form data ──────────────────────────────────────

  const collectFormData = () => ({
    name: `${qs('#f-nombre')?.value || ''} ${qs('#f-apellido')?.value || ''}`.trim(),
    email: qs('#f-email')?.value || '',
    phone: qs('#f-tel')?.value || '',
    projectType: qs('#f-tipo')?.value || '',
    requirements: qs('#f-desc')?.value || '',
    area: qs('#f-area')?.value || '',
    budget: qs('#f-presupuesto')?.value || '',
    contactPreference: qs('#f-contacto')?.value || 'Correo electrónico',
    photoNotes: qs('#f-fotos-notas')?.value || '',
  });

  // ── API submission ─────────────────────────────────────────

  const submitToApi = async (formData) => {
    const cart = Orders.getCart ? Orders.getCart() : [];
    if (!cart.length) {
      alert('Selecciona al menos un módulo de servicio antes de enviar la solicitud.');
      return null;
    }

    const orderPayload = {
      customer: {
        name: formData.name,
        email: formData.email,
        phone: formData.phone,
        contactPreference: formData.contactPreference,
      },
      projectType: formData.projectType,
      area: formData.area,
      requirements: formData.requirements,
      budget: formData.budget,
      photoNotes: formData.photoNotes,
      items: cart,
      total: cart.reduce((s, i) => s + Number(i.price || 0), 0),
    };

    const body = new FormData();
    body.append('order_data', JSON.stringify(orderPayload));

    // Attach selected photos from Upload module
    const photos = Upload.getFiles ? Upload.getFiles() : [];
    photos.forEach((file) => body.append('files', file));

    const res = await fetch('/api/orders/submit', { method: 'POST', body });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Error al enviar la solicitud.' }));
      throw new Error(err.detail || 'Error al enviar la solicitud.');
    }
    return res.json();
  };

  // ── Form submission ────────────────────────────────────────

  const handleSubmit = async () => {
    const termsChecked = qs('#terms')?.checked;
    if (!termsChecked) {
      alert('Por favor acepta los términos y condiciones para continuar.');
      return;
    }

    const submitBtn = qs('#submitBtn');
    const originalText = submitBtn?.textContent || 'Enviar solicitud';
    if (submitBtn) {
      submitBtn.textContent = 'Enviando solicitud...';
      submitBtn.disabled = true;
    }

    try {
      const formData = collectFormData();
      const result = await submitToApi(formData);

      if (!result) return;

      // Store order reference in localStorage for UX continuity
      const activeOrder = {
        id: result.orderId,
        clientToken: result.clientToken,
        customerName: formData.name,
        customerEmail: formData.email,
        status: 'recibido',
      };
      localStorage.setItem('noesis_last_order', JSON.stringify(activeOrder));

      // Show success modal
      const successDesc = qs('#successDesc');
      if (successDesc) {
        successDesc.innerHTML = `
          Tu solicitud <strong>${result.orderId}</strong> fue enviada correctamente.<br>
          Recibirás tu cotización en <strong>${formData.email}</strong> en 24–48 horas hábiles.
          <br><br>
          <a href="/mi-pedido?token=${result.clientToken}" class="btn btn--outline" style="margin-top:.5rem">
            Ver estado de mi solicitud →
          </a>
        `;
      }
      showModal('successOverlay');
      Orders.clearCart();

    } catch (err) {
      alert(err.message || 'Ocurrió un error. Por favor intenta de nuevo.');
    } finally {
      if (submitBtn) {
        submitBtn.textContent = originalText;
        submitBtn.disabled = false;
      }
    }
  };

  const resetForm = () => {
    qsa('.form-step input, .form-step textarea, .form-step select')
      .forEach((el) => { el.value = ''; });
    qsa('.form-step input[type="checkbox"]')
      .forEach((cb) => { cb.checked = false; });
    setTimeout(() => showStep(1), 300);
  };

  // ── Modal helpers ──────────────────────────────────────────

  const showModal = (id) => {
    const el = qs(`#${id}`);
    if (el) showEl(el);
  };

  // ── Event bindings ─────────────────────────────────────────

  const init = () => {
    qs('#step1-next')?.addEventListener('click', () => {
      if (validateStep(1)) showStep(2);
    });

    qs('#step2-back')?.addEventListener('click', () => showStep(1));
    qs('#step2-next')?.addEventListener('click', () => {
      if (validateStep(2)) showStep(3);
    });

    qs('#step3-back')?.addEventListener('click', () => showStep(2));
    qs('#step3-next')?.addEventListener('click', () => showStep(4));

    qs('#step4-back')?.addEventListener('click', () => showStep(3));
    qs('#submitBtn')?.addEventListener('click', handleSubmit);

    qs('#closeSuccess')?.addEventListener('click', () => {
      hideEl(qs('#successOverlay'));
    });
  };

  return { init };

})();
