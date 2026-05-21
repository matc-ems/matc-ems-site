-- v1.1: per-shift activity materials for the instructor hub.
-- Adds the `activities` JSONB column to the existing `shifts` table.
-- Idempotent — re-running is safe.

alter table shifts
  add column if not exists activities jsonb not null default '{}'::jsonb;
