from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, BeforeValidator, ConfigDict


def snowflake_validator(v: Optional[str]) -> Optional[int]:
    """Validator function for snowflake ID fields"""
    if v is None:
        return None
    if isinstance(v, str) and v.isdigit():
        return int(v)
    if isinstance(v, int):
        return v
    return v


# Use BeforeValidator to actually apply the validator
SnowflakeId = Annotated[Optional[int], BeforeValidator(snowflake_validator)]


class PlanaModel(BaseModel):
    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat() if v else None})
