import json
import re

from praw.models import Submission

import sqlite3
from sqlite3 import Error, Connection
from praw import Reddit

def create_connection(path: str) -> Connection:
	connection = None
	try:
		connection = sqlite3.connect(path)
		print("Connected to the posts database in process_post")
	except Error as e:
		print(f"The error '{e}' occurred")
		raise Exception("Failed to connect to posts database")

	return connection


conn = create_connection('posts.db')
c = conn.cursor()

config = json.load(open('config.json'))


async def process_post(submission: Submission):
	print("New post: " + submission.title)

	# Do not respond to memes!
	# Or non-image posts.
	# god I miss nullish coalescing
	if (hasattr(submission, 'link_flair_text') and submission.link_flair_text and ('meme' in submission.link_flair_text.lower() or 'news' in submission.link_flair_text.lower())) or submission.is_self:
		print("Either this is flaired Meme or this is a self-post.")
		return

	# Never ask for sauce twice on the same post.
	c.execute('SELECT * FROM allposts WHERE id=?', (submission.id,))
	if c.fetchone():
		print("Duplicate post. Not sure how this happened, but it did.")
		return

	# Make sure they have an author in the post.
	author_matcher = re.compile(r'.*\[.*].*')
	if not author_matcher.match(submission.title):
		comment = submission.reply("**Post titles must have the author in square brackets.**\n\n To avoid getting your post removed, make sure the author is in the "
		                 "title (i.e. [Author] Title).\n\n" + config['suffix'])

		if comment is not None:
			comment.mod.distinguish(how='yes', sticky=True)

		submission.mod.remove(mod_note="No author provided")
		return

	# See if they have made 4 posts within the last day
	c.execute('SELECT * FROM posts WHERE author=? AND timeposted>? AND removed=0', (str(submission.author), submission.created_utc - 86400))
	if len(c.fetchall()) >= 4:
		comment = submission.reply("**You have already posted 4 times within the last 24 hours.**\n\nPlease wait a bit before you post again.\n\n" + config['suffix'])

		if comment is not None:
			comment.mod.distinguish(how='yes', sticky=True)

		submission.mod.remove(mod_note="Too many posts within the last day")
		return

	print("This is an actual post, asking for sauce...")
	await ask_for_sauce(submission)


async def ask_for_sauce(submission: Submission):
	comment = submission.reply('**Reply to this comment** with the source. This can be either just the digits,'
	                           ' like 258133, or a URL, such as  \n\n```\nhttps://nhentai.net/g/(numbers).\n```\n\n'
	                           'You may also reply with a link to most non-nhentai URLs. We prefer you use nhentai in'
	                           ' most cases, but in certain cases, Imgchest is acceptable.'
	                           '\n\n' + config['suffix'])
	if comment is None:
		print('Something wacky happened')
		return

	comment.mod.distinguish(how='yes', sticky=True)
	c.execute('INSERT INTO allposts VALUES (?)', (submission.id,))
	c.execute('INSERT INTO pendingposts VALUES (?, ?, ?)', (submission.id, submission.author.name, comment.id))
	conn.commit()

	# Remove it until a source reply is found
	submission.mod.remove()
	return
