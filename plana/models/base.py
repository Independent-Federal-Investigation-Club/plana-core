from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field


def snowflake_validator(v: Optional[str]) -> Optional[int]:
    """Validator function for snowflake ID fields"""
    if v is None:
        return None
    if isinstance(v, str) and v.isdigit():
        return int(v)
    return v


# Custom type for snowflake IDs with validator
SnowflakeId = Annotated[Optional[int], Field(), snowflake_validator]


class PlanaModel(BaseModel):
    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat() if v else None})
