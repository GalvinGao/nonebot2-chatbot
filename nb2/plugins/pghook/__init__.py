import time

import nonebot
from fastapi import FastAPI
from nonebot import get_driver
from nonebot.adapters.onebot.v11.event import Event, Sender
from nonebot.adapters.onebot.v11.message import Message, MessageSegment

from .config import Config

global_config = get_driver().config
config = Config.parse_obj(global_config)


app: FastAPI = nonebot.get_app()

@app.get("/hook")
async def hook():
    bot = nonebot.get_bot()
    m = Message([
        MessageSegment.text("Hello World"),
        MessageSegment.face(6),
    ])
    r = await bot.call_api("send_msg", message=m, user_id=config.pghook_destination_user_id)
    return {"message": r}
