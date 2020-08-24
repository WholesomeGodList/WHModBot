import re
import json
import sqlite3
import asyncio
import time
import zlib
import base64
import datetime

from sqlite3 import Error
from praw.models import Comment
from praw import Reddit

import nhentai_fetcher

unwholesome_tags = [
	'shotacon',
	'lolicon',
	'cheating',
	'netorare',
	'rape',
	'guro',
	'scat',
	'mind break',
	'bestiality',
	'snuff',
	'abortion',
	'brain fuck',
	'eye penetration',
	'necrophilia',
	'vore',
	'blackmail',
	'torture',
	'infantilism',
	'corruption',
	'moral degeneration',
	'vomit',
	'cannibalism',
	'urethra insertion',
	'webtoon',
	'forbidden content'
]
underage_parodies = [
	'my hero academia',
	'love live',
	'toradora',
	'pokemon',
	'persona',
	'persona 2',
	'persona 3',
	'persona 4',
	'persona 5',
	'kono subarashii '
]
licensed_sites = [
	'hentai.cafe',
	'hc.fyi',
	'hentainexus'
]
warning_tags = {
	'sleeping': [
		''
	]
}


def create_connection(path):
	connection = None
	try:
		connection = sqlite3.connect(path)
		print("Connected to the posts database in process_comment")
	except Error as e:
		print(f"The error '{e}' occurred")

	return connection


conn = create_connection('posts.db')
c = conn.cursor()
config = json.load(open('config.json'))


