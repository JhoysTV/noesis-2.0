/**
 * config.js — Client-side runtime settings.
 *
 * Static mode keeps the site fully usable as a client demo. For production,
 * connect these URLs to a backend that creates Stripe Checkout sessions,
 * persists orders in Supabase and sends transactional emails.
 */

'use strict';

window.NOESIS_CONFIG = {
  mode: 'production',
  apiBaseUrl: '',
  stripeCheckoutEndpoint: '/api/payments/checkout-session',
  studioEmail: 'arqcristaloft@gmail.com',
  whatsappUrl: 'https://wa.me/18295425046',
  instagramUrl: 'https://www.instagram.com/noesis.cb/',
  facebookUrl: 'https://www.facebook.com/',
  linkedinUrl: 'https://www.linkedin.com/in/cristal-fabian-8961b53a7/',
};
