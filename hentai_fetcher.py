import json
import re
import traceback

import aiohttp
import asyncio
from bs4 import BeautifulSoup


LICENSED_MAGAZINES = {
	"always_licensed": [
		"happining",
		"aoha",
		"weekly kairakuten",
		"dascomi",
	],
	"partially_licensed": {
		"kairakuten": ["2015-06", "9999-99", None, None],
		"x-eros": [None, None, 30, -1],
		"shitsurakuten": ["2016-04", "9999-99", None, None],
		"kairakuten beast": ["2016-12", "9999-99", None, None],
		"bavel": ["2017-06", "9999-99", None, None],
		"europa": ["2017-04", "9999-99", 11, -1],
		"girls form": [None, None, 13, 16],
		"koh": ["2013-12", "2014-07", 1, 2]
	}
}

# nhentai regexes
NUMBERS_REGEX = re.compile(r"/g/(\d{1,6})/?")

# magazine date regexes
DATE_PATTERN = re.compile(r"(\d+)-(\d+)")
DATE_PATTERN_2 = re.compile(r"\D*(\d+)\D*")

# Generic regexes
TITLE_EXTRACTOR = re.compile(
	r"^(?:\s*(?:=.*?=|<.*?>|\[.*?]|\(.*?\)|{.*?})\s*)*(?:[^\[|\](){}<>=]*\s*\|\s*)?([^\[|\](){}<>=]*?)(?:\s*(?:=.*?=|<.*?>|\[.*?]|\(.*?\)|{.*?})\s*)*$")

# special magazine regexes
# See if this doujin has a magazine associated with it
MAGAZINE_REGEX = re.compile(r".*\(\s*comic\s*(.+?)\s*(?:vol\.)?\s*((\d|-|#|,|\s)*)\)")
# (girls forM is annoying because it doesn't have a COMIC, so I have to use another regex)
GIRLS_FORM_REGEX = re.compile(r".*\(\s*girls\s*form\s*(?:vol\.)?\s*(.+?)\)")
# (so is Weekly Kairakuten)
WEEKLY_MAG_REGEX = re.compile(r".*\(\s*weekly\s*kairakuten\s*(?:vol\.)?\s*(.+)\)")


def date_num_compare(magazine: str, issue: str) -> bool:
	if " " in issue:
		issues = issue.split(" ")

		try:
			ans = date_num_compare(magazine, issues[0])
			return ans
		except Exception:
			ans = date_num_compare(magazine, issues[1])
			return ans

	match = DATE_PATTERN.match(issue)
	match2 = DATE_PATTERN_2.match(issue)

	if match is not None:
		startdate = LICENSED_MAGAZINES["partially_licensed"][magazine][0]
		enddate = LICENSED_MAGAZINES["partially_licensed"][magazine][1]

		startmatch =  DATE_PATTERN.match(startdate)
		endmatch = DATE_PATTERN.match(enddate)

		issueyear = int(match.group(1))
		issuemonth = int(match.group(2))

		if startmatch and endmatch:
			startyear = int(startmatch.group(1))
			startmonth = int(startmatch.group(2))

			endyear = int(endmatch.group(1))
			endmonth = int(endmatch.group(2))
		else:
			raise AttributeError('Failed to find issue number!')

		if startyear > issueyear or issueyear > endyear:
			return False
		elif startyear == issueyear and startmonth > issuemonth:
			return False
		elif endyear == issueyear and endmonth < issuemonth:
			return False

		return True
	elif match2 is not None:
		startnum = LICENSED_MAGAZINES["partially_licensed"][magazine][2]
		endnum = LICENSED_MAGAZINES["partially_licensed"][magazine][3]

		if endnum == -1:
			endnum = 100000000

		issuenum = int(match2.group(1))

		return startnum <= issuenum <= endnum
	else:
		return False


