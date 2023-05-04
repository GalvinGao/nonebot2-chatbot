import time
from typing import Iterable

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

BASE_TEMPLATE: str = """{banner}

[{level}] {title}
{summary}

From: Prometheus (fingerprint: {fingerprint})"""


def format_base_template_message(context: NotifyContext) -> str:
    return BASE_TEMPLATE.format(
        banner="Prometheus Alert",
        level=apply_fancyuni("bold", context.theme.title),
        title=context.title,
        summary=context.summary,
        fingerprint=context.fingerprint,
    )


UNRELIABLE_REPORT_TEMPLATE: str = """{banner}

[{level}] {title}
{summary}

From: Prometheus (fingerprint: {fingerprint})

"""


def format_unreliable_report_template_message(context: NotifyContext) -> str:
    return BASE_TEMPLATE.format(
        banner="汇报数据源告警",
        level=apply_fancyuni("bold", context.theme.title),
        title=context.title,
        summary=context.summary,
        fingerprint=context.fingerprint,
    )


@app.post("/api/v1/notify")
async def notify_hook(context: NotifyContext):
    if context.theme.title == "Resolved" or context.slim:
        return
    if context.title == "BackendHighUnreliableReportRate":
        source_name = context.labels.get("source_name")
        if source_name is not None:
            mentions: list[int] = []
            for mention_map in config.pghook_unreliable_report_rate_mention_map:
                if source_name in mention_map.source_names:
                    mentions.extend(mention_map.mention_ids)

            segments: Iterable[MessageSegment] = [
                MessageSegment.text(format_unreliable_report_template_message(context))
            ]
            segments.extend([MessageSegment.at(mention) for mention in mentions])
            m = Message(segments)
            bot = nonebot.get_bot(config.onebot_bot_self_id)
            r = await bot.call_api("send_msg", message=m, group_id=config.pghook_unreliable_report_group_id)
            return {"message": r}
    bot = nonebot.get_bot()
    m = Message([
        # MessageSegment.at(498704999),
        # MessageSegment.at(2403901511),
        MessageSegment.text(format_base_template_message(context)),
    ])
    r = await bot.call_api("send_msg", message=m, group_id=config.pghook_destination_group_id)
    return {"message": r}
