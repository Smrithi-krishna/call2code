create table if not exists public.projects (
  id uuid primary key default gen_random_uuid(),
  vapi_call_id text,
  customer_phone text,
  transcript jsonb not null default '[]'::jsonb,
  website_brief jsonb,
  deployment_url text,
  status text not null default 'in_progress',
  whatsapp_sent_at timestamptz,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

create index if not exists projects_status_idx on public.projects(status);
