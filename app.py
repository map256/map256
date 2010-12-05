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

import cgi
import os
import sys
import datetime
import logging
import md5
import urllib

from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
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
        m256.output_template(self, 'templates/front.tmpl', {'page_title': 'Main'})

class FrontPageDataHandler(webapp.RequestHandler):
    def get(self):
        frontpage_userlist = memcache.get('frontpage_userlist')
        self.response.headers.add_header('Content-Type', 'application/json')

        if frontpage_userlist is None:

            data = []
            q1 = Checkin.all()
            q1.order('-occurred')
            r1 = q1.fetch(100)

            for res1 in r1:
                for item in data:
                    if item['account_key'] == str(res1.account_owner.key()):
                        break
                else:
                    if isinstance(res1.owner, FoursquareAccount):
                        if res1.owner.twitter_username:
                            data.append({'account_key': str(res1.account_owner.key()),
                                         'url': '/t/'+res1.owner.twitter_username,
                                         'name': res1.owner.twitter_username})
                        else:
                            data.append({'account_key': str(res1.account_owner.key()),
                                         'url': '/f/'+res1.owner.foursquare_id,
                                         'name': res1.owner.foursquare_id})

                    if isinstance(res1.owner, TwitterAccount):
                        data.append({'account_key': str(res1.account_owner.key()),
                                     'url': '/t/'+res1.owner.screen_name,
                                     'name': res1.owner.screen_name})

                    if isinstance(res1.owner, FlickrAccount):
                        pass

            frontpage_userlist = simplejson.dumps(data)
            memcache.add('frontpage_userlist', frontpage_userlist, 30)

        self.response.out.write(frontpage_userlist)

#FIXME: To sanitize
class KeyLookupHandler(webapp.RequestHandler):
    def get(self, handle=None):
        if handle is None:
            return

        account_key = memcache.get('lookup_'+handle)
        self.response.headers.add_header('Content-Type', 'application/json')

        if account_key is None:

            q1 = FoursquareAccount.all()
            q1.filter('twitter_username =', str(handle))

            if q1.count() == 1:
                f_account = q1.get()
                account_key = simplejson.dumps({'account_key': str(f_account.account.key())})
                memcache.add('lookup_'+handle, account_key, 5)
                self.response.out.write(account_key)
                return

            q2 = FoursquareAccount.all()
            q2.filter('foursquare_id =', str(handle))

            if q2.count() == 1:
                f_account = q2.get()
                account_key = simplejson.dumps({'account_key': str(f_account.account.key())})
                memcache.add('lookup_'+handle, account_key, 5)
                self.response.out.write(account_key)
                return

            q3 = TwitterAccount.all()
            q3.filter('screen_name =', str(handle))

            if q3.count() == 1:
                t_account = q3.get()
                account_key = simplejson.dumps({'account_key': str(t_account.account.key())})
                memcache.add('lookup_'+handle, account_key, 5)
                self.response.out.write(account_key)
                return

            q4 = TwitterAccount.all()
            q4.filter('twitter_id =', str(handle))

            if q4.count() == 1:
                t_account = q4.get()
                account_key = simplejson.dumps({'account_key': str(t_account.account.key())})
                memcache.add('lookup_'+handle, account_key, 5)
                self.response.out.write(account_key)
                return

            q5 = FlickrAccount.all()
            q5.filter('nsid =', urllib.unquote(handle))

            if q5.count() == 1:
                fl_account = q5.get()
                account_key = simplejson.dumps({'account_key': str(fl_account.account.key())})
                memcache.add('lookup_'+handle, account_key, 5)
                self.response.out.write(account_key)
                return

        self.response.out.write(account_key)

class LookupHandler(webapp.RequestHandler):
    def get(self, handle=None):
        m256.output_template(self, 'templates/map.tmpl', {})

class ProfileHandler(webapp.RequestHandler):
    def get(self):
        account = m256.get_user_model()
        template_values = {'page_title': 'Profile', 'page_header': 'Profile'}

        q1 = FoursquareAccount.all()
        q1.filter('account =', account)
        template_values['foursquare_accounts'] = q1.fetch(25)

        q2 = TwitterAccount.all()
        q2.filter('account =', account)
        template_values['twitter_accounts'] = q2.fetch(25)

        q3 = FlickrAccount.all()
        q3.filter('account =', account)
        template_values['flickr_accounts'] = q3.fetch(25)

        template_values['nickname'] = account.google_user.nickname()

        m256.output_template(self, 'templates/profile.tmpl', template_values)

