# WHModBot
A modbot for r/wholesomehentai.

## Brief description of how the bot works:
Every time someone posts to the subreddit, the bot will post and pin a comment asking for the source. Once a source is provided by the OP (by replying to that pin), the comment asking for the source will be edited into either a removal and a reason for removal, or a comment linking to the source and providing info (if the source is to nhentai).

If for some reason a post needs to be reapproved after automated removal, simply respond to the pin with a comment saying "override (url)" (case sensitive). The bot will reapprove the post and fix the pinned comment.

### What the bot can do:
- Detect any malformed links and ask for the link again.
- Detect any licensed magazines (i.e. if the title has COMIC something) and remove them.
- Fetch information for sources from nhentai, and detect any highly questionable tags that warrant removal. (NTR, cheating, rape, shota / loli, etc.)
- Remove any very common reposts or posts that have been posted recently.
- Remove any parodies with guaranteed underage in canon (i.e. MHA)
- Notably, it WILL ignore (not pin anything on) any self-posts (aka text posts), and any posts flaired with Meme.

### What the bot CAN'T do:
- License check fully. It only does a very surface level scan for magazines in the title on nhentai (which means SOME licensed doujins will be caught faster). All doujins that pass will still need manual license checking.
- Detect reposts at first. It needs to run for some time so it can populate its database of posts, so it can start detecting reposts.
- Check for underage properly. It can only detect lolicon/shotacon.
- Check for more subtle forms of unwholesomeness. The bot can only detect and remove extreme tags.
- Scan links in the comments for this stuff. I'll implement that if it's wanted.
