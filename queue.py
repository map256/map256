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
import urllib
import md5

from google.appengine.api import urlfetch
from google.appengine.api.urlfetch import DownloadError
from google.appengine.api import mail
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from google.appengine.api.labs import taskqueue
from google.appengine.api import memcache
from django.utils import simplejson

httplib2_path = 'lib/httplib2.zip'
sys.path.insert(0, httplib2_path)
import httplib2

oauth_path = 'lib/oauth2.zip'
sys.path.insert(0, oauth_path)
import oauth2 as oauth

from m256_cfg import *
from models import *
import m256


class FoursquareHistoryWorker(webapp.RequestHandler):
    def get(self, fsq_id=None, since=None):
        logging.info('Handling Foursquare history request')
        fsq_id = self.request.get('fsq_id')

        q1 = FoursquareAccount.all()
        q1.filter('foursquare_id = ', str(fsq_id))

        if q1.count() != 1:
            raise Exception('User does not exist')

        fsq_account = q1.get()

        if self.request.get('since'):
            since = self.request.get('since')
            request_url = m256.foursquare_history_url+'?l=50&sinceid='+since
        else:
            request_url = m256.foursquare_history_url+'?l=50&sinceid=1'

        logging.info('Using request URL: %s' % request_url)

        try:
            content = m256.foursquare_token_request(request_url,
                                                    'GET',
                                                    fsq_account.access_key,
                                                    fsq_account.access_secret)
        except urlfetch.DownloadError:
            m256.downloaderror_check()
            return
        except Exception, e:
            errmsg = 'Exception requesting URL (url: %s, msg: %s)' % (request_url, e)
            logging.error(errmsg)
            m256.notify_admin(errmsg)
            return

        history = simplejson.loads(content)

        if 'checkins' not in history:
            m256.notify_admin('Malformed response from Foursquare (%s)' % content)
            return

        checkins = history['checkins']
        checkins.sort(cmp=lambda x,y: cmp(datetime.datetime.strptime(x['created'], '%a, %d %b %y %H:%M:%S +0000'),
                                          datetime.datetime.strptime(y['created'], '%a, %d %b %y %H:%M:%S +0000')))

        for checkin in checkins:
            q2 = FoursquareCheckin.all()
            q2.filter('checkin_id = ', str(checkin['id']))

            if q2.count() == 0:
                if 'created' not in checkin:
                    continue

                if 'venue' not in checkin:
                    continue

                if 'geolat' not in checkin['venue']:
                    continue

                if 'geolong' not in checkin['venue']:
                    continue

                if 'name' not in checkin['venue']:
                    continue

                logging.info('Dont have existing record, going to create new checkin')
                ci = FoursquareCheckin()
                ci.foursquare_id = str(fsq_id)
                ci.owner = fsq_account
                ci.location = str(checkin['venue']['geolat'])+','+str(checkin['venue']['geolong'])

                if 'shout' in checkin:
                    description = checkin['venue']['name']+' \"'+checkin['shout']+'\"'
                else:
                    description = checkin['venue']['name']

                ci.description = description
                ci.checkin_id = str(checkin['id'])
                ci.occurred = datetime.datetime.strptime(checkin['created'], '%a, %d %b %y %H:%M:%S +0000')
                ci.account_owner = fsq_account.account
                ci.put()

        if len(history['checkins']) > 1:
            last = len(history['checkins'])-1
            last_id = history['checkins'][last]['id']
            logging.info('Have more than one checkin, enqueing at last_id: %s' % last_id)
            taskqueue.add(url='/worker_foursquare_history',
                          params={'fsq_id': fsq_account.foursquare_id, 'since': last_id },
                          method='GET')

