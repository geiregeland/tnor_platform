import os
import time
import subprocess
from flask import Flask, session, flash, json, request,jsonify,redirect
from rq.job import Job 
from datetime import datetime,timedelta
import redis
from rq import Worker, Queue, Connection
from pathlib import Path
#from functools import wraps
import requests
import rq_dashboard
import random


from dotenv import load_dotenv as loadenv

from config import myprint,logged, mytime,errorResponse
from config import G5Conf
from config import clean_osgetenv
from config import connRedis
from config import expq, q_start,q_stop
#from n2 import Start
from sniff import Start,Stop
from config import init_ustack

init_ustack()

Logfile = G5Conf['Logpath']
PLATFORM = G5Conf['Platform']

server={'UC1':'10.5.1.4','UC2':'10.5.1.4','UC3':'10.5.1.2'}

if PLATFORM == 'HP4':
    import flask_monitoringdashboard as dashboard


ServerPort = G5Conf['iperfport']
ServerAddress = G5Conf['iperfhost']
MeasurePort = G5Conf['mport']
    

app = Flask(__name__)
if PLATFORM == 'HP4':
    dashboard.config.init_from(file='config.cfg')
    dashboard.bind(app)

# Configuration Variables
redishost = G5Conf['redishost']
redisport = G5Conf['redisport']

app.config["DEBUG"] = True
app.config["RQ_DASHBOARD_REDIS_PORT"] = redisport
app.config["RQ_DASHBOARD_REDIS_URL"] = f"redis://{redishost}:{redisport}"

#pwd_get= subprocess.run(['pwd'],check=True,text=False,stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#app.config['UPLOAD_FOLDER'] = pwd_get.stdout.decode('utf-8')[:-1]+"/uploades"

app.config.from_object(rq_dashboard.default_settings)
if PLATFORM == 'HP4':
    rq_dashboard.web.setup_rq_connection(app)
app.register_blueprint(rq_dashboard.blueprint,url_prefix='/rq')

      
@app.route('/v1/parameters',methods=['POST','GET'])
@logged
def parameters():
    print(request)
    print(request.form)
    
    myprint(mytime(),request)
    try:
        arguments = request.json
        action = arguments['action']
        #explength=arguments['delta']
        use_case = arguments['use_case']
        test_case = arguments['test_case']
        test_case_id=arguments['test_case_id']
        try:
            regkpi=arguments['regkpi']
            regkpi=False
        except:
            regkpi=True

        myprint(mytime(),"json=",request.json)
        myprint(mytime(),f'action:{action}, use_case:{use_case}, test_case:{test_case},test_case_id:{test_case_id}')
        
        if request.method == 'POST':
            if action == 'start':
                r = requests.get(f'http://{server[use_case]}:9055/startexperiment/',json={'use_case':use_case,'test_case':test_case,'test_case_id':test_case_id,'regkpi':regkpi})
                myprint(mytime(),f'start status:{r.content}')
            elif action == 'stop':
                r = requests.get(f'http://{server[use_case]}:9055/stopexperiment/',json={'use_case':use_case,'test_case':test_case,'test_case_id':test_case_id})
                myprint(mytime(),f'stop status:{r.content}')
        elif request.method == 'GET':
            fetched_job = q_stop.fetch_job(test_case_id)
            
            print(f"job id={id}, status={fetched_job.get_status()},  results={fetched_job.result},meta:{fetched_job.meta}")

        
        return f'200 OK'
    
    except Exception as error:
        return errorResponse("Failed call to /parameters",error)


@app.route('/stopexperiment/',methods = ['GET','POST'])
@logged
def stop():
    arguments = request.json

    use_case = arguments['use_case']
    test_case = arguments['test_case']
    test_case_id=arguments['test_case_id']
    meta={}
    meta['use_case'] = arguments['use_case']
    meta['test_case'] = arguments['test_case']
    meta['test_case_id']=arguments['test_case_id']
    
    Stop(meta)
    return f'OK',200
    uid = test_case_id
    job = q_start.fetch_job('startq')
    if job != None:
        job.meta['q'][uid]['active']=0    
        job.meta['q'][uid]['state']='END'

        job.save_meta()

        expq.pop(uid)
        return f'OK 200'
    else:
        return f'Error 500'

@app.route('/startexperiment/',methods = ['GET','POST'])
@logged
def start():
    arguments = request.json
    use_case = arguments['use_case']
    test_case = arguments['test_case']
    test_case_id=arguments['test_case_id']
    uid = test_case_id
    meta={}
    meta['active'] = 1
    meta['use_case'] = use_case
    meta['test_case'] = test_case
    meta['test_case_id'] = uid
    meta['start'] = get_timestamp()
    meta['state'] = 'START'
    meta['regkpi'] = arguments['regkpi']
    Start(meta)
    return f'OK',200

    if len(expq):
        try:
            dummy=expq[uid]
            myprint(mytime(),f'Error: test_case_id already exist: {uid}')
            return f'ERROR: Experiment exist {uid}'        
        except:
            myprint(mytime(),f'Adding new measurement: {uid}')
        expq[uid] = meta
        job = q_start.fetch_job('startq')

        
        job.meta['q'][uid]=meta
        job.save_meta()
    else:
        expq[uid] = meta
        myprint(mytime(),f'Starting up measurement queue with first use_vase_id:{uid}')
        job = Job.create(Start,args=[meta],id='startq',connection=connRedis())
        job.meta['q']={}
        job.meta['q'][uid]=meta
        job.save_meta()
        #job.refresh()
        r=q_start.enqueue_job(job)
    return f'OK',200

def get_timestamp():
    return datetime.utcnow().isoformat().split('.')[0]+'Z'


if __name__ == '__main__':
    loadenv()

    port = int(os.environ.get('PORT', 9055))
    app.run(host = '0.0.0.0', port = port)

