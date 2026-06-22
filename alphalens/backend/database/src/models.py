"""
Database models and query builders for AlphaLens.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from .client import DataAPIClient
from .schemas import (
    AnalysisJobCreate,
    CandidateCreate,
    DiscoveryRunCreate,
    HoldingCreate,
    PortfolioCreate,
    UserCreate,
)


class BaseModel:
    table_name: Optional[str] = None

    def __init__(self, db: DataAPIClient):
        self.db = db
        if not self.table_name:
            raise ValueError("table_name must be defined")

    def find_by_id(self, record_id: str) -> Optional[Dict]:
        sql = f"SELECT * FROM {self.table_name} WHERE id = :id::uuid"
        return self.db.query_one(sql, [{"name": "id", "value": {"stringValue": str(record_id)}}])

    def delete(self, record_id: str) -> int:
        return self.db.delete(self.table_name, "id = :id::uuid", {"id": str(record_id)})


class Users(BaseModel):
    table_name = "users"

    def find_by_clerk_id(self, clerk_user_id: str) -> Optional[Dict]:
        sql = f"SELECT * FROM {self.table_name} WHERE clerk_user_id = :clerk_id"
        return self.db.query_one(
            sql, [{"name": "clerk_id", "value": {"stringValue": clerk_user_id}}]
        )

    def create_user(self, user: UserCreate) -> str:
        data = user.model_dump(exclude_none=True)
        return self.db.insert(self.table_name, data, returning="clerk_user_id")

    def update_user(self, clerk_user_id: str, data: Dict) -> int:
        return self.db.update(
            self.table_name, data, "clerk_user_id = :clerk_id", {"clerk_id": clerk_user_id}
        )


class Portfolios(BaseModel):
    table_name = "portfolios"

    def find_by_user(self, clerk_user_id: str) -> List[Dict]:
        sql = f"""
            SELECT * FROM {self.table_name}
            WHERE clerk_user_id = :user_id
            ORDER BY is_default DESC, created_at DESC
        """
        return self.db.query(sql, [{"name": "user_id", "value": {"stringValue": clerk_user_id}}])

    def find_default(self, clerk_user_id: str) -> Optional[Dict]:
        sql = f"""
            SELECT * FROM {self.table_name}
            WHERE clerk_user_id = :user_id AND is_default = TRUE
            LIMIT 1
        """
        return self.db.query_one(
            sql, [{"name": "user_id", "value": {"stringValue": clerk_user_id}}]
        )

    def create_portfolio(self, clerk_user_id: str, portfolio: PortfolioCreate) -> str:
        data = {"clerk_user_id": clerk_user_id, **portfolio.model_dump()}
        return self.db.insert(self.table_name, data, returning="id")


class Holdings(BaseModel):
    table_name = "holdings"

    def find_by_portfolio(self, portfolio_id: str) -> List[Dict]:
        sql = f"""
            SELECT * FROM {self.table_name}
            WHERE portfolio_id = :portfolio_id::uuid
            ORDER BY weight DESC, ticker
        """
        return self.db.query(
            sql, [{"name": "portfolio_id", "value": {"stringValue": portfolio_id}}]
        )

    def upsert_holding(self, portfolio_id: str, holding: HoldingCreate) -> Optional[str]:
        sql = """
            INSERT INTO holdings (portfolio_id, ticker, weight, cost_basis)
            VALUES (:portfolio_id::uuid, :ticker, :weight::numeric, :cost_basis::numeric)
            ON CONFLICT (portfolio_id, ticker)
            DO UPDATE SET
                weight = EXCLUDED.weight,
                cost_basis = EXCLUDED.cost_basis,
                updated_at = NOW()
            RETURNING id
        """
        params = self.db._build_parameters(
            {
                "portfolio_id": portfolio_id,
                "ticker": holding.ticker,
                "weight": holding.weight,
                "cost_basis": holding.cost_basis,
            }
        )
        response = self.db.execute(sql, params)
        if response.get("records"):
            return self.db._extract_value(response["records"][0][0])
        return None

    def replace_all(self, portfolio_id: str, holdings: List[HoldingCreate]) -> None:
        self.db.delete(self.table_name, "portfolio_id = :portfolio_id::uuid", {"portfolio_id": portfolio_id})
        for holding in holdings:
            self.upsert_holding(portfolio_id, holding)


class DiscoveryRuns(BaseModel):
    table_name = "discovery_runs"

    def create_run(self, clerk_user_id: str, run: DiscoveryRunCreate) -> str:
        data = {"clerk_user_id": clerk_user_id, **run.model_dump(), "status": "pending"}
        return self.db.insert(self.table_name, data, returning="id")

    def update_status(
        self,
        run_id: str,
        status: str,
        result_payload: Optional[Dict] = None,
        warnings: Optional[List] = None,
        error_message: Optional[str] = None,
    ) -> int:
        data: Dict[str, Any] = {"status": status}
        if result_payload is not None:
            data["result_payload"] = result_payload
        if warnings is not None:
            data["warnings"] = warnings
        if status in ("completed", "failed"):
            data["completed_at"] = datetime.utcnow()
        return self.db.update(self.table_name, data, "id = :id::uuid", {"id": run_id})

    def find_by_id(self, run_id: str) -> Optional[Dict]:
        return super().find_by_id(run_id)

    def update_research_status(
        self,
        run_id: str,
        research_status: str,
        research_progress: Optional[Dict[str, Any]] = None,
    ) -> int:
        data: Dict[str, Any] = {"research_status": research_status}
        if research_progress is not None:
            data["research_progress"] = research_progress
        return self.db.update(self.table_name, data, "id = :id::uuid", {"id": run_id})

    def find_by_user(self, clerk_user_id: str, limit: int = 20) -> List[Dict]:
        sql = f"""
            SELECT * FROM {self.table_name}
            WHERE clerk_user_id = :user_id
            ORDER BY created_at DESC
            LIMIT :limit
        """
        return self.db.query(
            sql,
            [
                {"name": "user_id", "value": {"stringValue": clerk_user_id}},
                {"name": "limit", "value": {"longValue": limit}},
            ],
        )


class Candidates(BaseModel):
    table_name = "candidates"

    def find_by_run(self, discovery_run_id: str) -> List[Dict]:
        sql = f"""
            SELECT * FROM {self.table_name}
            WHERE discovery_run_id = :run_id::uuid
            ORDER BY company_name
        """
        return self.db.query(
            sql, [{"name": "run_id", "value": {"stringValue": discovery_run_id}}]
        )

    def create_candidate(self, discovery_run_id: str, candidate: CandidateCreate) -> str:
        data = {"discovery_run_id": discovery_run_id, **candidate.model_dump(exclude_none=True)}
        return self.db.insert(self.table_name, data, returning="id")

    def bulk_create(self, discovery_run_id: str, candidates: List[CandidateCreate]) -> List[str]:
        return [self.create_candidate(discovery_run_id, c) for c in candidates]

    def update_deep_research(
        self, discovery_run_id: str, ticker: str, deep_research: Dict[str, Any]
    ) -> int:
        import json

        sql = f"""
            UPDATE {self.table_name}
            SET deep_research = :deep_research::jsonb
            WHERE discovery_run_id = :run_id::uuid
              AND UPPER(ticker) = :ticker
        """
        params = self.db._build_parameters(
            {
                "run_id": discovery_run_id,
                "ticker": ticker.upper().strip(),
                "deep_research": json.dumps(deep_research),
            }
        )
        response = self.db.execute(sql, params)
        return response.get("numberOfRecordsUpdated", 0)


class AnalysisJobs(BaseModel):
    table_name = "analysis_jobs"

    def create_job(self, clerk_user_id: str, job: AnalysisJobCreate) -> str:
        data = {
            "clerk_user_id": clerk_user_id,
            "status": "pending",
            **job.model_dump(exclude_none=True),
        }
        return self.db.insert(self.table_name, data, returning="id")

    def update_status(self, job_id: str, status: str, error_message: Optional[str] = None) -> int:
        data: Dict[str, Any] = {"status": status}
        if status == "running":
            data["started_at"] = datetime.utcnow()
        elif status in ("completed", "failed"):
            data["completed_at"] = datetime.utcnow()
        if error_message:
            data["error_message"] = error_message
        return self.db.update(self.table_name, data, "id = :id::uuid", {"id": job_id})

    def update_ranked(self, job_id: str, ranked_payload: Dict) -> int:
        return self.db.update(
            self.table_name,
            {"ranked_payload": ranked_payload},
            "id = :id::uuid",
            {"id": job_id},
        )

    def update_recommendation(self, job_id: str, recommendation_payload: Dict) -> int:
        return self.db.update(
            self.table_name,
            {"recommendation_payload": recommendation_payload},
            "id = :id::uuid",
            {"id": job_id},
        )

    def update_discovery_run(self, job_id: str, discovery_run_id: str) -> int:
        return self.db.update(
            self.table_name,
            {"discovery_run_id": discovery_run_id},
            "id = :id::uuid",
            {"id": job_id},
        )

    def find_by_user(self, clerk_user_id: str, limit: int = 20) -> List[Dict]:
        sql = f"""
            SELECT * FROM {self.table_name}
            WHERE clerk_user_id = :user_id
            ORDER BY created_at DESC
            LIMIT :limit
        """
        return self.db.query(
            sql,
            [
                {"name": "user_id", "value": {"stringValue": clerk_user_id}},
                {"name": "limit", "value": {"longValue": limit}},
            ],
        )

    def find_by_id(self, job_id: str) -> Optional[Dict]:
        return super().find_by_id(job_id)


class Database:
    """Main database interface."""

    def __init__(
        self,
        cluster_arn: Optional[str] = None,
        secret_arn: Optional[str] = None,
        database: Optional[str] = None,
        region: Optional[str] = None,
    ):
        self.client = DataAPIClient(cluster_arn, secret_arn, database, region)
        self.users = Users(self.client)
        self.portfolios = Portfolios(self.client)
        self.holdings = Holdings(self.client)
        self.discovery_runs = DiscoveryRuns(self.client)
        self.candidates = Candidates(self.client)
        self.analysis_jobs = AnalysisJobs(self.client)

    def execute_raw(self, sql: str, parameters: Optional[List[Dict]] = None) -> Dict:
        return self.client.execute(sql, parameters)

    def query_raw(self, sql: str, parameters: Optional[List[Dict]] = None) -> List[Dict]:
        return self.client.query(sql, parameters)
