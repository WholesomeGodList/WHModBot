import pprint

from praw.models import Submission

import process_comment


def process_post(submission: Submission):
	print("New post: " + submission.title)
	# If the submission has the green shield, no touchy touchy
	if submission.distinguished:
		print("Mod post. Skipping...")
		return

	# Do not respond to memes!
	# Or non-image posts.
	# god I miss nullish coalescing
	if (hasattr(submission, 'link_flair_text') and submission.link_flair_text and submission.link_flair_text.lower() == 'meme') or submission.is_self:
		print("Either this is flaired Meme or this is a self-post.")
		return

	print("This is an actual post, asking for sauce...")
	ask_for_sauce(submission)


def ask_for_sauce(submission: Submission):
	comment = submission.reply('**Reply to this comment** with the source, in regular link format, '
	                           'such as  \n```\nhttps://nhentai.net/g/(numbers).\n```\nIf you feel like your post '
	                           'has no applicable source, reply with "None".\n\n'
	                           '*I am not a bot. I am being forced to mod this sub. Please send food and water*')
	if comment is None:
		print('Something wacky happened')
		return

	comment.mod.distinguish(how='yes', sticky=True)
	process_comment.register_pending_sauce(submission.author.name, submission.id, comment.id)
