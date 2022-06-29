from pydantic import BaseSettings


class Config(BaseSettings):
    # Your Config Here

    pghook_destination_user_id: int = 0

    class Config:
        extra = "ignore"