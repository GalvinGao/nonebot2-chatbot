import argparse
import asyncio
import datetime
import itertools
import os
from pprint import pprint
from time import time
from urllib.parse import urlparse

import aiohttp
from loguru import logger
from nonebot import get_driver, on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11.message import MessageSegment
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from playwright.async_api import async_playwright

from .config import Config

global_config = get_driver().config
config = Config.parse_obj(global_config)


SCREENSHOT_DEST = "tmp/screenshot.jpg"

PROMQL_SUM = "https://prometheus.exusiai.dev/api/v1/query?query=sum%20by%20(source_name)%20(increase(penguinbackend_report_reliability%7Bjob!~%22.*-preview%24%22%7D%5B24h%5D))"
PROMQL_VERIFY_HIST = "https://prometheus.exusiai.dev/api/v1/query?query=max_over_time(histogram_quantile(0.99%2C%20sum%20by(le%2C%20verifier)%20(rate(penguinbackend_report_verify_duration_seconds_bucket%7Bjob!~%22.*-preview%22%7D%5B5m%5D)))%5B1d%3A%5D)"
PROMSITE_SUM_URL = "https://prometheus.exusiai.dev/graph?g0.expr=sum%20by%20(source_name%2C%20reliability)%20(increase(penguinbackend_report_reliability%7Bjob!~%22.*-preview%24%22%7D%5B5m%5D))&g0.tab=0&g0.stacked=0&g0.show_exemplars=0&g0.range_input=2d&g0.step_input=300"
PENGUIN_BACKEND_USERS_URL = "https://penguin-stats.io/api/admin/analytics/report-unique-users/by-source?recent={recent}"


uploads = on_command('penguinuploads', aliases={'uploads'})
uploads_last_run = None


@uploads.handle()
async def uploads_handler(matcher: Matcher, args: Message = CommandArg()):
    global uploads_last_run
    if uploads_last_run is None:
        uploads_last_run = datetime.datetime.now()
    else:
        delta = datetime.datetime.now() - uploads_last_run
        if delta.seconds < config.report_stats_interval:
            return await uploads.finish(f'uploads: 调用过快。查询限频 {config.report_stats_interval} 秒')

    await uploads.send("uploads: 开始查询 Prometheus...")
    logger.debug("uploads: 开始查询 Prometheus...")
    try:
        [sum, hist, _] = await asyncio.gather(get_stats_sum(), get_stats_histogram(), screenshot_sum())
    except Exception as e:
        random_log_id = str(int(time()))
        logger.debug(f"uploads: 查询 Prometheus 失败 ({random_log_id}):", e)
        logger.exception(e)
        return await uploads.finish(f'uploads: 查询 Prometheus 失败 ({random_log_id})')
    logger.debug("uploads: Got responses from queries")

    msg = MessageSegment.text(f'uploads: 于 {datetime.datetime.now().isoformat()} 的查询结果如下\n\n{sum}\n\n') + \
        MessageSegment.image(await read_file(SCREENSHOT_DEST)) + \
        f'\n\n{hist}'

    await uploads.finish(msg)


async def read_file(path):
    with open(path, 'rb') as f:
        return f.read()


async def fetch(url, auth):
    async with aiohttp.ClientSession() as session:
        headers = {}
        if auth == 'cloudflare':
            headers = {
                'CF-Access-Client-Id': config.cf_access_client_id,
                'CF-Access-Client-Secret': config.cf_access_client_secret
            }
        elif auth == 'penguin':
            headers = {
                'Authorization': f"Bearer {config.penguin_admin_api_key}"
            }
        async with session.get(url, headers=headers) as response:
            return await response.json()


async def get_stats_histogram():
    print("get_stats_histogram: start")
    obj = await fetch(PROMQL_VERIFY_HIST, auth='cloudflare')
    print("get_stats_histogram: got response")
    parsed = parse_prom_resp(obj, 'verifier')
    list_str = '\n'.join(
        f"  - 检查 \"{k}\": {format_float_str(v*1000)}ms" for [k, v] in parsed)
    return f"# 最近 24hr 掉落汇报检查 P99 耗时\n{list_str}"