class DataHandler(webapp.RequestHandler):
    def get(self, key=None):
        data = memcache.get('checkindata_'+key)
        self.response.headers.add_header('Content-Type', 'application/json')

        #FIXME: Yes, basically this means that cursord requests arent being cached.  Should fix.
        cursor = self.request.get('cursor')
        if cursor is not None:
            data = None

        if data is None:
            data = []

            try:
                k1 = db.Key(key)
            except:
                return

            user = Account.get(k1)

            if user is None:
                return

            q1 = Checkin.all()
            #FIXME: Need to check to see if account is disabled
            q1.filter('account_owner =', user)
            q1.order('-occurred')

            if cursor is not None:
                q1.with_cursor(cursor)

            if q1.count() == 0:
                return

            r1 = q1.fetch(50)

            for checkin in r1:
                info = {}

                if checkin.owner.hide_last_values:
                    td = datetime.timedelta(days=1)

                    if (datetime.datetime.now() - checkin.occurred) < td:
                        continue

                info['location'] = str(checkin.location)
                #FIXME: So, turns out some browsers doing JSON decoding dont parse Unicode properly.  Dropping chars for now, need to find better libs later.
                info['description'] = checkin.description.encode('ascii', 'replace')
                #FIXME: At some point should pretty print this, and set it to a saner timezone
                info['occurred'] = str(checkin.occurred)
                data.append(info)

            data.sort(cmp=lambda x,y: cmp(datetime.datetime.strptime(x['occurred'], '%Y-%m-%d %H:%M:%S'),
                                          datetime.datetime.strptime(y['occurred'], '%Y-%m-%d %H:%M:%S')), reverse=True)

            if len(r1) == 50:
                lastinfo = {}
                lastinfo['cursor'] = q1.cursor()
                lastinfo['key'] = key
                data.append(lastinfo)

            encoded = simplejson.dumps(data)
            memcache.add('checkindata_'+key, encoded, 150)
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
        except Exception, e:
            m256.output_error(self, 'Exception requesting URL (url: %s, msg: %s)' % (m256.foursquare_request_token_url, e))
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
        m256.output_template(self, 'templates/authorize.tmpl', {'url': url, 'service_name': 'Foursquare', 'page_title': 'Authorize Access', 'page_header': 'Authorize Access'})

class FoursquareCallbackHandler(webapp.RequestHandler):
    def get(self):
        arg = self.request.get('oauth_token')
        q1 = OauthRequest.all()
        q1.filter('request_key = ', arg)

        if q1.count() < 1:
            self.redirect('/foursquare_authorization')

        req = q1.get()

        try:
            content = m256.foursquare_token_request(m256.foursquare_access_token_url, 'POST', req.request_key, req.request_secret)
        except urlfetch.DownloadError:
            m256.output_error(self, 'DownloadError requesting %s' % m256.foursquare_access_token_url)
            return
        except Exception, e:
            m256.output_error(self, 'Exception requesting URL (url: %s, msg: %s)' % (m256.foursquare_access_token_url, e))
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
        except Exception, e:
            m256.output_error(self, 'Exception requesting URL (url: %s, msg: %s)' % (m256.foursquare_userdetail_url, e))
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
        m256.output_template(self, 'templates/callback.tmpl', {'map_url': url, 'page_title': 'Authorization Completed', 'page_header': 'Authorization Completed'})
        m256.notify_admin("New Foursquare account added: http://www.map256.com/f/%s" % new_account.foursquare_id)

class AccountHideHandler(webapp.RequestHandler):
    def get(self):
        account_key = self.request.get('account_key')

        if account_key is None:
            self.redirect('/profile')

        try:
            k1 = db.Key(account_key)
        except:
            self.redirect('/profile')

        account = ServiceAccount.get(k1)

        if account is None:
            self.redirect('/profile')

        u_acc = m256.get_user_model()

        if account.account != u_acc:
            self.redirect('/profile')

        if account.hide_last_values:
            account.hide_last_values = False
        else:
            #FIXME: Should try to invalidate all memcache entries associated with this
            memcache.delete('checkindata_'+str(account.account.key))
            account.hide_last_values = True

        account.put()
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
        m256.output_template(self, 'templates/authorize.tmpl', {'url': url, 'service_name': 'Twitter', 'page_title': 'Authorize Account', 'page_header': 'Authorize Account'})

class TwitterCallbackHandler(webapp.RequestHandler):
    def get(self):
        arg = self.request.get('oauth_token')
        q1 = OauthRequest.all()
        q1.filter('request_key = ', arg)

        if q1.count() < 1:
            self.redirect('/twitter_authorization')

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
        m256.output_template(self, 'templates/callback.tmpl', {'map_url': url, 'page_title': 'Authorization Completed', 'page_header': 'Authorization Completed'})
        m256.notify_admin("New Twitter account added: http://www.map256.com/t/%s" % new_account.screen_name)

class FaqHandler(webapp.RequestHandler):
    def get(self):
        m256.output_template(self, 'templates/faq.tmpl', {'page_title': 'FAQ', 'page_header': 'FAQ'})

