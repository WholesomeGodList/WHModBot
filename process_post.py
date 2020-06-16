import json

from praw.models import Submission

import process_comment
import sqlite3
from sqlite3 import Error


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


async def process_post(submission: Submission):
	print("New post: " + submission.title)

	# Do not respond to memes!
	# Or non-image posts.
	# god I miss nullish coalescing
	if (hasattr(submission, 'link_flair_text') and submission.link_flair_text and 'meme' in submission.link_flair_text.lower()) or submission.is_self:
		print("Either this is flaired Meme or this is a self-post.")
		return

	# Never ask for sauce twice on the same post.
	c.execute('SELECT * FROM allposts WHERE id=?', (submission.id,))
	if c.fetchone():
		print("Duplicate post. Not sure how this happened, but it did.")

	print("This is an actual post, asking for sauce...")
	await ask_for_sauce(submission)


async def ask_for_sauce(submission: Submission):
	comment = submission.reply('**Reply to this comment** with the source, in regular link format, '
	                           'such as  \n```\nhttps://nhentai.net/g/(numbers).\n```\nIf you feel like your post '
	                           'has no applicable source, reply with "None".\n\n' + config['suffix'])
	if comment is None:
		print('Something wacky happened')
		return

	comment.mod.distinguish(how='yes', sticky=True)
	c.execute('INSERT INTO allposts VALUES (?)', (submission.id,))
	c.execute('INSERT INTO pendingposts VALUES (?, ?, ?)', (submission.id, submission.author.name, comment.id))
	conn.commit()