class FlickrHistoryWorker(webapp.RequestHandler):
    def post(self):
        logging.info('Handling Flickr history request')
        flickr_id = str(self.request.get('flickr_id'))

        q1 = FlickrAccount.all()
        q1.filter('nsid = ', flickr_id)

        if q1.count() != 1:
            raise Exception('User does not exist')

        flickr_account = q1.get()

        m = md5.new()

        if self.request.get('since'):
            date = self.request.get('since')
            dateencoded = urllib.quote(date)
            m.update(flickr_api_secret+'api_key'+flickr_api_key+'auth_token'+flickr_account.auth_token+'extrasdescription,date_taken,url_sq,geoformatjson'+'methodflickr.photos.getWithGeoData'+'min_taken_date'+date+'per_page50privacy_filter1sortdate-taken-asc')
            url = m256.flickr_base_api_url+'?method=flickr.photos.getWithGeoData&api_key='+flickr_api_key+'&format=json&auth_token='+flickr_account.auth_token+'&api_sig='+m.hexdigest()+'&per_page=50&privacy_filter=1&extras=description,date_taken,url_sq,geo&sort=date-taken-asc&min_taken_date='+dateencoded
        else:
            m.update(flickr_api_secret+'api_key'+flickr_api_key+'auth_token'+flickr_account.auth_token+'extrasdescription,date_taken,url_sq,geoformatjson'+'methodflickr.photos.getWithGeoData'+'per_page50privacy_filter1sortdate-taken-asc')
            url = m256.flickr_base_api_url+'?method=flickr.photos.getWithGeoData&api_key='+flickr_api_key+'&format=json&auth_token='+flickr_account.auth_token+'&api_sig='+m.hexdigest()+'&per_page=50&privacy_filter=1&extras=description,date_taken,url_sq,geo&sort=date-taken-asc'

        try:
            result = urlfetch.fetch(url)
        except urlfetch.DownloadError:
            logging.error('Download error on %s' % url)
            m256.downloaderror_check()
            return

        if result.status_code != 200:
            logging.error('Status code on %s was %s' % (url, result.status_code))
            m256.downloaderror_check()
            return

        #FIXME: Horrible no good very bad way to get rid of JSON header.  Should regex, but Python regexes are ug-ly.
        content = result.content
        str1 = content.replace('jsonFlickrApi(', '')
        str2 = str1.rstrip(')')

        userdata = simplejson.loads(str2)

        if 'photos' not in userdata:
            errmsg = 'Photos not in userdata (url: %s, content: %s)' % (url, content)
            logging.error(errmsg)
            m256.notify_admin(errmsg)
            return

        if 'photo' not in userdata['photos']:
            errmsg = 'Photo not in userdata (url: %s, content: %s)' % (url, content)
            logging.error(errmsg)
            m256.notify_admin(errmsg)
            return

        if len(userdata['photos']['photo']) > 0:
            for photo in userdata['photos']['photo']:
                #FIXME: Only using this for count, can probably switch to keys-only
                q2 = FlickrCheckin.all()
                q2.filter('photo_id = ', str(photo['id']))

                if q2.count() != 0:
                    logging.info('Found photo that already existed (%s)' % photo['id'])
                    continue

                if 'latitude' not in photo:
                    errmsg = 'Latitude not in photo (url: %s, content: %s)' % (url, content)
                    logging.error(errmsg)
                    m256.notify_admin(errmsg)
                    continue

                if 'longitude' not in photo:
                    errmsg = 'Longitude not in photo (url: %s, content: %s)' % (url, content)
                    logging.error(errmsg)
                    m256.notify_admin(errmsg)
                    continue

                if 'datetaken' not in photo:
                    errmsg = 'Datetaken not in photo (url: %s, content: %s)' % (url, content)
                    logging.error(errmsg)
                    m256.notify_admin(errmsg)
                    continue

                if 'datetaken' not in photo:
                    errmsg = 'Longitude not in photo (url: %s, content: %s)' % (url, content)
                    logging.error(errmsg)
                    m256.notify_admin(errmsg)
                    continue

                if 'url_sq' not in photo:
                    errmsg = 'Longitude not in photo (url: %s, content: %s)' % (url, content)
                    logging.error(errmsg)
                    m256.notify_admin(errmsg)
                    continue

                ci = FlickrCheckin()
                ci.owner = flickr_account
                ci.occurred = datetime.datetime.strptime(photo['datetaken'], '%Y-%m-%d %H:%M:%S')
                ci.location = str(photo['latitude'])+','+str(photo['longitude'])
                ci.photo_url = photo['url_sq']
                ci.photo_id = str(photo['id'])
                ci.description = '<img src="'+photo['url_sq']+'" width="75" height="75" />'
                ci.account_owner = flickr_account.account
                ci.put()

        if len(userdata['photos']['photo']) > 49:
            lngth = len(userdata['photos']['photo']) - 1
            date = urllib.quote(userdata['photos']['photo'][lngth]['datetaken'])
            taskqueue.add(url='/worker_flickr_history', params={'flickr_id': flickr_id, 'since': date})

