try:
    import json
except ImportError:
    import simplejson as json

from twitter import Twitter, OAuth
from tokenize import *
from BeautifulSoup import BeautifulSoup
import re, os,time,sys,datetime, requests, schedule
from configHelper import myconfig

URLINTEXT_PAT = \
    re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')

# from twitter_sentence_spliter import *


# Variables that contains the user credentials to access Twitter API 
ACCESS_TOKEN = myconfig.accesstoken
ACCESS_SECRET = myconfig.accessscecret
CONSUMER_KEY = myconfig.consumertoken
CONSUMER_SECRET = myconfig.consumersecret

oauth = OAuth(ACCESS_TOKEN, ACCESS_SECRET, CONSUMER_KEY, CONSUMER_SECRET)


twitter = Twitter(auth=oauth)
# Get a sample of the public data following through Twitter
formalAccount = ['@nytimes','@cnnbrk','@BBCBreaking','@CNN','@ABC','@NBCNews']


def getDate():
    return '_'.join(datetime.datetime.now().__str__().split(':')[0].split())


def getTargetDate():
    targetdate = (datetime.date.today() - datetime.timedelta(days=0)).__str__()
    return targetdate


def getOldUrl(fhander):
    try:
        fhander.seek(0, os.SEEK_SET)
        return dict((l.strip().split()) for l in fhander.readlines() )
    except:
        return dict()


def queryNewUrl(oldurls, acnt):
    """

    :param oldurls: urls queried before
    :param acnt: account name
    :return: newurl2text mapping short urls to a list of tweets
             oldurls
    """
    newurl2text = {}

    try:
        query = twitter.statuses.user_timeline(screen_name=acnt, include_rts=False)
    except:
        return newurl2text,oldurls
    else:
        shorturlSets = set()
        for result in query:
            try:
                url = URLINTEXT_PAT.findall(result["text"])[0]
                if oldurls.has_key(url):
                    continue
                shorturlSets.add(url)
                newurl2text[url] = [result]
            except:
                pass
        '''
            crawling the source news article
            finding the twitter property tag in source HTML file
            adding title and description to the list in newurl2text
        '''
        tag = None
        if 'nytimes' in acnt:
            tag = 'property'
        else:
            tag = 'name'

        for surl in shorturlSets:
            try:
                r = requests.get(surl)
                parsed_html = BeautifulSoup(r.text)
                oldurls[surl] = r.url.split('?')[0]
                try:
                    # property --- nytimes
                    # name --- bbc/cnn/NBCNews

                    tw_prop = parsed_html.find('meta', attrs={tag: "twitter:title"}).attrMap
                    newurl2text[surl].append(tw_prop['content'])
                except:
                    pass

                try:
                    tw_prop = parsed_html.find('meta', attrs={tag: "twitter:description"}).attrMap
                    newurl2text[surl].append(tw_prop['content'])
                except:
                    pass

            except:
                pass
    return newurl2text,oldurls


def rateLimited(maxPerSecond,lastTimeCalled):
    """
    :param maxPerSecond: 0.2
    :param lastTimeCalled:
    :return:
    """

    minInterval = 1.0 / float(maxPerSecond)
    elapsed = time.clock() - lastTimeCalled
    leftToWait = int(minInterval - elapsed)+1
    if leftToWait>0:
        time.sleep(leftToWait)
    return time.clock()


def getQuery(oritweets, maxid, minid, furl):
    """
    try search tweets with ID larger than maxid
    if finding no new tweets
    try search tweets with ID smaller than minid
    if both maxid and minid are None
    try search with no limitation on tweets ID
    this is the case when it is the first time to search with the url
    thus original tweet need appending to the end of the result list
    :param oritweets: original tweets
    :param maxid: maximum tweets ID
    :param minid: minimum tweets ID
    :param furl: full url
    :return: query: original tweet is appended at the end of the tweets list
    """
    query = None
    if maxid is not None and minid is not None:
        try:
            query = twitter.search.tweets(q=furl,
                                      count="100",
                                      lang="en",
                                      max_id=minid
                                      )
        except:
            return None
        else:
            if len(query["statuses"]) == 0:
                try:
                    query = twitter.search.tweets(q=furl,
                                      count="100",
                                      lang="en",
                                      since_id=maxid
                                      )
                except:
                    return None
    else:
        try:
            query = twitter.search.tweets(q=furl,
                                  count="100",
                                  lang="en"
                                  )
            if oritweets is not None:
                query['statuses'].append(oritweets)
        except:
            return None

    return query


