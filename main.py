import json
import time
import asyncio
import traceback

import praw
from prawcore import ResponseException

import process_comment
import process_post


async def main():
	print("Loading config file...")
	config = json.load(open('config.json'))

	print("Logging in...")
	reddit = praw.Reddit(client_id=config['id'],
	                     client_secret=config['secret'],
	                     user_agent=config['agent'],
	                     username=config['username'],
	                     password=config['password'])
	print("Logged in as u/" + str(reddit.user.me()))

	subreddit = reddit.subreddit(config['subreddit'])

	if not subreddit.user_is_moderator:
		print("User is not a moderator. Exiting...")
		return

	comment_stream = subreddit.stream.comments(pause_after=-1)
	submission_stream = subreddit.stream.submissions(pause_after=-1)

	start_time = time.time()

	# Scan all new posts and comments
	while True:
		try:
			for comment in comment_stream:
				if comment is None:
					break
				if comment.created_utc < start_time:
					continue
				await process_comment.process_comment(comment)

			for submission in submission_stream:
				if submission is None:
					break
				if submission.created_utc < start_time:
					continue
				await process_post.process_post(submission)
		except ResponseException:
			traceback.print_exc()


if __name__ == '__main__':
	asyncio.run(main())
