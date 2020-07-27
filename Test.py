import requests
import pandas as pd
import urllib3
import os
import ast
import time
import datetime
import bisect
import math
import webbrowser
from bs4 import BeautifulSoup


def list_to_dict(leaders,times):
    leaderli = []
    timesli = []
    for i in range(len(leaders)):
        diction = ast.literal_eval(leaders[i]["data-tracking-properties"])
        leaderli.append(diction)
        if ":" in times[i].text:
            sec = time.strptime(times[i].text,'%M:%S')
        else:
            sec = time.strptime(times[i].text.strip("s"), '%S')
        timesli.append(datetime.timedelta(minutes=sec.tm_min,seconds=sec.tm_sec).total_seconds())
    df = pd.DataFrame(leaderli)
    df['Seconds'] = timesli
    return df


def find_wr_pace(df):
    wr_ref = pd.read_csv('WorldRecord.csv')
    idx = bisect.bisect(wr_ref['WR_Distance'], df['Distance'])
    if 0<idx<len(wr_ref['WR_Distance']):
        wr = (wr_ref['WR_Pace'][idx] - wr_ref['WR_Pace'][idx-1])/(wr_ref['WR_Distance'][idx] - wr_ref['WR_Distance'][idx-1])
        seg_pace = (wr*(df['Distance']-wr_ref['WR_Distance'][idx-1]))+wr_ref['WR_Pace'][idx-1]
        return seg_pace
    elif idx == 0:
        return wr_ref.iloc[0,2]
    elif idx == len(wr_ref['WR_Distance']):
        return wr_ref.iloc[len(wr_ref['WR_Distance']),2]


def text_pace(x):
    totseconds = 60*x
    minutes = math.floor(totseconds/60)
    seconds = math.floor(totseconds % 60)
    return str(minutes) + ":" + str(seconds) + "/km"


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ['EMAIL'] = 'XXXXX'
os.environ['Password'] = 'XXXXX'

auth_url = "https://www.strava.com/oauth/token?"
activities_url = "https://www.strava.com/api/v3/athlete/activities?"
activity_url = "https://www.strava.com/api/v3/activities/"
segment_url = "https://www.strava.com/segments/"
seg_filter = "?filter=overall"
strava_login = "https://www.strava.com/login"
df = pd.DataFrame()
segdf= pd.DataFrame()
leader_boarddf = pd.DataFrame()

auth_param = {
    "client_id":"xx",
    "client_secret": "xx",
    "refresh_token":"xx",
    "grant_type":"refresh_token"
}
access_token = requests.post(auth_url,data=auth_param).json()['access_token']
activities_param = {
    "access_token":access_token,
    "per_page": "2"
}
activity_param = {
    "access_token": access_token
}

r = requests.get(activities_url, params=activities_param).json()
for i in range(len(r)):
    #temp = {'Start Date': r[i]['start_date_local'], 'Athlete_id': r[i]['athlete']['id'], 'Activity_id': r[i]['id'], 'type': r[i]['type']}
    #tempdf = pd.DataFrame(temp, index=[i])
    #df = df.append(tempdf, ignore_index=True)
    l = requests.get(activity_url+str(r[i]['id'])+'?',params=activity_param).json()
    seg_act = l['segment_efforts']
    for i in range(len(seg_act)):
        temp = {'Segment Name': seg_act[i]["name"],'Type': seg_act[i]["segment"]["activity_type"], 'segment_id':seg_act[i]["segment"]["id"], 'Distance':seg_act[i]["segment"]["distance"]}
        tempdf = pd.DataFrame(temp, index=[i])
        segdf = segdf.append(tempdf, ignore_index=True)
segdf = segdf.drop_duplicates(subset='segment_id',keep='first')
#print(df)


