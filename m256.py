from m256_cfg import *
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

def output_template(app, template_path, variables):
	app.response.headers.add_header('Content-Type', 'text/html; charset=\"utf-8\"')

	user = users.get_current_user()
	if user is None:
		variables['logged_in'] = False
	else:
		variables['logged_in'] = True
		variables['signout_url'] = users.create_logout_url('/')

	path = os.path.join(os.path.dirname(__file__), template_path)
	app.response.out.write(template.render(path, variables))