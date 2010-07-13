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
from google.appengine.api.labs import taskqueue

import logging

from m256_cfg import *
from models import *

class FoursquareHistoryDispatcher(webapp.RequestHandler):
	def get(self):
		q1 = FoursquareAccount.all()
		q1.filter('foursquare_disabled = ', False)

		for user in q1:
			params = {}
			params['fsq_id'] = user.foursquare_id

			q2 = FoursquareCheckin.all()
			q2.filter('owner = ', user)
			q2.order('-checkin_id')

			if q.count() != 0:
				latest = q2.get()
				params['since'] = latest.checkin_id
			else:
				params['since'] = 0

			logging.info('Enqueing task worker_foursquare_history with params %s' % params)
			taskqueue.add(url='/worker_foursquare_history', params=params, method='GET')

class TwitterHistoryDispatcher(webapp.RequestHandler):
	def get(self):
		q1 = TwitterAccount.all()
		q1.filter('disabled =', False)

		for user in q1:
			params = {}
			params['twitter_id'] = user.twitter_id

			q2 = TwitterCheckin.all()
			q2.filter('owner =', user)
			q2.order('-tweet_id')

			if q2.count() != 0:
				latest = q2.get()
				params['since'] = latest.tweet_id
			else:
				params['since'] = 0

			logging.info('Enqueing task worker_twitter_history with params %s' % params)
			taskqueue.add(url='/worker_twitter_history', params=params, method='GET')

class StatisticsDispatcher(webapp.RequestHandler):
	def get(self):
		periods = ('week', 'month', 'alltime')
		kinds = ('checkin_speed', 'distance_traveled', 'number_checkins')

		for kind in kinds:
			for period in periods:
				taskqueue.add(url='/worker_statistics', params={'period': period, 'kind': kind}, method='GET')

def main():
	application = webapp.WSGIApplication([('/cron_foursquare_history', FoursquareHistoryDispatcher),
										  ('/cron_twitter_history', TwitterHistoryDispatcher),
										  ('/cron_statistics', StatisticsDispatcher)],
		                                  debug=True)

	util.run_wsgi_app(application)

if __name__ == '__main__':
	main()
