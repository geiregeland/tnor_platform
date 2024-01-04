import os
import time
import subprocess
from flask import Flask, session, flash, json, request,jsonify
from rq import Queue
from rq.job import Job 
#import rq_dashboard
#from mworker import connRedis
#import worker as myworker
import uuid
#from mmapp import mytime
import pandas as pd
from datetime import datetime,timedelta
from flask import jsonify
import redis
from rq import Worker, Queue, Connection
import iperf3 as ip3
from pathlib import Path
import shlex
from mmapp import Startsample,StartExp,rxtx,get_kpis,logged

from dotenv import load_dotenv as loadenv
from config import myprint
from config import G5Conf
import requests

Logfile = G5Conf['Logpath']


def clean_osgetenv(s):
    try:
        if ord(s[0:1]) == 8220:
            return(s[1:-1])
    except:
        pass
    return s

ServerPort = G5Conf['iperfport']
ServerAddress = G5Conf['iperfhost']
MeasurePort = G5Conf['mport']
    
#q = Queue(connection = myworker.connRedis(), default_timeout = 7200)
def mytime():
  now = datetime.now()
  return(str(now.date())+" "+str(now.time()).split('.')[0])


def errorResponse(message, error):
    myprint(mytime(),f'{message}: {error}')
    return jsonify({'Status': 'Error', 'Message': message, 'Error': f'{error}'}), 403

@logged    
def connect_redis(url):
    try:
        conn = redis.from_url(url)
        return conn
    except Exception as error:
        return errorResponse("Could not connect to redis",error)
@logged
def connRedis():
    try:
        #redisPort=get_redisport()
        #redis_url = os.getenv('REDIS_URL', 'redis://localhost:'+redisPort)
        host = G5Conf['redishost']
        port = G5Conf['redisport']
        redis_url = f'redis://{host}:{port}'
        myprint(mytime(),"redis url: ",redis_url)
        return connect_redis(redis_url)
    
    except Exception as error:
        return errorResponse("Failed main redis connection",error)



      
q = Queue('low',connection = connRedis(), default_timeout = 7200)

app = Flask(__name__)
# Configuration Variables
redishost = G5Conf['redishost']
redisport = G5Conf['redisport']

app.config["DEBUG"] = True
app.config["RQ_DASHBOARD_REDIS_PORT"] = redisport
app.config["RQ_DASHBOARD_REDIS_URL"] = f"redis://{redishost}:{redisport}"

#pwd_get= subprocess.run(['pwd'],check=True,text=False,stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#app.config['UPLOAD_FOLDER'] = pwd_get.stdout.decode('utf-8')[:-1]+"/uploades"

#app.config.from_object(rq_dashboard.default_settings)
#app.register_blueprint(rq_dashboard.blueprint,url_prefix='/rq')

@logged
def get_token():
    try:
        url = 'https://iambackend.netapps-5gmediahub.eu/realms/5GMediaHUB/protocol/openid-connect/token'
        headers = { 'Content-Type': 'application/x-www-form-urlencoded'}
        data = {
            'grant_type': 'client_credentials',
            'client_id': 'tnor-client-collector',
            'client_secret': clean_osgetenv(os.getenv('CLIENT_SECRET'))
        }
    

        response = requests.post(url, headers=headers, data=data)

        myprint(mytime(),"Get token response", response.status_code)
        token=response.json()['access_token']
        return token
    except Exception as error:
        return errorResponse("Failed <get_token>",error)

@logged
def get_timestamp():
    return datetime.utcnow().isoformat().split('.')[0]+'Z'

@logged
def registerkpis(meta):
    try:
        test_case = meta['test_case']
        use_case = meta['use_case']
        test_case_id = meta['test_case_id']
        uc_kpis = meta['kpis']
    
        headers={'Content-Type': 'application/json', 'Authorization':''}
        headers['Authorization'] = 'Bearer ' + get_token()
    
        data={'test': {'use_case': f'{use_case}', 'test_case': f'{test_case}', 'test_case_id': f'{test_case_id}'}, 'data': {'timestamp': f'{get_timestamp()}', 'kpis': uc_kpis['kpis']}}
    
        myprint(mytime(),"Data to register=",data)
        r=requests.post('http://5gmediahub.vvservice.cttc.es/5gmediahub/data-collector/kpis',headers=headers,json=data)
        myprint(mytime(),"Register response:",r)
    except Exception as error:
        return errorResponse("Failed call <registerkpis>",error)

