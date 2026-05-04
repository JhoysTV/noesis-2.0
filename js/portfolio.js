/**
 * portfolio.js — Portfolio filter behavior
 */

'use strict';

const Portfolio = (() => {

  const filterBtns = qsa('.filter-btn');
  const items      = qsa('.port-item');

  const filter = (category) => {
    items.forEach((item) => {
      const match = category === 'all' || item.dataset.cat === category;
      item.classList.toggle('port-item--hidden', !match);
      // Accessibility
      item.setAttribute('aria-hidden', String(!match));
    });
  };

  const init = () => {
    filterBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        // Update active state
        filterBtns.forEach((b) => {
          b.classList.remove('filter-btn--active');
          b.removeAttribute('aria-pressed');
        });
        btn.classList.add('filter-btn--active');
        btn.setAttribute('aria-pressed', 'true');

        filter(btn.dataset.filter);
      });
    });
  };

  return { init };

})();
