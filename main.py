import json
import time
import asyncio
import traceback

import praw
from termcolor import cprint
from prawcore import ResponseException
from praw.models.util import stream_generator
from praw.models import Submission
from praw.models import Comment

import process_comment
import process_post


def submissions_and_comments(subreddit, **kwargs):
	results = []
	results.extend(subreddit.new(**kwargs))
	results.extend(subreddit.comments(**kwargs))
	results.sort(key=lambda post: post.created_utc, reverse=True)
	return results


async def main():
	cprint('Wholesome Hentai Mod Bot v1.0', 'yellow', attrs=['reverse'])
	print('Loading config file...')
	config = json.load(open('config.json'))

	print('Logging in...')
	reddit = praw.Reddit(client_id=config['id'],
	                     client_secret=config['secret'],
	                     user_agent=config['agent'],
	                     username=config['username'],
	                     password=config['password'])
	print('Logged in as u/' + str(reddit.user.me()))

	subreddit = reddit.subreddit(config['subreddit'])

	print(f'Checking status of user in subreddit (r/{config["subreddit"]})')

	if not subreddit.user_is_moderator:
		print('User is not a moderator. Exiting...')
		return

	print('User is a moderator. Scanning started...')

	# comment_stream = subreddit.stream.comments(pause_after=-1)
	# submission_stream = subreddit.stream.submissions(pause_after=-1)

	start_time = time.time()
	stream = stream_generator(lambda **kwargs: submissions_and_comments(subreddit, **kwargs))

	# Scan all new posts and comments
	"""
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
			continue
	"""

	for post in stream:
		if post.created_utc < start_time:
			continue
		if isinstance(post, Submission):
			await process_post.process_post(post)
		elif isinstance(post, Comment):
			await process_comment.process_comment(post, reddit)


if __name__ == '__main__':
	asyncio.run(main())
