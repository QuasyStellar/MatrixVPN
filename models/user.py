from aredis_om import JsonModel, Field
import datetime as dt
from enum import Enum

class UserStatusType(Enum):
    pending = "pending"
    denied = "denied"
    accepted = "accepted"


class User(JsonModel):
    user_id: int = Field(primary_key=True)
    username: str = Field(index=True)
    status: UserStatusType = Field(default=UserStatusType.pending)
    access_granted_date: dt.datetime | None = None
    access_duration: int | None = None
    access_end_date: dt.datetime | None = None
    last_notification_id: int | None = None
    notifications_enabled: bool = True
