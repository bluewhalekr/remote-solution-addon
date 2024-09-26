import asyncio
import json
import os
import aiohttp
from getmac import get_mac_address
from aiohttp import ClientSession
from loguru import logger

# Home Assistant 설정
HA_URL = os.environ.get("SUPERVISOR_URL", "http://supervisor/core")
HA_WS_URL = HA_URL.replace("http", "ws", 1) + "/api/websocket"
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
    HA_TOKEN = options.get("hass_token")
    if not HA_TOKEN:
        raise ValueError("HASS_TOKEN is not set in environment variables or options.json")

# 폴링 간격 (초)
POLLING_INTERVAL = options.get("polling_interval", 60)

# 타임아웃 설정 (초)
TIMEOUT = options.get("timeout", 30)


async def get_all_states(session):
    url = f"{HA_URL}/api/states"
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


async def listen_for_changes(session):
    async with session.ws_connect(HA_WS_URL) as ws:
        await ws.send_json({"type": "auth", "access_token": HA_TOKEN})
        auth_response = await ws.receive_json()
        if auth_response["type"] != "auth_ok":
            logger.error("Authentication failed")
            return

        # 처음 실행 시 모든 상태 전송
        all_states = await get_all_states(session)
        if all_states:
            await send_to_external_server(session, all_states)

        await ws.send_json({"id": 1, "type": "subscribe_events", "event_type": "state_changed"})
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                if data["type"] == "event" and data["event"]["event_type"] == "state_changed":
                    new_state = data["event"]["data"]["new_state"]
                    if new_state:
                        await send_to_external_server(session, [new_state])
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error(f"WebSocket connection closed with exception {ws.exception()}")
                break


async def main():
    while True:
        try:
            async with ClientSession() as session:
                await listen_for_changes(session)
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            logger.info("Reconnecting in 10 seconds...")
            await asyncio.sleep(10)


if __name__ == "__main__":
    logger.info(f"System MAC Address: {SYSTEM_MAC_ADDRESS}")
    asyncio.run(main())