async def get_stats_sum():
    print("get_stats_sum: start")
    obj = await fetch(PROMQL_SUM, auth='cloudflare')
    print("get_stats_sum: got response")
    parsed = parse_prom_resp(obj, 'source_name')
    list_str = '\n'.join(
        f"  - 来源 \"{k}\": {int(v)}" for [k, v] in parsed if int(v) > 0)
    return f"# 最近 24hr Top 汇报来源\n{list_str}"


async def handle_route(route, request):
    # check if domain is 'prometheus.exusiai.dev'; request.url is a str
    # FIXME: use proper URL parsing instead of substring matching
    if 'prometheus.exusiai.dev' not in request.url:
        logger.debug(
            'playwright route: not prometheus.exusiai.dev: skipping request ({})', request.url)
        await route.continue_()
    else:
        logger.debug(
            'playwright route: IS prometheus.exusiai.dev: handling request ({})', request.url)
        logger.trace('playwright route: using cf_access_client_id: {}, cf_access_client_secret: {}',
                     config.cf_access_client_id, config.cf_access_client_secret)
        headers = route.request.headers
        headers['CF-Access-Client-Id'] = config.cf_access_client_id
        headers['CF-Access-Client-Secret'] = config.cf_access_client_secret
        await route.continue_(headers=headers)


async def screenshot_sum():
    # FIXME: parse path to screenshot based on proper variable instead of using
    # a hardcoded path
    os.makedirs('tmp', exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            locale='zh-CN',
            timezone_id='Asia/Shanghai',  # make screenshot show correct timezone
        )
        page = await context.new_page()
        # modify requests on-the-fly
        await page.route("**/*", handle_route)
        await page.goto(PROMSITE_SUM_URL)
        screenshot_el_sel = 'div.tab-pane.active div[class^=graph]'
        # await for element sel to be visible
        await page.wait_for_selector(screenshot_el_sel)
        # various adjustments via JS
        await page.evaluate(f'''
            // extra padding for vertical alignment
            document.querySelector('{screenshot_el_sel}').style.paddingTop = '24px';

            // hide navbar: navbar shows incorrectly in the screenshot
            document.querySelector('.navbar').style.display = 'none';

            // hide mouse hints under the legends area ("CMD+Click ...")
            document.querySelector('.graph-legend .pl-1.mt-1.text-muted').style.display = 'none';

            // check the use local time checkbox to produce time matching environment (defined in browser.new_context)
            document.querySelector('#use-local-time-checkbox').click();
        ''')
        # test checked state of #use-local-time-checkbox
        await page.wait_for_selector('#use-local-time-checkbox:checked')
        # take screenshot
        await page.pause()
        await page.locator(screenshot_el_sel).first.screenshot(path=SCREENSHOT_DEST)
        await browser.close()


def format_float_str(f):
    return f"{f:.2f}"


def parse_prom_resp(resp, groupkey):
    result = resp['data']['result']
    mapped = []
    for k, v in itertools.groupby(
            result, lambda x: x['metric'][groupkey]):
        mapped.append((k, sum(float(x['value'][1]) for x in v)))

    # mapped turns values
    return sorted(mapped, key=lambda x: x[1], reverse=True)


users = on_command('penguinusers', aliases={'users'})
users_last_run = None


@users.handle()
async def users_handler(args: Message = CommandArg()):
    global users_last_run
    if users_last_run is None:
        users_last_run = datetime.datetime.now()
    else:
        delta = datetime.datetime.now() - users_last_run
        if delta.seconds < config.report_stats_interval:
            return await users.finish(f'users: 调用过快。查询限频 {config.report_stats_interval} 秒')

    if len(args) >= 1:
        recent = str(args[0]).strip()
    else:
        recent = '24h'
    logger.info(f"users: recent: {recent}")

    url = PENGUIN_BACKEND_USERS_URL.format(recent=recent)
    logger.debug('users: url: {}', url)

    try:
        data = await fetch(url, auth='penguin')
        logger.debug('users: got response: {}', data)

        data = sorted(data.items(), key=lambda x: x[1], reverse=True)

        list_str = '\n'.join(
            f"  - {k}: {int(v)}" for [k, v] in data if int(v) > 0)

        msg = MessageSegment.text(f"users: 汇报掉落用户数\n{list_str}")
    except Exception as e:
        logger.exception(e)
        return await users.finish(MessageSegment.text(f"users: 获取汇报掉落用户数时出现错误"))

    await users.finish(msg)