async def process_comment(comment: Comment, reddit: Reddit):
	# Mod override - if the user is a moderator, has "override" in his comment, and
	if not comment.is_root and comment.author.name in comment.subreddit.moderator() and "override" in comment.body:
		print("Moderator override activated.")

		# get rid of any override leftovers
		body = comment.body.replace('override', '').strip()

		url = extract_url(body)

		if not url:
			# no URL present, so we execute the british
			comment.reply("That doesn't seem to be a valid URL. Try again?"
			              f'\n\n{config["suffix"]}')
			return

		if 'nhentai.net' in url:
			try:
				magazine, market, data = await nhentai_fetcher.check_link(url)
			except Exception:
				print("Invalid page.")
				comment.reply("That doesn't seem to be a valid nhentai page. Try again?"
				              f'\n\n{config["suffix"]}')
				return

			parodies = '' if len(data[3]) == 0 else f"**Parodies:**  \n{', '.join(data[3])}\n\n"
			characters = '' if len(data[4]) == 0 else f"**Characters:**  \n{', '.join(data[4])}\n\n"
			tags = 'Tags:  \nNone' if len(data[2]) == 0 else f"**Tags:**  \n{', '.join(data[2])}\n\n"

			comment.parent().edit(
				f"The source OP provided:  \n> <{url}>\n\n"
				f'**{data[0]}**  \nby {data[1]}\n\n{data[5]} pages\n\n{parodies}{characters}{tags}'
				f'{config["suffix"]}'
			)

		else:
			comment.parent().edit(
				f"The source OP provided:  \n> <{url}>\n\n"
				f'{config["suffix"]}'
			)

		# The post is good.
		print('Updating database and cleaning up...')
		c.execute('DELETE FROM posts WHERE source=?', (url,))
		approve_post(reddit, comment, url)

		# Reapprove the post if it was removed
		if comment.submission.removed:
			print("This post was removed. Reapproving...")
			comment.submission.mod.approve()
		else:
			print("This post was not removed. Ignoring...")

	# If this is the reply to a sauce request, handle it
	elif not comment.is_root and c.execute('SELECT * FROM pendingposts WHERE submission_id=?', (comment.submission.id,)).fetchone():
		c.execute('SELECT * FROM pendingposts WHERE submission_id=?', (comment.submission.id,))
		submission_id, author, comment_id = c.fetchone()

		# Normal handling
		if comment_id == comment.parent_id[3:] and author == comment.author.name:
			# It's a reply to a sauce request.
			print("Sauce reply found.")
			print(comment.body)

			# If there is no applicable source...
			if comment.body.lower() == 'none':
				comment.parent().edit(
					'OP has indicated that there is no applicable source.'
					f'\n\n{config["suffix"]}'
				)
				c.execute('DELETE FROM pendingposts WHERE submission_id=?', (comment.submission.id,))
				conn.commit()
				return

			url = extract_url(comment.body)

			if not url:
				# no URL present, so we execute the british
				comment.reply("That doesn't seem to be a valid URL. Try again?"
				              f'\n\n{config["suffix"]}')
				return

			# Handle any licensed sites here
			for site in licensed_sites:
				if site in url:
					print("It's a licensed site.")
					remove_post(reddit, comment,
					    'The link you provided links to a site that solely rips licensed content. As such, it breaks rule 4.\n\n'
					    'Please read our [guide on how to spot licensed doujins](https://www.reddit.com/r/wholesomehentai/wiki/licensedguide)'
					    ' to avoid making this mistake in the future.',
					    'Licensed link',
					    'Rule 4 - Linked to hentai.cafe/hentainexus',
					    True
					)

					return

			# Check if the post is a repost or not
			c.execute('SELECT * FROM commonreposts WHERE source=?', (url,))
			is_common_repost = c.fetchone()
			if is_common_repost:  # if this tuple even exists, it's uh oh stinky
				# It's a really common repost. Kill it.
				print('Common repost detected!')

				remove_post(reddit, comment,
					'The link you provided is a **very common repost** on this subreddit.\n\n'
					'Please read our [list of common reposts](https://www.reddit.com/r/wholesomehentai/wiki/posts), to avoid '
					'posting common reposts in the future.',
					'Really common repost.',
				    'Rule 10 - Common Repost',
					True
				)

				return

			# Check if the post is a repost that isn't that common
			c.execute('SELECT * FROM posts WHERE source=?', (url,))
			post = c.fetchone()
			if post:
				print('Post found in repost database.')
				# It's a repost.
				# Check how recently it was reposted (604800 seconds/week)
				if comment.submission.created_utc - post[2] > (8 * 604800):
					# It's already been enough since this was last posted.
					# Delete the entry, and we'll add it back later. (With the current timestamp)
					c.execute('DELETE FROM posts WHERE source=?', (url,))
					conn.commit()
					print('It\'s been long enough since this was last posted!')
				else:
					old_submission = reddit.submission(url=f'https://reddit.com{post[0]}')
					if (not old_submission.removed) and ((not (old_submission and old_submission.author)) or (old_submission.author.name == author)):
						# It's the same person. It's fine.
						print('OP is the same person. Ignoring...')
						c.execute('DELETE FROM posts WHERE source=?', (url,))
						conn.commit()
					else:
						if post[3] != 0:
							print('It\'s a recently removed repost. Removing...')

							remove_post(
								f'The link you provided has already been [posted and removed by the mods](https://reddit.com{post[0]}) recently.\n\n'
								'Please check why the previous post was removed by the moderators to understand what rule you broke, and '
								'make sure to [check the rules](https://reddit.com/r/wholesomehentai/wiki/rules) to avoid breaking the rules in the future.',
								'Removed repost.',
								'Reposting a removed post'
							)

						else:
							# It's not been long enough since the last post. Link them to the last post and delete the entry.
							print('It\'s a recent repost. Removing...')

							remove_post(reddit, comment,
								f'The link you provided has [already been posted](https://reddit.com{post[0]}) recently.\n\n'
								'Please [check here](https://reddit.com/r/wholesomehentai/wiki/posts) before posting to avoid posting reposts in the future.',
								'Repost.',
						        'Rule 10 - Repost',
								True
							)

						return

			if 'nhentai.net' in url:
				# hoo boy
				print('nhentai URL detected, parsing info / magazines')

				for attempt in range(3):
					try:
						magazine, market, data = await nhentai_fetcher.check_link(url)
						break
					except Exception:
						if attempt == 2:
							print("Invalid page.")
							print(url)
							comment.reply("Either that isn't a valid nhentai page, or my connection to nhentai has a problem currently. Try again?" f'\n\n{config["suffix"]}')
							return
						else:
							await asyncio.sleep(1)

				if magazine:
					# It's licensed!
					print("Licensed magazine detected.")

					remove_post(reddit, comment,
						f'The provided source is licensed! It appears in the licensed magazine issue `{magazine}`.\n\n'
						f'Please [contact the mods](https://www.reddit.com/message/compose?to=/r/{config["subreddit"]}) if you think this is a mistake. Otherwise, please read the '
						'[guide on how to spot licensed doujins.](https://www.reddit.com/r/wholesomehentai/wiki/licensedguide)',
						f'Licensed, appears in magazine {magazine}',
					    f'Rule 4 - Licensed (appears in {magazine})',
						True
					)

					return

				if market:
					# It literally has 2d-market.com in the title.
					print("2d-market in title.")

					remove_post(reddit, comment,
						f'The provided source is licensed! It has `2d-market.com` in the title.\n\n'
						f'Please [contact the mods](https://www.reddit.com/message/compose?to=/r/{config["subreddit"]}) if you think this is a mistake. Otherwise, please read the '
						'[guide on how to spot licensed doujins.](https://www.reddit.com/r/wholesomehentai/wiki/licensedguide)',
						f'Licensed, has 2d-market.com in title',
					    f'Rule 4 - Licensed (2d-market.com in title)',
						True
					)

					return

				if "english" not in data[6]:
					print("The language of this doujin does not seem to be English.")
					remove_post(reddit, comment,
					    'The provided source does not seem to be in English.\n\n'
					    'This subreddit only allows English submissions, as most people cannot understand other languages.\n\n'
					    f'If you believe this was a mistake, you can [contact the mods](https://www.reddit.com/message/compose?to=/r/{config["subreddit"]}).',
					    'Not English',
					    'Rule 2 - Non-English Source',
					    False
					)

					return

				detected_tags = []
				for tag in data[2]:
					if tag in unwholesome_tags:
						detected_tags.append(tag)

				if len(detected_tags) != 0:
					# Oh no, there's an illegal tag!
					print("Illegal tags detected: " + ', '.join(detected_tags))

					remove_post(reddit, comment,
						f'The provided source has the disallowed tags:\n```\n{", ".join(detected_tags)}\n```\n'
						'These tags are banned because they are either almost never wholesome or almost always licensed. '
						f'Please [contact the mods](https://www.reddit.com/message/compose?to=/r/{config["subreddit"]}) if you think this is either '
						'a mistagged doujin or a wholesome/unlicensed exception. '
						'Otherwise, make sure you understand Rules 1, 4, and 5.',
						f'Has the illegal tag(s): {", ".join(detected_tags)}',
					    f'Rule 1/4/5 - Has the tags {", ".join(detected_tags)}',
						True
					)

					return

				detected_parodies = []
				for parody in data[3]:
					if parody in underage_parodies:
						detected_parodies.append(parody)

				if len(detected_parodies) != 0:
					# Oh no, there's an illegal parody!
					print("Illegal tags detected: " + ', '.join(detected_parodies))

					remove_post(reddit, comment,
						f'The provided source has the disallowed parodies:\n```\n{", ".join(detected_parodies)}\n```\n'
						'These parodies are banned because they are almost always underage.'
						f'Please [contact the mods](https://www.reddit.com/message/compose?to=/r/{config["subreddit"]}) if you think this is an of-age exception. '
						'Otherwise, make sure you understand Rule 1.',
						f'Has the illegal tag(s): {", ".join(detected_parodies)}',
					    f'Rule 1 - Has the parodies {", ".join(detected_parodies)}',
						True
					)

					return

				parodies = '' if len(data[3]) == 0 else f"**Parodies:**  \n{', '.join(data[3])}\n\n"
				characters = '' if len(data[4]) == 0 else f"**Characters:**  \n{', '.join(data[4])}\n\n"
				tags = '**Tags:**  \nNone' if len(data[2]) == 0 else f"**Tags:**  \n{', '.join(data[2])}\n\n"

				comment.parent().edit(
					f"The source OP provided:  \n> <{url}>\n\n"
					f'**{data[0]}**  \nby {data[1]}\n\n{data[5]} pages\n\n{parodies}{characters}{tags}'
					f'{config["suffix"]}'
				)
			else:
				comment.parent().edit(
					f"The source OP provided:  \n> <{url}>\n\n"
					f'{config["suffix"]}'
				)

			# If we made it here, the post is good. Clean up any trackers and add a post entry to the database.
			print('Updating database and cleaning up...')
			approve_post(reddit, comment, url)


