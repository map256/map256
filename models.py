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

from google.appengine.ext import db
from google.appengine.ext.db import polymodel

class Account(db.Model):
	google_user = db.UserProperty()
	created = db.DateTimeProperty(auto_now_add=True)

class OauthRequest(db.Model):
	request_key = db.StringProperty()
	request_secret = db.StringProperty()
	created = db.DateTimeProperty(auto_now_add=True)
	
class TrackedUser(db.Model):
	access_key = db.StringProperty()
	access_secret = db.StringProperty()
	twitter_username = db.StringProperty()
	foursquare_id = db.IntegerProperty()
	created = db.DateTimeProperty(auto_now_add=True)
	foursquare_disabled = db.BooleanProperty(default=False)
	account = db.ReferenceProperty(Account)

class TrackedUserCheckin(db.Model):
	foursquare_id = db.IntegerProperty()
	location = db.GeoPtProperty()
	occured = db.DateTimeProperty()
	checkin_id = db.IntegerProperty()
	created = db.DateTimeProperty(auto_now_add=True)
	distance_traveled = db.FloatProperty() #stored in kilometers
	velocity = db.FloatProperty() #stored in km/s
	previous_checkin = db.SelfReferenceProperty()

class GeneratedStatistic(db.Model):
	created = db.DateTimeProperty(auto_now_add=True)
	description = db.StringProperty()
	contents = db.TextProperty() #JSON encoded values

class FoursquareAccount(db.Model):
	access_key = db.StringProperty()
	access_secret = db.StringProperty()
	twitter_username = db.StringProperty()
	foursquare_id = db.StringProperty()
	created = db.DateTimeProperty(auto_now_add=True)
	foursquare_disabled = db.BooleanProperty(default=False)
	account = db.ReferenceProperty(Account)

class Checkin(polymodel.PolyModel):
	created = db.DateTimeProperty(auto_now_add=True)
	occurred = db.DateTimeProperty()
	location = db.GeoPtProperty()
	description = db.StringProperty()
	distance_traveled = db.FloatProperty() #stored in kilometers
	velocity = db.FloatProperty() #stored in km/s
	previous_checkin = db.SelfReferenceProperty()
	account_owner = db.ReferenceProperty(Account)

class FoursquareCheckin(Checkin):
	owner = db.ReferenceProperty(FoursquareAccount)
	checkin_id = db.StringProperty()
	foursquare_id = db.StringProperty()

class TwitterAccount(db.Model):
	access_key = db.StringProperty()
	access_secret = db.StringProperty()
	screen_name = db.StringProperty()
	twitter_id = db.StringProperty()
	created = db.DateTimeProperty(auto_now_add=True)
	disabled = db.BooleanProperty(default=False)
	account = db.ReferenceProperty(Account)

class TwitterCheckin(Checkin):
	owner = db.ReferenceProperty(TwitterAccount)
	tweet_id = db.StringProperty()
