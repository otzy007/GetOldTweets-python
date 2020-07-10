import urllib.request, urllib.parse, urllib.error,urllib.request,urllib.error,urllib.parse,json,re,datetime,sys,http.cookiejar
from .. import models
from pyquery import PyQuery

FILTER_TWEETS = "tweets"
FILTER_REPLIES = "replies"

class TweetManager:

	def __init__(self):
		pass

	@staticmethod
	def getTweets(tweetCriteria, receiveBuffer=None, bufferLength=100, proxy=None):
		refreshCursor = ''

		results = []
		resultsAux = []
		cookieJar = http.cookiejar.CookieJar()

		active = True

		while active:
			json = TweetManager.getJsonReponse(FILTER_TWEETS, tweetCriteria, refreshCursor, cookieJar, proxy)
			if len(json['items_html'].strip()) == 0:
				break

			refreshCursor = json['min_position']
			scrapedTweets = PyQuery(json['items_html'])
			#Remove incomplete tweets withheld by Twitter Guidelines
			scrapedTweets.remove('div.withheld-tweet')
			tweets = scrapedTweets('div.js-stream-tweet')

			if len(tweets) == 0:
				break

			for tweetHTML in tweets:
				tweetPQ = PyQuery(tweetHTML)
				tweet = models.Tweet()
				usernameTweet = tweetPQ("span.username.u-dir.u-textTruncate b")[0].text
				txt = re.sub(r"\s+", " ", tweetPQ("p.js-tweet-text").text().replace('# ', '#').replace('@ ', '@'))
				retweets = int(tweetPQ("span.ProfileTweet-action--retweet span.ProfileTweet-actionCount").attr("data-tweet-stat-count").replace(",", ""))
				favorites = int(tweetPQ("span.ProfileTweet-action--favorite span.ProfileTweet-actionCount").attr("data-tweet-stat-count").replace(",", ""))
				replies = int(tweetPQ("span.ProfileTweet-action--reply span.ProfileTweet-actionCount").attr("data-tweet-stat-count").replace(",", ""))
				dateSec = int(tweetPQ("small.time span.js-short-timestamp").attr("data-time"))
				id = tweetPQ.attr("data-tweet-id")
				permalink = tweetPQ.attr("data-permalink-path")
				user_id = int(tweetPQ("a.js-user-profile-link").attr("data-user-id"))
				avatar = tweetPQ("img.avatar").attr['src']
				geo = ''
				geoSpan = tweetPQ('span.Tweet-geo')
				if len(geoSpan) > 0:
					geo = geoSpan.attr('title')
				urls = []
				for link in tweetPQ("a"):
					try:
						urls.append((link.attrib["data-expanded-url"]))
					except KeyError:
						pass
				tweet.id = id
				tweet.permalink = 'https://twitter.com' + permalink
				tweet.username = usernameTweet

				tweet.text = txt
				tweet.date = datetime.datetime.fromtimestamp(dateSec)
				tweet.formatted_date = datetime.datetime.fromtimestamp(dateSec).strftime("%a %b %d %X +0000 %Y")
				tweet.retweets = retweets
				tweet.favorites = favorites
				tweet.replies = replies
				tweet.mentions = " ".join(re.compile('(@\\w*)').findall(tweet.text))
				tweet.hashtags = " ".join(re.compile('(#\\w*)').findall(tweet.text))
				tweet.geo = geo
				tweet.urls = ",".join(urls)
				tweet.author_id = user_id
				tweet.avatar = avatar

				results.append(tweet)
				resultsAux.append(tweet)

				if receiveBuffer and len(resultsAux) >= bufferLength:
					receiveBuffer(resultsAux)
					resultsAux = []

				if tweetCriteria.maxTweets > 0 and len(results) >= tweetCriteria.maxTweets:
					active = False
					break


		if receiveBuffer and len(resultsAux) > 0:
			receiveBuffer(resultsAux)

		return results

	@staticmethod
	def getReplies(tweetCriteria, receiveBuffer=None, bufferLength=100, proxy=None):
		refreshCursor = ''
		results = []
		resultsAux = []
		cookieJar = http.cookiejar.CookieJar()
		active = True
		while active:
			json = TweetManager.getJsonReponse(FILTER_REPLIES, tweetCriteria, refreshCursor, cookieJar, proxy)
			if len(json['items_html'].strip()) == 0:
				break

			refreshCursor = json['min_position']
			scrapedTweets = PyQuery(json['items_html'])
			scrapedTweets.remove('li.AdaptiveStreamUserGallery')
			replies = scrapedTweets('li.js-stream-item')

			if len(replies) == 0:
				break

			for replyHTML in replies:
				replyPQ = PyQuery(replyHTML)
				reply = models.Reply()
				if replyPQ("div ").attr("data-is-reply-to") != "true":
					continue

				time = int(replyPQ("div div.content div.stream-item-header small.time a.tweet-timestamp span").attr("data-time"))
				favorites = int(replyPQ("div div.content div.stream-item-footer div span.ProfileTweet-action--favorite span.ProfileTweet-actionCount").attr("data-tweet-stat-count").replace(",", ""))
				retweets = int(replyPQ("div div.content div.stream-item-footer div span.ProfileTweet-action--retweet span.ProfileTweet-actionCount").attr("data-tweet-stat-count").replace(",", ""))
				replies = int(replyPQ("div div.content div.stream-item-footer div span.ProfileTweet-action--reply span.ProfileTweet-actionCount").attr("data-tweet-stat-count").replace(",", ""))
				
				reply.replying_to_tweet_id = int(replyPQ("div ").attr("data-conversation-id"))
				reply.current_tweet_id = int(replyPQ("div ").attr("data-tweet-id"))
				reply.text = replyPQ("div div.content div.js-tweet-text-container p").text()
				reply.permalink = "https://twitter.com" + replyPQ("div ").attr("data-permalink-path")
				reply.owner_username = replyPQ("div ").attr("data-screen-name").lower()
				reply.published_at = time
				reply.favorites = favorites
				reply.retweets = retweets
				reply.replies = replies

				results.append(reply)
				resultsAux.append(reply)

		if receiveBuffer and len(resultsAux) > 0:
			receiveBuffer(resultsAux)

		return results

	@staticmethod
	def getJsonReponse(filterItems, tweetCriteria, refreshCursor, cookieJar, proxy):
		url = "https://twitter.com/i/search/timeline?f=%s&q=%s&src=typd&%smax_position=%s"

		urlGetData = ''
		if hasattr(tweetCriteria, 'username'):
			if filterItems == FILTER_TWEETS:
				urlGetData += ' from:' + tweetCriteria.username
			if filterItems == FILTER_REPLIES:
				urlGetData += ' to:' + tweetCriteria.username

		if hasattr(tweetCriteria, 'since'):
			urlGetData += ' since:' + tweetCriteria.since

		if hasattr(tweetCriteria, 'until'):
			urlGetData += ' until:' + tweetCriteria.until

		if hasattr(tweetCriteria, 'querySearch'):
			urlGetData += ' ' + tweetCriteria.querySearch

		if hasattr(tweetCriteria, 'lang'):
			urlLang = 'lang=' + tweetCriteria.lang + '&'
		else:
			urlLang = ''
		url = url % (filterItems, urllib.parse.quote(urlGetData), urlLang, refreshCursor)
		#print(url)

		headers = [
			('Host', "twitter.com"),
			('User-Agent', "Mozilla/5.0 (Windows NT 6.1; Win64; x64)"),
			('Accept', "application/json, text/javascript, */*; q=0.01"),
			('Accept-Language', "de,en-US;q=0.7,en;q=0.3"),
			('X-Requested-With', "XMLHttpRequest"),
			('Referer', url),
			('Connection', "keep-alive")
		]

		if proxy:
			opener = urllib.request.build_opener(urllib.request.ProxyHandler({'http': proxy, 'https': proxy}), urllib.request.HTTPCookieProcessor(cookieJar))
		else:
			opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookieJar))
		opener.addheaders = headers

		try:
			response = opener.open(url)
			jsonResponse = response.read()
		except:
			#print("Twitter weird response. Try to see on browser: ", url)
			print("Twitter weird response. Try to see on browser: https://twitter.com/search?q=%s&src=typd" % urllib.parse.quote(urlGetData))
			print("Unexpected error:", sys.exc_info()[0])
			sys.exit()
			return

		dataJson = json.loads(jsonResponse.decode())

		return dataJson