def writeQuery2File(acnt, date, urldict, urlid_dict, data):
    """
    write searching result to files
        format for info_acnt_date_auto.txt
        full_url
        tweet_id    screen_name tweets

        format for acnt_date_auto.txt
        tweets

        format for acnt_date_urlcounts.txt
        full_url number_of_tweets
    :param acnt: account name
    :param date: date of the last searching
    :param urldict:
    :param urlid_dict:
    :param data: full url to a list of tweets dictionary
    :return: urldict, urlid_dict
    """

    f = open('files/info_'+acnt+'_'+date+'_auto.txt', 'a')
    rawfilename = 'files/'+acnt+'_'+date+'_auto.txt'
    ff = open(rawfilename, 'a')
    statff = open('files/'+acnt+'_'+date+'_urlcounts.txt', 'a')
    # mytextmanager = textManager()
    for k,v in data.items():
        f.write(k+'\n')
        filteredv = filterUniqSentSet(v)
        statff.write(k+'\t'+str(len(filteredv))+'\t'+str(len(v))+'\n')
        for [id, scrn_name, selected] in filteredv:
            tokens = tokenizeRawTweetText(selected)
            f.write(id+"\t")
            f.write(scrn_name+"\t")
            for t in tokens:
                try:
                    f.write(t.encode('utf-8')+" ")
                    ff.write(t.encode('utf-8')+" ")
                except:
                    pass

            f.write('\n')
            ff.write('\n')
        f.write('\n')
        ff.write('\n')
        '''
         remove url with searching result containing tweets less than 10
        '''
        if len(v) < 10:
            try:
                del urldict[k]
            except:
                pass
            try:
                del urlid_dict[k]
            except:
                pass
    f.close()
    statff.close()
    ff.close()
    return urldict, urlid_dict


def querywithFull(newurl2text, urldict, urlid_dict):
    """
    query with full url and update minID and maxID for each full url
    :param newurl2text:
    :param urldict:
    :param acnt:
    :param urlid_dict:
    :return:
    """

    data = {}
    lastTimeCalled = time.clock()
    for surl, furl in urldict.items():
        data[furl] = []
        cur = set()
        lastTimeCalled = rateLimited(0.2, lastTimeCalled)
        if urlid_dict.has_key(surl):
            maxid = urlid_dict[surl][0]
            minid = urlid_dict[surl][1]
        else:
            maxid, minid = None, None
        oritweets = newurl2text[surl] if newurl2text.has_key(surl) else [None]
        query = getQuery(oritweets[0], maxid, minid, furl)
        if query is None:
            continue
        for result in query["statuses"]:
            nre = re.sub(URLINTEXT_PAT,"",result["text"]).lower().strip()
            if nre not in cur:
                data[furl].append([result["id_str"], result['user']['screen_name'], nre])
                maxid = max(maxid, result["id_str"])
                if minid is None:
                    minid = result["id_str"]
                else:
                    minid = min(minid, result["id_str"])
                cur.add(nre)

        if oritweets is not None:
            for i in xrange(1, len(oritweets)):
                data[furl].append(["", "", oritweets[i].lower().strip()])
        urlid_dict[furl] = (maxid, minid)

    # f = open('files/info_'+acnt+'_'+date+'_auto.txt', 'a')
    # rawfilename = 'files/'+acnt+'_'+date+'_auto.txt'
    # ff = open(rawfilename, 'a')
    # statff = open('files/'+acnt+'_'+date+'_urlcounts.txt', 'a')
    # # mytextmanager = textManager()
    # for k,v in data.items():
    #     f.write(k+'\n')
    #     filteredv = filterUniqSentSet(v)
    #     statff.write(k+'\t'+str(len(filteredv))+'\t'+str(len(v))+'\n')
    #     for [id, scrn_name,selected] in filteredv:
    #         tokens = tokenizeRawTweetText(selected)
    #         f.write(id+"\t")
    #         f.write(scrn_name+"\t")
    #         for t in tokens:
    #             try:
    #                 f.write(t.encode('utf-8')+" ")
    #                 ff.write(t.encode('utf-8')+" ")
    #             except:
    #                 pass
    #
    #         f.write('\n')
    #         ff.write('\n')
    #     f.write('\n')
    #     ff.write('\n')
    #     if len(v) < 10:
    #         try:
    #             del urldict[k]
    #         except:
    #             pass
    #         try:
    #             del urlid_dict[k]
    #         except:
    #             pass
    # f.close()
    # statff.close()
    # ff.close()
    return urldict, urlid_dict, data


