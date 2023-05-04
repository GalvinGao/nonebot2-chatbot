from typing import Optional

from pydantic import BaseModel


class NotifyContextTheme(BaseModel):
    title: str
    color: str

class NotifyContext(BaseModel):
    theme: NotifyContextTheme
    title: str
    summary: str
    labels: dict[str, str]
    description: str
    fingerprint: str
    alertmanagerURL: str
    runbookURL: Optional[str]
    slim: bool = False
