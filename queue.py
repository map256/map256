#!/usr/bin/env python

#
# Copyright (c) 2010 Eric Sigler, esigler@gmail.com
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

from google.appengine.ext import webapp
from google.appengine.ext.webapp import util

import cgi
import os
import sys
import datetime

from google.appengine.api.labs import taskqueue
from google.appengine.api import memcache

httplib2_path = 'lib/httplib2.zip'
sys.path.insert(0, httplib2_path)
import httplib2

oauth_path = 'lib/oauth2.zip'
sys.path.insert(0, oauth_path)
import oauth2 as oauth

from django.utils import simplejson

import urllib
from google.appengine.api import urlfetch
from google.appengine.api.urlfetch import DownloadError
from google.appengine.api import mail

import math

from m256_cfg import *
from models import *
import m256

class FoursquareHistoryWorker(webapp.RequestHandler):
	def get(self, fsq_id=None, since=None):
		fsq_id = self.request.get('fsq_id')

		q = FoursquareAccount.all()
		q.filter('foursquare_id = ', str(fsq_id))

		if q.count() != 1:
			raise Exception('User does not exist')

		user = q.get()

		consumer = oauth.Consumer(consumer_key, consumer_secret)
		token = oauth.Token(user.access_key, user.access_secret)
		client = oauth.Client(consumer, token)
		headers = {'User-Agent': 'map256.com:20100617'}

		if self.request.get('since'):
			since = self.request.get('since')
			url_to_fetch = history_url+'?l=250&sinceid='+since
		else:
			url_to_fetch = history_url+'?l=250'

		try:
			resp, content = client.request(url_to_fetch, 'GET', headers=headers)
		except urlfetch.Error:
			recent = memcache.get('urlfetch_count')

			if recent is None:
				memcache.add('urlfetch_count', 1, 150)
			else:
				recent = recent + 1
				memcache.replace('urlfetch_count', recent, 150)

			if recent > 10:
				mail.send_mail(sender='Map256 <service@map256.com', to='Eric Sigler <esigler@gmail.com>', subject='Map256 Foursquare Errors', body='High error rate on FSQ fetches')

			return

		if resp.status == 403:
			recent = memcache.get('fsq_403_'+fsq_id)

			if recent is None:
				memcache.add('fsq_403_'+fsq_id, 1, 3600)
			else:
				memcache.replace('fsq_403_'+fsq_id, recent+1, 3600)

			if recent > 10:
				user.foursquare_disabled = True
				user.put()
				mail.send_mail(sender='Map256 <service@map256.com', to='Eric Sigler <esigler@gmail.com>', subject='Map256 Foursquare 403 error', body='High 403 rate on %s user' % fsq_id )

			return

		if resp.status != 200:
			raise Exception('Invalid response %s.' % resp['status'])

		history = simplejson.loads(content)

		checkins = history['checkins']
		checkins.sort(cmp=lambda x,y: cmp(datetime.datetime.strptime(x['created'], '%a, %d %b %y %H:%M:%S +0000'), datetime.datetime.strptime(y['created'], '%a, %d %b %y %H:%M:%S +0000')))

		for checkin in checkins:
			q2 = FoursquareCheckin.all()
			q2.filter('checkin_id = ', checkin['id'])

			if q2.count() == 0:
				ci = FoursquareCheckin()
				ci.foursquare_id = str(fsq_id)
				ci.location = str(checkin['venue']['geolat'])+','+str(checkin['venue']['geolong'])
				ci.checkin_id = str(checkin['id'])
				ci.occurred = datetime.datetime.strptime(checkin['created'], '%a, %d %b %y %H:%M:%S +0000')

				q3 = FoursquareCheckin.all()
				q3.filter('foursquare_id = ', ci.foursquare_id)
				q3.order('-occurred')
				prev = q3.get()

				if prev is None:
					ci.put()
					ci.previous_checkin = ci
				else:
					ci.previous_checkin = prev

				ci.owner = user

				#Using Spherical Law of Cosines to determine distance
				lon1 = ci.previous_checkin.location.lon
				lon2 = ci.location.lon
				lat1 = ci.previous_checkin.location.lat
				lat2 = ci.location.lat

				delta = lon2 - lon1
				a = math.radians(lat1)
				b = math.radians(lat2)
				c = math.radians(delta)
				x = math.sin(a) * math.sin(b) + math.cos(a) * math.cos(b) * math.cos(c)
				distance = math.acos(x)
				distance = math.degrees(distance)
				distance = distance * 60
				distance = distance * 1.852 #to kilometer

				ci.distance_traveled = distance
				td = ci.occurred - ci.previous_checkin.occurred

				if distance != 0:
					ci.velocity = distance / td.seconds
				else:
					ci.velocity = 0.0

				ci.account_owner = user.account

				ci.put()