def buildurlDictfromFile(handler):
    handler.seek(0, os.SEEK_SET)

    def item(l):
        ts = l.strip().split()
        try:
            return (ts[0], (ts[1], ts[2]))
        except:
            return None
    try:
        return dict(item(l) for l in handler.readlines())
    except:
        return dict()


def filterUniqSentSet(sentences):
    """
     replace #hashtag and @usrname
     merge those are the same
     if one tweet is the substr of the other, only keep the shorter one
    :param sentences:
    :return: filteredsents
    """
    filteredsents = []
    regex = re.compile('[%s]' % re.escape(string.punctuation))

    for [id, acnt, sentence] in sentences:
        merged = False
        sentence = re.sub(r'[@#]\S+', r'', sentence).strip()
        if len(filteredsents) > 0 :
            for i, [_,_,filteredsent] in enumerate(filteredsents):
                sentence_nopunc = re.sub(r' +', r' ', regex.sub(' ', sentence)).strip()
                filteredsent_nopunc = re.sub(r' +', r' ', regex.sub(' ', filteredsent)).strip()
                if sentence_nopunc.lower() in filteredsent_nopunc.lower():
                    filteredsents[i] =[id,acnt,sentence]
                    merged = True
                    break
                if filteredsent_nopunc.lower() in sentence_nopunc.lower():
                    merged = True
                    break
        if not merged:
            filteredsents.append([id,acnt,sentence])
    return filteredsents


def job():
    for acnt in formalAccount:
        print acnt, time.asctime()
        sys.stdout.flush()
        '''
            get urls from file
        '''
        urlfiles = 'files/'+acnt+'_urls.txt'
        urlfile_handler= open(urlfiles,'a+')
        urldict = getOldUrl(urlfile_handler)
        '''
            get url to minID and maxID from file
        '''
        urlidfiles = "files/"+ acnt+"_urlID.txt"
        urlid_handler = open(urlidfiles,'a+')
        urlid_dict = buildurlDictfromFile(urlid_handler)
        newurl2text, urldict = queryNewUrl(urldict,acnt)

        if len(urldict) > 0:
            date = getDate()
            urldict, urlid_dict, data = querywithFull(newurl2text, urldict, urlid_dict)
            urldict, urlid_dict = writeQuery2File(acnt, date, urldict, urlid_dict, data)
        '''
            update acnt_url.txt file and acnt_urlID.txt file
        '''
        urlfile_handler.seek(0, os.SEEK_SET)
        urlfile_handler.truncate(0)
        for k, v in urldict.items():
            urlfile_handler.write(k+'\t'+v+'\n')
        urlfile_handler.close()

        urlid_handler.seek(0,os.SEEK_SET)
        urlid_handler.truncate(0)
        for k,v in urlid_dict.items():
            urlid_handler.write(k+'\t'+v[0]+'\t'+v[1]+'\n')
        urlid_handler.close()


schedule.every().hour.do(job)

job()

while True:
    schedule.run_pending()
    time.sleep(1)