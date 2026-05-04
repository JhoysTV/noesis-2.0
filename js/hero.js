/**
 * hero.js — Hero counter animation
 * Triggers animated number counters when hero stats enter the viewport
 */

'use strict';

const Hero = (() => {

  const counterEls = qsa('.hero__stat-num[data-target]');
  let animated = false;

  const runCounters = () => {
    if (animated) return;
    animated = true;
    counterEls.forEach((el) => {
      const target = parseInt(el.dataset.target, 10);
      animateCounter(el, target, 1600);
    });
  };

  const init = () => {
    if (!counterEls.length) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) runCounters();
        });
      },
      { threshold: 0.5 }
    );

    const statsEl = qs('.hero__stats');
    if (statsEl) observer.observe(statsEl);
  };

  return { init };

})();
