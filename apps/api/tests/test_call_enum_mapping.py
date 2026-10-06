from app.models.call import Call
from app.models.enums import CallOutcome
from sqlalchemy import Enum


def test_call_outcome_uses_string_enum_compatible_with_migration():
    outcome_type = Call.__table__.c.outcome.type

    assert isinstance(outcome_type, Enum)
    assert outcome_type.native_enum is False
    assert outcome_type.length == 24
    assert outcome_type.enums == [outcome.value for outcome in CallOutcome]
