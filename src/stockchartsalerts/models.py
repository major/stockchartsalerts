from pydantic import BaseModel, ConfigDict, Field


class Alert(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    alert: str
    bearish: str = "no"
    lastfired: str
    symbol: str = Field(default="UNKNOWN")
