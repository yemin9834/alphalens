"""
Aurora Data API client for AlphaLens.
"""

import json
import logging
import os
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

try:
    from dotenv import load_dotenv

    load_dotenv(override=True)
    _env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
    if os.path.exists(_env_path):
        load_dotenv(_env_path, override=True)
except ImportError:
    pass

logger = logging.getLogger(__name__)

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)
_NON_UUID_ID_COLUMNS = frozenset({"clerk_user_id"})


def _default_database_name() -> str:
    return os.environ.get("DATABASE_NAME") or os.environ.get("AURORA_DATABASE", "alphalens")


class DataAPIClient:
    """Wrapper for AWS RDS Data API."""

    def __init__(
        self,
        cluster_arn: Optional[str] = None,
        secret_arn: Optional[str] = None,
        database: Optional[str] = None,
        region: Optional[str] = None,
    ):
        self.cluster_arn = cluster_arn or os.environ.get("AURORA_CLUSTER_ARN")
        self.secret_arn = secret_arn or os.environ.get("AURORA_SECRET_ARN")
        self.database = database or _default_database_name()
        self.region = region or os.environ.get("DEFAULT_AWS_REGION", "us-east-1")

        if not self.cluster_arn or not self.secret_arn:
            raise ValueError(
                "Missing Aurora configuration. Set AURORA_CLUSTER_ARN and AURORA_SECRET_ARN."
            )

        self.client = boto3.client("rds-data", region_name=self.region)

    @staticmethod
    def _placeholder(col: str, val: Any) -> str:
        """Build a typed SQL placeholder for RDS Data API parameters."""
        if isinstance(val, (dict, list)):
            return f":{col}::jsonb"
        if isinstance(val, Decimal):
            return f":{col}::numeric"
        if isinstance(val, date) and not isinstance(val, datetime):
            return f":{col}::date"
        if isinstance(val, datetime):
            return f":{col}::timestamp"
        if (
            col not in _NON_UUID_ID_COLUMNS
            and isinstance(val, str)
            and _UUID_RE.match(val)
            and (col == "id" or col.endswith("_id"))
        ):
            return f":{col}::uuid"
        return f":{col}"

    def execute(self, sql: str, parameters: Optional[List[Dict]] = None) -> Dict:
        kwargs = {
            "resourceArn": self.cluster_arn,
            "secretArn": self.secret_arn,
            "database": self.database,
            "sql": sql,
            "includeResultMetadata": True,
        }
        if parameters:
            kwargs["parameters"] = parameters
        try:
            return self.client.execute_statement(**kwargs)
        except ClientError as e:
            logger.error("Database error: %s", e)
            raise

    def query(self, sql: str, parameters: Optional[List[Dict]] = None) -> List[Dict]:
        response = self.execute(sql, parameters)
        if "records" not in response:
            return []

        columns = [col["name"] for col in response.get("columnMetadata", [])]
        results = []
        for record in response["records"]:
            row = {}
            for i, col in enumerate(columns):
                row[col] = self._extract_value(record[i])
            results.append(row)
        return results

    def query_one(self, sql: str, parameters: Optional[List[Dict]] = None) -> Optional[Dict]:
        rows = self.query(sql, parameters)
        return rows[0] if rows else None

    def insert(self, table: str, data: Dict, returning: Optional[str] = None) -> Optional[str]:
        columns = list(data.keys())
        placeholders = [self._placeholder(col, data[col]) for col in columns]

        sql = f'INSERT INTO {table} ({", ".join(columns)}) VALUES ({", ".join(placeholders)})'
        if returning:
            sql += f" RETURNING {returning}"

        response = self.execute(sql, self._build_parameters(data))
        if returning and response.get("records"):
            return self._extract_value(response["records"][0][0])
        return None

    def update(
        self, table: str, data: Dict, where: str, where_params: Optional[Dict] = None
    ) -> int:
        set_parts = [f"{col} = {self._placeholder(col, val)}" for col, val in data.items()]

        sql = f'UPDATE {table} SET {", ".join(set_parts)} WHERE {where}'
        all_params = {**data, **(where_params or {})}
        response = self.execute(sql, self._build_parameters(all_params))
        return response.get("numberOfRecordsUpdated", 0)

    def delete(self, table: str, where: str, where_params: Optional[Dict] = None) -> int:
        sql = f"DELETE FROM {table} WHERE {where}"
        response = self.execute(
            sql, self._build_parameters(where_params) if where_params else None
        )
        return response.get("numberOfRecordsUpdated", 0)

    def _build_parameters(self, data: Optional[Dict]) -> List[Dict]:
        if not data:
            return []

        parameters = []
        for key, value in data.items():
            param: Dict[str, Any] = {"name": key}
            if value is None:
                param["value"] = {"isNull": True}
            elif isinstance(value, bool):
                param["value"] = {"booleanValue": value}
            elif isinstance(value, int):
                param["value"] = {"longValue": value}
            elif isinstance(value, float):
                param["value"] = {"doubleValue": value}
            elif isinstance(value, Decimal):
                param["value"] = {"stringValue": str(value)}
            elif isinstance(value, (date, datetime)):
                param["value"] = {"stringValue": value.isoformat()}
            elif isinstance(value, (dict, list)):
                param["value"] = {"stringValue": json.dumps(value)}
            else:
                param["value"] = {"stringValue": str(value)}
            parameters.append(param)
        return parameters

    @staticmethod
    def _extract_value(field: Dict) -> Any:
        if field.get("isNull"):
            return None
        if "booleanValue" in field:
            return field["booleanValue"]
        if "longValue" in field:
            return field["longValue"]
        if "doubleValue" in field:
            return field["doubleValue"]
        if "stringValue" in field:
            value = field["stringValue"]
            if value and value[0] in ("{", "["):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    pass
            return value
        if "blobValue" in field:
            return field["blobValue"]
        return None
