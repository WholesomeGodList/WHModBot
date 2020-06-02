import re
import asyncio
import json
import sqlite3
from sqlite3 import Error

from praw.models import Comment

import nhentai_fetcher

pending_sauces = {}
unwholesome_tags = [
	'shotacon',
	'lolicon',
	'cheating',
	'netorare',
	'rape',
	'guro',
	'scat',
	'mind break',
	'bestiality'
]
underage_parodies = [
	'my hero academia'
]


def create_connection(path):
	connection = None
	try:
		connection = sqlite3.connect(path)
		print("Connected to SQLite posts database")
	except Error as e:
		print(f"The error '{e}' occurred")

	return connection


conn = create_connection('posts.db')
c = conn.cursor()
config = json.load(open('config.json'))


def process_comment(comment: Comment):
	global pending_sauces

	# Mod override
	if not comment.is_root and comment.distinguished and comment.parent().name == config['username']:
		print("Moderator override activated.")
		# Validate the URL
		url_extractor = re.compile(r'(https?://(?:\w+:?\w*@)?(\S+)(:[0-9]+)?(/|/([\w#!:.?+=&%@!\-/]))?)')
		url_verify = url_extractor.search(comment.body)

		if not url_verify:
			# no URL present, so we execute the british
			comment.reply("That doesn't seem to be a valid URL. Try again?"
			              '\n\n*I am not a bot. I am being forced to mod this sub. Please send food and water*')
			return

		# Handle any wacky Markdown, and enforce HTTPS
		url = url_verify.group(1).strip(')').replace('http://', 'https://')

		if 'nhentai.net' in url:
			try:
				magazine, market, data = asyncio.run(nhentai_fetcher.check_link(comment.body))
			except Exception:
				comment.reply("That doesn't seem to be a valid nhentai page. Try again?"
				              '\n\n*I am not a bot. I am being forced to mod this sub. Please send food and water*')
				return

			parodies = '' if len(data[3]) == 0 else f"**Parodies:**  \n{', '.join(data[3])}\n\n"
			characters = '' if len(data[4]) == 0 else f"**Characters:**  \n{', '.join(data[4])}\n\n"
			tags = 'Tags:  \nNone' if len(data[2]) == 0 else f"**Tags:**  \n{', '.join(data[2])}\n\n"

			comment.parent().edit(
				f"The source OP provided:  \n> <{url}>\n\n"
				f'**{data[0]}** by {data[1]}  \n^{data[5]} pages\n\n{parodies}{characters}{tags}'
				'*I am not a bot. I am being forced to mod this sub. Please send food and water*'
			)

		else:
			comment.parent().edit(
				f"The source OP provided:  \n> <{url}>\n\n"
				'*I am not a bot. I am being forced to mod this sub. Please send food and water*'
			)

		# The post is good.
		c.execute('INSERT INTO posts VALUES (?, ?, ?)',
		          (comment.submission.permalink, url, comment.submission.created_utc))
		conn.commit()
		del pending_sauces[comment.submission.id]

	# If this is the reply to a sauce request, handle it
	elif not comment.is_root and comment.submission.id in pending_sauces:
		temp = pending_sauces[comment.submission.id]

		# Normal handling
		if temp['comment_id'] == comment.parent_id[3:] and temp['author'] == comment.author.name:
			# It's a reply to a sauce request.
			print("Sauce reply found.")
			print(comment.body)

			# If there is no applicable source...
			if comment.body.lower() == 'none':
				comment.parent().edit(
					'OP has indicated that there is no applicable source.'
					'\n\n*I am not a bot. I am being forced to mod this sub. Please send food and water*'
				)
				del pending_sauces[comment.submission.id]
				return

			# Validate the URL
			url_extractor = re.compile(r'(https?://(?:\w+:?\w*@)?(\S+)(:[0-9]+)?(/|/([\w#!:.?+=&%@!\-/]))?)')
			url_verify = url_extractor.search(comment.body)

			if not url_verify:
				# no URL present, so we execute the british
				comment.reply("That doesn't seem to be a valid URL. Try again?"
				              '\n\n*I am not a bot. I am being forced to mod this sub. Please send food and water*')
				return

			# Handle any wacky Markdown, and enforce HTTPS
			url = url_verify.group(1).strip(')').replace('http://', 'https://')

			# Check if the post is a repost or not
			c.execute('SELECT * FROM commonreposts WHERE source=?', (url,))
			is_common_repost = c.fetchone()
			if is_common_repost:  # if this tuple even exists, it's uh oh stinky
				# It's a really common repost. Kill it.
				comment.parent().edit(
					'The link you provided is a **very common repost** on this subreddit.  \n'
					'Please read our list of common reposts [here](https://www.reddit.com/r/wholesomehentai/comments/cjmiy4/list_of_common_reposts_and_common_licensed/), to avoid'
					'posting common reposts in the future.'
					'\n\n*I am not a bot. I am being forced to mod this sub. Please send food and water*'
				)
				comment.submission.mod.remove(spam=False, mod_note='Really common repost.')
				del pending_sauces[comment.submission.id]
				return

			# Check if the post is a repost that isn't that common
			c.execute('SELECT * FROM posts WHERE source=?', (url,))
			post = c.fetchone()
			if post:
				print('Post found in repost database.')
				# It's a repost.
				# Check how recently it was reposted (604800 seconds/week)
				if comment.submission.created_utc - post[2] > (5 * 604800):
					# It's already been enough since this was last posted.
					# Delete the entry, and we'll add it back later. (With the current timestamp)
					c.execute('DELETE FROM posts WHERE source=?', (url,))
					conn.commit()
					print('It\'s been long enough since this was last posted!')
				else:
					# It's not been long enough since the last post. Link them to the last post and delete the entry.
					print('It\'s a recent repost. Removing...')
					comment.parent().edit(
						f'The link you provided has [already been posted]({post[0]}) recently.  \n'
						'Please search before posting to avoid posting reposts in the future.'
						'\n\n*I am not a bot. I am being forced to mod this sub. Please send food and water*'
					)

					# Remove it and get rid of the post tracker
					comment.submission.mod.remove(spam=False, mod_note='Repost.')
					del pending_sauces[comment.submission.id]
					return

			if 'nhentai.net' in url:
				# hoo boy
				print('nhentai URL detected, parsing info / magazines')
				try:
					magazine, market, data = asyncio.run(nhentai_fetcher.check_link(comment.body))
				except Exception:
					print("Invalid page.")
					comment.reply("That doesn't seem to be a valid nhentai page. Try again?"
					              '\n\n*I am not a bot. I am being forced to mod this sub. Please send food and water*')
					return

				if magazine:
					# It's licensed!
					print("Licensed magazine detected.")
					comment.parent().edit(
						f'The provided source is licensed! It appears in the licensed magazine issue `{magazine}`.  \n'
						f'Please [contact the mods](https://www.reddit.com/message/compose?to=/r/{config["subreddit"]}) if you think this is a mistake. Otherwise, please read the '
						'[guide on how to spot licensed doujins.](https://www.reddit.com/r/wholesomehentai/comments/eq74k0/in_order_to_enforce_the_rules_a_bit_more_bans/fexum0v?utm_source=share&utm_medium=web2x)'
						''
						'\n\n*I am not a bot. I am being forced to mod this sub. Please send food and water*'
					)

					# Remove it and get rid of the post tracker
					comment.submission.mod.remove(spam=False, mod_note=f'Licensed, appears in magazine {magazine}')
					del pending_sauces[comment.submission.id]
					return

				if market:
					# It literally has 2d-market.com in the title.
					print("2d-market in title.")
					comment.parent().edit(
						f'The provided source is licensed! It has `2d-market.com` in the title.  \n'
						f'Please [contact the mods](https://www.reddit.com/message/compose?to=/r/{config["subreddit"]}) if you think this is a mistake. Otherwise, please read the '
						'[guide on how to spot licensed doujins.](https://www.reddit.com/r/wholesomehentai/comments/eq74k0/in_order_to_enforce_the_rules_a_bit_more_bans/fexum0v?utm_source=share&utm_medium=web2x)'
						''
						'\n\n*I am not a bot. I am being forced to mod this sub. Please send food and water*'
					)

					# Remove it and get rid of the post tracker
					comment.submission.mod.remove(spam=False, mod_note=f'Licensed, appears in magazine {magazine}')
					del pending_sauces[comment.submission.id]
					return

				detected_tags = []
				for tag in data[2]:
					if tag in unwholesome_tags:
						detected_tags.append(tag)

				if len(detected_tags) != 0:
					# Oh no, there's an illegal tag!
					print("Illegal tags detected: " + ', '.join(detected_tags))
					comment.parent().edit(
						f'The provided source has the disallowed tags:\n```\n{", ".join(detected_tags)}\n```'
						f'Please [contact the mods](https://www.reddit.com/message/compose?to=/r/{config["subreddit"]}) if you think this is either'
						'a mistagged doujin or a wholesome exception.'
						'Otherwise, make sure you understand Rules 1 and 5.'
						'\n\n*I am not a bot. I am being forced to mod this sub. Please send food and water*'
					)

					# Remove it and get rid of the post tracker
					comment.submission.mod.remove(spam=False, mod_note=f'Has the illegal tag(s): {", ".join(detected_tags)}')
					del pending_sauces[comment.submission.id]
					return

				parodies = '' if len(data[3]) == 0 else f"**Parodies:**  \n{', '.join(data[3])}\n\n"
				characters = '' if len(data[4]) == 0 else f"**Characters:**  \n{', '.join(data[4])}\n\n"
				tags = '**Tags:**  \nNone' if len(data[2]) == 0 else f"**Tags:**  \n{', '.join(data[2])}\n\n"

				comment.parent().edit(
					f"The source OP provided:  \n> <{url}>\n\n"
					f'**{data[0]}** by {data[1]}  \n^{data[5]} pages\n\n{parodies}{characters}{tags}'
					'*I am not a bot. I am being forced to mod this sub. Please send food and water*'
				)
			else:
				comment.parent().edit(
					f"The source OP provided:  \n> <{url}>\n\n"
					'*I am not a bot. I am being forced to mod this sub. Please send food and water*'
				)

			# If we made it here, the post is good. Clean up any trackers and add a post entry to the database.
			print('Updating database and cleaning up...')
			c.execute('INSERT INTO posts VALUES (?, ?, ?)',
			          (comment.submission.permalink, url, comment.submission.created_utc))
			conn.commit()
			del pending_sauces[comment.submission.id]


def register_pending_sauce(author: str, submission_id: str, comment_id: str):
	global pending_sauces
	pending_sauces[submission_id] = {'author': author, 'comment_id': comment_id}
