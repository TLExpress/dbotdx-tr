import config
import time
import asyncio
import aiohttp
import logging
import random

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

token_expire_time = 3600 * 23  # 令牌有效时间

# 配置logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


async def basic_query(url, method="GET", data=None, headers=None):
    while True:
        async with aiohttp.ClientSession() as session:
            try:
                async with session.request(
                    method=method,
                    url=url,
                    data=data if method == "POST" else None,
                    headers=headers,
                ) as response:
                    # 處理成功的情況
                    if response.status == 200:
                        try:
                            # 嘗試將回應轉換為 JSON
                            return (response.status, await response.json())
                        except Exception as e:
                            logger.error(f"Failed to parse JSON response: {e}")
                            raise

                    # 處理 429 (Too Many Requests)
                    elif response.status == 429:
                        logger.warning("Too many requests, retrying in 5 seconds")
                        await asyncio.sleep(5)

                    # 處理其他非 200 狀態碼
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"Bad request, status={response.status}, response={error_text}"
                        )
                        return (response.status, error_text)
            except aiohttp.ClientError as e:
                logger.error(f"Client error: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                raise


async def tdx_fetch_token(api_id, api_secret, url):
    data = {
        "grant_type": "client_credentials",
        "client_id": api_id,
        "client_secret": api_secret,
    }
    try:
        response_status, response_data = await basic_query(
            url, method="POST", data=data
        )
        if response_status != 200:
            raise ValueError(
                f"{response_status}: Failed to fetch token: {response_data}"
            )
        access_token = response_data["access_token"]
        if access_token:
            return access_token
        else:
            raise ValueError("Access token not found in response.")
    except ValueError as ve:
        logger.error(f"ValueError fetching token: {ve}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching token: {e}")
        raise


class TDXTokenManager:
    def __init__(self, api_id, api_secret, auth_root):
        self.api_id = api_id
        self.api_secret = api_secret
        self.auth_root = auth_root
        self.token = None
        self.last_fetch_time = time.time() - token_expire_time
        self.lock = None

    async def get(self):
        if self.lock is None:
            self.lock = asyncio.Lock()
        now = time.time()
        async with self.lock:
            if now - self.last_fetch_time > token_expire_time or not self.token:
                logger.info("Fetching new token...")
                self.last_fetch_time = now
                self.token = await tdx_fetch_token(
                    self.api_id, self.api_secret, self.auth_root
                )
                logger.info("Token fetched successfully.")
            else:
                logger.info("Using cached token.")
        return self.token

    async def refresh(self):
        async with self.lock:
            logger.info("Refreshing token...")
            self.last_fetch_time = time.time() - token_expire_time
            await self.get()


class TDXRequester:
    def __init__(
        self,
        api_id=config.api_id,
        api_secret=config.api_secret,
        auth_root=config.tdx_auth_root,
        api_root=config.tdx_api_root,
        api_relay=(
            config.tdx_api_relay if hasattr(config, "tdx_api_relay") else None
        ),  # api_relay is an array, may contain multiple urls
    ):
        self.token_manager = TDXTokenManager(api_id, api_secret, auth_root)
        self.api_root = api_root
        self.api_relay = api_relay
        if self.api_relay is not None:
            logger.info(f"Using relay: {self.api_relay}")

    async def get(self, subpath, no_relay=False):
        headers = {"Authorization": f"Bearer {await self.token_manager.get()}"}
        # if api_relay is not None, try one of them ramdomly
        if self.api_relay is not None and not no_relay:
            api_root = self.api_relay[random.randint(0, len(self.api_relay) - 1)]
        else:
            api_root = self.api_root
        try:
            response_status, ret = await basic_query(
                api_root + subpath, headers=headers
            )
            if response_status == 200:
                return ret
            elif response_status == 401:
                logger.warning("Token expired, refreshing...")
                await self.token_manager.refresh()
                return await self.get(subpath)
            else:
                raise ValueError(f"Failed to fetch data: {response_status}, {ret}")
        # if failed to fetch data from api_relay, try to fetch data directly from api_root
        except aiohttp.ClientError as e:
            if self.api_relay is not None and not no_relay:
                logger.warning(
                    f"Failed to fetch data from relay, try to fetch data directly from api_root: {e}"
                )
                return await self.get(subpath, no_relay=True)
            else:
                raise