def remove_post(reddit: Reddit, comment: Comment, message: str, mod_note: str, note_message: str, strike: bool):
	comment.parent().edit(message + f'\n\n{config["suffix"]}')
	comment.submission.mod.remove(spam=False, mod_note=mod_note)
	c.execute('DELETE FROM pendingposts WHERE submission_id=?', (comment.submission.id,))
	conn.commit()

	# Time to update the usernotes...
	if strike:
		print("Updating usernotes...")
		usernotespage = reddit.subreddit(config['subreddit']).wiki["usernotes"]
		usernotescontent = json.loads(usernotespage.content_md)
		usernotes = decode_blob(usernotescontent['blob'])
		username = comment.submission.author.name

		if username in usernotes:
			usernotes[username]['ns'].append({
				'l': f'l,{comment.submission.id}',
				'm': 2,
				'n': note_message,
				't': int(time.time()),
				'w': 0
			})
		else:
			usernotes[username] = {
				'ns': [{
					'l': f'l,{comment.submission.id}',
					'm': 2,
					'n': note_message,
					't': int(time.time()),
					'w': 0
				}]
			}

		usernotescontent["blob"] = encode_blob(usernotes)
		usernotespage.edit(content=json.dumps(usernotescontent, separators=(',', ':')))
		print('User notes updated.')


