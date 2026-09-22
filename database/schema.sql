CREATE TABLE IF NOT EXISTS icd_codes (
    icd_code     VARCHAR(20)  PRIMARY KEY,
    description  TEXT         NOT NULL,
    chapter      VARCHAR(100),
    category     VARCHAR(100),
    is_billable  BOOLEAN      DEFAULT TRUE
);


-- ── Discharge summaries ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS documents (
    document_id        SERIAL        PRIMARY KEY,
    source_filename    VARCHAR(255),
    patient_ref        VARCHAR(100),
    raw_text           TEXT          NOT NULL,
    upload_date        TIMESTAMP     DEFAULT NOW(),
    status             VARCHAR(20)   DEFAULT 'pending',
    notes              TEXT,

    patient_system_id  VARCHAR(100),
    encounter_type     VARCHAR(20),

    CONSTRAINT documents_status_check
        CHECK (status IN ('pending', 'processing', 'reviewed', 'finalized')),
    CONSTRAINT documents_encounter_type_check
        CHECK (encounter_type IS NULL OR encounter_type IN ('inpatient', 'outpatient'))
);


-- ── Suggested codes ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS suggestions (
    suggestion_id      SERIAL        PRIMARY KEY,
    document_id        INTEGER       NOT NULL,
    suggestion_type    VARCHAR(30)   NOT NULL,
    extracted_text     TEXT          NOT NULL,
    icd_code           VARCHAR(20),
    confidence_score   NUMERIC,
    source_char_start  INTEGER       NOT NULL,
    source_char_end    INTEGER       NOT NULL,
    source_snippet     TEXT,
    is_ambiguous       BOOLEAN       DEFAULT FALSE,
    ambiguity_reason   TEXT,
    coder_decision     VARCHAR(20)   DEFAULT 'pending',
    created_at         TIMESTAMP     DEFAULT NOW(),

    CONSTRAINT suggestions_document_id_fkey
        FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE,
    CONSTRAINT suggestions_icd_code_fkey
        FOREIGN KEY (icd_code) REFERENCES icd_codes(icd_code),
    CONSTRAINT suggestions_suggestion_type_check
        CHECK (suggestion_type IN ('diagnosis_principal', 'diagnosis_associative',
                                   'procedure_principal', 'procedure_associative',
                                   'medication')),
    CONSTRAINT suggestions_coder_decision_check
        CHECK (coder_decision IN ('pending', 'approved', 'rejected', 'edited')),
    CONSTRAINT suggestions_confidence_score_check
        CHECK (confidence_score >= 0 AND confidence_score <= 1)
);


-- ── Coder decisions (the audit trail) ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS corrections (
    correction_id       SERIAL        PRIMARY KEY,
    suggestion_id       INTEGER       NOT NULL,
    original_icd_code   VARCHAR(20),
    corrected_icd_code  VARCHAR(20),
    correction_type     VARCHAR(20),
    coder_name          VARCHAR(100),
    comment             TEXT,
    corrected_at        TIMESTAMP     DEFAULT NOW(),
    document_id         INTEGER,

    CONSTRAINT corrections_suggestion_id_fkey
        FOREIGN KEY (suggestion_id) REFERENCES suggestions(suggestion_id) ON DELETE CASCADE,
    CONSTRAINT corrections_document_id_fkey
        FOREIGN KEY (document_id) REFERENCES documents(document_id),
    CONSTRAINT corrections_corrected_icd_code_fkey
        FOREIGN KEY (corrected_icd_code) REFERENCES icd_codes(icd_code),
    CONSTRAINT corrections_correction_type_check
        CHECK (correction_type IN ('reclassified', 'rejected', 'added_missed', 'confirmed'))
);


-- ── Query assistant history ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chat_messages (
    message_id             SERIAL        PRIMARY KEY,
    document_id            INTEGER       NOT NULL,
    related_suggestion_id  INTEGER,
    sender                 VARCHAR(20)   NOT NULL,
    message_text           TEXT          NOT NULL,
    created_at             TIMESTAMP     DEFAULT NOW(),

    CONSTRAINT chat_messages_document_id_fkey
        FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE,
    CONSTRAINT chat_messages_related_suggestion_id_fkey
        FOREIGN KEY (related_suggestion_id) REFERENCES suggestions(suggestion_id),
    CONSTRAINT chat_messages_sender_check
        CHECK (sender IN ('coder', 'assistant'))
);


-- ── Phrases learned from coder corrections ──────────────────────────────────
-- Loaded by the NLP at startup, so a code a coder fixes once is matched
-- correctly the next time.
CREATE TABLE IF NOT EXISTS learned_synonyms (
    synonym_id                  SERIAL        PRIMARY KEY,
    phrase                      TEXT          NOT NULL,
    icd_code                    VARCHAR(20)   NOT NULL,
    learned_from_correction_id  INTEGER,
    created_at                  TIMESTAMP     DEFAULT NOW(),

    CONSTRAINT learned_synonyms_icd_code_fkey
        FOREIGN KEY (icd_code) REFERENCES icd_codes(icd_code),
    CONSTRAINT learned_synonyms_learned_from_correction_id_fkey
        FOREIGN KEY (learned_from_correction_id) REFERENCES corrections(correction_id)
);


-- ── Retraining runs ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS retraining_batches (
    batch_id              SERIAL        PRIMARY KEY,
    started_at            TIMESTAMP     DEFAULT NOW(),
    completed_at          TIMESTAMP,
    num_corrections_used  INTEGER,
    status                VARCHAR(20)   DEFAULT 'running',
    notes                 TEXT,

    CONSTRAINT retraining_batches_status_check
        CHECK (status IN ('running', 'completed', 'failed'))
);


-- ── Accounts ────────────────────────────────────────────────────────────────
-- Temporary: SIUT intends to replace this with their own hospital login.
-- Kept until that integration exists, so the data is never left unprotected.
CREATE TABLE IF NOT EXISTS users (
    user_id        SERIAL        PRIMARY KEY,
    username       VARCHAR(100)  NOT NULL,
    password_hash  TEXT          NOT NULL,
    name           VARCHAR(100),
    role           VARCHAR(20)   DEFAULT 'coder',
    created_at     TIMESTAMP     DEFAULT NOW(),

    CONSTRAINT users_username_key UNIQUE (username),
    CONSTRAINT users_role_check CHECK (role IN ('coder', 'admin'))
);


-- ── Indexes for the queries the app actually runs ───────────────────────────
CREATE INDEX IF NOT EXISTS idx_suggestions_document   ON suggestions(document_id);
CREATE INDEX IF NOT EXISTS idx_corrections_document   ON corrections(document_id);
CREATE INDEX IF NOT EXISTS idx_corrections_suggestion ON corrections(suggestion_id);
CREATE INDEX IF NOT EXISTS idx_chat_document          ON chat_messages(document_id);
CREATE INDEX IF NOT EXISTS idx_documents_status       ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_system_id    ON documents(patient_system_id);