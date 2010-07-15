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
from google.appengine.api import urlfetch
from google.appengine.api.urlfetch import DownloadError

from django.utils import simplejson

import m256

from m256_cfg import *
from models import *

class FrontHandler(webapp.RequestHandler):
    def get(self):
		frontpage_userlist = memcache.get('frontpage_userlist')

		if frontpage_userlist is None:

			q1 = FoursquareAccount.all()
			q1.filter('foursquare_disabled =', False)

			fsq_accounts = {}

			for fsq_account in q1:
				q2 = FoursquareCheckin.all()
				q2.filter('owner = ', fsq_account)
				q2.order('-occurred')
				r2 = q2.fetch(10)
				tmpa = []

				for res2 in r2:
					tmpa.append(str(res2.location))

				fsq_accounts[str(fsq_account.foursquare_id)] = tmpa

			frontpage_userlist = simplejson.dumps(fsq_accounts)
			memcache.add('frontpage_userlist', frontpage_userlist, 300)

		m256.output_template(self, 'templates/front.tmpl', {'frontpage_userlist': frontpage_userlist})

#FIXME: To sanitize
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

#FIXME: To sanitize
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

#FIXME: To sanitize
class DataHandler(webapp.RequestHandler):
	def get(self, key=None):
		data = memcache.get('checkindata_'+key)
		self.response.headers.add_header('Content-Type', 'application/json')

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

				if checkin.owner.hide_last_values:
					td = datetime.timedelta(days=1)

					if (datetime.datetime.now() - checkin.occurred) < td:
						continue

				info['location'] = str(checkin.location)
				info['occurred'] = str(checkin.occurred)
				#FIXME: So, turns out some browsers doing JSON decoding dont parse Unicode properly.  Dropping chars for now, need to find better libs later.
				info['description'] = checkin.description.encode('ascii', 'replace')
				#FIXME: At some point should pretty print this, and set it to a saner timezone
				info['occurred'] = str(checkin.occurred)
				data.append(info)

			data.sort(cmp=lambda x,y: cmp(datetime.datetime.strptime(x['occurred'], '%Y-%m-%d %H:%M:%S'),
			                              datetime.datetime.strptime(y['occurred'], '%Y-%m-%d %H:%M:%S')), reverse=True)

			encoded = simplejson.dumps(data)
			memcache.add('checkindata_'+key, encoded, 60)
			self.response.out.write(encoded)
		else:
			self.response.out.write(data)

class FoursquareAuthorizationHandler(webapp.RequestHandler):
	def get(self):

		try:
			content = m256.foursquare_consumer_request(m256.foursquare_request_token_url, 'GET')
		except urlfetch.DownloadError:
			m256.output_error(self, 'DownloadError requesting %s' % m256.foursquare_request_token_url)
			return

		request_token = dict(cgi.parse_qsl(content))

		if 'oauth_token' not in request_token:
			m256.output_error(self, 'Foursquare request token response was invalid')
			return

		if 'oauth_token_secret' not in request_token:
			m256.output_error(self, 'Foursquare request token response was invalid')
			return

		req = OauthRequest()
		req.request_key = request_token['oauth_token']
		req.request_secret = request_token['oauth_token_secret']

		try:
			req.put()
		except CapabilityDisabledError:
			m256.output_maintenance(self)
			return

		url = m256.foursquare_authorize_url+'?oauth_token='+req.request_key
		m256.output_template(self, 'templates/authorize.tmpl', {'url': url, 'service_name': 'Foursquare'})

class FoursquareCallbackHandler(webapp.RequestHandler):
	def get(self):
		arg = self.request.get('oauth_token')
		q1 = OauthRequest.all()
		q1.filter('request_key = ', arg)

		if q1.count() < 1:
			#FIXME: Should be self.redirect('/foursquare_authorization')
			raise Exception('Invalid request (key does not exist)')

		req = q1.get()

		try:
			content = m256.foursquare_token_request(m256.foursquare_access_token_url, 'POST', req.request_key, req.request_secret)
		except urlfetch.DownloadError:
			m256.output_error(self, 'DownloadError requesting %s' % m256.foursquare_access_token_url)
			return

		access_token = dict(cgi.parse_qsl(content))

		if 'oauth_token' not in access_token:
			m256.output_error(self, 'Foursquare access token response was invalid')
			return

		if 'oauth_token' not in access_token:
			m256.output_error(self, 'Foursquare access token response was invalid')
			return

		try:
			content = m256.foursquare_token_request(m256.foursquare_userdetail_url, 'GET', access_token['oauth_token'], access_token['oauth_token_secret'])
		except urlfetch.DownloadError:
			m256.output_error(self, 'DownloadError requesting %s' % m256.foursquare_userdetail_url)
			return

		userinfo = simplejson.loads(content)

		if 'user' not in userinfo:
			m256.output_error(self, 'Foursquare user detail response was invalid')

		if 'id' not in userinfo['user']:
			m256.output_error(self, 'Foursquare user detail response was invalid')

		q2 = FoursquareAccount.all()
		q2.filter('foursquare_id = ', str(userinfo['user']['id']))

		if q2.count() > 0:
			self.redirect('/profile')
			return

		new_account = FoursquareAccount()
		new_account.access_key = access_token['oauth_token']
		new_account.access_secret = access_token['oauth_token_secret']
		new_account.foursquare_id = str(userinfo['user']['id'])
		new_account.account = m256.get_user_model()

		if 'twitter' in userinfo['user']:
			new_account.twitter_username = userinfo['user']['twitter']

		try:
			new_account.put()
		except CapabilityDisabledError:
			m256.output_maintenance(self)
			return

		taskqueue.add(url='/worker_foursquare_history', params={'fsq_id': new_account.foursquare_id}, method='GET')

		url = '/f/'+new_account.foursquare_id
		m256.output_template(self, 'templates/callback.tmpl', {'map_url': url})
		m256.notify_admin("New Foursquare account added: http://www.map256.com/f/%s" % new_account.foursquare_id)

