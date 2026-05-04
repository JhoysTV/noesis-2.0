/**
 * utils.js — Shared utility functions
 * Nóesis del Caribe
 */

'use strict';

/**
 * Shorthand querySelector
 * @param {string} selector
 * @param {Element} [context=document]
 * @returns {Element|null}
 */
const qs = (selector, context = document) => context.querySelector(selector);

/**
 * Shorthand querySelectorAll → Array
 * @param {string} selector
 * @param {Element} [context=document]
 * @returns {Element[]}
 */
const qsa = (selector, context = document) =>
  Array.from(context.querySelectorAll(selector));

/**
 * Clamp a number between min and max
 * @param {number} val
 * @param {number} min
 * @param {number} max
 * @returns {number}
 */
const clamp = (val, min, max) => Math.min(Math.max(val, min), max);

/**
 * Debounce a function
 * @param {Function} fn
 * @param {number} delay ms
 * @returns {Function}
 */
const debounce = (fn, delay = 200) => {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
};

/**
 * Show an element (remove hidden attribute + display none)
 * @param {Element} el
 */
const showEl = (el) => {
  if (!el) return;
  el.hidden = false;
  el.removeAttribute('hidden');
};

/**
 * Hide an element
 * @param {Element} el
 */
const hideEl = (el) => {
  if (!el) return;
  el.hidden = true;
};

/**
 * Toggle aria-expanded on a button
 * @param {Element} btn
 * @param {boolean} expanded
 */
const setExpanded = (btn, expanded) => {
  if (!btn) return;
  btn.setAttribute('aria-expanded', String(expanded));
};

/**
 * Format a credit card number string (groups of 4)
 * @param {string} raw
 * @returns {string}
 */
const formatCardNumber = (raw) => {
  const digits = raw.replace(/\D/g, '').substring(0, 16);
  return digits.replace(/(.{4})/g, '$1 ').trim();
};

/**
 * Format card expiry as MM/AA
 * @param {string} raw
 * @returns {string}
 */
const formatExpiry = (raw) => {
  const digits = raw.replace(/\D/g, '').substring(0, 4);
  if (digits.length >= 3) {
    return digits.substring(0, 2) + '/' + digits.substring(2);
  }
  return digits;
};

/**
 * Animate a numeric counter from 0 to target
 * @param {Element} el
 * @param {number} target
 * @param {number} [duration=1400] ms
 */
const animateCounter = (el, target, duration = 1400) => {
  if (!el) return;
  const start = performance.now();

  const tick = (now) => {
    const elapsed = now - start;
    const progress = clamp(elapsed / duration, 0, 1);
    // Ease-out cubic
    const eased = 1 - Math.pow(1 - progress, 3);
    el.textContent = Math.round(eased * target);
    if (progress < 1) requestAnimationFrame(tick);
  };

  requestAnimationFrame(tick);
};

/**
 * Format bytes to human-readable string
 * @param {number} bytes
 * @returns {string}
 */
const formatBytes = (bytes) => {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
};
