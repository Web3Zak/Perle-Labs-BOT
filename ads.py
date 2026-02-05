import aiohttp

ADS_API_BASE = "http://localhost:50325/api/v1"


# START PROFILE

async def start_profile(profile_id: str):
    """
    Запускает ADS профиль и возвращает данные для Playwright CDP
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{ADS_API_BASE}/browser/start",
            params={"user_id": profile_id},
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            data = await resp.json()

    if data.get("code") != 0:
        raise Exception(f"ADS start_profile failed: {data}")

    return data["data"]


# STOP PROFILE

async def stop_profile(profile_id: str):
    """
    Останавливает ADS профиль
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{ADS_API_BASE}/browser/stop",
            params={"user_id": profile_id},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            await resp.json()
