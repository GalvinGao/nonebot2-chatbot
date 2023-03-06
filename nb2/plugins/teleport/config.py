from pydantic import BaseSettings


class Config(BaseSettings):
    # Your Config Here

    tg_bot_token: str = ""
    tg_bot_self_id: str = ""
    tg_bot_dest_chat_id: int = 0
    onebot_bot_self_id: str = ""
    onebot_bot_dest_group_id: int = 0

    class Config:
        extra = "ignore"
