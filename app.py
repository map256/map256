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

from google.appengine.ext.webapp import template
from google.appengine.api import memcache
from google.appengine.api import users

from django.utils import simplejson

from m256_cfg import *
from models import *

class MainHandler(webapp.RequestHandler):
    def get(self):
		blob = memcache.get('frontpage_blob')

		if blob is None:

			users = TrackedUser.all()
			users.filter('foursquare_disabled =', False)

			blob = {}

			for user in users:
				if user.twitter_username is not None:
					q1 = TrackedUserCheckin.all()
					q1.filter('foursquare_id = ', user.foursquare_id)
					q1.order('-occured')
					r1 = q1.fetch(10)
					tmpa = []

					for res1 in r1:
						tmpa.append(str(res1.location))

					blob[str(user.twitter_username)] = tmpa

			blob = simplejson.dumps(blob)
			memcache.add('frontpage_blob', blob, 300)

		path = os.path.join(os.path.dirname(__file__), 'templates/front.tmpl')
		self.response.out.write(template.render(path, {'blob': blob}))

class TwitLookupHandler(webapp.RequestHandler):
	def get(self, username=None):
		datapts = memcache.get('datapts_'+username)

		if datapts is None:
			q = TrackedUser.all()
			q.filter('twitter_username = ', username)

			if q.count() < 1:
				raise Exception('User does not exist!')

			user = q.get()
			q = TrackedUserCheckin.all()
			q.filter('foursquare_id =', user.foursquare_id)
			q.order('-occured')

			if q.count() < 1:
				self.response.out.write('Datapoints havent been gathered yet.  I need to make a pretty page saying to wait another 5-15 seconds and then refresh.  Its probably done in the time its taken you to read this.')
				return

			datapts = []

			for checkin in q.fetch(100):
				datapts.append( checkin.location )

			memcache.add('datapts_'+username, datapts, 300)

		lastpt = datapts[0]
		template_values = {'datapoints': datapts, 'centerpt': lastpt }
		path = os.path.join(os.path.dirname(__file__), 'templates/map.tmpl')
		self.response.out.write(template.render(path, template_values))

class FourSqIdLookupHandler(webapp.RequestHandler):
	def get(self, fsq_id=None):
		q = TrackedUser.all()
		q.filter('foursquare_id =', long(fsq_id))

		if q.count() < 1:
			raise Exception('User does not exist!')

		user = q.get()

		q = TrackedUserCheckin.all()
		q.filter('foursquare_id =', user.foursquare_id)
		q.order('-occured')

		datapts = []
		for checkin in q.fetch(100):
			datapts.append( checkin.location )

		lastpt = datapts[0]
		template_values = {'datapoints': datapts, 'centerpt': lastpt }
		path = os.path.join(os.path.dirname(__file__), 'templates/map.tmpl')
		self.response.out.write(template.render(path, template_values))

class ScoreboardHandler(webapp.RequestHandler):
	def get(self):
		periods = ('week', 'month', 'alltime')
		kinds = ('checkin_speed', 'distance_traveled', 'number_checkins')
		template_values = {}

		for kind in kinds:
			for period in periods:
				q = GeneratedStatistic.all()
				q.filter('description =', kind + '_' + period)
				q.order('-created')
				r = q.get()
				template_values[kind + '_' + period] = simplejson.loads(r.contents)

		path = os.path.join(os.path.dirname(__file__), 'templates/scoreboard.tmpl')
		self.response.out.write(template.render(path, template_values))

class ProfileHandler(webapp.RequestHandler):
	def get(self):
		user = users.get_current_user()
		template_values = {}

		account = Account.all()
		account.filter('google_user =', user)

		if account.count() == 0:
			account = Account()
			account.google_user = user
			self.response.out.write('Here')
			account.put()

		acc = account.get()

		tusers = TrackedUser.all()
		tusers.filter('account =', acc)
		template_values['tusers'] = tusers.fetch(50)

		template_values['nickname'] = user.nickname()
		template_values['sign_out_url'] = users.create_logout_url('/')

		path = os.path.join(os.path.dirname(__file__), 'templates/profile.tmpl')
		self.response.out.write(template.render(path, template_values))

class DataHandler(webapp.RequestHandler):
	def get(self, key=None):
		data = memcache.get('checkindata_'+key)
		self.response.headers.add_header('Content-Type', 'application/json')

		if data is None:
			data = []

			try:
				k1 = db.Key(key)
			except:
				return

			user = TrackedUser.get(k1)

			if user is None:
				return

			checkins = TrackedUserCheckin.all()
			checkins.filter('foursquare_id =', user.foursquare_id)

			if checkins.count() == 0:
				return

			for checkin in checkins:
				info = {}
				info['location'] = str(checkin.location)
				info['occurred'] = str(checkin.occured)
				data.append(info)

			data.sort(cmp=lambda x,y: cmp(datetime.datetime.strptime(x['occurred'], '%Y-%m-%d %H:%M:%S'),
			                              datetime.datetime.strptime(y['occurred'], '%Y-%m-%d %H:%M:%S')))

			encoded = simplejson.dumps(data)
			memcache.add('checkindata_'+key, encoded, 60)
			self.response.out.write(encoded)
		else:
			self.response.out.write(data)

def main():
    application = webapp.WSGIApplication([('/', MainHandler),
										 ('/scoreboard', ScoreboardHandler),
										 ('/profile', ProfileHandler),
										 ('/data/(.*)', DataHandler),
										 ('/t/(.*)', TwitLookupHandler),
										 ('/f/(.*)', FourSqIdLookupHandler)],
                                         debug=True)
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()
