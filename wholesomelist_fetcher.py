import aiohttp
import json
import asyncio


async def process_nums(nums):
	link = "https://wholesomelist.com/api/check?code=" + str(nums)
	async with aiohttp.ClientSession() as session:
		resp = await session.get(link)
		data = await resp.text()

		if not data:
			return False, {}

		payload = json.loads()

		print(payload)

		if payload['result']:
			return True, payload['entry']
		else:
			return False, {}

# print(asyncio.run(process_nums(287294)))