@logged
def registerkpis_test(data):
    headers={'Content-Type': 'application/json', 'Authorization':''}
    headers['Authorization'] = 'Bearer ' + get_token()
    
    
    myprint(mytime(),data)
    r=requests.post('http://5gmediahub.vvservice.cttc.es/5gmediahub/data-collector/kpis',headers=headers,json=data)
    myprint(mytime(),r)

    
@app.route('/startexperiment/',methods = ['GET','POST'])
@logged
def startexp():
    try:
        arguments = request.json
        #explength=arguments['delta']
        use_case = arguments['use_case']
        test_case = arguments['test_case']
        test_case_id=arguments['test_case_id']
        
        #uid = uuid.uuid4().hex
        uid = test_case_id

        job = Job.create(StartExp,args=[uid],id=uid,connection=connRedis())
        job.meta['active'] = 1
        job.meta['use_case'] = use_case
        job.meta['test_case'] = test_case
        job.meta['test_case_id'] = uid
        
        job.save_meta()
        
        #delta = timedelta(minutes = 5)
        #at=datetime.now()+delta
        r=q.enqueue_job(job)
        return f'startexperiment: ok'
    except Exception as error:
        return errorResponse("Failed call to /startexperiment",error)

@app.route('/stopexperiment/',methods = ['GET','POST'])
@logged
def stoptexp():
    try:
        arguments = request.json

        use_case = arguments['use_case']
        test_case = arguments['test_case']
        test_case_id=arguments['test_case_id']
        
        #uid = uuid.uuid4().hex
        uid = test_case_id

        #uid = uuid.uuid4().hex
        job = Job.fetch(uid,connection=connRedis())
        
        #job = Job.create(startexp,args=[uid,delta],id=uid,connection=connRedis())
        job.meta['active'] = 0
        job.save_meta()
        time.sleep(2)
        job.refresh()
        #delta = timedelta(minutes = 5)
        #at=datetime.now()+delta
        #r=q.enqueue_job(job)
        
        myprint(mytime(),job.meta)
        myprint(mytime(),"about to register kpis......")
        registerkpis(job.meta)

        return f'stopexperiment: ok'
    except Exception as error:
        return errorResponse("Failed call to /stopexperiment",error)

@app.route('/stopexperimentnorep/',methods = ['GET','POST'])
@logged
def stoptexpnorep():
    try:
        arguments = request.json

        use_case = arguments['use_case']
        test_case = arguments['test_case']
        test_case_id=arguments['test_case_id']
        
        #uid = uuid.uuid4().hex
        uid = test_case_id

        #uid = uuid.uuid4().hex
        job = Job.fetch(uid,connection=connRedis())
        
        #job = Job.create(startexp,args=[uid,delta],id=uid,connection=connRedis())
        job.meta['active'] = 0
        job.save_meta()
        time.sleep(2)
        job.refresh()
        #delta = timedelta(minutes = 5)
        #at=datetime.now()+delta
        #r=q.enqueue_job(job)
        
        myprint(mytime(),job.meta)
        myprint(mytime(),"will not register kpis......")
        
        meta = job.meta
        test_case = meta['test_case']
        use_case = meta['use_case']
        test_case_id = meta['test_case_id']
        uc_kpis = meta['kpis']
    
    
        data={'test': {'use_case': f'{use_case}', 'test_case': f'{test_case}', 'test_case_id': f'{test_case_id}'}, 'data': {'timestamp': f'{get_timestamp()}', 'kpis': uc_kpis['kpis']}}
    
        myprint(mytime(),"Data that will not be  registered=",data)

        #registerkpis(job.meta)

        return f'stopexperimentnorep: ok'
    except Exception as error:
        return errorResponse("Failed call to /stopexperimentnorep",error)


#----------------------------------------- old stuff below ----------------------------------


@app.route('/registerping/<uid>',methods = ['GET','POST'])
def regping(uid):
    try:
        arguments = request.json
        val=arguments['RTT']
        if float(val)*1.0 == 0:
            print(mytime(),f'Error: we got a RTT = {val}')
            print(arguments)
        #print(arguments)
        dfd = pd.read_csv(f'{Logfile}/iperf.csv',sep=',')
        #dfd=df.copy()
        if len(dfd.loc[dfd['Id']==f'{uid}']):
            dfd.loc[dfd['Id']==f'{uid}','RTT'] = float(val)
            #dfd.loc[dfd.index[-1],'RTT']=float(val)

        #df = pd.concat([df,pd.DataFrame(sample,columns=['Date','Uplink','Downlink','RTT'])])
        dfd.to_csv(f'{Logfile}/iperf.csv', sep=',', encoding='utf-8',index=False)
        print(mytime(),dfd)


        return f'registerping: ok'
    except Exception as error:
        return errorResponse("Failed call to /registerping",error)


    
