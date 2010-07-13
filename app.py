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
import logging

from google.appengine.ext.webapp import template
from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.api.labs import taskqueue
from google.appengine.api import mail
from google.appengine.runtime.apiproxy_errors import CapabilityDisabledError

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

class LookupHandler(webapp.RequestHandler):
	def get(self, handle=None):
		if handle is None:
			return

		cached = memcache.get('lookup_'+handle)

		if cached is not None:
			m256.output_template(self, 'templates/map.tmpl', {'account_key': cached})
			return

		q1 = FoursquareAccount.all()
		q1.filter('twitter_username =', str(handle))

		if q1.count() == 1:
			f_account = q1.get()
			key = f_account.account.key()
			m256.output_template(self, 'templates/map.tmpl', {'account_key': key})
			memcache.add('lookup_'+handle, key, 5)
			return

		q2 = FoursquareAccount.all()
		q2.filter('foursquare_id =', str(handle))

		if q2.count() == 1:
			f_account = q2.get()
			key = f_account.account.key()
			m256.output_template(self, 'templates/map.tmpl', {'account_key': key})
			memcache.add('lookup_'+handle, key, 5)
			return

		q3 = TwitterAccount.all()
		q3.filter('screen_name =', str(handle))

		if q3.count() == 1:
			t_account = q3.get()
			key = t_account.account.key()
			m256.output_template(self, 'templates/map.tmpl', {'account_key': key})
			memcache.add('lookup_'+handle, key, 5)
			return

		q4 = TwitterAccount.all()
		q4.filter('twitter_id =', str(handle))

		if q4.count() == 1:
			t_account = q4.get()
			key = t_account.account.key()
			m256.output_template(self, 'templates/map.tmpl', {'account_key': key})
			memcache.add('lookup_'+handle, key, 5)
			return

		self.response.out.write('Sorry, but I cant find a matching user')

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
		account = m256.get_user_model()
		template_values = {}

		q1 = FoursquareAccount.all()
		q1.filter('account =', account)
		template_values['foursquare_accounts'] = q1.fetch(25)

		q2 = TwitterAccount.all()
		q2.filter('account =', account)
		template_values['twitter_accounts'] = q2.fetch(25)

		template_values['nickname'] = account.google_user.nickname()

		m256.output_template(self, 'templates/profile.tmpl', template_values)

class DataHandler(webapp.RequestHandler):
	def get(self, key=None):
		data = memcache.get('checkindata_'+key)

		if data is None:
			data = []

			try:
				k1 = db.Key(key)
			except:
				self.response.out.write('A')
				return

			user = Account.get(k1)

			if user is None:
				self.response.out.write('B')
				return

			checkins = Checkin.all()
			checkins.filter('account_owner =', user)

			if checkins.count() == 0:
				self.response.out.write('C')
				return

			for checkin in checkins:
				info = {}
				info['location'] = str(checkin.location)
				info['occurred'] = str(checkin.occurred)
				data.append(info)

			data.sort(cmp=lambda x,y: cmp(datetime.datetime.strptime(x['occurred'], '%Y-%m-%d %H:%M:%S'),
			                              datetime.datetime.strptime(y['occurred'], '%Y-%m-%d %H:%M:%S')), reverse=True)

			encoded = simplejson.dumps(data)
			wrapped = 'var checkin_data = json_parse(\''+encoded+'\')'
			memcache.add('checkindata_'+key, wrapped, 60)
			self.response.out.write(wrapped)
		else:
			self.response.out.write(data)

class FoursquareAuthorizationHandler(webapp.RequestHandler):
	def get(self):
		content = m256.foursquare_consumer_request(m256.foursquare_request_token_url, 'GET')
		request_token = dict(cgi.parse_qsl(content))

		if 'oauth_token' in request_token and 'oauth_token_secret' in request_token:
			req = OauthRequest()
			req.request_key = request_token['oauth_token']
			req.request_secret = request_token['oauth_token_secret']

			try:
				req.put()
			except CapabilityDisabledError:
				m256.output_maintenance(self)
				return

			url = authorize_url+'?oauth_token='+request_token['oauth_token']
			m256.output_template(self, 'templates/authorize.tmpl', {'url': url, 'service_name': 'Foursquare'})
		else:
			m256.output_error(self, 'Foursquare request token response was invalid')

