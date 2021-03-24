import aiohttp
import json
import asyncio


async def process_nums(nums):
	link = "https://wholesomelist.com/api/check?code=" + str(nums)
	async with aiohttp.ClientSession() as session:
		resp = await session.get(link)
		payload = json.loads(await resp.text())

		print(payload)

		if payload['result']:
			return True, payload['entry']
		else:
			return False, {}

# asyncio.run(process_nums(258133))
