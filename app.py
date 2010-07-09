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
from google.appengine.api.labs import taskqueue
from google.appengine.api import mail

from django.utils import simplejson

import m256

from m256_cfg import *
from models import *

class MainHandler(webapp.RequestHandler):
    def get(self):
		blob = memcache.get('frontpage_blob')

		if blob is None:

			users = FoursquareAccount.all()
			users.filter('foursquare_disabled =', False)

			blob = {}

			for user in users:
				if user.twitter_username is not None:
					q1 = FoursquareCheckin.all()
					q1.filter('owner = ', user)
					q1.order('-occurred')
					r1 = q1.fetch(10)
					tmpa = []

					for res1 in r1:
						tmpa.append(str(res1.location))

					blob[str(user.twitter_username)] = tmpa

			blob = simplejson.dumps(blob)
			memcache.add('frontpage_blob', blob, 300)

		m256.output_template(self, 'templates/front.tmpl', {'blob': blob})

class TwitLookupHandler(webapp.RequestHandler):
	def get(self, username=None):
		datapts = memcache.get('datapts_'+username)

		if datapts is None:
			q = FoursquareAccount.all()
			q.filter('twitter_username = ', username)

			if q.count() < 1:
				raise Exception('User does not exist!')

			user = q.get()
			q = FoursquareCheckin.all()
			q.filter('owner =', user)
			q.order('-occurred')

			if q.count() < 1:
				self.response.out.write('Datapoints havent been gathered yet.  I need to make a pretty page saying to wait another 5-15 seconds and then refresh.  Its probably done in the time its taken you to read this.')
				return

			datapts = []

			for checkin in q.fetch(100):
				datapts.append( checkin.location )

			memcache.add('datapts_'+username, datapts, 300)

		m256.output_template(self, 'templates/map.tmpl', {'datapoints': datapts, 'centerpt': datapts[0] })

class FourSqIdLookupHandler(webapp.RequestHandler):
	def get(self, fsq_id=None):
		q = FoursquareAccount.all()
		q.filter('foursquare_id =', str(fsq_id))

		if q.count() < 1:
			raise Exception('User does not exist!')

		user = q.get()

		q = FoursquareCheckin.all()
		q.filter('owner =', user)
		q.order('-occurred')

		datapts = []
		for checkin in q.fetch(100):
			datapts.append( checkin.location )

		if len(datapts) > 0:
			centerpt = datapts[0]
		else:
			centerpt = '37.9523113,-91.7715052'

		m256.output_template(self, 'templates/map.tmpl', {'datapoints': datapts, 'centerpt': centerpt })

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

		m256.output_template(self, 'templates/scoreboard.tmpl', template_values)

class ProfileHandler(webapp.RequestHandler):
	def get(self):
		user = users.get_current_user()
		template_values = {}

		account = Account.all()
		account.filter('google_user =', user)

		if account.count() == 0:
			account = Account()
			account.google_user = user
			account.put()
			acc = account
		else:
			acc = account.get()

		tusers = FoursquareAccount.all()
		tusers.filter('account =', acc)
		template_values['tusers'] = tusers.fetch(50)

		template_values['nickname'] = user.nickname()

		m256.output_template(self, 'templates/profile.tmpl', template_values)

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

			user = FoursquareAccount.get(k1)

			if user is None:
				return

			checkins = FoursquareCheckin.all()
			checkins.filter('owner =', user)

			if checkins.count() == 0:
				return

			for checkin in checkins:
				info = {}
				info['location'] = str(checkin.location)
				info['occurred'] = str(checkin.occurred)
				data.append(info)

			data.sort(cmp=lambda x,y: cmp(datetime.datetime.strptime(x['occurred'], '%Y-%m-%d %H:%M:%S'),
			                              datetime.datetime.strptime(y['occurred'], '%Y-%m-%d %H:%M:%S')))

			encoded = simplejson.dumps(data)
			memcache.add('checkindata_'+key, encoded, 60)
			self.response.out.write(encoded)
		else:
			self.response.out.write(data)

class FoursquareAuthorizationHandler(webapp.RequestHandler):
	def get(self):
		req_ip = memcache.get('iprate_'+self.request.remote_addr)

		if req_ip is None:
			req_ip = 1
			memcache.add('iprate_'+self.request.remote_addr, req_ip, 120)
		else:
			req_ip = req_ip+1
			memcache.replace('iprate_'+self.request.remote_addr, req_ip, 120)

		if req_ip > 10:
			self.response.out.write('Rate limiter kicked in, /authorize blocked for 120 seconds')
			return

		content = m256.foursquare_consumer_request(request_token_url, 'GET')

		request_token = dict(cgi.parse_qsl(content))

		req = OauthRequest()
		req.request_key = request_token['oauth_token']
		req.request_secret = request_token['oauth_token_secret']

		try:
			req.put()
		except CapabilityDisabledError:
			self.response.out.write('Hmm, looks like Google\'s currently doing maintenance on their platform, sorry!')
			return
		else:
			url = authorize_url+'?oauth_token='+request_token['oauth_token']
			m256.output_template(self, 'templates/authorize.tmpl', {'url': url})