class TwitterHistoryWorker(webapp.RequestHandler):
    def get(self):
        logging.info('Handling Twitter history request')
        twitter_id = str(self.request.get('twitter_id'))

        q1 = TwitterAccount.all()
        q1.filter('twitter_id = ', twitter_id)

        if q1.count() != 1:
            raise Exception('User does not exist')

        t_acct = q1.get()

        if self.request.get('since'):
            since = self.request.get('since')
            request_url = m256.twitter_user_timeline_url+'?count=50&since_id='+since
        elif self.request.get('before'):
            before = self.request.get('before')
            request_url = m256.twitter_user_timeline_url+'?count=50&max_id='+before
        else:
            request_url = m256.twitter_user_timeline_url+'?count=50'

        logging.info('Using request URL: %s' % request_url)

        try:
            content = m256.twitter_token_request(request_url,
                                                 'GET',
                                                 t_acct.access_key,
                                                 t_acct.access_secret)
        except urlfetch.DownloadError:
            m256.downloaderror_check()
            return
        except Exception, e:
            errmsg = 'Exception requesting URL (url: %s, msg: %s)' % (request_url, e)
            logging.error(errmsg)
            m256.notify_admin(errmsg)
            return

        history = simplejson.loads(content)

        for tweet in history:
            if tweet['geo'] is not None:
                logging.info('Found geo tweet, ID# %s' % tweet['id'])
                q2 = TwitterCheckin.all()
                q2.filter('tweet_id = ', str(tweet['id']))

                if q2.count() == 0:
                    #FIXME: Should verify all of these properties exist before adding
                    logging.info('Dont have existing record, going to create new checkin')
                    ci = TwitterCheckin()
                    ci.owner = t_acct
                    ci.location = str(tweet['geo']['coordinates'][0])+','+str(tweet['geo']['coordinates'][1])
                    ci.tweet_id = str(tweet['id'])
                    ci.description = tweet['text']
                    ci.occurred = datetime.datetime.strptime(tweet['created_at'], '%a %b %d %H:%M:%S +0000 %Y')
                    ci.account_owner = t_acct.account
                    ci.put()

        if len(history) > 1:
            if self.request.get('since'):
                logging.info('Have more than one tweet, enqueing since last_id: %s' % history[0]['id'])
                taskqueue.add(url='/worker_twitter_history',
                              params={'twitter_id': t_acct.twitter_id, 'since': history[0]['id']},
                              method='GET')

            elif self.request.get('before'):
                logging.info('Have more than one tweet, enqueing before last_id: %s' % history[len(history)-1]['id'])
                taskqueue.add(url='/worker_twitter_history',
                              params={'twitter_id': t_acct.twitter_id, 'before': history[len(history)-1]['id']},
                              method='GET')

            else:
                logging.info('Have more than one tweet, enqueing since last_id: %s and before last_id: %s' % (history[0]['id'], history[len(history)-1]['id']))
                taskqueue.add(url='/worker_twitter_history',
                              params={'twitter_id': t_acct.twitter_id, 'since': history[0]['id']},
                              method='GET')
                taskqueue.add(url='/worker_twitter_history',
                              params={'twitter_id': t_acct.twitter_id, 'before': history[len(history)-1]['id']},
                              method='GET')

        else:
            if self.request.get('since'):
                t_acct.most_recent_tweet_id = self.request.get('since')
                t_acct.put() #FIXME: Not very race condition proof

