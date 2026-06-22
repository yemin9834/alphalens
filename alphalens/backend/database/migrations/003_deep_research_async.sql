-- Phase 2: async deep research progress on discovery runs
ALTER TABLE discovery_runs ADD COLUMN IF NOT EXISTS research_status VARCHAR(20) DEFAULT 'pending';
ALTER TABLE discovery_runs ADD COLUMN IF NOT EXISTS research_progress JSONB DEFAULT '{}'::jsonb;