class FoursquareCallbackHandler(webapp.RequestHandler):
	def get(self):
		arg = self.request.get('oauth_token')
		q = OauthRequest.all()
		q.filter('request_key = ', arg)

		if q.count() < 1:
			raise Exception('Invalid request (key does not exist)')

		req = q.get()

		content = m256.foursquare_token_request(access_token_url, 'POST', req.request_key, req.request_secret)

		access_token = dict(cgi.parse_qsl(content))

		content = m256.foursquare_token_request(userdetail_url, 'GET', access_token['oauth_token'], access_token['oauth_token_secret'])

		db.delete(req)
		#FIXME: Is there any scenario in which a request key, once approved, should be kept around?

		#FIXME: Saw an odd bug one time where access token was requested, approved, but timed out before response was given
		#Dunno how to handle it just yet, but putting it in here before I forget

		userinfo = simplejson.loads(content)

		q = FoursquareAccount.all()
		q.filter('foursquare_id = ', str(userinfo['user']['id']))

		if q.count() > 0:
			raise Exception('User is already authorized!')

		#FIXME: Need to check for these keys first
		tuser = FoursquareAccount()
		tuser.access_key = access_token['oauth_token']
		tuser.access_secret = access_token['oauth_token_secret']

		if userinfo['user'].has_key('twitter'):
			tuser.twitter_username = userinfo['user']['twitter']

		tuser.foursquare_id = str(userinfo['user']['id'])

		user = users.get_current_user()
		if user is not None:

			account = Account.all()
			account.filter('google_user =', user)

			if account.count() == 0:
				acc = Account()
				acc.google_user = user
				acc.put()
				tuser.account = acc
			else:
				acc = account.get()
				tuser.account = acc

		try:
			tuser.put()
		except CapabilityDisabledError:
			self.response.out.write('Hmm, looks like Google\'s currently doing maintenance on their platform, sorry!')
			pass
		else:
			taskqueue.add(url='/worker_foursquare_history', params={'fsq_id': tuser.foursquare_id}, method='GET')

			if userinfo['user'].has_key('twitter'):
				url = '/t/'+userinfo['user']['twitter']
			else:
				url = '/f/'+str(userinfo['user']['id'])

			path = os.path.join(os.path.dirname(__file__), 'templates/callback.tmpl')
			self.response.out.write(template.render(path, {'map_url': url}))

		mail.send_mail(sender='Map256 <service@map256.com>',
		              to='Eric Sigler <esigler@gmail.com>',
		              subject='Map256 Foursquare Authorization',
		              body="""
		Hey!  It looks like another person has authorized Map256 to access
		Foursquare data!

		Foursquare ID: %s

		""" % tuser.foursquare_id )

class FoursquareAccountDeleteHandler(webapp.RequestHandler):
	def get(self):
		fsq_id = self.request.get('fsq_id')
		user = users.get_current_user()

		q3 = Account.all()
		q3.filter('google_user =', user)
		u_acc = q3.get()

		q1 = FoursquareAccount.all()
		q1.filter('foursquare_id =', str(fsq_id))
		q1.filter('account =', u_acc)

		if q1.count() != 0:
			r1 = q1.fetch(10)

			for fsq_acct in r1:
				fsq_acct.delete()

		q2 = FoursquareCheckin.all()
		q2.filter('foursquare_id =', str(fsq_id))

		if q2.count() != 0:
			r2 = q2.fetch(1000)

			for ci in r2:
				ci.delete()

		m256.output_template(self, 'templates/fsq_deleted.tmpl', {'sign_out_url': users.create_logout_url('/')})

def main():
    application = webapp.WSGIApplication([('/', MainHandler),
										 ('/scoreboard', ScoreboardHandler),
										 ('/profile', ProfileHandler),
										 ('/foursquare_authorization', FoursquareAuthorizationHandler),
										 ('/foursquare_callback', FoursquareCallbackHandler),
										 ('/foursquare_account_delete', FoursquareAccountDeleteHandler),
										 ('/data/(.*)', DataHandler),
										 ('/t/(.*)', TwitLookupHandler),
										 ('/f/(.*)', FourSqIdLookupHandler)],
                                         debug=True)
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()
