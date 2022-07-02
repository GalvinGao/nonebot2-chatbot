from pydantic import BaseSettings


class Config(BaseSettings):
    # Your Config Here

    pghook_destination_group_id: int = 0

    class Config:
        extra = "ignore"