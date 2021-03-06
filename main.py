# -*- coding: utf-8 -*-
"""google_trend_twitter.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/15h6IpXS0WUbbo7dls3Fi4GiUWH5fw_Hc
"""
"""
!pip install pytrends
!pip install git+https://github.com/GeneralMills/pytrends@master --upgrade
!pip install bottlenose
!pip install python-dotenv
!pip install retry
!pip install twitter
!pip install beautifulsoup4
!pip install requests requests_oauthlib
"""
from pytrends.request import TrendReq
import requests
import os
import urllib
import re
import pandas as pd
# from dotenv import find_dotenv, load_dotenv
from bottlenose import Amazon
from bs4 import BeautifulSoup
from retry import retry

from twitter import *

from requests_oauthlib import OAuth1Session
import json
# from settings import *    #ここでトークンなどの設定ファイルを読み込む。
import random
import datetime

from time import sleep

#amazonのアクセスキー
AWS_ACCESS_KEY_ID = os.environ["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = os.environ["AWS_SECRET_ACCESS_KEY"]
AWS_ASSOCIATE_TAG = os.environ["AWS_ASSOCIATE_TAG"]

# twitterのアクセストークン
CONSUMER_KEY        = os.environ["CONSUMER_KEY"]
CONSUMER_SECRET_KEY = os.environ["CONSUMER_SECRET_KEY"]
ACCESS_TOKEN        = os.environ["ACCESS_TOKEN"]
ACCESS_TOKEN_SECRET = os.environ["ACCESS_TOKEN_SECRET"]

#pytrendのupgradeが効かないので関数を修正
class TrendReq(object):
    
    GET_METHOD = 'get'
    POST_METHOD = 'post'

    GENERAL_URL = 'https://trends.google.com/trends/api/explore'
    INTEREST_OVER_TIME_URL = 'https://trends.google.com/trends/api/widgetdata/multiline'
    INTEREST_BY_REGION_URL = 'https://trends.google.com/trends/api/widgetdata/comparedgeo'
    RELATED_QUERIES_URL = 'https://trends.google.com/trends/api/widgetdata/relatedsearches'
    TRENDING_SEARCHES_URL = 'https://trends.google.com/trends/hottrends/hotItems'
    TOP_CHARTS_URL = 'https://trends.google.com/trends/topcharts/chart'
    SUGGESTIONS_URL = 'https://trends.google.com/trends/api/autocomplete/'
    CATEGORIES_URL = 'https://trends.google.com/trends/api/explore/pickers/category'

    def __init__(self, hl='en-US', tz=360, geo='', proxies=''):
        """
        Initialize default values for params
        """
        # google rate limit
        self.google_rl = 'You have reached your quota limit. Please try again later.'
        self.results = None

        # set user defined options used globally
        self.tz = tz
        self.hl = hl
        self.geo = geo
        self.kw_list = list()
        self.proxies = proxies #add a proxy option 
        #proxies format: {"http": "http://192.168.0.1:8888" , "https": "https://192.168.0.1:8888"}

        # intialize widget payloads
        self.token_payload = dict()
        self.interest_over_time_widget = dict()
        self.interest_by_region_widget = dict()
        self.related_topics_widget_list = list()
        self.related_queries_widget_list = list()

    def _get_data(self, url, method=GET_METHOD, trim_chars=0, **kwargs):
        """Send a request to Google and return the JSON response as a Python object
        :param url: the url to which the request will be sent
        :param method: the HTTP method ('get' or 'post')
        :param trim_chars: how many characters should be trimmed off the beginning of the content of the response
            before this is passed to the JSON parser
        :param kwargs: any extra key arguments passed to the request builder (usually query parameters or data)
        :return:
        """
        if method == TrendReq.POST_METHOD:
            s = requests.session()
            if self.proxies != '':
                s.proxies.update(self.proxies)
            response = s.post(url, **kwargs)
        else:
            s = requests.session()
            if self.proxies != '':
                s.proxies.update(self.proxies)
            response = s.get(url,**kwargs)

        # check if the response contains json and throw an exception otherwise
        # Google mostly sends 'application/json' in the Content-Type header,
        # but occasionally it sends 'application/javascript
        # and sometimes even 'text/javascript
        if 'application/json' in response.headers['Content-Type'] or \
            'application/javascript' in response.headers['Content-Type'] or \
                'text/javascript' in response.headers['Content-Type']:

            # trim initial characters
            # some responses start with garbage characters, like ")]}',"
            # these have to be cleaned before being passed to the json parser
            content = response.text[trim_chars:]

            # parse json
            return json.loads(content)
        else:
            # this is often the case when the amount of keywords in the payload for the IP
            # is not allowed by Google
            raise exceptions.ResponseError('The request failed: Google returned a '
                                           'response with code {0}.'.format(response.status_code), response=response)

    def build_payload(self, kw_list, cat=0, timeframe='today 5-y', geo='', gprop=''):
        """Create the payload for related queries, interest over time and interest by region"""
        self.kw_list = kw_list
        self.geo = geo
        self.token_payload = {
            'hl': self.hl,
            'tz': self.tz,
            'req': {'comparisonItem': [], 'category': cat, 'property': gprop}
        }

        # build out json for each keyword
        for kw in self.kw_list:
            keyword_payload = {'keyword': kw, 'time': timeframe, 'geo': self.geo}
            self.token_payload['req']['comparisonItem'].append(keyword_payload)
        # requests will mangle this if it is not a string
        self.token_payload['req'] = json.dumps(self.token_payload['req'])
        # get tokens
        self._tokens()
        return

    def _tokens(self):
        """Makes request to Google to get API tokens for interest over time, interest by region and related queries"""

        # make the request and parse the returned json
        widget_dict = self._get_data(
            url=TrendReq.GENERAL_URL,
            method=TrendReq.GET_METHOD,
            params=self.token_payload,
            trim_chars=4,
        )['widgets']

        # order of the json matters...
        first_region_token = True
        # clear self.related_queries_widget_list and self.related_topics_widget_list
        # of old keywords'widgets
        self.related_queries_widget_list[:] = []
        self.related_topics_widget_list[:] = []
        # assign requests
        for widget in widget_dict:
            if widget['id'] == 'TIMESERIES':
                self.interest_over_time_widget = widget
            if widget['id'] == 'GEO_MAP' and first_region_token:
                self.interest_by_region_widget = widget
                first_region_token = False
            # response for each term, put into a list
            if 'RELATED_TOPICS' in widget['id']:
                self.related_topics_widget_list.append(widget)
            if 'RELATED_QUERIES' in widget['id']:
                self.related_queries_widget_list.append(widget)
        return
        
    def trending_searches(self, pn='p1'):
        # make the request
        forms = {'ajax': 1, 'pn': 'p4', 'htd': '', 'htv': 'l'}
        req_json = self._get_data(
            url=TrendReq.TRENDING_SEARCHES_URL,
            method=TrendReq.POST_METHOD,
            data=forms,
        )['trendsByDateList']
        result_df = pd.DataFrame()

        # parse the returned json
        sub_df = pd.DataFrame()
        for trenddate in req_json:
            sub_df['date'] = trenddate['date']
            for trend in trenddate['trendsList']:
                sub_df = sub_df.append(trend, ignore_index=True)
        result_df = pd.concat([result_df, sub_df])
        return result_df

# pytrendでトレンドワードを取得する >trend_words
def pytre():
    pytrend = TrendReq()
    trending_searches_df = pytrend.trending_searches()
    trend_words = trending_searches_df["title"]
    print(trend_words)
    return(trend_words)

#trend_wordsをアマゾンで検索、書籍のみ > tweet_dfにtitle/image/url/rankを格納する

# エラーの場合、1秒待機しリトライ（最大7回）

@retry(urllib.error.HTTPError, tries=7, delay=1)
def search(amazon, k, i):
    print('get products...')
    return amazon.ItemSearch(Keywords=k, SearchIndex=i, Sort="daterank", ResponseGroup="Medium")

def tweetdf():
    amazon = Amazon(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_ASSOCIATE_TAG, Region='JP',
                    Parser=lambda text: BeautifulSoup(text, 'xml')
                    )
    #最終格納用のDF作成
    data_frame = pd.DataFrame(index=[], columns=['title','image', 'url', 'rank','author','keyword','ad'])
    trend_words = pytre()
    for keyword in trend_words:
    
        response = search(amazon, keyword, "Books")
        print(response)
    
        for item in response.find_all('Item'):
            print(item.Title.string, item.LargeImage, item.DetailPageURL.string, item.SalesRank, item.IsAdultProduct, item)
            sr = item.SalesRank
            li = item.LargeImage
            au = item.Author
            ad = item.IsAdultProduct
            if sr and li and au :
                series = pd.Series([item.Title.string, li.URL.string, item.DetailPageURL.string, sr.string, au.string, keyword, ad], index=data_frame.columns)
                data_frame = data_frame.append(series, ignore_index = True)
            elif sr == None and li and au :
                series = pd.Series([item.Title.string, li.URL.string, item.DetailPageURL.string, "9999999", au.string, keyword, ad], index=data_frame.columns)
                data_frame = data_frame.append(series, ignore_index = True)
            else:
                continue
                
    data_frame[["rank"]]=data_frame[["rank"]].astype(int)
    tweet_df = data_frame.sort_values(by="rank")
    print(tweet_df)
    return tweet_df

def tweet():
    twitter = OAuth1Session(CONSUMER_KEY, CONSUMER_SECRET_KEY, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)

    url_media = "https://upload.twitter.com/1.1/media/upload.json"
    url_text = "https://api.twitter.com/1.1/statuses/update.json"

    loopCounter = 1
    tweets = []   #ここにツイートする内容を入れる
    tweet_df = tweetdf()

    for i,v in tweet_df.iterrows():
        print(i,v["title"],v["author"],v["url"])
        print("i: " + str(i) + " v: " + str(v))
        if v["ad"] != "<IsAdultProduct>1</IsAdultProduct>":
            tweet =v["title"] +"\n"+ v["author"] + "\n" +"#"+ v["keyword"]+" #trendbooks" + "\n" + v["url"]
            media_name = v["image"]
            tweets.append(tweet)
        else:
            continue

        files = {"media" : urllib.request.urlopen(media_name).read()}
        req_media = twitter.post(url_media, files = files)

        media_id = json.loads(req_media.text)['media_id']
        print("MEDIA ID: %d" % media_id)

        params = {"status" : tweet, "media_ids" : [media_id]}
        req = twitter.post("https://api.twitter.com/1.1/statuses/update.json", params = params)    

        sleep(120) #2分待つ
    
        if loopCounter > 15:
            break
        loopCounter += 1

def main():
    # find .env automagically by walking up directories until it's found, then
    # load up the .env entries as environment variables
    # load_dotenv(find_dotenv())
    tweet()

if __name__ == '__main__':
    main()