with requests.session() as sess:
    result = sess.get(strava_login)
    logintest = BeautifulSoup(result.text,'lxml')
    authenticity_token = logintest.find('input',{"name":"authenticity_token"})['value']
    login_result = sess.post(
        'https://www.strava.com/session',
        data=dict(email=os.environ['EMAIL'], password=os.environ['PASSWORD'], authenticity_token=authenticity_token),
        headers=dict(referer=strava_login)
    )
    for i in range(len(segdf)):
        seg = sess.get(segment_url+str(segdf.iloc[i,2])+seg_filter)
        soup = BeautifulSoup(seg.text,'lxml')
        leader_board = soup.findAll('td',{"class":"athlete track-click"})
        time_value = soup.find_all('td',{"class":"last-child"})
        tempdf = list_to_dict(leader_board,time_value)
        tempdf['segment_id'] = segdf.iloc[i,2]
        tempdf['Distance'] = segdf.iloc[i,3]
        leader_boarddf = leader_boarddf.append(tempdf)
    leader_boarddf['Segment Pace(min/km)'] = (leader_boarddf['Seconds']/60)/(leader_boarddf['Distance']/1000)
    finaldf = pd.merge(leader_boarddf,segdf,how='left',left_on=['segment_id','Distance'],right_on=['segment_id','Distance'])
    finaldf['WR Pace'] = finaldf.apply(find_wr_pace,axis=1)
    finaldf['Unbelievable'] = (finaldf['Segment Pace(min/km)'] - finaldf['WR Pace']) < 0
    finaldf.to_csv('stravaall.csv', index=False)
    segmentdf = finaldf[(finaldf['Unbelievable']==True)]
    restdf = finaldf[(finaldf['Unbelievable']==False)]
    all_activities = restdf.iloc[:,[0,1]]
    distanceli = []
    timeli = []
    paceli = []
    for i in range(len(all_activities['activity_id'])):
        link = "https://www.strava.com/activities/" + str(all_activities.iloc[i, 1])
        act = sess.get(link)
        acttest = BeautifulSoup(act.text, 'lxml')
        stats_sec = acttest.find('ul', {'class': 'inline-stats section'})
        distance = float(stats_sec.findAll('strong')[0].findAll(text=True)[0]) * 1.60934 * 1000
        distanceli.append(distance)
        times = str(stats_sec.findAll('strong')[1].findAll(text=True)[0])
        timeli.append(times)
        pace = str(stats_sec.findAll('strong')[2].findAll(text=True)[0])
        if ":" in pace:
            sec = time.strptime(pace,'%M:%S')
        else:
            sec = time.strptime(pace, '%S')
        totsec = datetime.timedelta(minutes=sec.tm_min,seconds=sec.tm_sec).total_seconds()/(1.60934*60)
        paceli.append(totsec)
    all_activities['Distance'] = distanceli
    all_activities['Time'] = timeli
    all_activities['Pace'] = paceli
    all_activities['WR_Pace'] = all_activities.apply(find_wr_pace,axis=1)
    all_activities['Unbelievable'] = (all_activities['Pace'] - all_activities['WR_Pace']) < 0
    all_activities = all_activities[(all_activities['Unbelievable']==True)]
    all_activities.to_csv('Unreal_activities.csv',index=False)
    segmentdf.to_csv('Unreal_seg.csv',index=False)
    for i in range(len(segmentdf)):
        link = "www.strava.com/activities/" + str(segmentdf.iloc[i, 1]) + "/overview"
        webbrowser.open(link,new=2)
        formatted_time = text_pace(segmentdf.iloc[i,7])
        print("The pace on segment " + str(segmentdf.iloc[i,8]) + " is " + formatted_time +" which is unbelievable")
        break
    for i in range(len(all_activities)):
        link = "www.strava.com/activities/" + str(all_activities.iloc[i, 1]) + "/overview"
        webbrowser.open(link, new=2)
        formatted_time = text_pace(all_activities.iloc[i, 4])
        print("The pace on the run is " + formatted_time + " which is unbelievable")
        break