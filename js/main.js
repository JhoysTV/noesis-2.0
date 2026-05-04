/**
 * main.js — Application entry point
 * Initialises all modules after DOM is ready
 */

'use strict';

document.addEventListener('DOMContentLoaded', () => {

  // Core UI
  Nav.init();
  Hero.init();
  Portfolio.init();
  Orders.init();

  // Forms & interactions
  QuoteForm.init();
  Upload.init();
  Payment.init();

  // Visual polish
  Animations.init();

  // ── Global keyboard shortcuts ──────────────────────────────

  document.addEventListener('keydown', (e) => {
    // Close any open modal with Escape
    if (e.key === 'Escape') {
      qsa('.modal-overlay:not([hidden])').forEach((modal) => {
        hideEl(modal);
      });
      // Also close mobile nav
      qs('.nav__links--open') && qs('.nav__hamburger')?.click();
    }
  });

  // ── Smooth anchor scrolling (offset for fixed nav) ─────────

  const NAV_HEIGHT = 72; // px — matches nav height in CSS

  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener('click', (e) => {
      const target = document.querySelector(anchor.getAttribute('href'));
      if (!target) return;
      e.preventDefault();
      const top = target.getBoundingClientRect().top + window.scrollY - NAV_HEIGHT;
      window.scrollTo({ top, behavior: 'smooth' });
    });
  });

});
