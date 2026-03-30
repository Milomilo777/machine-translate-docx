CREATE TABLE IF NOT EXISTS documents (
    doc_id VARCHAR(36) PRIMARY KEY,
    filename VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS queries (
    id VARCHAR(36) PRIMARY KEY,
    doc_id VARCHAR(2048),
    model_name VARCHAR(50),
    prompt_json TEXT,
    response_json TEXT,
    execution_time_sec DOUBLE,
    input_tokens INT,
    output_tokens INT,
    total_tokens INT,
    cost_usd DOUBLE
);
