import psycopg
from psycopg.rows import dict_row
from config import config

SCHEMA_SQL = """
-- 1. Clients Directory
CREATE TABLE IF NOT EXISTS clients (
    client_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Client Policies Registry
CREATE TABLE IF NOT EXISTS client_policies (
    policy_id VARCHAR(64) PRIMARY KEY,
    client_id VARCHAR(64) REFERENCES clients(client_id) ON DELETE CASCADE,
    policy_number VARCHAR(100) NOT NULL,
    category VARCHAR(100) DEFAULT 'General',
    coverage_limit NUMERIC(12, 2) DEFAULT 0.00,
    start_date DATE,
    end_date DATE,
    status VARCHAR(50) DEFAULT 'ACTIVE'
);

-- 3. Human-in-the-Loop Review Tasks
CREATE TABLE IF NOT EXISTS human_review_tasks (
    instance_id VARCHAR(128) PRIMARY KEY,
    client_id VARCHAR(64) REFERENCES clients(client_id) ON DELETE SET NULL,
    risk_score INT NOT NULL,
    status VARCHAR(50) DEFAULT 'PENDING_REVIEW', -- PENDING_REVIEW, APPROVED, REJECTED
    compliance_report TEXT,
    reviewer_comments TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP WITH TIME ZONE
);

-- 4. Operational Audit & Verdict Logs
CREATE TABLE IF NOT EXISTS evaluation_audit_log (
    log_id SERIAL PRIMARY KEY,
    instance_id VARCHAR(128) NOT NULL,
    client_id VARCHAR(64),
    risk_score INT,
    final_verdict TEXT,
    status VARCHAR(50) DEFAULT 'COMPLETED',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_tasks_status ON human_review_tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_client ON human_review_tasks(client_id);
CREATE INDEX IF NOT EXISTS idx_audit_instance ON evaluation_audit_log(instance_id);
"""

def migrate():
    print(f"Connecting to PostgreSQL: {config.POSTGRES_DB_URI}")
    with psycopg.connect(config.POSTGRES_DB_URI, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
            print("Successfully provisioned relational tables in PostgreSQL!")

if __name__ == "__main__":
    migrate()