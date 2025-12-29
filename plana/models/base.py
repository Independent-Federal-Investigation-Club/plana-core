from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


def snowflake_validator(v):
    """Validator function for snowflake ID fields"""
    if isinstance(v, str) and v.isdigit():
        return int(v)
    return v


# Custom type for snowflake IDs with validator
SnowflakeId = Annotated[int, Field(), snowflake_validator]


class PlanaModel(BaseModel):
    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat() if v else None})
