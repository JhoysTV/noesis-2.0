/**
 * form.js — Multi-step quote form logic
 * Handles step navigation, validation and review generation
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
    // Hide current
    getStep(currentStep)?.classList.remove('form-step--active');
    getProg(currentStep)?.classList.remove('form-progress__step--active');
    getProg(currentStep)?.classList.add('form-progress__step--done');

    // Show next
    currentStep = n;
    getStep(n)?.classList.add('form-step--active');

    // Update all progress dots
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

    // Scroll form into view
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

  // ── Form submission ────────────────────────────────────────

  const handleSubmit = () => {
    const termsChecked = qs('#terms')?.checked;
    if (!termsChecked) {
      alert('Por favor acepta los términos y condiciones para continuar.');
      return;
    }

    const formData = {
      name: `${qs('#f-nombre')?.value || ''} ${qs('#f-apellido')?.value || ''}`.trim(),
      email: qs('#f-email')?.value || '',
      phone: qs('#f-tel')?.value || '',
      projectType: qs('#f-tipo')?.value || '',
      requirements: qs('#f-desc')?.value || '',
      area: qs('#f-area')?.value || '',
      budget: qs('#f-presupuesto')?.value || '',
      contactPreference: qs('#f-contacto')?.value || 'Correo electrónico',
    };

    const order = Orders.createDraftOrder(formData);
    if (!order) return;

    showModal('successOverlay');
    Payment.showPaymentSection();
  };

  const resetForm = () => {
    // Reset all fields
    qsa('.form-step input, .form-step textarea, .form-step select')
      .forEach((el) => { el.value = ''; });
    qsa('.form-step input[type="checkbox"]')
      .forEach((cb) => { cb.checked = false; });

    // Go back to step 1 (after a short delay)
    setTimeout(() => showStep(1), 300);
  };

  // ── Modal helpers ──────────────────────────────────────────

  const showModal = (id) => {
    const el = qs(`#${id}`);
    if (el) showEl(el);
  };

  // ── Event bindings ─────────────────────────────────────────

  const init = () => {
    // Step 1
    qs('#step1-next')?.addEventListener('click', () => {
      if (validateStep(1)) showStep(2);
    });

    // Step 2
    qs('#step2-back')?.addEventListener('click', () => showStep(1));
    qs('#step2-next')?.addEventListener('click', () => {
      if (validateStep(2)) showStep(3);
    });

    // Step 3
    qs('#step3-back')?.addEventListener('click', () => showStep(2));
    qs('#step3-next')?.addEventListener('click', () => showStep(4));

    // Step 4
    qs('#step4-back')?.addEventListener('click', () => showStep(3));
    qs('#submitBtn')?.addEventListener('click', handleSubmit);

    // Modal close
    qs('#closeSuccess')?.addEventListener('click', () => {
      hideEl(qs('#successOverlay'));
    });
  };

  return { init };

})();