class TwitterHistoryWorker(webapp.RequestHandler):
	def get(self):
		twitter_id = str(self.request.get('twitter_id'))

		q1 = TwitterAccount.all()
		q1.filter('twitter_id = ', twitter_id)

		if q1.count() != 1:
			raise Exception('User does not exist')

		t_acct = q1.get()

		if self.request.get('since'):
			since = self.request.get('since')
			request_url = twitter_user_timeline_url+'?count=200&since_id='+since
		elif self.request.get('before'):
			before = self.request.get('before')
			request_url = twitter_user_timeline_url+'?count=200&max_id='+before
		else:
			request_url = twitter_user_timeline_url+'?count=200'

		self.response.out.write('Using request URL: %s<br>' % request_url)
		content = m256.twitter_token_request(request_url, 'GET', t_acct.access_key, t_acct.access_secret)
		history = simplejson.loads(content)

		for tweet in history:
			if tweet['geo'] is not None:
				self.response.out.write('Found geo tweet, ID# %s<br>' % tweet['id'])
				q2 = TwitterCheckin.all()
				q2.filter('tweet_id = ', tweet['id'])

				if q2.count() == 0:
					self.response.out.write('Dont have existing record, going to create new checkin<br>')
					ci = TwitterCheckin()
					ci.owner = t_acct
					ci.location = str(tweet['geo']['coordinates'][0])+','+str(tweet['geo']['coordinates'][1])
					ci.tweet_id = str(tweet['id'])
					ci.occurred = datetime.datetime.strptime(tweet['created_at'], '%a %b %d %H:%M:%S +0000 %Y')
					ci.account_owner = t_acct.account
					ci.put()

		if len(history) > 1:
			last_id = history[len(history)-1]['id']
			self.response.out.write('Have more than one tweet, enqueing at last_id: %s' % last_id)
			taskqueue.add(url='/worker_twitter_history', params={'twitter_id': t_acct.twitter_id, 'before': last_id }, method='GET')

class StatisticsWorker(webapp.RequestHandler):
	def get(self, kind=None, period=None):
		kind = self.request.get('kind')
		period = self.request.get('period')

		if period == 'week':
			start_date = datetime.datetime.now()
			delta = datetime.timedelta(days=start_date.weekday(), hours=start_date.hour, minutes=start_date.minute, seconds=start_date.second+1)
			start_date = start_date - delta
		elif period == 'month':
			start_date = datetime.datetime.now()
			delta = datetime.timedelta(days=start_date.day-1, hours=start_date.hour, minutes=start_date.minute, seconds=start_date.second+1)
			start_date = start_date - delta
		elif period == 'alltime':
			start_date = datetime.date(2005, 1, 1)
		else:
			raise Exception('Invalid period!')

		listing = {}

		if kind == 'checkin_speed':
			checkins = FoursquareCheckin.all()
			checkins.filter('occurred >= ', start_date)

			for checkin in checkins:
				if listing.has_key(str(checkin.foursquare_id)):
					listing[str(checkin.foursquare_id)] = (listing[str(checkin.foursquare_id)] + checkin.velocity) / 2
				else:
					listing[str(checkin.foursquare_id)] = checkin.velocity

			from operator import itemgetter
			results = simplejson.dumps(sorted(listing.iteritems(), key=itemgetter(1), reverse=True))

		elif kind == 'distance_traveled':
			checkins = FoursquareCheckin.all()
			checkins.filter('occurred >= ', start_date)

			for checkin in checkins:
				if listing.has_key(str(checkin.foursquare_id)):
					listing[str(checkin.foursquare_id)] = listing[str(checkin.foursquare_id)] + checkin.distance_traveled
				else:
					listing[str(checkin.foursquare_id)] = checkin.distance_traveled

			from operator import itemgetter
			results = simplejson.dumps(sorted(listing.iteritems(), key=itemgetter(1), reverse=True))

		elif kind == 'number_checkins':
			listing = {}
			users = FoursquareAccount.all()

			for user in users:
				q1 = FoursquareCheckin.all()
				q1.filter('foursquare_id = ', str(user.foursquare_id))
				q1.filter('occurred >= ', start_date)

				listing[str(user.foursquare_id)] = q1.count()

			from operator import itemgetter
			results =  simplejson.dumps(sorted(listing.iteritems(), key=itemgetter(1), reverse=True))

		else:
			raise Exception('Invalid kind!')

		stat = GeneratedStatistic()
		stat.description = kind + '_' + period
		stat.contents = results
		stat.put()

def main():
	application = webapp.WSGIApplication([('/worker_foursquare_history', FoursquareHistoryWorker),
										  ('/worker_twitter_history', TwitterHistoryWorker),
										  ('/worker_statistics', StatisticsWorker)],
		                                  debug=True)

	util.run_wsgi_app(application)

if __name__ == '__main__':
	main()