class FoursquareCallbackHandler(webapp.RequestHandler):
	def get(self):
		arg = self.request.get('oauth_token')
		q1 = OauthRequest.all()
		q1.filter('request_key = ', arg)

		if q1.count() < 1:
			#FIXME: Should be self.redirect('/foursquare_authorization')
			raise Exception('Invalid request (key does not exist)')

		req = q1.get()

		content = m256.foursquare_token_request(access_token_url, 'POST', req.request_key, req.request_secret)
		access_token = dict(cgi.parse_qsl(content))

		content = m256.foursquare_token_request(userdetail_url, 'GET', access_token['oauth_token'], access_token['oauth_token_secret'])
		userinfo = simplejson.loads(content)

		q2 = FoursquareAccount.all()
		q2.filter('foursquare_id = ', str(userinfo['user']['id']))

		if q2.count() > 0:
			raise Exception('User is already authorized!')

		#FIXME: Need to check for these keys first
		tuser = FoursquareAccount()
		tuser.access_key = access_token['oauth_token']
		tuser.access_secret = access_token['oauth_token_secret']
		tuser.foursquare_id = str(userinfo['user']['id'])
		tuser.account = m256.get_user_model()

		if userinfo['user'].has_key('twitter'):
			tuser.twitter_username = userinfo['user']['twitter']

		tuser.put()

		taskqueue.add(url='/worker_foursquare_history', params={'fsq_id': tuser.foursquare_id}, method='GET')

		url = '/f/'+str(userinfo['user']['id'])

		m256.output_template(self, 'templates/callback.tmpl', {'map_url': url})
		m256.notify_admin("New Foursquare account added: http://www.map256.com/f/%s" % tuser.foursquare_id)

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

		m256.output_template(self, 'templates/account_deleted.tmpl')

class TwitterAuthorizationHandler(webapp.RequestHandler):
	def get(self):
		result = m256.twitter_consumer_request(twitter_request_token_url, 'POST')
		request_token = dict(cgi.parse_qsl(result))

		#FIXME: Should check to see if keys exist here (aka did we get a well formed response)
		req = OauthRequest()
		req.request_key = request_token['oauth_token']
		req.request_secret = request_token['oauth_token_secret']
		req.put()

		url = twitter_authorize_url+'?oauth_token='+request_token['oauth_token']
		m256.output_template(self, 'templates/authorize.tmpl', {'url': url, 'service_name': 'Twitter'})

class TwitterCallbackHandler(webapp.RequestHandler):
	def get(self):
		arg = self.request.get('oauth_token')
		q1 = OauthRequest.all()
		q1.filter('request_key = ', arg)

		if q1.count() < 1:
			raise Exception('Invalid request (key does not exist)')

		req = q1.get()

		content = m256.twitter_token_request(twitter_access_token_url, 'POST', req.request_key, req.request_secret)
		access_token = dict(cgi.parse_qsl(content))

		content = m256.twitter_token_request(twitter_user_timeline_url, 'GET', access_token['oauth_token'], access_token['oauth_token_secret'])
		userinfo = simplejson.loads(content)

		q2 = TwitterAccount.all()
		q2.filter('twitter_id =', str(userinfo[0]['user']['id']))

		if q2.count() != 0:
			raise Exception('Twitter account is already authorized!')

		new_account = TwitterAccount()
		new_account.access_key = access_token['oauth_token']
		new_account.access_secret = access_token['oauth_token_secret']
		new_account.twitter_id = str(userinfo[0]['user']['id'])
		new_account.screen_name = str(userinfo[0]['user']['screen_name'])
		new_account.account = m256.get_user_model()
		new_account.put()

		taskqueue.add(url='/worker_twitter_history', params={'twitter_id': new_account.twitter_id}, method='GET')

		url = '/t/'+new_account.screen_name
		m256.output_template(self, 'templates/callback.tmpl', {'map_url': url})
		m256.notify_admin("New Twitter account added: http://www.map256.com/t/%s" % new_account.screen_name)

class TwitterAccountDeleteHandler(webapp.RequestHandler):
	def get(self):
		twitter_id = str(self.request.get('twitter_id'))
		u_acc = m256.get_user_model()

		q1 = TwitterAccount.all()
		q1.filter('twitter_id =', twitter_id)
		q1.filter('account =', u_acc)

		if q1.count() != 0:
			r1 = q1.fetch(50)

			for twitter_account in r1:
				q2 = TwitterCheckin.all(keys_only=True)
				q2.filter('owner =', twitter_account)
				db.delete(q2.fetch(1000)) #FIXME: Won't delete all
				twitter_account.delete()

		m256.output_template(self, 'templates/account_deleted.tmpl')

def main():
    application = webapp.WSGIApplication([('/', MainHandler),
										 ('/scoreboard', ScoreboardHandler),
										 ('/profile', ProfileHandler),
										 ('/foursquare_authorization', FoursquareAuthorizationHandler),
										 ('/foursquare_callback', FoursquareCallbackHandler),
										 ('/foursquare_account_delete', FoursquareAccountDeleteHandler),
										 ('/twitter_authorization', TwitterAuthorizationHandler),
										 ('/twitter_callback', TwitterCallbackHandler),
										 ('/twitter_account_delete', TwitterAccountDeleteHandler),
										 ('/data/(.*)', DataHandler),
										 ('/t/(.*)', LookupHandler),
										 ('/f/(.*)', LookupHandler)],
                                         debug=True)
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()
