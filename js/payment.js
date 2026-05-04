/**
 * payment.js — Payment section behavior
 * - Payment method selection
 * - Card number / expiry live formatting & preview
 * - Payment processing (simulation)
 */

'use strict';

const Payment = (() => {

  // ── DOM references ─────────────────────────────────────────
  const methodBtns    = qsa('.pay-method');
  const cardNumInput  = qs('#cardNum');
  const cardNameInput = qs('#cardName');
  const cardExpInput  = qs('#cardExp');
  const cardCvvInput  = qs('#cardCvv');

  const numPreview    = qs('#cardNumPreview');
  const namePreview   = qs('#cardNamePreview');
  const expPreview    = qs('#cardExpPreview');

  const payBtn        = qs('#payBtn');
  const paySection    = qs('#pago');

  // ── Payment method toggle ──────────────────────────────────

  const initMethodToggle = () => {
    methodBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        methodBtns.forEach((b) => {
          b.classList.remove('pay-method--selected');
          b.setAttribute('aria-pressed', 'false');
        });
        btn.classList.add('pay-method--selected');
        btn.setAttribute('aria-pressed', 'true');
      });
    });
  };

  // ── Card number formatting & preview ──────────────────────

  const initCardInputs = () => {
    cardNumInput?.addEventListener('input', (e) => {
      const formatted = formatCardNumber(e.target.value);
      e.target.value = formatted;
      if (numPreview) {
        numPreview.textContent = formatted || '•••• •••• •••• ••••';
      }
    });

    cardNameInput?.addEventListener('input', (e) => {
      if (namePreview) {
        namePreview.textContent = e.target.value.toUpperCase() || 'NOMBRE APELLIDO';
      }
    });

    cardExpInput?.addEventListener('input', (e) => {
      const formatted = formatExpiry(e.target.value);
      e.target.value = formatted;
      if (expPreview) {
        expPreview.textContent = formatted || 'MM/AA';
      }
    });

    // CVV: digits only
    cardCvvInput?.addEventListener('input', (e) => {
      e.target.value = e.target.value.replace(/\D/g, '').substring(0, 4);
    });
  };

  // ── Validation ─────────────────────────────────────────────

  const validateCard = () => {
    if (window.NOESIS_CONFIG?.mode === 'production') return true;

    const selectedMethod = qs('.pay-method--selected')?.dataset.method || 'card';
    if (selectedMethod !== 'card') return true;

    const num  = cardNumInput?.value.replace(/\s/g, '') || '';
    const name = cardNameInput?.value.trim() || '';
    const exp  = cardExpInput?.value || '';
    const cvv  = cardCvvInput?.value || '';

    if (num.length < 16) {
      alert('Por favor ingresa un número de tarjeta de prueba válido (16 dígitos).');
      return false;
    }
    if (!name) {
      alert('Por favor ingresa el nombre que aparece en la tarjeta.');
      return false;
    }
    if (exp.length < 5) {
      alert('Por favor ingresa la fecha de vencimiento (MM/AA).');
      return false;
    }
    if (cvv.length < 3) {
      alert('Por favor ingresa el código CVV de la tarjeta.');
      return false;
    }
    return true;
  };

  // ── Payment processing ─────────────────────────────────────

  const processPayment = async () => {
    if (!validateCard()) return;

    const selectedMethod = qs('.pay-method--selected')?.dataset.method || 'card';
    const config = window.NOESIS_CONFIG || {};
    const activeOrder = Orders.getActiveOrder?.();

    if (!activeOrder) {
      alert('Primero crea un pedido desde el formulario de cotización.');
      return;
    }

    // Show loading state
    if (payBtn) {
      payBtn.textContent = selectedMethod === 'card' ? 'Procesando en Stripe test…' : 'Registrando pago…';
      payBtn.disabled = true;
    }

    if (config.mode === 'production' && config.apiBaseUrl && config.stripeCheckoutEndpoint) {
      try {
        const response = await fetch(`${config.apiBaseUrl}${config.stripeCheckoutEndpoint}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ order: activeOrder }),
        });
        if (!response.ok) throw new Error('No se pudo iniciar Stripe Checkout.');
        const data = await response.json();
        if (!data.url) throw new Error('El backend no devolvió la URL de Stripe.');
        window.location.href = data.url;
        return;
      } catch (error) {
        alert(error.message || 'No se pudo iniciar el pago.');
        if (payBtn) {
          payBtn.textContent = `Pagar ${Orders.money(activeOrder.total)}`;
          payBtn.disabled = false;
        }
        return;
      }
    }

    // Simulates Stripe Checkout + webhook confirmation.
    setTimeout(() => {
      const order = Orders.markActiveOrderPaid();

      if (payBtn) {
        payBtn.textContent = order ? `Pagado ${Orders.money(order.total)}` : 'Pagar';
        payBtn.disabled = false;
      }

      const desc = qs('#paySuccessDesc');
      if (desc && order) {
        desc.textContent = `Pago confirmado para ${order.id}. Se simuló el envío del resumen a ${order.customer.email} y de la orden detallada al arquitecto.`;
      }

      // Show success modal
      const modal = qs('#paySuccessOverlay');
      if (modal) showEl(modal);
    }, 2000);
  };

  // ── Close modal ────────────────────────────────────────────

  const initModalClose = () => {
    qs('#closePaySuccess')?.addEventListener('click', () => {
      hideEl(qs('#paySuccessOverlay'));
    });
  };

  // ── Reveal payment section ─────────────────────────────────

  /**
   * Show payment section — called externally after quote is accepted
   */
  const showPaymentSection = () => {
    if (!paySection) return;
    showEl(paySection);
    paySection.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  // ── Init ───────────────────────────────────────────────────

  const init = () => {
    initMethodToggle();
    initCardInputs();
    const note = qs('#paymentModeNote');
    if (note && window.NOESIS_CONFIG?.mode === 'production') {
      note.textContent = 'Pago seguro: serás redirigido a Stripe Checkout. No guardamos datos de tarjeta en este sitio.';
    }
    payBtn?.addEventListener('click', processPayment);
    initModalClose();
  };

  return { init, showPaymentSection };

})();
