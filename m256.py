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


def foursquare_consumer_request(url, method):
	consumer = oauth.Consumer(consumer_key, consumer_secret)
	client = oauth.Client(consumer)
	headers = {'User-Agent': 'map256.com:20100617'}
	resp, content = client.request(url, method, headers=headers)

	if resp.status != 200:
		raise Exception('Invalid response %s.' % resp['status'])

	return content

def foursquare_token_request(url, method, key, secret):
	consumer = oauth.Consumer(consumer_key, consumer_secret)
	token = oauth.Token(key, secret)
	client = oauth.Client(consumer, token)
	headers = {'User-Agent': 'map256.com:20100617'}
	resp, content = client.request(url, method, headers=headers)

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
		raise Exception('User has not been created!')

	return account.get()

def notify_admin(body):
	mail.send_mail(sender='Map256 <service@map256.com>',
	               to='Eric Sigler <esigler@gmail.com>',
	               subject='Map256 Admin Notification',
	               body=body)