# merge fetching everything lol
async def process_site(link: str) -> tuple[str, list[str] | None, str | None, list[str] | None, list[str] | None, int | None, list[str] | None]:
	async with aiohttp.ClientSession() as session:
		title = ""
		tags = list()
		artists = list()
		parodies = list()
		characters = list()
		pages: int
		language = list()

		if 'nhentai' in link:
			numbers_match = NUMBERS_REGEX.search(link)
			numbers = int(numbers_match.group(1))

			api_url = f"https://nhentai.net/api/gallery/{numbers}"

			response = await session.get(api_url)
			code = response.status

			if code == 403 or code == 503 or 'application/json' not in response.headers.get('Content-Type', ''):  # cloudflare IUAM
				return "Cloudflare IUAM", None, None, None, None, None, None

			data = await response.json()

			title = data["titles"]["english"] if data["titles"]["english"] else data["titles"]["pretty"] if data["titles"]["pretty"] else "None"

			for tag in data["tags"]:
				match tag["type"]:
					case 'language':
						if tag["name"] != 'translated' and tag["name"] != 'rewrite':
							language.append(tag["name"])
					case 'parody':
						if tag["name"] != 'original':
							parody_match = re.search(fr'(?i)({tag["name"]})', data["titles"]["english"])

							if parody_match:
								parodies.append(parody_match.group(1))
							else:
								parodies.append(tag["name"].title())
					case 'character':
						characters.append(tag["name"])
					case 'tag':
						tags.append(tag["name"])
					case 'artist':
						artist_match = re.search(fr'(?i)({tag["name"]})', data["titles"]["english"])

						if artist_match:
							artists.append(artist_match.group(1))
						else:
							artists.append(tag["name"].title())
					case _:
						continue

			pages = data["num_pages"]
		else:
			try:
				match = re.search(r'/g/(\d+?)/(.+?)/', link)

				if match is None:
					raise AttributeError('Failed to find gallery ID and token')

				gallery_id, gallery_token = match.group(1, 2)

				response = await session.post('https://api.e-hentai.org/api.php',
					json={
						"method": "gdata",
						"gidlist": [
							[int(gallery_id), gallery_token]
						],
						"namespace": 1
					})

				resp = await response.json(content_type='text/html')

				if 'error' in resp['gmetadata'][0]:
					raise RuntimeError(resp['error'])

				data = resp['gmetadata'][0]

				title = data['title'].strip()

				for tag in data['tags']:
					if ':' in tag:
						namespace, name = tag.split(':')

						match namespace:
							case 'artist':
								artist_match = re.search(fr'(?i)({name})', title)

								if artist_match:
									artists.append(artist_match.group(1))
								else:
									artists.append(name.title())
							case 'parody':
								if name != 'original':
									parody_match = re.search(fr'(?i)({name})', data["title"])

									if parody_match:
										parodies.append(parody_match.group(1))
									else:
										parodies.append(name.title())
							case "character":
								characters.append(name)
							case "language":
								if name not in ["translated", "rewrite"]:
									language.append(name)
							case 'female' | "male" | "mixed" | "other":
								tags.append(tag)
							case _:
								continue
				
				pages = int(data['filecount'])
			except (AttributeError, RuntimeError) as e:
				print(f'E-hentai error: {e}')
				return 'E-Hentai error', None, None, None, None, None, None

		print([title, tags, ', '.join(artists), parodies, characters, pages, language])
		return title, tags, ', '.join(artists), parodies, characters, pages, language


async def check_link(link: str) -> tuple[str | None, bool | None, str | list[list[str] | str | int | None]]:
	title, tags, artists, parodies, characters, pages, lang = await process_site(link)

	if title == "Cloudflare IUAM":
		return None, None, "Cloudflare IUAM"
	elif title == 'E-hentai error':
		return None, None, "E-hentai error"

	match = TITLE_EXTRACTOR.match(title)

	parsed_title = title

	if match:
		parsed_title = match.group(1)

	print([parsed_title, artists, tags, parodies, characters, pages, lang])

	# Make the title lowercase
	title = title.lower()

	magazine_name = None
	magazine_issue = None
	market = "2d-market.com" in title

	match1 = MAGAZINE_REGEX.match(title)
	match2 = GIRLS_FORM_REGEX.match(title)
	match3 = WEEKLY_MAG_REGEX.match(title)

	# Extract the magazine issue and name
	if match1 is not None:
		magazine_name = match1.group(1).lower()
		magazine_issue = match1.group(2)
	# again, girls forM special handling
	elif match2 is not None:
		magazine_name = "girls form"
		magazine_issue = match2.group(1).lower()
	# special handling for kairakuten weekly
	elif match3 is not None:
		magazine_name = "weekly kairakuten"
		magazine_issue = match3.group(1).lower()

	# handle any wacky
	if magazine_issue is not None and "," in magazine_issue:
		magazine_issue = magazine_issue.split(",")[0].strip()

	licensed = False

	# If this is in a licensed magazine, check if it's in a licensed issue
	if magazine_name and magazine_issue:
		if magazine_name in LICENSED_MAGAZINES["always_licensed"]:
			licensed = True
		elif magazine_name in LICENSED_MAGAZINES["partially_licensed"]:
			try:
				licensed = date_num_compare(magazine_name, magazine_issue)
			except Exception:
				# Something has gone very wrong with a regular expression while trying to fetch the issue.
				# In other words, the regular expression has failed. Ignore the post - the mods will remove it if it's
				# actually licensed.
				traceback.print_exc()
				print("Error while detecting magazine. Setting licensed to false and continuing.")

		if licensed:
			return magazine_name.upper() + " " + magazine_issue, market, [parsed_title, artists, tags, parodies, characters,
																		pages, lang]

	return None, market, [parsed_title, artists, tags, parodies, characters, pages, lang]


# a, b, data = asyncio.run(check_link('https://nhentai.net/g/374491/'))
# print(a, b, data)
