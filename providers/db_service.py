import atexit
from typing import List, Dict, Any, Optional
from datetime import datetime
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
from config import config

# Central connection pool
pool = ConnectionPool(
    conninfo=config.POSTGRES_DB_URI,
    max_size=20,
    open=False, # Defers thread creation until explicitly opened or first acquired
    kwargs={"autocommit": True, "row_factory": dict_row}
)
pool.open()

# Cleanly close pool background threads if the process exits
atexit.register(pool.close)

class DatabaseService:
    @staticmethod
    def get_pending_reviews() -> List[Dict[str, Any]]:
        with pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT instance_id, client_id, risk_score, status, compliance_report, reviewer_comments, created_at
                    FROM human_review_tasks
                    WHERE status = 'PENDING_REVIEW'
                    ORDER BY created_at DESC;
                    """
                )
                return cur.fetchall()

    @staticmethod
    def create_review_task(instance_id: str, client_id: str, risk_score: int, compliance_report: str):
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO clients (client_id, name)
                    VALUES (%s, %s)
                    ON CONFLICT (client_id) DO NOTHING;
                    """,
                    (client_id, f"Client {client_id}")
                )
                cur.execute(
                    """
                    INSERT INTO human_review_tasks (instance_id, client_id, risk_score, compliance_report, status)
                    VALUES (%s, %s, %s, %s, 'PENDING_REVIEW')
                    ON CONFLICT (instance_id) DO UPDATE SET
                        risk_score = EXCLUDED.risk_score,
                        compliance_report = EXCLUDED.compliance_report;
                    """,
                    (instance_id, client_id, risk_score, compliance_report)
                )

    @staticmethod
    def resolve_review_task(instance_id: str, status: str, comments: str):
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE human_review_tasks
                    SET status = %s, reviewer_comments = %s, reviewed_at = %s
                    WHERE instance_id = %s;
                    """,
                    (status, comments, datetime.now(), instance_id)
                )

    @staticmethod
    def archive_evaluation(instance_id: str, client_id: str, risk_score: int, final_verdict: str):
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO evaluation_audit_log (instance_id, client_id, risk_score, final_verdict)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (instance_id) DO UPDATE SET
                        risk_score = EXCLUDED.risk_score,
                        final_verdict = EXCLUDED.final_verdict;
                    """,
                    (instance_id, client_id, risk_score, final_verdict)
                )

db_service = DatabaseService()