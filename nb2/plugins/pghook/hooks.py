import string
from pydantic import BaseModel

class NotifyContextTheme(BaseModel):
    title: str
    color: str

class NotifyContext(BaseModel):
    theme: NotifyContextTheme
    title: str
    summary: str
    labels: str
    description: str
    fingerprint: str
    alertmanagerURL: str
    runbookURL: string
    slim: bool = False
