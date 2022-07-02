import time

import nonebot
from fastapi import FastAPI
from nonebot import get_driver
from nonebot.adapters.onebot.v11.event import Event, Sender
from nonebot.adapters.onebot.v11.message import Message, MessageSegment

from .config import Config
from .fancyuni import apply_fancyuni
from .hooks import NotifyContext

global_config = get_driver().config
config = Config.parse_obj(global_config)

app: FastAPI = nonebot.get_app()

TEMPLATE: str = """
运维告警已触发

[{level}] {title}
{summary}

From: Prometheus (fingerprint: {fingerprint})"""


def format_stats(context: NotifyContext) -> str:
    return TEMPLATE.format(
        level=apply_fancyuni("bold", context.theme.title),
        title=context.title,
        summary=context.summary,
        fingerprint=context.fingerprint,
    )

@app.post("/api/v1/notify")
async def notify_hook(context: NotifyContext):
    bot = nonebot.get_bot()
    m = Message([
        MessageSegment.at(498704999),
        MessageSegment.at(2403901511),
        MessageSegment.text(format_stats(context)),
    ])
    r = await bot.call_api("send_msg", message=m, group_id=config.pghook_destination_group_id)
    return {"message": r}
