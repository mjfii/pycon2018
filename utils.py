import requests
from bs4 import BeautifulSoup
from ibm_botocore.client import Config
import ibm_boto3
from sklearn.externals import joblib
import json
import pandas as pd
try:
    from secrets import creds_hmac, wml_credentials
except:
    mode = 'offline'
from watson_machine_learning_client import WatsonMachineLearningAPIClient
import numpy as np
from sklearn.preprocessing import LabelEncoder

topic_list = {'biz-news': {'css_class': '.biz-news', 'display_name': 'Biz-News'},
    'business': {'css_class': '.business', 'display_name': 'Business'},
    'crypto': {'css_class': '.crypto', 'display_name': 'Crypto'},
    'dev': {'css_class': '.dev', 'display_name': 'Dev'},
    'github': {'css_class': '.github', 'display_name': 'Github'},
    'ml': {'css_class': '.ml', 'display_name': 'Ml'},
    'news': {'css_class': '.news', 'display_name': 'News'},
    'random': {'css_class': '.random', 'display_name': 'Random'},
    'science': {'css_class': '.science', 'display_name': 'Science'},
    'tech': {'css_class': '.tech', 'display_name': 'Tech'},
    'thought': {'css_class': '.thought', 'display_name': 'Thought'}}


class hn_collector():


    def __init__(self):
        self.API_BASE = 'https://hacker-news.firebaseio.com/v0/'
        self.TOP ='topstories.json'
        self.NEW ='newstories.json'
        self.ITEM ='item/'
        self.HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36'}

    def get_top_stories(self, return_all = False):
        return(eval(requests.get(self.API_BASE + self.TOP).content))

    def get_new_stories(self,return_all=False):
        return(eval(requests.get(self.API_BASE + self.NEW).content))


    def get_story(self, story_id):
        return(eval(requests.get(self.API_BASE + self.ITEM + str(story_id)+".json").content))

    def get_text(self, story_url):

        try:
            page = requests.get(story_url, headers=self.HEADERS)
            soup = BeautifulSoup(page.content,'lxml')
            s= ' '.join([p.text for p in soup.find_all('p')])
            return(s)
        except:
            return('{} FAILED'.format(story_url))

    def get_list_content(self, story_list,title='data/stories.json'):
        all_stories = []
        for story in story_list:

            try:
                s = self.get_story(story)
                s['text'] =  self.get_text(s['url'])
            except:
                print(story)
                pass
            all_stories.append(s)
        with open(title, 'w') as outfile:
            json.dump(all_stories, outfile)
        print("All stories saved to {}".format(title))
        return(all_stories)


def refresh_COS_data(file_key , out_path, creds_hmac ):

    import boto
    import boto.s3.connection
    access_key = creds_hmac["cos_hmac_keys"][ "access_key_id"]   # Change to match your setup
    secret_key = creds_hmac["cos_hmac_keys"][ "secret_access_key"] # Change to match your setup
    bucket = 'pyconproject-donotdelete-pr-hvlammk95c1rrk'      # Change to match your setup

    host = "s3-api.us-geo.objectstorage.softlayer.net"

    conn = boto.connect_s3(
            aws_access_key_id = access_key,
            aws_secret_access_key = secret_key,
            host = host,
            calling_format = boto.s3.connection.OrdinaryCallingFormat(),
            )

    b =conn.get_bucket(bucket)
    key = b.get_key(file_key)
    key.get_contents_to_filename(out_path)

def prep_card_data(source_json = 'data/scored_nmf.json', threshold=0.05, mode = 'topic'):
    with open(source_json) as json_data:
        story_list = json.load(json_data)
    if mode == 'topic':
        for story in story_list:
            try:
                filtered_dict = {k:v for k,v in story.items() if "Topic" in k and v > threshold} #filter topics for scores in topics
                story['ml_topics'] = filtered_dict
                story['card_class'] = 'element-item ' + ' '.join(list(filtered_dict.keys()))
                story['id'] = str(story['id'])[:-2]
                #print(model.transform([story['text']]))
            except:
                pass
        return(story_list[:200])
    elif mode == 'cluster':
        for story in story_list:
            story['card_class'] = 'element-item {}'.format(story['label_name'])
            try:
                story['id'] = str(story['id'])

            except:
                pass
        return(story_list)

def score_stories(in_path,out_path,model_path):
    with open(in_path) as json_data:
        story_list = json.load(json_data)
    df = pd.DataFrame(story_list)
    df = df[~df.text.isnull()]
    clf = joblib.load(model_path)
    df['label'] = clf.predict(df.text)
    encoder = LabelEncoder()
    encoder.classes_ = np.load('models/topic_classes.npy')
    df['label_name'] = encoder.inverse_transform(df['label'])
    topic_dict = {}
    for topic in encoder.classes_ :
        topic_dict[topic] =  {'css_class': ".{}".format(topic),
                            'display_name': topic.title(),
                            #'count': df.label_name.value_counts().get(topic,0)  # not accurate
                           }
    df.to_json(out_path,orient='records')
    return(df,topic_dict)

def load_wml_model(wml_credentials):
    client = WatsonMachineLearningAPIClient(wml_credentials)
    return(client.repository.load(wml_credentials['guid'] ))