class FoursquareAccountDeleteHandler(webapp.RequestHandler):
	def get(self):
		fsq_id = str(self.request.get('fsq_id'))
		u_acc = m256.get_user_model()

		q1 = FoursquareAccount.all()
		q1.filter('foursquare_id =', fsq_id)
		q1.filter('account =', u_acc)

		if q1.count() != 0:
			r1 = q1.fetch(50)

			for fsq_account in r1:
				q2 = FoursquareCheckin.all(keys_only=True)
				q2.filter('owner =', fsq_account)

				try:
					db.delete(q2.fetch(1000)) #FIXME: Won't delete all
					fsq_account.delete()
				except CapabilityDisabledError:
					m256.output_maintenance(self)
					return

			m256.output_template(self, 'templates/account_deleted.tmpl')
		else:
			self.redirect('/profile')

class TwitterAuthorizationHandler(webapp.RequestHandler):
	def get(self):
		try:
			result = m256.twitter_consumer_request(m256.twitter_request_token_url, 'POST')
		except urlfetch.DownloadError:
			m256.output_error(self, 'DownloadError requesting %s' % m256.twitter_request_token_url)
			return

		request_token = dict(cgi.parse_qsl(result))

		if 'oauth_token' not in request_token:
			m256.output_error(self, 'Twitter request token response was invalid')
			return

		if 'oauth_token_secret' not in request_token:
			m256.output_error(self, 'Twitter request token response was invalid')
			return

		req = OauthRequest()
		req.request_key = request_token['oauth_token']
		req.request_secret = request_token['oauth_token_secret']

		try:
			req.put()
		except CapabilityDisabledError:
			m256.output_maintenance(self)
			return

		url = m256.twitter_authorize_url+'?oauth_token='+req.request_key
		m256.output_template(self, 'templates/authorize.tmpl', {'url': url, 'service_name': 'Twitter'})

class TwitterCallbackHandler(webapp.RequestHandler):
	def get(self):
		arg = self.request.get('oauth_token')
		q1 = OauthRequest.all()
		q1.filter('request_key = ', arg)

		if q1.count() < 1:
			#FIXME: Should be self.redirect('/foursquare_authorization')
			raise Exception('Invalid request (key does not exist)')

		req = q1.get()

		try:
			content = m256.twitter_token_request(m256.twitter_access_token_url, 'POST', req.request_key, req.request_secret)
		except urlfetch.DownloadError:
			m256.output_error(self, 'DownloadError requesting %s' % m256.twitter_access_token_url)
			return

		access_token = dict(cgi.parse_qsl(content))

		if 'oauth_token' not in access_token:
			m256.output_error(self, 'Twitter access token response was invalid')
			return

		if 'oauth_token' not in access_token:
			m256.output_error(self, 'Twitter access token response was invalid')
			return

		try:
			content = m256.twitter_token_request(m256.twitter_user_timeline_url, 'GET', access_token['oauth_token'], access_token['oauth_token_secret'])
		except urlfetch.DownloadError:
			m256.output_error(self, 'DownloadError requesting %s' % m256.twitter_user_timeline_url)
			return

		userinfo = simplejson.loads(content)

		if len(userinfo) == 0:
			m256.output_error(self, 'Twitter user timeline response was invalid')
			return

		if 'user' not in userinfo[0]:
			m256.output_error(self, 'Twitter user timeline response was invalid')
			return

		if 'id' not in userinfo[0]['user']:
			m256.output_error(self, 'Twitter user timeline response was invalid')
			return

		if 'screen_name' not in userinfo[0]['user']:
			m256.output_error(self, 'Twitter user timeline response was invalid')
			return

		q2 = TwitterAccount.all()
		q2.filter('twitter_id =', str(userinfo[0]['user']['id']))

		if q2.count() > 0:
			self.redirect('/profile')
			return

		new_account = TwitterAccount()
		new_account.access_key = access_token['oauth_token']
		new_account.access_secret = access_token['oauth_token_secret']
		new_account.twitter_id = str(userinfo[0]['user']['id'])
		new_account.screen_name = str(userinfo[0]['user']['screen_name'])
		new_account.account = m256.get_user_model()

		try:
			new_account.put()
		except CapabilityDisabledError:
			m256.output_maintenance(self)
			return

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
		else:
			self.redirect('/profile')

def main():
    application = webapp.WSGIApplication([('/', FrontHandler),
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
