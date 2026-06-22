-- Deep research dossier per discovery candidate (Phase 1)
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS deep_research JSONB;
