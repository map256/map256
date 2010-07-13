from m256_cfg import *
from models import *
import os
import sys

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

foursquare_request_token_url = 'http://foursquare.com/oauth/request_token'
foursquare_access_token_url = 'http://foursquare.com/oauth/access_token'
foursquare_authorize_url = 'http://foursquare.com/oauth/authorize'
foursquare_userdetail_url = 'http://api.foursquare.com/v1/user.json'

twitter_request_token_url = 'https://api.twitter.com/oauth/request_token'
twitter_authorize_url = 'https://api.twitter.com/oauth/authorize'


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
	consumer = oauth.Consumer(consumer_key, consumer_secret)
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
	app.response.out.write(template.render(path, {}))
	notify_admin('ERROR: '+admin_description)

def output_maintenance(app):
	app.error(500)
	path = os.path.join(os.path.dirname(__file__), 'templates/maintenance.tmpl')
	app.response.out.write(template.render(path, {}))

def rate_limit_check():
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
