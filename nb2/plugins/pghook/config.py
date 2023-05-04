from pydantic import BaseSettings

class UnreliableReportRateMention(BaseSettings):
    source_names: list[str] = []
    mention_ids: list[int] = []


class Config(BaseSettings):
    # Your Config Here

    pghook_destination_group_id: int = 0

    # BackendHighUnreliableReportRate
    pghook_unreliable_report_rate_mention_map: list[UnreliableReportRateMention] = []

    onebot_bot_self_id: str = ""

    class Config:
        extra = "ignore"