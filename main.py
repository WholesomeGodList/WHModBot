import json
import time

import praw

import process_comment
import process_post


def main():
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

	comment_stream = subreddit.stream.comments(pause_after=-1)
	submission_stream = subreddit.stream.submissions(pause_after=-1)

	start_time = time.time()

	# Scan all new posts and comments
	while True:
		for comment in comment_stream:
			if comment is None:
				break
			if comment.created_utc < start_time:
				continue
			process_comment.process_comment(comment)

		for submission in submission_stream:
			if submission is None:
				break
			if submission.created_utc < start_time:
				continue
			process_post.process_post(submission)


if __name__ == '__main__':
	main()
