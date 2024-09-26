import asyncio
import json
import os
import aiohttp
from getmac import get_mac_address
from aiohttp import ClientSession
from loguru import logger

# Home Assistant 설정
HA_URL = "http://supervisor/core/api"
HA_TOKEN = os.environ.get("SUPERVISOR_TOKEN")

# 외부 서버 URL
EXTERNAL_SERVER_URL = os.environ.get("EXTERNAL_SERVER_URL", "https://rs-command-crawler.azurewebsites.net")
SYSTEM_MAC_ADDRESS = get_mac_address()

# 설정 파일에서 옵션 로드
with open("/data/options.json", encoding="utf8") as f:
    options = json.load(f)

ASSIST_TOKEN = options.get("assist_token")
if not ASSIST_TOKEN:
    raise ValueError("ASSIST_TOKEN is not set in options.json, please set it")

if not HA_TOKEN:
    raise ValueError("SUPERVISOR_TOKEN is not set in environment variables")

# 폴링 간격 (초)
POLLING_INTERVAL = options.get("polling_interval", 60)
# 타임아웃 설정 (초)
TIMEOUT = options.get("timeout", 30)


async def get_states(session):
    url = f"{HA_URL}/states"
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json",
    }
    async with session.get(url, headers=headers, timeout=TIMEOUT) as response:
        if response.status == 200:
            return await response.json()
        else:
            logger.error(f"Failed to get states. Status: {response.status}")
            return None


async def send_to_external_server(session, data_list):
    try:
        headers = {"x-functions-key": ASSIST_TOKEN}
        payload = {"macAddress": SYSTEM_MAC_ADDRESS, "states": data_list}
        url = f"{EXTERNAL_SERVER_URL}/api/v1/command-crawler"
        async with session.post(url, headers=headers, json=payload, timeout=TIMEOUT) as response:
            if response.status == 200:
                logger.info(f"Data sent successfully for {len(data_list)} entities")
            else:
                logger.error(f"Failed to send data. Status: {response.status}")
    except asyncio.TimeoutError:
        logger.error("Timeout while sending data")
    except Exception as e:
        logger.error(f"Error sending data: {str(e)}")


async def main():
    previous_states = {}
    first_run = True

    async with ClientSession() as session:
        while True:
            try:
                current_states = await get_states(session)
                if current_states:
                    changed_states = []

                    for state in current_states:
                        entity_id = state["entity_id"]
                        if first_run or entity_id not in previous_states or state != previous_states[entity_id]:
                            changed_states.append(state)
                            previous_states[entity_id] = state

                    if changed_states:
                        await send_to_external_server(session, changed_states)

                    first_run = False

                await asyncio.sleep(POLLING_INTERVAL)
            except Exception as e:
                logger.error(f"Error occurred: {str(e)}")
                await asyncio.sleep(POLLING_INTERVAL)


if __name__ == "__main__":
    logger.info(f"System MAC Address: {SYSTEM_MAC_ADDRESS}")
    asyncio.run(main())
