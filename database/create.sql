DROP TABLE IF EXISTS retraining_batches, chat_messages, corrections, suggestions, icd_codes, documents CASCADE;
CREATE TABLE documents (
    document_id         SERIAL PRIMARY KEY,
    source_filename      VARCHAR(255),
    patient_ref          VARCHAR(100),        -- de-identified/internal reference, NOT real patient name
    raw_text              TEXT NOT NULL,        -- full discharge summary text
    upload_date           TIMESTAMP DEFAULT NOW(),
    status                 VARCHAR(20) DEFAULT 'pending'
                            CHECK (status IN ('pending','processing','reviewed','finalized')),
    notes                  TEXT                  -- free text for flags/ambiguity notes
);



CREATE TABLE icd_codes (
    icd_code              VARCHAR(10) PRIMARY KEY,   -- e.g. 'E11.9'
    description            TEXT NOT NULL,
    chapter                 VARCHAR(255),
    category                VARCHAR(255),
    is_billable             BOOLEAN DEFAULT TRUE
);


CREATE TABLE suggestions (
    suggestion_id          SERIAL PRIMARY KEY,
    document_id             INTEGER NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,

    suggestion_type         VARCHAR(30) NOT NULL
                             CHECK (suggestion_type IN (
                                 'diagnosis_principal',
                                 'diagnosis_associative',
                                 'procedure_principal',
                                 'procedure_associative',
                                 'medication'
                             )),

    extracted_text           TEXT NOT NULL,         -- the entity span as found in the note, e.g. "DM type 2"
    icd_code                  VARCHAR(10) REFERENCES icd_codes(icd_code),  -- NULL allowed for medications
                                                                            -- (meds may not need ICD mapping)
    confidence_score          NUMERIC(4,3) CHECK (confidence_score BETWEEN 0 AND 1),

    -- source anchoring (for "where did you find this?")
    source_char_start         INTEGER NOT NULL,
    source_char_end           INTEGER NOT NULL,
    source_snippet             TEXT,                -- cached surrounding text for quick display

    is_ambiguous               BOOLEAN DEFAULT FALSE, -- flagged instead of guessed
    ambiguity_reason            TEXT,

    coder_decision               VARCHAR(20) DEFAULT 'pending'
                                 CHECK (coder_decision IN ('pending','approved','rejected','edited')),
    created_at                    TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_suggestions_document ON suggestions(document_id);
CREATE INDEX idx_suggestions_type ON suggestions(suggestion_type);


CREATE TABLE corrections (
    correction_id            SERIAL PRIMARY KEY,
    suggestion_id              INTEGER NOT NULL REFERENCES suggestions(suggestion_id) ON DELETE CASCADE,

    original_icd_code            VARCHAR(10),
    corrected_icd_code            VARCHAR(10) REFERENCES icd_codes(icd_code),
    correction_type                 VARCHAR(20)
                                    CHECK (correction_type IN ('reclassified','rejected','added_missed','confirmed')),

    coder_name                       VARCHAR(100),     -- free text for now, single-user phase
    comment                            TEXT,
    corrected_at                       TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_corrections_suggestion ON corrections(suggestion_id);



CREATE TABLE chat_messages (
    message_id              SERIAL PRIMARY KEY,
    document_id               INTEGER NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    related_suggestion_id      INTEGER REFERENCES suggestions(suggestion_id),  -- NULL if general question

    sender                       VARCHAR(10) NOT NULL CHECK (sender IN ('coder','assistant')),
    message_text                  TEXT NOT NULL,
    created_at                     TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_chat_document ON chat_messages(document_id);


CREATE TABLE retraining_batches (
    batch_id                SERIAL PRIMARY KEY,
    started_at                 TIMESTAMP DEFAULT NOW(),
    completed_at                TIMESTAMP,
    num_corrections_used         INTEGER,
    status                        VARCHAR(20) DEFAULT 'running'
                                  CHECK (status IN ('running','completed','failed')),
    notes                          TEXT
);
