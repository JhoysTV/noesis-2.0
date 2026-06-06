/**
 * orders.js — Catalog, cart and local order persistence.
 * This mirrors the target draft-order flow before Stripe/Supabase exist.
 */

'use strict';

const Orders = (() => {
  const CART_KEY = 'noesis_cart_v1';
  const ORDERS_KEY = 'noesis_orders_v1';
  const ACTIVE_ORDER_KEY = 'noesis_active_order_v1';

  let cart = [];

  const money = (value) =>
    new Intl.NumberFormat('es-DO', {
      style: 'currency',
      currency: 'DOP',
      maximumFractionDigits: 0,
    }).format(value || 0);

  const readJson = (key, fallback) => {
    try {
      return JSON.parse(localStorage.getItem(key)) || fallback;
    } catch (_err) {
      return fallback;
    }
  };

  const writeJson = (key, value) => {
    localStorage.setItem(key, JSON.stringify(value));
  };

  const getOrders = () => readJson(ORDERS_KEY, []);

  const saveOrders = (orders) => {
    writeJson(ORDERS_KEY, orders);
  };

  const getTotal = (items = cart) =>
    items.reduce((sum, item) => sum + Number(item.price || 0), 0);

  const persistCart = () => writeJson(CART_KEY, cart);

  const setActiveOrder = (order) => {
    writeJson(ACTIVE_ORDER_KEY, order);
  };

  const getActiveOrder = () => readJson(ACTIVE_ORDER_KEY, null);

  const clearActiveOrder = () => localStorage.removeItem(ACTIVE_ORDER_KEY);

  const renderCart = () => {
    const list = qs('#cartItems');
    const total = qs('#cartTotal');
    if (!list || !total) return;

    if (!cart.length) {
      list.innerHTML = '<p class="order-cart__empty">Aún no has elegido servicios.</p>';
      total.textContent = money(0);
      qsa('[data-add-service]').forEach((btn) => {
        btn.textContent = 'Añadir al pedido';
        btn.closest('.service-card')?.classList.remove('service-card--selected');
      });
      return;
    }

    list.innerHTML = cart
      .map((item) => `
        <div class="order-cart__item">
          <strong>${item.name}</strong>
          <span>${money(item.price)}</span>
          <button type="button" class="order-cart__remove" data-remove-service="${item.id}" aria-label="Quitar ${item.name}">×</button>
        </div>`)
      .join('');
    total.textContent = money(getTotal());

    qsa('[data-add-service]').forEach((btn) => {
      const card = btn.closest('.service-card');
      const selected = cart.some((item) => item.id === card?.dataset.serviceId);
      btn.textContent = selected ? 'Añadido' : 'Añadir al pedido';
      card?.classList.toggle('service-card--selected', selected);
    });
  };

  const renderOrderReview = () => {
    const container = qs('#orderReview');
    if (!container) return;

    if (!cart.length) {
      container.innerHTML = '<p class="order-cart__empty">Selecciona al menos un módulo de servicio para continuar con pago.</p>';
      return;
    }

    container.innerHTML = `
      <div class="review-row">
        <span class="review-row__key">Servicios</span>
        <span>${cart.map((item) => item.name).join(', ')}</span>
      </div>
      <div class="review-row">
        <span class="review-row__key">Total</span>
        <span>${money(getTotal())}</span>
      </div>
    `;
  };

  const renderPayment = (order) => {
    const active = order || getActiveOrder();
    const totalEl = qs('#paymentTotal');
    const projectEl = qs('#paymentProject');
    const breakdownEl = qs('#paymentBreakdown');
    const payBtn = qs('#payBtn');
    if (!active || !totalEl || !projectEl || !breakdownEl || !payBtn) return;

    totalEl.innerHTML = `<span class="quote-summary__currency">RD$</span>${Number(active.total || 0).toLocaleString('es-DO')}`;
    projectEl.textContent = `${active.projectType || 'Pedido'} — ${active.area || 0} m² — ${active.id}`;
    breakdownEl.innerHTML = active.items
      .map((item) => `
        <div class="quote-line" role="row">
          <span role="cell">${item.name}</span>
          <span role="cell">${money(item.price)}</span>
        </div>`)
      .join('') + `
        <div class="quote-line quote-line--total" role="row">
          <span role="cell"><strong>Total</strong></span>
          <span role="cell" class="quote-line__total-amount">${money(active.total)}</span>
        </div>`;
    payBtn.textContent = `Pagar ${money(active.total)}`;
  };

  const addFromCard = (card) => {
    if (!card?.dataset.serviceId) return;
    const item = {
      id: card.dataset.serviceId,
      name: card.dataset.serviceName,
      price: Number(card.dataset.servicePrice || 0),
    };

    if (cart.some((selected) => selected.id === item.id)) {
      cart = cart.filter((selected) => selected.id !== item.id);
    } else {
      cart = [...cart, item];
    }

    persistCart();
    renderCart();
    renderOrderReview();
  };

  const createDraftOrder = (formData) => {
    if (!cart.length) {
      alert('Selecciona al menos un módulo de servicio antes de crear el pedido.');
      return null;
    }

    const order = {
      id: `NOE-${Date.now().toString().slice(-6)}`,
      status: 'borrador',
      paymentProvider: 'stripe_test_simulado',
      stripeSessionId: null,
      emailNotifications: [],
      createdAt: new Date().toISOString(),
      paidAt: null,
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
      items: [...cart],
      total: getTotal(),
    };

    const orders = getOrders().filter((existing) => existing.id !== order.id);
    saveOrders([order, ...orders]);
    setActiveOrder(order);
    renderPayment(order);
    return order;
  };

  const markActiveOrderPaid = () => {
    const active = getActiveOrder();
    if (!active) return null;

    const paidOrder = {
      ...active,
      status: 'pagado',
      paidAt: new Date().toISOString(),
      stripeSessionId: `cs_test_${active.id.toLowerCase()}`,
      emailNotifications: [
        `Resumen enviado a ${active.customer.email}`,
        'Orden detallada enviada al arquitecto',
      ],
    };

    const orders = getOrders().map((order) =>
      order.id === paidOrder.id ? paidOrder : order
    );
    saveOrders(orders);
    setActiveOrder(paidOrder);
    cart = [];
    persistCart();
    renderCart();
    return paidOrder;
  };

  const init = () => {
    cart = readJson(CART_KEY, []);
    const availableIds = qsa('[data-service-id]').map((card) => card.dataset.serviceId);
    cart = cart.filter((item) => availableIds.includes(item.id));
    persistCart();

    qsa('[data-add-service]').forEach((btn) => {
      btn.addEventListener('click', () => addFromCard(btn.closest('.service-card')));
    });

    qs('#cartItems')?.addEventListener('click', (event) => {
      const removeBtn = event.target.closest('[data-remove-service]');
      if (!removeBtn) return;
      cart = cart.filter((item) => item.id !== removeBtn.dataset.removeService);
      persistCart();
      renderCart();
      renderOrderReview();
    });

    renderCart();
    renderOrderReview();
    renderPayment();
  };

  const getCart = () => [...cart];

  const clearCart = () => {
    cart = [];
    persistCart();
    renderCart();
    renderOrderReview();
  };

  return {
    init,
    money,
    renderOrderReview,
    createDraftOrder,
    markActiveOrderPaid,
    getActiveOrder,
    clearActiveOrder,
    getCart,
    clearCart,
  };
})();
