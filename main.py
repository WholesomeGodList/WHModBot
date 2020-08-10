import json
import time
import asyncio
import traceback
import pprint

import praw
from termcolor import cprint
from prawcore import ResponseException
from http.client import HTTPException
from prawcore import RequestException

import process_comment
import process_post
import process_removal


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

	comment_stream = subreddit.stream.comments(pause_after=4, skip_existing=True)
	submission_stream = subreddit.stream.submissions(pause_after=4, skip_existing=True)
	mod_log_stream = subreddit.mod.stream.log(action="removelink", pause_after=-1, skip_existing=True)

	start_time = time.time()

	# Scan all new posts and comments
	while True:
		try:
			for comment in comment_stream:
				if comment is None:
					break
				if comment.created_utc < start_time:
					continue
				await process_comment.process_comment(comment, reddit)

			for submission in submission_stream:
				if submission is None:
					break
				if submission.created_utc < start_time:
					continue
				await process_post.process_post(submission)

			for link_removal in mod_log_stream:
				if link_removal is None:
					break
				if link_removal.created_utc < start_time:
					continue
				process_removal.process_removal(link_removal, reddit)

		except ResponseException:
			traceback.print_exc()
			await asyncio.sleep(10)
			comment_stream = subreddit.stream.comments(pause_after=4, skip_existing=True)
			submission_stream = subreddit.stream.submissions(pause_after=4, skip_existing=True)
			mod_log_stream = subreddit.mod.stream.log(action="removelink", pause_after=-1, skip_existing=True)
			continue

		except HTTPException:
			traceback.print_exc()
			await asyncio.sleep(10)
			comment_stream = subreddit.stream.comments(pause_after=4, skip_existing=True)
			submission_stream = subreddit.stream.submissions(pause_after=4, skip_existing=True)
			mod_log_stream = subreddit.mod.stream.log(action="removelink", pause_after=-1, skip_existing=True)
			continue

		except RequestException:
			traceback.print_exc()
			await asyncio.sleep(10)
			comment_stream = subreddit.stream.comments(pause_after=4, skip_existing=True)
			submission_stream = subreddit.stream.submissions(pause_after=4, skip_existing=True)
			mod_log_stream = subreddit.mod.stream.log(action="removelink", pause_after=-1, skip_existing=True)
			continue

		except Exception:
			traceback.print_exc()
			continue


if __name__ == '__main__':
	asyncio.run(main())
