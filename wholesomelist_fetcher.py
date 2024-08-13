import aiohttp
import json
import asyncio


async def process_nums(nums: int|str) -> tuple[bool, dict]:
	link = "https://wholesomelist.com/api/check?code=" + str(nums)
	async with aiohttp.ClientSession() as session:
		resp = await session.get(link)
		data = await resp.text()

		if not data:
			return False, {}

		payload = json.loads(data)

		print(payload)

		if payload.get('result'):
			entry = payload['entry']

			for key, value in entry.items():
				if value == "None":
					entry[key] = None

			return True, entry
		else:
			return False, {}

# result, test = asyncio.run(process_nums(258133))
# print("tags" in test)
# print(get_god_list_str(test))
