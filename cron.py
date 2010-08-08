#!/usr/bin/python
# -*- coding: utf-8 -*-

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

import datetime
import logging

from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from google.appengine.ext import db
from google.appengine.api.labs import taskqueue

from models import *


class FoursquareHistoryDispatcher(webapp.RequestHandler):
    def get(self):
        q1 = FoursquareAccount.all()
        q1.filter('disabled = ', False)

        for user in q1:
            params = {}
            params['fsq_id'] = user.foursquare_id

            q2 = FoursquareCheckin.all()
            q2.filter('owner = ', user)
            q2.order('-occurred')

            if q2.count() > 0:
                latest = q2.get()
                params['since'] = latest.checkin_id

            logging.info('Adding worker_foursquare_history with: %s' % params)
            taskqueue.add(url='/worker_foursquare_history',
                          params=params,
                          method='GET')

class TwitterHistoryDispatcher(webapp.RequestHandler):
    def get(self):
        q1 = TwitterAccount.all()
        q1.filter('disabled =', False)

        for user in q1:
            params = {}
            params['twitter_id'] = user.twitter_id

            q2 = TwitterCheckin.all()
            q2.filter('owner =', user)
            q2.order('-occurred')

            if q2.count() > 0:
                latest = q2.get()
                params['since'] = latest.tweet_id
            elif user.most_recent_tweet_id is not None:
                params['since'] = user.most_recent_tweet_id

            logging.info('Adding worker_twitter_history with: %s' % params)
            taskqueue.add(url='/worker_twitter_history',
                          params=params,
                          method='GET')

class FlickrHistoryDispatcher(webapp.RequestHandler):
    def get(self):
        q1 = FlickrAccount.all()
        q1.filter('disabled =', False)

        for user in q1:
            params = {}
            params['flickr_id'] = user.nsid

            q2 = FlickrCheckin.all()
            q2.filter('owner =', user)
            q2.order('-occurred')

            if q2.count() > 0:
                latest = q2.get()
                params['since'] = latest.occurred
                #FIXME: Need an elif here to do no geodata import catchall

            logging.info('Adding worker_flickr_history with %s' % params)
            taskqueue.add(url='/worker_flickr_history',
                          params=params)

class StatisticsDispatcher(webapp.RequestHandler):
    def get(self):
        periods = ('week', 'month', 'alltime')
        kinds = ('checkin_speed', 'distance_traveled', 'number_checkins')

        for kind in kinds:
            for period in periods:
                taskqueue.add(url='/worker_statistics',
                              params={'period': period, 'kind': kind},
                              method='GET')

class OauthRequestCleanupDispatcher(webapp.RequestHandler):
    def get(self):
        oldest_allowed = datetime.datetime.now() - datetime.timedelta(hours=8)
        q1 = OauthRequest.all()
        q1.filter('created <=', oldest_allowed)
        db.delete(q1.fetch(250))

def main():

    routes = [
        ('/cron_foursquare_history', FoursquareHistoryDispatcher),
        ('/cron_twitter_history', TwitterHistoryDispatcher),
        ('/cron_flickr_history', FlickrHistoryDispatcher),
        ('/cron_oauth_request_cleanup', OauthRequestCleanupDispatcher),
        ('/cron_statistics', StatisticsDispatcher)
    ]

    application = webapp.WSGIApplication(routes, debug=True)
    util.run_wsgi_app(application)

if __name__ == '__main__':
    main()
