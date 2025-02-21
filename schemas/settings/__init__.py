from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    REDIS_URL: str = Field(validation_alias="REDIS_URL")
    REDIS_PASSWORD: str = Field(validation_alias="REDIS_PASSWORD")

    BOT_TOKEN: str = Field(validation_alias="BOT_TOKEN")
    ADMIN_ID: int = Field(validation_alias="ADMIN_ID", default=0)