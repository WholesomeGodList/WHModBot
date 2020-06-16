import re
import json
import sqlite3
import asyncio
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
	'urethra insertion'
]
underage_parodies = [
	'my hero academia',
	'love live',
	'toradora'
]


def create_connection(path):
	connection = None
	try:
		connection = sqlite3.connect(path)
		print("Connected to the posts database")
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

		# Validate the URL
		url_extractor = re.compile(r'(https?://(?:\w+:?\w*@)?(\S+)(:[0-9]+)?(/|/([\w#!:.?+=&%@!\-/]))?)')
		url_verify = url_extractor.search(body)

		nhentai_url_extractor = re.compile(r'(https?://nhentai.net/g/\d{1,6}/?)')
		nhentai_url = nhentai_url_extractor.search(body)

		if not url_verify:
			# no URL present, so we execute the british
			comment.reply("That doesn't seem to be a valid URL. Try again?"
			              f'\n\n{config["suffix"]}')
			return

		if nhentai_url:
			# it's an nhentai url, don't bother with other stuff
			url = nhentai_url.group(1).replace('http://', 'https://')

		else:
			# Handle any wacky Markdown, and enforce HTTPS
			url = url_verify.group(1).strip('(').strip(')').strip('[').strip(']').replace('http://', 'https://')

		if not url[-1] == "/":
			url = url + "/"

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
		c.execute('SELECT * FROM posts WHERE source=?', (url,))
		if c.fetchone():
			c.execute('DELETE FROM posts WHERE source=?', (url,))
		c.execute('INSERT INTO posts VALUES (?, ?, ?)',
		          (comment.submission.permalink, url, comment.submission.created_utc))
		c.execute('DELETE FROM pendingposts WHERE submission_id=?', (comment.submission.id,))
		conn.commit()
		
		# Reapprove the post
		comment.submission.mod.approve()

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

			# Validate the URL
			url_extractor = re.compile(r'(https?://(?:\w+:?\w*@)?(\S+)(:[0-9]+)?(/|/([\w#!:.?+=&%@!\-/]))?)')
			url_verify = url_extractor.search(comment.body)

			nhentai_url_extractor = re.compile(r'(https?://nhentai.net/g/\d{1,6}/?)')
			nhentai_url = nhentai_url_extractor.search(comment.body)

			if not url_verify:
				# no URL present, so we execute the british
				comment.reply("That doesn't seem to be a valid URL. Try again?"
				              f'\n\n{config["suffix"]}')
				return

			if nhentai_url:
				# it's an nhentai url, don't bother with other stuff
				url = nhentai_url.group(1).replace('http://', 'https://')

			else:
				# Handle any wacky Markdown, and enforce HTTPS
				url = url_verify.group(1).strip('(').strip(')').strip('[').strip(']').replace('http://', 'https://')

			if not url[-1] == "/":
				url = url + "/"

			# Check if the post is a repost or not
			c.execute('SELECT * FROM commonreposts WHERE source=?', (url,))
			is_common_repost = c.fetchone()
			if is_common_repost:  # if this tuple even exists, it's uh oh stinky
				# It's a really common repost. Kill it.
				comment.parent().edit(
					'The link you provided is a **very common repost** on this subreddit.\n\n'
					'Please read our [list of common reposts](https://www.reddit.com/r/wholesomehentai/comments/cjmiy4/list_of_common_reposts_and_common_licensed/), to avoid '
					'posting common reposts in the future.'
					f'\n\n{config["suffix"]}'
				)
				comment.submission.mod.remove(spam=False, mod_note='Really common repost.')
				c.execute('DELETE FROM pendingposts WHERE submission_id=?', (comment.submission.id,))
				conn.commit()
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
					if old_submission.author.name == author:
						# It's the same person. It's fine.
						print('OP is the same person. Ignoring...')
						c.execute('DELETE FROM posts WHERE source=?', (url,))
						conn.commit()
					else:
						# It's not been long enough since the last post. Link them to the last post and delete the entry.
						print('It\'s a recent repost. Removing...')
						comment.parent().edit(
							f'The link you provided has [already been posted](https://reddit.com{post[0]}) recently.\n\n'
							'Please search before posting to avoid posting reposts in the future.'
							f'\n\n{config["suffix"]}'
						)

						# Remove it and get rid of the post tracker
						comment.submission.mod.remove(spam=False, mod_note='Repost.')
						c.execute('DELETE FROM pendingposts WHERE submission_id=?', (comment.submission.id,))
						conn.commit()
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
					comment.parent().edit(
						f'The provided source is licensed! It appears in the licensed magazine issue `{magazine}`.\n\n'
						f'Please [contact the mods](https://www.reddit.com/message/compose?to=/r/{config["subreddit"]}) if you think this is a mistake. Otherwise, please read the '
						'[guide on how to spot licensed doujins.](https://www.reddit.com/r/wholesomehentai/comments/eq74k0/in_order_to_enforce_the_rules_a_bit_more_bans/fexum0v?utm_source=share&utm_medium=web2x)'
						''
						f'\n\n{config["suffix"]}'
					)

					# Remove it and get rid of the post tracker
					comment.submission.mod.remove(spam=False, mod_note=f'Licensed, appears in magazine {magazine}')
					c.execute('DELETE FROM pendingposts WHERE submission_id=?', (comment.submission.id,))
					conn.commit()
					return

				if market:
					# It literally has 2d-market.com in the title.
					print("2d-market in title.")
					comment.parent().edit(
						f'The provided source is licensed! It has `2d-market.com` in the title.\n\n'
						f'Please [contact the mods](https://www.reddit.com/message/compose?to=/r/{config["subreddit"]}) if you think this is a mistake. Otherwise, please read the '
						'[guide on how to spot licensed doujins.](https://www.reddit.com/r/wholesomehentai/comments/eq74k0/in_order_to_enforce_the_rules_a_bit_more_bans/fexum0v?utm_source=share&utm_medium=web2x)'
						''
						f'\n\n{config["suffix"]}'
					)

					# Remove it and get rid of the post tracker
					comment.submission.mod.remove(spam=False, mod_note=f'Licensed, appears in magazine {magazine}')
					c.execute('DELETE FROM pendingposts WHERE submission_id=?', (comment.submission.id,))
					conn.commit()
					return

				detected_tags = []
				for tag in data[2]:
					if tag in unwholesome_tags:
						detected_tags.append(tag)

				if len(detected_tags) != 0:
					# Oh no, there's an illegal tag!
					print("Illegal tags detected: " + ', '.join(detected_tags))
					comment.parent().edit(
						f'The provided source has the disallowed tags:\n```\n{", ".join(detected_tags)}\n```\n'
						'These tags are banned because they are almost never wholesome. '
						f'Please [contact the mods](https://www.reddit.com/message/compose?to=/r/{config["subreddit"]}) if you think this is either '
						'a mistagged doujin or a wholesome exception. '
						'Otherwise, make sure you understand Rules 1 and 5.'
						f'\n\n{config["suffix"]}'
					)

					# Remove it and get rid of the post tracker
					comment.submission.mod.remove(spam=False, mod_note=f'Has the illegal tag(s): {", ".join(detected_tags)}')
					c.execute('DELETE FROM pendingposts WHERE submission_id=?', (comment.submission.id,))
					conn.commit()
					return

				detected_parodies = []
				for parody in data[3]:
					if parody in underage_parodies:
						detected_parodies.append(parody)

				if len(detected_parodies) != 0:
					# Oh no, there's an illegal parody!
					print("Illegal tags detected: " + ', '.join(detected_tags))
					comment.parent().edit(
						f'The provided source has the disallowed parodies:\n```\n{", ".join(detected_parodies)}\n```\n'
						'These parodies are banned because they are almost always underage.'
						f'Please [contact the mods](https://www.reddit.com/message/compose?to=/r/{config["subreddit"]}) if you think this is an of-age exception. '
						'Otherwise, make sure you understand Rules 1 and 5.'
						f'\n\n{config["suffix"]}'
					)

					# Remove it and get rid of the post tracker
					comment.submission.mod.remove(spam=False, mod_note=f'Has the illegal tag(s): {", ".join(detected_tags)}')
					c.execute('DELETE FROM pendingposts WHERE submission_id=?', (comment.submission.id,))
					conn.commit()
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
			c.execute('INSERT INTO posts VALUES (?, ?, ?)',
			          (comment.submission.permalink, url, comment.submission.created_utc))
			c.execute('DELETE FROM pendingposts WHERE submission_id=?', (comment.submission.id,))
			conn.commit()
