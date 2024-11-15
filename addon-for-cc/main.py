import asyncio
import json
import os
import aiohttp
from getmac import get_mac_address
from aiohttp import ClientSession
from loguru import logger

# Home Assistant 설정
HA_URL = "http://supervisor/core"
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
    HA_TOKEN = options.get("haas_token")
    raise ValueError("HA_TOKEN is not set in environment variables")

# 폴링 간격 (초)
POLLING_INTERVAL = options.get("polling_interval", 60)
# 타임아웃 설정 (초)
TIMEOUT = options.get("timeout", 30)


async def fetch_and_send_states(session, previous_states):
    try:
        current_states = await get_states(session)
        if not current_states:
            logger.warning("Failed to fetch states")
            return previous_states

        if not previous_states:
            await send_initial_states(session, current_states)
            return {state["entity_id"]: state for state in current_states}

        changed_states = get_changed_states(current_states, previous_states)
        if changed_states:
            await send_changed_states(session, changed_states)

        return update_previous_states(previous_states, current_states)

    except Exception as e:
        logger.exception(f"Error in fetch_and_send_states: {str(e)}")
        return previous_states


async def get_states(session):
    url = f"{HA_URL}/api/states"
    headers = {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}

    try:
        async with session.get(url, headers=headers, timeout=TIMEOUT) as response:
            if response.status == 200:
                states = await response.json()
                logger.info(f"Successfully fetched {len(states)} states")
                return states
            logger.error(f"Failed to get states. Status: {response.status}")
    except Exception as e:
        logger.exception(f"Error fetching states: {str(e)}")

    return None


async def get_services(session):
    url = f"{HA_URL}/api/services"
    headers = {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}

    try:
        async with session.get(url, headers=headers, timeout=TIMEOUT) as response:
            if response.status == 200:
                states = await response.json()
                logger.info(f"Successfully fetched {len(states)} states")
                return states
            logger.error(f"Failed to get states. Status: {response.status}")
    except Exception as e:
        logger.exception(f"Error fetching states: {str(e)}")

    return None


async def send_initial_states(session, states):
    logger.info("First run detected. Sending all states.")
    await send_states_to_external_server(session, states)


def get_changed_states(current_states, previous_states):
    return [
        state
        for state in current_states
        if state["entity_id"] not in previous_states or state != previous_states[state["entity_id"]]
    ]


async def send_changed_states(session, changed_states):
    logger.info(f"Sending {len(changed_states)} changed states")
    await send_states_to_external_server(session, changed_states)


def update_previous_states(previous_states, current_states):
    for state in current_states:
        previous_states[state["entity_id"]] = state
    return previous_states


async def send_states_to_external_server(session, data_list):
    headers = {"x-functions-key": ASSIST_TOKEN, "Content-Type": "application/json"}
    payload = {"macAddress": SYSTEM_MAC_ADDRESS, "states": data_list}
    url = f"{EXTERNAL_SERVER_URL}/api/v1/command-crawler"

    try:
        async with session.post(url, headers=headers, data=json.dumps(payload), timeout=TIMEOUT) as response:
            if response.status == 200:
                logger.info(f"Data sent successfully for {len(data_list)} entities")
            else:
                logger.error(f"Failed to send data. Status: {response.status}")
                response_text = await response.text()
                logger.error(f"Response: {response_text}")
    except asyncio.TimeoutError:
        logger.error("Timeout while sending data to external server")
    except Exception as e:
        logger.exception(f"Error sending data: {str(e)}")


async def send_services_to_external_server(session, data_list):
    headers = {"x-functions-key": ASSIST_TOKEN, "Content-Type": "application/json"}
    payload = {"macAddress": SYSTEM_MAC_ADDRESS, "services": data_list}
    url = f"{EXTERNAL_SERVER_URL}/api/v1/command-crawler"

    try:
        async with session.post(url, headers=headers, data=json.dumps(payload), timeout=TIMEOUT) as response:
            if response.status == 200:
                logger.info(f"Data sent successfully for {len(data_list)} entities")
            else:
                logger.error(f"Failed to send data. Status: {response.status}")
                response_text = await response.text()
                logger.error(f"Response: {response_text}")
    except asyncio.TimeoutError:
        logger.error("Timeout while sending data to external server")
    except Exception as e:
        logger.exception(f"Error sending data: {str(e)}")


async def main():
    previous_states = {}
    async with aiohttp.ClientSession() as session:
        logger.info("Starting main loop")
        await send_services_to_external_server(session, await get_services(session))
        while True:
            previous_states = await fetch_and_send_states(session, previous_states)
            logger.debug(f"Sleeping for {POLLING_INTERVAL} seconds")
            await asyncio.sleep(POLLING_INTERVAL)


if __name__ == "__main__":
    logger.info(f"System MAC Address: {SYSTEM_MAC_ADDRESS}")
    logger.info(f"Home Assistant API URL: {HA_URL}")
    logger.info(f"External Server URL: {EXTERNAL_SERVER_URL}")
    logger.info(f"Polling Interval: {POLLING_INTERVAL} seconds")
    asyncio.run(main())
