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

!pip install git+https://github.com/GeneralMills/pytrends@master --upgrade
    
from pytrends.request import TrendReq

import os
import urllib
import re
import pandas as pd
from dotenv import find_dotenv, load_dotenv
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

# pytrendでトレンドワードを取得する >trend_words
def pytre():
    pytrend = TrendReq()
    trending_searches_df = pytrend.trending_searches(pn='p4')
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

        sleep(10) #3分待つ
    
        if loopCounter > 3:
            break
        loopCounter += 1

def main():
    # find .env automagically by walking up directories until it's found, then
    # load up the .env entries as environment variables
    load_dotenv(find_dotenv())
    tweet()

if __name__ == '__main__':
    main()
