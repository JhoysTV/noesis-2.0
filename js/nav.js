/**
 * nav.js — Navigation behavior
 * - Scroll shadow
 * - Active link highlighting
 * - Mobile hamburger toggle
 */

'use strict';

const Nav = (() => {

  const nav        = qs('.nav');
  const toggle     = qs('#navToggle');
  const menu       = qs('#navMenu');
  const navLinks   = qsa('.nav__links a');
  const sections   = qsa('section[id]');

  // ── Scroll shadow & active link ────────────────────────────

  const onScroll = debounce(() => {
    // Shadow
    nav.classList.toggle('nav--scrolled', window.scrollY > 10);

    // Active section highlight
    let currentId = '';
    sections.forEach((sec) => {
      if (window.scrollY >= sec.offsetTop - 110) {
        currentId = sec.id;
      }
    });

    navLinks.forEach((a) => {
      const href = a.getAttribute('href');
      const isCurrent = href === '#' + currentId;
      a.setAttribute('aria-current', isCurrent ? 'page' : 'false');
    });
  }, 60);

  // ── Mobile hamburger ────────────────────────────────────────

  const toggleMenu = () => {
    const isOpen = menu.classList.toggle('nav__links--open');
    setExpanded(toggle, isOpen);
    toggle.setAttribute('aria-label', isOpen ? 'Cerrar menú' : 'Abrir menú');
  };

  // Close menu on link click (mobile)
  const closeMenu = () => {
    menu.classList.remove('nav__links--open');
    setExpanded(toggle, false);
    toggle.setAttribute('aria-label', 'Abrir menú');
  };

  // ── Init ───────────────────────────────────────────────────

  const init = () => {
    window.addEventListener('scroll', onScroll, { passive: true });
    toggle?.addEventListener('click', toggleMenu);
    navLinks.forEach((a) => a.addEventListener('click', closeMenu));

    // Close on outside click
    document.addEventListener('click', (e) => {
      if (menu.classList.contains('nav__links--open') &&
          !nav.contains(e.target)) {
        closeMenu();
      }
    });
  };

  return { init };

})();
