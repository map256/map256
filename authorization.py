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

from google.appengine.ext.webapp import template
from google.appengine.api.labs import taskqueue
from google.appengine.api import memcache
from google.appengine.api import users

httplib2_path = 'lib/httplib2.zip'
sys.path.insert(0, httplib2_path)
import httplib2

oauth_path = 'lib/oauth2.zip'
sys.path.insert(0, oauth_path)
import oauth2 as oauth

from django.utils import simplejson

from m256_cfg import *
from models import *

from google.appengine.runtime.apiproxy_errors import CapabilityDisabledError
from google.appengine.api import mail

class AuthorizeHandler(webapp.RequestHandler):
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

		consumer = oauth.Consumer(consumer_key, consumer_secret)
		client = oauth.Client(consumer)
		headers = {'User-Agent': 'map256.com:20100617'}
		resp, content = client.request(request_token_url, 'GET', headers=headers)

		if resp.status != 200:
		    raise Exception('Invalid response %s.' % resp['status'])

		request_token = dict(cgi.parse_qsl(content))

		req = OauthRequest()
		req.request_key = request_token['oauth_token']
		req.request_secret = request_token['oauth_token_secret']

		try:
			req.put()
		except CapabilityDisabledError:
			self.response.out.write('Hmm, looks like Google\'s currently doing maintenance on their platform, sorry!')
			pass
		else:
			url = authorize_url+'?oauth_token='+request_token['oauth_token']
			path = os.path.join(os.path.dirname(__file__), 'templates/authorize.tmpl')
			self.response.out.write(template.render(path, {'url': url}))

class CallbackHandler(webapp.RequestHandler):
    def get(self):
		consumer = oauth.Consumer(consumer_key, consumer_secret)
		client = oauth.Client(consumer)
		arg = self.request.get('oauth_token')
		q = OauthRequest.all()
		q.filter('request_key = ', arg)

		if q.count() < 1:
			raise Exception('Invalid request (key does not exist)')

		req = q.get()

		token = oauth.Token(req.request_key, req.request_secret)
		client = oauth.Client(consumer, token)
		headers = {'User-Agent': 'map256.com:20100617'}
		resp, content = client.request(access_token_url, 'POST', headers=headers)

		if resp.status != 200:
		    raise Exception('Invalid response %s.' % resp['status'])

		access_token = dict(cgi.parse_qsl(content))

		token = oauth.Token(access_token['oauth_token'], access_token['oauth_token_secret'])
		client = oauth.Client(consumer, token)
		headers = {'User-Agent': 'map256.com:20100617'}
		resp, content = client.request(userdetail_url, 'GET', headers=headers)

		db.delete(req)
		#FIXME: Is there any scenario in which a request key, once approved, should be kept around?

		#FIXME: Saw an odd bug one time where access token was requested, approved, but timed out before response was given
		#Dunno how to handle it just yet, but putting it in here before I forget

		if resp.status != 200:
			raise Exception('Invalid response %s.' % resp['status'])

		userinfo = simplejson.loads(content)

		q = TrackedUser.all()
		q.filter('foursquare_id = ', userinfo['user']['id'])

		if q.count() > 0:
			raise Exception('User is already authorized!')

		tuser = TrackedUser()
		tuser.access_key = access_token['oauth_token']
		tuser.access_secret = access_token['oauth_token_secret']

		if userinfo['user'].has_key('twitter'):
			tuser.twitter_username = userinfo['user']['twitter']

		tuser.foursquare_id = userinfo['user']['id']

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
			url = '/t/'+userinfo['user']['twitter']
			path = os.path.join(os.path.dirname(__file__), 'templates/callback.tmpl')
			self.response.out.write(template.render(path, {'map_url': url}))

		mail.send_mail(sender='Map256 <service@map256.com>',
		              to='Eric Sigler <esigler@gmail.com>',
		              subject='Map256 Foursquare Authorization',
		              body="""
		Hey!  It looks like another person has authorized Map256 to access
		Foursquare data!

		Twitter username: %s
		Foursquare ID: %s

		""" % ( tuser.twitter_username, tuser.foursquare_id ) )

def main():
    application = webapp.WSGIApplication([('/authorize', AuthorizeHandler),
										 ('/callback', CallbackHandler)],
                                         debug=True)
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()
