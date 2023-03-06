from nonebot import on_message, get_bot, get_driver
from nonebot.adapters.telegram import Bot as TelegramBot
from nonebot.adapters.telegram.event import GroupMessageEvent as TelegramGroupMessageEvent
from nonebot.adapters.telegram.model import InputMediaPhoto

from nonebot.adapters.onebot.v11 import GroupMessageEvent as OneBotGroupMessageEvent
from nonebot.adapters.onebot.v11 import MessageSegment
import asyncio
import httpx
import tempfile
from .config import Config

global_config = get_driver().config
config = Config.parse_obj(global_config)

tempdir = tempfile.TemporaryDirectory()


def format_prefix(event: OneBotGroupMessageEvent):
    name = event.sender.card or event.sender.nickname
    group_id = event.group_id
    if name:
        return name + " (" + str(group_id) + ")\n"
    return ""


any_onebot = on_message()


@any_onebot.handle()
async def onebot_handler(event: OneBotGroupMessageEvent):
    print("received new message from OneBot:", event)

    text = event.message.extract_plain_text()
    any_image = [seg for seg in event.message if seg.type == "image"]
    prefix = format_prefix(event)

    print("extracted text:", text)
    print("extracted images:", any_image)
    print("extracted prefix:", prefix)

    sending_text = prefix + text

    tg_bot = get_bot(config.tg_bot_self_id)

    if len(sending_text) > 0 and len(any_image) == 0:
        await tg_bot.call_api("send_message", chat_id=config.tg_bot_dest_chat_id, text=sending_text)
        print("sent text message to Telegram")
    elif len(any_image) > 0:
        image_paths = []
        async with httpx.AsyncClient() as client:
            # parallel download images
            async def download_image(image):
                resp = await client.get(image.data["url"])
                # save the image to a file
                path = tempdir.name + "/teleportimg." + image.data["file"]
                if resp.content[0:4] == b"GIF8":
                    path += ".gif"
                with open(path, "wb") as f:
                    f.write(resp.content)
                image_paths.append(path)

            await asyncio.gather(*[download_image(image) for image in any_image])

        if len(image_paths) == 1:
            # determine if the image is a GIF by checking the magic number
            image_path = image_paths[0]
            with open(image_path, "rb") as f:
                magic_number = f.read(4)
            if magic_number == b"GIF8":
                await tg_bot.call_api("send_animation", chat_id=config.tg_bot_dest_chat_id,
                                      animation=image_path, caption=sending_text, width=100)
            else:
                await tg_bot.call_api("send_photo", chat_id=config.tg_bot_dest_chat_id,
                                      photo=image_path, caption=sending_text)
        else:
            await tg_bot.call_api("send_media_group", chat_id=config.tg_bot_dest_chat_id,
                                  media=[InputMediaPhoto(media=path) for path in image_paths], caption=sending_text)
    else:
        print("nothing to send, or unsupported message type:", event.message)
        await tg_bot.call_api("send_message", chat_id=config.tg_bot_dest_chat_id, text=prefix + "(Sent an unsupported message type)\nmessageId=" + str(event.message_id))

any_telegram = on_message()


@any_telegram.handle()
async def telegram_handler(bot: TelegramBot, event: TelegramGroupMessageEvent):
    if event.get_user_id() == config.tg_bot_self_id:
        return
    print("received new message from Telegram:", event)

    prefix = "tg::" + (event.from_.first_name or "") + " " + \
        (event.from_.last_name or "") + "\n"

    text = event.message.extract_plain_text()

    messages = MessageSegment.text(prefix)

    if text:
        messages += MessageSegment.text(text)
    
    photo_segs = [seg for seg in event.message if seg.type == "photo" or seg.type == "animation"]
    if photo_segs:
        file_ = await bot.call_api("get_file", file_id=photo_segs[0].data["file"])
        url = "https://api.telegram.org/file/bot{token}/{path}".format(
            token=config.tg_bot_token, path=file_.file_path)
        messages += MessageSegment.image(url)
    
    onebot = get_bot(config.onebot_bot_self_id)
    await onebot.call_api(
        "send_msg", group_id=config.onebot_bot_dest_group_id, message=messages)
