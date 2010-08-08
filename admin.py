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


from google.appengine.ext import webapp
from google.appengine.ext.webapp import util

import datetime

import m256

from m256_cfg import *
from models import *

class MainHandler(webapp.RequestHandler):
    def get(self):
        info = {}
        info['page_title'] = 'Admin'
        info['page_header'] = 'Admin Stats'

        start_date = datetime.datetime.now()
        delta = datetime.timedelta(days=1)
        start_date = start_date - delta

        q1 = Account.all()
        info['accounts_count'] = q1.count()

        q2 = Checkin.all()
        info['checkins_count'] = q2.count()

        q3 = ServiceAccount.all()
        info['service_accounts_count'] = q3.count()

        q4 = FoursquareAccount.all()
        info['foursquare_account_count'] = q4.count()

        q5 = FoursquareCheckin.all()
        info['foursquare_checkin_count'] = q5.count()

        q6 = TwitterAccount.all()
        info['twitter_account_count'] = q6.count()

        q7 = TwitterCheckin.all()
        info['twitter_checkin_count'] = q7.count()

        q8 = FlickrAccount.all()
        info['flickr_account_count'] = q8.count()

        q9 = FlickrCheckin.all()
        info['flickr_checkin_count'] = q9.count()

        q5.filter('occurred >=', start_date)
        info['foursquare_last24hour'] = q5.count()

        q7.filter('occurred >=', start_date)
        info['twitter_last24hour'] = q7.count()

        q9.filter('occurred >=', start_date)
        info['flickr_last24hour'] = q9.count()

        m256.output_template(self, 'templates/admin.tmpl', info)

def main():

    routes = [
        ('/admin/', MainHandler)
    ]

    application = webapp.WSGIApplication(routes, debug=True)
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()
