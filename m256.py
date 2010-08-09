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

import os
import sys
import logging

httplib2_path = 'lib/httplib2.zip'
sys.path.insert(0, httplib2_path)
import httplib2

oauth_path = 'lib/oauth2.zip'
sys.path.insert(0, oauth_path)
import oauth2 as oauth

from google.appengine.ext.webapp import template
from google.appengine.api import users
from google.appengine.api import mail
from google.appengine.api import memcache

from m256_cfg import *
from models import *

foursquare_request_token_url = 'http://foursquare.com/oauth/request_token'
foursquare_access_token_url = 'http://foursquare.com/oauth/access_token'
foursquare_authorize_url = 'http://foursquare.com/oauth/authorize'
foursquare_userdetail_url = 'http://api.foursquare.com/v1/user.json'
foursquare_history_url = 'http://api.foursquare.com/v1/history.json'

twitter_request_token_url = 'https://api.twitter.com/oauth/request_token'
twitter_access_token_url = 'https://api.twitter.com/oauth/access_token'
twitter_authorize_url = 'https://api.twitter.com/oauth/authorize'
twitter_user_timeline_url = 'http://api.twitter.com/1/statuses/user_timeline.json'

flickr_login_url = 'http://www.flickr.com/services/auth/'
flickr_base_api_url = 'https://secure.flickr.com/services/rest/'

def oauth_consumer_request(url, method, consumer_key, consumer_secret):
    consumer = oauth.Consumer(consumer_key, consumer_secret)
    client = oauth.Client(consumer)
    headers = {'User-Agent': 'map256.com:20100617'}
    return client.request(url, method, headers=headers)

def oauth_token_request(url, method, consumer_key, consumer_secret, token_key, token_secret):
    consumer = oauth.Consumer(consumer_key, consumer_secret)
    token = oauth.Token(token_key, token_secret)
    client = oauth.Client(consumer, token)
    headers = {'User-Agent': 'map256.com:20100617'}
    return client.request(url, method, headers=headers)

def foursquare_consumer_request(url, method):
    resp, content = oauth_consumer_request(url, method, foursquare_consumer_key, foursquare_consumer_secret)

    if resp.status != 200:
        raise Exception('Invalid response %s.' % resp['status'])

    return content

def foursquare_token_request(url, method, key, secret):
    resp, content = oauth_token_request(url, method, foursquare_consumer_key, foursquare_consumer_secret, key, secret)

    if resp.status != 200:
        raise Exception('Invalid response %s.' % resp['status'])
    
    return content

def output_template(app, template_path, variables={}):
    app.response.headers.add_header('Content-Type', 'text/html; charset=\"utf-8\"')

    user = users.get_current_user()
    if user is None:
        variables['logged_in'] = False
    else:
        variables['logged_in'] = True
        variables['signout_url'] = users.create_logout_url('/')

    path = os.path.join(os.path.dirname(__file__), template_path)
    app.response.out.write(template.render(path, variables))

def twitter_consumer_request(url, method):
    consumer = oauth.Consumer(twitter_consumer_key, twitter_consumer_secret)
    client = oauth.Client(consumer)
    headers = {'User-Agent': 'map256.com:20100617'}
    resp, content = client.request(url, method, headers=headers)

    if resp.status != 200:
        raise Exception('Invalid response %s.' % resp['status'])

    return content

def twitter_token_request(url, method, key, secret):
    consumer = oauth.Consumer(twitter_consumer_key, twitter_consumer_secret)
    token = oauth.Token(key, secret)
    client = oauth.Client(consumer, token)
    headers = {'User-Agent': 'map256.com:20100617'}
    resp, content = client.request(url, method, headers=headers)

    if resp.status != 200:
        raise Exception('Invalid response %s.' % resp['status'])

    return content

def calculate_distance(lat1, lon1, lat2, lon2):
    #Using Spherical Law of Cosines to determine distance

    delta = lon2 - lon1
    a = math.radians(lat1)
    b = math.radians(lat2)
    c = math.radians(delta)
    x = math.sin(a) * math.sin(b) + math.cos(a) * math.cos(b) * math.cos(c)
    distance = math.acos(x)
    distance = math.degrees(distance)
    distance = distance * 60
    distance = distance * 1.852 #to kilometer

    return distance

def get_user_model():
    user = users.get_current_user()

    if user is None:
        raise Exception('User is not logged in!')

    account = Account.all()
    account.filter('google_user =', user)

    if account.count() == 0:
        account = Account()
        account.google_user = user
        #FIXME: Unchecked put
        account.put()
        notify_admin('A new map256.com user has been created: %s' % user.nickname())
    else:
        account = account.get()

    return account

def notify_admin(body):
    mail.send_mail(sender='Map256 <service@map256.com>',
                   to='Eric Sigler <esigler@gmail.com>',
                   subject='Map256 Admin Notification',
                   body=body)

def output_error(app, admin_description):
    app.error(500)
    path = os.path.join(os.path.dirname(__file__), 'templates/error.tmpl')
    app.response.out.write(template.render(path, {'page_title': 'Error', 'page_header': 'Error'}))
    notify_admin('ERROR: '+admin_description)
    logging.error(admin_description)

def output_maintenance(app):
    app.error(500)
    path = os.path.join(os.path.dirname(__file__), 'templates/maintenance.tmpl')
    app.response.out.write(template.render(path, {'page_title': 'Google Maintenance', 'page_header': 'Google Maintenance'}))

def downloaderror_check():
    recent = memcache.get('urlfetch_count')

    if recent > 5:
        return True
    else:
        return False

def downloaderror_update():
    recent = memcache.get('urlfetch_count')

    if recent is None:
        memcache.add('urlfetch_count', 1, 150)
    else:
        recent = recent + 1
        memcache.replace('urlfetch_count', recent, 150)

    if recent > 5:
        notify_admin('High error rate on URL fetches')

#def rate_limit_check(app):
    #req_ip = memcache.get('iprate_'+app.request.remote_addr)

    #if req_ip is None:
        #req_ip = 1
        #memcache.add('iprate_'+app.request.remote_addr, req_ip, 120)
    #else:
        #req_ip = req_ip+1
        #memcache.replace('iprate_'+app.request.remote_addr, req_ip, 120)

    #if req_ip > 10:
        #self.response.out.write('Rate limiter kicked in, /authorize blocked for 120 seconds')
        #return

        #if resp.status == 403:
            #recent = memcache.get('fsq_403_'+fsq_id)

            #if recent is None:
                #memcache.add('fsq_403_'+fsq_id, 1, 3600)
            #else:
                #memcache.replace('fsq_403_'+fsq_id, recent+1, 3600)

            #if recent > 10:
                #user.foursquare_disabled = True
                #user.put()
                #mail.send_mail(sender='Map256 <service@map256.com', to='Eric Sigler <esigler@gmail.com>', subject='Map256 Foursquare 403 error', body='High 403 rate on %s user' % fsq_id )

            #return