class StatisticsWorker(webapp.RequestHandler):
    def get(self, kind=None, period=None):
        kind = self.request.get('kind')
        period = self.request.get('period')

        if period == 'week':
            start_date = datetime.datetime.now()
            delta = datetime.timedelta(days=start_date.weekday(),
                                       hours=start_date.hour,
                                       minutes=start_date.minute,
                                       seconds=start_date.second+1)
            start_date = start_date - delta

        elif period == 'month':
            start_date = datetime.datetime.now()
            delta = datetime.timedelta(days=start_date.day-1,
                                       hours=start_date.hour,
                                       minutes=start_date.minute,
                                       seconds=start_date.second+1)
            start_date = start_date - delta

        elif period == 'alltime':
            start_date = datetime.date(2005, 1, 1)

        else:
            raise Exception('Invalid period!')

        listing = {}

        if kind == 'checkin_speed':
            checkins = FoursquareCheckin.all()
            checkins.filter('occurred >= ', start_date)

            for checkin in checkins:
                ci_fsq_id = str(checkin.foursquare_id)

                if listing.has_key(ci_fsq_id):
                    listing[ci_fsq_id] = (listing[ci_fsq_id] + checkin.velocity) / 2
                else:
                    listing[ci_fsq_id] = checkin.velocity

            from operator import itemgetter
            results = simplejson.dumps(sorted(listing.iteritems(),
                                              key=itemgetter(1),
                                              reverse=True))

        elif kind == 'distance_traveled':
            checkins = FoursquareCheckin.all()
            checkins.filter('occurred >= ', start_date)

            for checkin in checkins:
                ci_fsq_id = str(checkin.foursquare_id)

                if listing.has_key(ci_fsq_id):
                    listing[ci_fsq_id] = listing[ci_fsq_id] + checkin.distance_traveled
                else:
                    listing[ci_fsq_id] = checkin.distance_traveled

            from operator import itemgetter
            results = simplejson.dumps(sorted(listing.iteritems(),
                                              key=itemgetter(1),
                                              reverse=True))

        elif kind == 'number_checkins':
            listing = {}
            users = FoursquareAccount.all()

            for user in users:
                q1 = FoursquareCheckin.all()
                q1.filter('foursquare_id = ', str(user.foursquare_id))
                q1.filter('occurred >= ', start_date)

                listing[str(user.foursquare_id)] = q1.count()

            from operator import itemgetter
            results =  simplejson.dumps(sorted(listing.iteritems(),
                                               key=itemgetter(1),
                                               reverse=True))

        else:
            raise Exception('Invalid kind!')

        stat = GeneratedStatistic()
        stat.description = kind + '_' + period
        stat.contents = results
        stat.put()

class AccountDeleteWorker(webapp.RequestHandler):
    def post(self):
        account_key = self.request.get('account_key')

        if account_key is None:
            logging.info('A')
            return

        try:
            k1 = db.Key(account_key)
        except:
            logging.info('B %s' % account_key)
            return

        account = ServiceAccount.get(k1)

        if account is None:
            logging.info('C')
            return

        q1 = Checkin.all()
        q1.filter('owner = ', account)

        if q1.count() > 100:
            db.delete(q1.fetch(100))
            logging.info('Adding additional deletion worker for account key: %s' % account_key)
            taskqueue.add(url='/worker_account_delete', params={'account_key': account_key})
        else:
            db.delete(q1.fetch(100))
            #FIXME: Should invalidate memcaches here
            logging.info('Finishing account delete of %s' % account_key)
            m256.notify_admin('Account deleted: %s' % account_key)
            account.delete()

def main():

    routes = [
        ('/worker_foursquare_history', FoursquareHistoryWorker),
        ('/worker_flickr_history', FlickrHistoryWorker),
        ('/worker_twitter_history', TwitterHistoryWorker),
        ('/worker_statistics', StatisticsWorker),
        ('/worker_account_delete', AccountDeleteWorker)
    ]

    application = webapp.WSGIApplication(routes, debug=True)
    util.run_wsgi_app(application)

if __name__ == '__main__':
    main()
