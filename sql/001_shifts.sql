-- v1: shifts table for the matc-ems-site homepage.
-- Idempotent — re-running is safe.

create table if not exists shifts (
  id                    bigserial primary key,
  shift_date            date    not null,
  am_pm                 text    not null check (am_pm in ('am','pm')),
  cohort_number         int     not null check (cohort_number between 1 and 4),
  class_id              int     not null,
  start_time            time    not null,
  end_time              time    not null,
  title                 text,
  type                  text    check (type is null or type in
                          ('scenario','lecture','skills','clinical','exam')),
  room                  text,
  instructors           jsonb   not null default '[]'::jsonb,
  cohort_lead_last_name text,
  synced_at             timestamptz not null default now(),
  unique (shift_date, cohort_number, start_time)
);

create index if not exists shifts_date_idx on shifts (shift_date);

alter table shifts enable row level security;

drop policy if exists "public read" on shifts;
create policy "public read" on shifts for select using (true);
