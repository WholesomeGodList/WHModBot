import time
import datetime
import praw
import json
import re
import sqlite3
from sqlite3 import Error, Connection

from process_comment import decode_blob, encode_blob

config = json.load(open('config.json'))

print(datetime.datetime.fromtimestamp(int(time.time()), tz=datetime.UTC).strftime("%b %d, %Y %I:%M %p"))
print(str(b'test', 'utf-8'))


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


reddit = praw.Reddit(client_id=config['id'],
                     client_secret=config['secret'],
                     user_agent=config['agent'],
                     username=config['username'],
                     password=config['password'])

print("Connected to reddit")

subreddit = reddit.subreddit("wholesomehentai")
subreddit_wiki = subreddit.wiki

content = subreddit_wiki['commonreposts'].content_md

matcher = re.compile(r'https?://nhentai\.net/g/\d{1,6}/')

items = matcher.findall(content)

for item in items:
	c.execute('SELECT * FROM commonreposts WHERE source=?', (item,))
	if not c.fetchone():
		print(f"Found URL: {item}")
		c.execute('INSERT INTO commonreposts VALUES (?)', (item,))

conn.commit()
