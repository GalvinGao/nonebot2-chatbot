from pydantic import BaseSettings


class Config(BaseSettings):
    # Your Config Here
    cf_access_client_id: str = "clientId"
    cf_access_client_secret: str = "secret"

    # report_stats_interval: by default it's 60 seconds
    report_stats_interval = 60

    class Config:
        extra = "ignore"
