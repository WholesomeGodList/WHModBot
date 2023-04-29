from praw import reddit
from praw.models import Submission
import sqlite3
from sqlite3 import Error, Connection

import process_comment


def create_connection(path: str) -> Connection:
	connection = None
	try:
		connection = sqlite3.connect(path)
		print("Connected to the posts database in process_removal")
	except Error as e:
		print(f"The error '{e}' occurred")
		raise Exception("Failed to connect to posts database")

	return connection


conn = create_connection('posts.db')
c = conn.cursor()


def process_removal(removal_action, reddit: reddit):
	c.execute('SELECT * FROM pendingposts WHERE submission_id=?', (Submission.id_from_url('https://reddit.com' + removal_action.target_permalink),))

	# If post is pending now, don't bother
	if c.fetchone():
		return

	print('Removal detected. Updating database...')
	c.execute('UPDATE posts SET removed=1 WHERE url=?', (removal_action.target_permalink,))
	conn.commit()
	process_comment.update_wiki(reddit)