class FlickrAuthorizationHandler(webapp.RequestHandler):
    def get(self):
        url = m256.flickr_login_url+'?api_key='+flickr_api_key+'&perms=read&api_sig='+flickr_api_sig
        m256.output_template(self, 'templates/authorize.tmpl', {'url': url, 'service_name': 'Flickr', 'page_title': 'Authorize Account', 'page_header': 'Authorize Account'})

class FlickrCallbackHandler(webapp.RequestHandler):
    def get(self):
        frob = self.request.get('frob')

        if frob is None:
            self.redirect('/flickr_authorization')

        m = md5.new()
        m.update(flickr_api_secret+'api_key'+flickr_api_key+'formatjsonfrob'+frob+'methodflickr.auth.getToken')
        url = m256.flickr_base_api_url+'?method=flickr.auth.getToken&api_key='+flickr_api_key+'&format=json&frob='+frob+'&api_sig='+m.hexdigest()

        try:
            result = urlfetch.fetch(url)
        except urlfetch.DownloadError:
            m256.output_error(self, 'DownloadError requesting %s' % url)
            return

        if result.status_code != 200:
            m256.output_error(self, 'Flickr user token request returned error (url: %s, content: %s)' % (url, content))
            return

        #FIXME: Horrible no good very bad way to get rid of JSON header.  Should regex, but Python regexes are ug-ly.
        content = result.content
        str1 = content.replace('jsonFlickrApi(', '')
        str2 = str1.rstrip(')')
        usertoken = simplejson.loads(str2)

        if 'auth' not in usertoken:
            m256.output_error(self, 'No auth in Flickr user token response (url: %s, content: %s)' % (url, content))
            return

        if 'token' not in usertoken['auth']:
            m256.output_error(self, 'No token in Flickr user token response (url: %s, content: %s)' % (url, content))
            return

        if '_content' not in usertoken['auth']['token']:
            m256.output_error(self, 'No _content in Flickr user token response (url: %s, content: %s)' % (url, content))
            return

        if 'user' not in usertoken['auth']:
            m256.output_error(self, 'No user in Flickr user token response (url: %s, content: %s)' % (url, content))
            return

        if 'nsid' not in usertoken['auth']['user']:
            m256.output_error(self, 'No nsid in Flickr user token response (url: %s, content: %s)' % (url, content))
            return

        q1 = FlickrAccount.all()
        q1.filter('nsid =', usertoken['auth']['user']['nsid'])

        if q1.count() > 0:
            self.redirect('/profile')
            return

        new_account = FlickrAccount()
        new_account.auth_token = usertoken['auth']['token']['_content']

        if 'username' in usertoken['auth']['user']:
            new_account.username = usertoken['auth']['user']['username']

        new_account.nsid = usertoken['auth']['user']['nsid']
        new_account.account = m256.get_user_model()

        try:
            new_account.put()
        except CapabilityDisabledError:
            m256.output_maintenance(self)
            return

        taskqueue.add(url='/worker_flickr_history', params={'flickr_id': new_account.nsid})

        url = '/fl/'+new_account.nsid
        m256.output_template(self, 'templates/callback.tmpl', {'map_url': url, 'page_title': 'Authorization Completed', 'page_header': 'Authorization Completed'})
        m256.notify_admin("New Flickr account added: http://www.map256.com%s" % url)

class AccountDeleteHandler(webapp.RequestHandler):
    def get(self):
        account_key = self.request.get('account_key')

        if account_key is None:
            self.redirect('/profile')

        try:
            k1 = db.Key(account_key)
        except:
            self.redirect('/profile')

        account = ServiceAccount.get(k1)

        if account is None:
            self.redirect('/profile')

        u_acc = m256.get_user_model()

        if account.account != u_acc:
            self.redirect('/profile')

        taskqueue.add(url='/worker_account_delete', params={'account_key': account.key()})
        m256.output_template(self, 'templates/account_deleted.tmpl', {'page_title': 'Account Deleted', 'page_header': 'Account Deleted'})

def main():

    routes = [
        ('/', FrontHandler),
        ('/faq', FaqHandler),
        ('/profile', ProfileHandler),
        ('/front_page_data', FrontPageDataHandler),
        ('/foursquare_authorization', FoursquareAuthorizationHandler),
        ('/foursquare_callback', FoursquareCallbackHandler),
        ('/twitter_authorization', TwitterAuthorizationHandler),
        ('/twitter_callback', TwitterCallbackHandler),
        ('/flickr_authorization', FlickrAuthorizationHandler),
        ('/flickr_callback', FlickrCallbackHandler),
        ('/profile/account_delete', AccountDeleteHandler),
        ('/profile/account_hide', AccountHideHandler),
        ('/data/(.*)', DataHandler),
        ('/t/(.*)', LookupHandler),
        ('/fl/(.*)', LookupHandler),
        ('/f/(.*)', LookupHandler),
        ('/kl/(.*)', KeyLookupHandler)
    ]

    application = webapp.WSGIApplication(routes, debug=True)
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()