@app.route('/registerowamp/<uid>',methods = ['GET','POST'])
def regowamp(uid):
    try:
        arguments = request.json
        jitter=arguments['jitter']
        availebility=arguments['availebility']
        delay=arguments['delay']

        if float(jitter)*1.0 == 0:
            print(mytime(),f'Error: we got jitter = {jitter}')
            print(arguments)
        
        if float(availebility)*1.0 == 0:
            print(mytime(),f'Error: we got A = {availebility}')
            print(arguments)

        if float(delay)*1.0 == 0:
            print(mytime(),f'Error: we got delay = {delay}')
            print(arguments)


        #print(arguments)
        dfd = pd.read_csv(f'{Logfile}/iperf.csv',sep=',')
        #dfd=df.copy()
        if len(dfd.loc[dfd['Id']==f'{uid}']):
            dfd.loc[dfd['Id']==f'{uid}','Delay']=float(delay)
            dfd.loc[dfd['Id']==f'{uid}','Availebility']=float(availebility)
            dfd.loc[dfd['Id']==f'{uid}','Jitter']=float(jitter)
        else:
            print(mytime(),f'Failed to write data to pandas for uid:{uid}')

        #df = pd.concat([df,pd.DataFrame(sample,columns=['Date','Uplink','Downlink','RTT'])])
        dfd.to_csv(f'{Logfile}/iperf.csv', sep=',', encoding='utf-8',index=False)
        print(mytime(),dfd)


        return f'registerowamp: ok'
    except Exception as error:
        return errorResponse("Failed call to /registerowamp",error)


#Reliability	The likelihood of a service failing, i.e. 	Mean time between failure (MTBF). 
@app.route('/getmtbf',methods=['GET','POST'])
def getmtbf():    
    df = pd.read_csv(f'{Logfile}/iperf.csv',sep=',')
    a=df['Availebility'].tail(10)
    u=0
    d=0
    for i in a:
        if i>=1.0:
            u+=600
        else:
            d+=1
    if d:
        mtbf=u/d
    else:
        return 1.0

@app.route('/getdelay',methods=['GET','POST'])
def getdelay():
    df = pd.read_csv(f'{Logfile}/iperf.csv',sep=',')
    return df['Delay'].tail(10).mean()

@app.route('/getjitter',methods=['GET','POST'])
def getjitter():
    df = pd.read_csv(f'{Logfile}/iperf.csv',sep=',')
    return df['Jitter'].tail(10).mean()

@app.route('/getavailebility',methods=['GET','POST'])
def getavailebility():
    df = pd.read_csv(f'{Logfile}/iperf.csv',sep=',')   
    return df['Availebility'].tail(10).mean()

@app.route('/getdl',methods=['GET','POST'])
def getdl():
    df = pd.read_csv(f'{Logfile}/iperf.csv',sep=',')  
    return df['Downlink'].tail(10).mean()

@app.route('/getul',methods=['GET','POST'])
def getul():
    df = pd.read_csv(f'{Logfile}/iperf.csv',sep=',')
    return df['Uplink'].tail(10).mean()




   
@app.route('/startiperf3', methods=['GET', 'POST'])
def startsiperf3():
   try:
       uid = uuid.uuid4().hex
       print("starting iperf3")
       #job = Job.create(Startsample,args=[uid],id=uid,connection=connRedis())
       
       #r=q.enqueue_job(job)

       job = Job.create(StartExp,args=[uid],id=uid,connection=connRedis())
       
       r=q.enqueue_job(job)

       return f'starteiperf3: ok,  request_id:{uid}'
   except Exception as error:
       return errorResponse("Failed call to /startiperf3",error)


   
@app.route('/')
def home():
   try:
       print("jobs in Q: "+str(q.jobs))
       return "jobs in Q:"+str(len(q))
   except Exception as error:
       return errorResponse("Failed call to /",error)

   
   
if __name__ == '__main__':
    loadenv()

    port = int(os.environ.get('PORT', 9055))
    app.run(host = '0.0.0.0', port = port)
