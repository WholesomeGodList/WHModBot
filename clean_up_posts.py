import json
import praw
import sqlite3
import time
from sqlite3 import Connection, Error


def create_connection(path: str) -> Connection:
	connection = None
	try:
		connection = sqlite3.connect(path)
		print("Connected to the posts database")
	except Error as e:
		print(f"The error '{e}' occurred")
		raise Exception("Failed to connect to posts database")

	return connection


# Script to clean up all old posts. Run if posts gets cluttered somehow.
conn = create_connection('posts.db')
c = conn.cursor()
config = json.load(open('config.json'))

print('Logging in...')
reddit = praw.Reddit(client_id=config['id'],
                     client_secret=config['secret'],
                     user_agent=config['agent'],
                     username=config['username'],
                     password=config['password'])

c.execute("SELECT * FROM posts")
records = c.fetchall()

for row in records:
	print(f"Checking post: {row[0]}")
	submission = reddit.submission(url=f'https://reddit.com{row[0]}')

	c.execute('UPDATE posts SET author=? WHERE source=?', (str(submission.author), row[1]))

	if submission.removed:
		print("This submission was removed.")
		c.execute('UPDATE posts SET removed=1 WHERE source=?', (row[1],))

c.execute('DELETE FROM posts WHERE timeposted<?', (int(time.time()) - (8 * 604800),))
c.execute("DELETE FROM posts WHERE source LIKE '%hc.fyi%'")
c.execute("DELETE FROM posts WHERE source LIKE '%hentainexus%'")
c.execute("DELETE FROM posts WHERE source LIKE '%hentai.cafe%'")

conn.commit()
