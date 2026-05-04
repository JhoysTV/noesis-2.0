-- Esquema equivalente para Supabase/PostgreSQL si se migra desde SQLite.
-- Ejecutar en Supabase SQL Editor y adaptar RLS según el panel admin final.

create table if not exists public.orders (
  id text primary key,
  status text not null check (status in ('borrador', 'pagado', 'recibido', 'en_curso', 'entregado', 'cancelado')),
  customer_name text not null,
  customer_email text not null,
  customer_phone text,
  contact_preference text,
  project_type text not null,
  area text,
  requirements text,
  budget text,
  total integer not null check (total >= 0),
  stripe_session_id text unique,
  stripe_payment_intent text,
  created_at timestamptz not null default now(),
  paid_at timestamptz,
  raw_json jsonb not null
);

create table if not exists public.order_lines (
  id bigint generated always as identity primary key,
  order_id text not null references public.orders(id) on delete cascade,
  catalog_item_id text not null,
  name text not null,
  price integer not null check (price >= 0)
);

create table if not exists public.payment_events (
  stripe_event_id text primary key,
  event_type text not null,
  processed_at timestamptz not null default now(),
  payload jsonb not null
);

create table if not exists public.email_logs (
  id bigint generated always as identity primary key,
  order_id text not null,
  recipient text not null,
  subject text not null,
  status text not null,
  created_at timestamptz not null default now(),
  error text
);

alter table public.orders enable row level security;
alter table public.order_lines enable row level security;
alter table public.payment_events enable row level security;
alter table public.email_logs enable row level security;