def decode_blob(blob: str):
	return json.loads(zlib.decompress(base64.decodebytes(blob.encode())))


def encode_blob(json_blob: dict):
	compress = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, method=zlib.DEFLATED, wbits=15, memLevel=8, strategy=zlib.Z_DEFAULT_STRATEGY)
	compressed_data = compress.compress(json.dumps(json_blob, separators=(',', ':')).encode())
	compressed_data += compress.flush()
	return str(base64.b64encode(compressed_data), 'utf-8')


def approve_post(reddit: Reddit, comment: Comment, url: str):
	c.execute('INSERT INTO posts VALUES (?, ?, ?, ?)',
	          (comment.submission.permalink, url, comment.submission.created_utc, 0))
	c.execute('DELETE FROM pendingposts WHERE submission_id=?', (comment.submission.id,))

	# Prune old posts
	c.execute('DELETE FROM posts WHERE timeposted<?', (int(time.time()) - (8 * 604800),))
	conn.commit()

	# Now to rebuild the wiki page...
	update_wiki(reddit)


def update_wiki(reddit: Reddit):
	print("Generating wiki page...")
	c.execute('SELECT * FROM posts WHERE removed=0 ORDER BY timeposted DESC')
	all_posts = c.fetchall()
	subreddit_wiki = reddit.subreddit(config['subreddit']).wiki

	wiki_text = (
		'# **Posts and Common Reposts**\n\n'
		+ subreddit_wiki['commonreposts'].content_md +
		'\n\n## **Recent Posts**'
		'\n\n*This list is auto-generated by the bot, and includes all posts from the last 8 weeks.  \nMake sure that your post is not'
		' already in this list before you post, or it will be removed upon posting.*\n\n'
		'*All timestamps are in UTC.*\n\n'
		'| Source Given | Time Posted | Post Link |\n'
		'|-|-|-|\n'
	)
	id_extractor = re.compile(r'/comments/([^/]*)/')
	for post in all_posts:
		wiki_text += f'| {post[1] if len(post[1]) < 30 else ("[" + post[1][:30] + "...](" + post[1] + ")")} | {datetime.datetime.utcfromtimestamp(post[2]).strftime("%b %d, %Y %I:%M %p")} | https://redd.it/{id_extractor.search(post[0]).group(1)} |\n'

	repostspage = subreddit_wiki['posts']
	repostspage.edit(content=wiki_text)

	print('Wiki page generated.')


def extract_url(body: str):
	# Validate the URL
	url_extractor = re.compile(r'(https?://(?:\w+:?\w*@)?(\S+)(:[0-9]+)?(/|/([\w#!:.?+=&%@!\-/]))?)')
	url_verify = url_extractor.search(body)

	if not url_verify:
		return None

	nhentai_url_extractor = re.compile(r'(https?://nhentai\.net/g/\d{1,6}/?)')
	nhentai_url = nhentai_url_extractor.search(body)

	markdown_extractor = re.compile(r'\[.*\]\((.*)\)')
	markdown_url = markdown_extractor.search(body)

	if nhentai_url:
		# it's an nhentai url, don't bother with other stuff
		url = nhentai_url.group(1).replace('http://', 'https://')

	elif markdown_url:
		# it's a markdown URL, don't bother with other stuff
		url = markdown_url.group(1).replace('http://', 'https://')

	else:
		# Find the first URL, and enforce HTTPS
		url = url_verify.group(1).replace('http://', 'https://')

	if not url[-1] == "/":
		url = url + "/"

	return url
