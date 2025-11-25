
CREATE TABLE IF NOT EXISTS document (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    filename VARCHAR(255),
    file_path TEXT,
    description TEXT,
    mime_type VARCHAR(100),
    uploaded_by_id BIGINT, /* reference to app_user.id if you want */
    extracted_text TEXT,
    uploaded_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now()
);

-- optional: if you want chat message history table
CREATE TABLE IF NOT EXISTS chat_message (
    id BIGSERIAL PRIMARY KEY,
    role VARCHAR(16), /* 'user' or 'bot' */
    content TEXT,
    meta JSONB,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now()
);
