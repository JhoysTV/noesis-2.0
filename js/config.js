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
  studioEmail: 'info@noesisdelcaribe.com',
  whatsappUrl: 'https://wa.me/18090000000',
  instagramUrl: 'https://www.instagram.com/',
  facebookUrl: 'https://www.facebook.com/',
  linkedinUrl: 'https://www.linkedin.com/',
};
