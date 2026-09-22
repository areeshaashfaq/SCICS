ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS patient_system_id VARCHAR(100);

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS encounter_type VARCHAR(20);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'documents_encounter_type_check'
    ) THEN
        ALTER TABLE documents
            ADD CONSTRAINT documents_encounter_type_check
            CHECK (encounter_type IS NULL OR encounter_type IN ('inpatient', 'outpatient'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_documents_system_id ON documents(patient_system_id);