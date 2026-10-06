from app.models.call import Call
from sqlalchemy import Float, cast, select
from sqlalchemy.dialects import postgresql


def test_latency_metric_query_uses_json_operator_supported_by_json_column():
    total_latency = Call.latency_ms["total"].as_string()
    statement = select(cast(total_latency, Float)).where(total_latency.is_not(None))
    sql = str(statement.compile(dialect=postgresql.dialect()))

    assert "latency_ms ->>" in sql
    assert "jsonb_extract_path_text" not in sql
