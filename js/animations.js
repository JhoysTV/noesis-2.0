/**
 * animations.js — Scroll-triggered reveal animations
 * Uses IntersectionObserver to add .is-visible to .fade-up elements
 */

'use strict';

const Animations = (() => {

  const THRESHOLD = 0.12;
  const ROOT_MARGIN = '0px 0px -40px 0px';

  const init = () => {
    const targets = qsa('.fade-up');
    if (!targets.length) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
            // Unobserve after reveal — no need to watch anymore
            observer.unobserve(entry.target);
          }
        });
      },
      {
        threshold: THRESHOLD,
        rootMargin: ROOT_MARGIN,
      }
    );

    targets.forEach((el) => observer.observe(el));
  };

  return { init };

})();
