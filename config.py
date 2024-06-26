import os
from functools import wraps
from dotenv import load_dotenv
import time
from datetime import datetime
from flask import jsonify
import redis
from rq import Worker, Queue, Connection
import subprocess

load_dotenv()

expq={}

os_platform = os.getenv('PLATFORM')
run_jobs={}

def get_logsize(ff):
    s = os.path.getsize(f'{ff}')
    return (int(s))

def rotate(ff,s):    
    if get_logsize(ff)>s:
        return True
    return False

def find_new(ff):
    n=1
    for i in [1,2,3,4,5,7,8,9,10,11,12,13,14,15,16]:
        if os.path.isfile(f'{ff}.{i}'):
            continue
        else:
            break
    return str(i)

def create_new(ffpath,ffname,i):
    os.rename(f'{ffpath}/{ffname}',f'{ffpath}/{ffname}.{i}')

    with open(os.path.join(f'{ffpath}',f'{ffname}'),'w') as fp:
        pass


def Merge(dict1, dict2):
    res = {**dict1, **dict2}

    return res

def trim(s):
    return s.lstrip().rstrip()


def flavor():
    cmd = f'microstack.openstack flavor list|grep einbliq'
    r=subprocess.run(f'{cmd}',capture_output=True,shell=True,text=True)
    ee = r.stdout.split('|')[1:-1]
    flavors={}
    data={}
    #data['ID']=trim(ee[0])                                                                                                                      
    data['ram']=int(trim(ee[2]))
    data['cpu']=int(trim(ee[5]))
    flavors[trim(ee[1])]=data
    data={}
    #data['ID']=trim(ee[8])                                                                                                                      
    data['ram']=int(trim(ee[10]))
    data['cpu']=int(trim(ee[13]))
    flavors[trim(ee[9])]=data

    return {'ustack':server(flavors)}

def server(flavors):
    cmd = f'microstack.openstack server list|grep einbliq'
    r=subprocess.run(f'{cmd}',capture_output=True,shell=True,text=True)
    ee = r.stdout.split('|')[1:-1]
    data={}
    data[trim(ee[5])]=trim(ee[3].split(', ')[1])
    data[trim(ee[12])]=trim(ee[10].split(', ')[1])
    for i in flavors:
        flavors[i]['IP']=data[i]
    return flavors

if os_platform == 'DOCKER':
    RedisConf = {'redishost':'172.240.20.3', 'redisport':6379}
    IperfConf = {'iperfhost':'172.240.20.2','iperfport':30955}

    LocalConf = {'Platform':'DOCKER','Logpath':'/root/5GMediaMeasure-main/Logs','logfile1':'iperf.cvs','logfile2':'iperf2.cvs','logfiletemp':'logfiletmp','nic':'eth0'}
    owampConf = {'owping':'/root/inst/bin/owping','owconf':'-c100 -i0.1 -L10 -s0 -t -AO -nm','owampdest':f'{IperfConf["iperfhost"]}'}


elif os_platform == 'INTEL1':
    RedisConf = {'redishost':'10.5.1.2', 'redisport':30379}
    IperfConf = {'iperfhost':'10.5.1.2','iperfport':30955}

    LocalConf = {'Platform':'INTEL1','Logpath':'/home/tnor/5GMediahub/Measurements/tnor_platform/Logs','logfile1':'iperf.cvs','logfile2':'iperf2.cvs','logfiletemp':'logfiletmp','nic':'ens260f0'}
    owampConf = {'owping':'/opt/bin/owping','owconf':'-c100 -i0.1 -L10 -s0 -t -AO -nm','owampdest':f'{IperfConf["iperfhost"]}'}

elif os_platform == 'HP4':
    RedisConf = {'redishost':'10.5.1.4', 'redisport':30379}
    IperfConf = {'iperfhost':'10.5.1.4','iperfport':30955}

    LocalConf = {'Platform':'HP4','Logpath':'/home/tnor/5GMediahub/Measurements/tnor_platform/Logs','logfile1':'iperf.cvs','logfile2':'iperf2.cvs','logfiletemp':'logfiletmp','nic':'ens3f0'}
    owampConf = {'owping':'/opt/bin/owping','owconf':'-c100 -i0.1 -L10 -s0 -t -AO -nm','owampdest':f'{IperfConf["iperfhost"]}'}


uc = {'UC1-netapp':'norigin-streaming', 'UC2-netapp':'ektacom-stream-selector','UC3-netapp':'ektacom-stream-selector','UC31-netapp':'ektacom-stream-selector','UC32-netapp':'ektacom-stream-selector'}
ucowner = {'UC1-owner':'norigin', 'UC2-owner':'ektacom-','UC3-owner':'ektacom','UC31-owner':'ektacom','UC32-owner':'ektacom'}

pingConf = {'clientcmd':'ping -c 12 -i 0.3','mport':9055}

G5Conf = Merge(RedisConf,IperfConf)
G5Conf = Merge(G5Conf,LocalConf)
G5Conf = Merge(G5Conf,owampConf)
G5Conf = Merge(G5Conf,pingConf)
G5Conf = Merge(G5Conf,uc)
G5Conf = Merge(G5Conf,ucowner)

microstack = {'ustack': {'einbliq-mcdncache': {'ram': 8192, 'cpu': 8, 'IP': '10.20.20.40','cpuacct': '/sys/fs/cgroup/cpuacct/machine/qemu-2-instance-0000000e.libvirt-qemu/','used_now':61}, 'einbliq-mediaplayout': {'ram': 65536, 'cpu': 32, 'IP': '10.20.20.26','cpuacct': '/sys/fs/cgroup/cpuacct/machine/qemu-1-instance-0000000d.libvirt-qemu/','used_now':61}}}

#microstack = {'ustack': {'einbliq-mcdncache': {'ram': 8192, 'cpu': 8, 'IP': '10.20.20.40'}, 'einbliq-mediaplayout': {'ram': 65536, 'cpu': 32, 'IP': '10.20.20.26'}}}
#microstack.openstack host show  5mh-intel1|grep used_now
#| 5mh-intel1 | (used_now)                       |  61 |     95744 |    1604 |
#microstack.openstack host show  5mh-intel1|grep total
#| 5mh-intel1 | (total)                       |  128 |     95744 |    1604 |

G5Conf = Merge(G5Conf,microstack)

def init_ustack():
    global G5Conf
    if os.getenv('PLATFORM') == 'INTEL1':
        myprint(mytime(),"Getting microstack parameters")
        microstack = flavor()
        myprint(mytime(),f"Microstack param ready!, {microstack}")
    else:
        print("unknown platform")

PEAK_UL = 126
PEAK_DL= 794
MAX_UL = 130.0
MAX_DL = 800.0
E2E_LATENCY = 10
TN_LATENCY = 0.14400
RAN_LATENCY = 5
RAN_SNR = 100.0
UE_PER_M2 = 1.0
RELIABILITY = 100
PACKET_ERROR_RATE = 0.0
JITTER=0.0
CAPACITY_UL = 80
CAPACITY_DL = 80
AVAILEBILITY = 100.0
MEC_CPU_USAGE = 100.0
MEC_MEM_USAGE = 100.0

fp={'CKPI-1':'PEAK_UL',
    'CKPI-2':'PEAK_DL',
    'CKPI-3':'MAX_UL',
    'CKPI-4':'MAX_DL',
    'CKPI-5':'E2E_LATENCY',
    'CKPI-6':'TN_LATENCY',
    'CKPI-7':'RAN_LATENCY',
    'CKPI-8':'RAN_SNR',
    'CKPI-9':'UE_PER_M2',
    'CKPI-10':'RELIABIL',
    'CKPI-11':'PCKT_ERR',
    'CKPI-12':'JITTER',
    'CKPI-13':'CAP_UL',
    'CKPI-14':'CAP_DL',
    'CKPI-15':'AVAIL',
    'PKPI-9':'CPU_USAG',
    'PKPI-10':'MEM_USAG'
    }

MAX_UL = 130.0
MAX_DL = 800.0
E2E_LATENCY = 10
TN_LATENCY = 0.14400
RAN_LATENCY = 5
RAN_SNR = 100.0
UE_PER_M2 = 1.0
RELIABILITY = 100
PACKET_ERROR_RATE = 0.0
JITTER=0.0
CAPACITY_UL = 80
CAPACITY_DL = 80
AVAILEBILITY = 100.0
MEC_CPU_USAGE = 100.0
MEC_MEM_USAGE = 100.0

tnor_stats ={'CKPI-1':PEAK_UL,'CKPI-2':PEAK_DL,'CKPI-3':MAX_UL,'CKPI-4':MAX_DL,'CKPI-5':E2E_LATENCY,'CKPI-6':TN_LATENCY,'CKPI-7':RAN_LATENCY,'CKPI-8':RAN_SNR,'CKPI-9':UE_PER_M2,'CKPI-10':RELIABILITY,'CKPI-11':PACKET_ERROR_RATE,'CKPI-12':JITTER,'CKPI-13':CAPACITY_UL,'CKPI-14':CAPACITY_DL,'CKPI-15':AVAILEBILITY,'PKPI-9':MEC_CPU_USAGE,'PKPI-10':MEC_MEM_USAGE}


kpis_all = {"kpis":[{"name":"CKPI-1","value":f"{PEAK_UL}","unit":"Mbps"},

                {"name":"CKPI-2","value":f"{PEAK_DL}","unit":"Mbps"},
                {"name":"CKPI-3","value":f"{MAX_UL}","unit":"Mbps"},
                {"name":"CKPI-4","value":f"{MAX_UL}","unit":"Mbps"},
                {"name":"CKPI-5","value":f"{E2E_LATENCY}","unit":"ms"},
                {"name":"CKPI-6","value":f"{TN_LATENCY}","unit":"ms"},
                {"name":"CKPI-7","value":f"{RAN_LATENCY}","unit":"ms"},
                {"name":"CKPI-8","value":f"{RAN_SNR}","unit":"%"},
                {"name":"CKPI-9","value":f"{UE_PER_M2}","unit":"devices/m2"},
                {"name":"CKPI-10","value":f"{RELIABILITY}","unit":"%"},
                {"name":"CKPI-11","value":f"{PACKET_ERROR_RATE}","unit":"%"},
                {"name":"CKPI-12","value":f"{JITTER}","unit":"ms"},
                {"name":"CKPI-13","value":f"{CAPACITY_UL}","unit":"MHz"},
                {"name":"CKPI-14","value":f"{CAPACITY_DL}","unit":"MHz"},
                {"name":"CKPI-15","value":f"{AVAILEBILITY}","unit":"%"},
                {"name":"PKPI-9","value":f"{MEC_CPU_USAGE}","unit":"%"},
                {"name":"PKPI-10","value":f"{MEC_MEM_USAGE}","unit":"%"}
]
}
kpis_txrx = {"kpis":[{"name":"CKPI-1","value":f"{PEAK_UL}","unit":"Mbps"},

                {"name":"CKPI-2","value":f"{PEAK_DL}","unit":"Mbps"},
                {"name":"CKPI-3","value":f"{MAX_UL}","unit":"Mbps"},
                {"name":"CKPI-4","value":f"{MAX_UL}","unit":"Mbps"},
                {"name":"CKPI-5","value":f"{E2E_LATENCY}","unit":"ms"},
                {"name":"CKPI-6","value":f"{TN_LATENCY}","unit":"ms"},
                {"name":"CKPI-7","value":f"{RAN_LATENCY}","unit":"ms"},
                {"name":"CKPI-8","value":f"{RAN_SNR}","unit":"%"},
                {"name":"CKPI-9","value":f"{UE_PER_M2}","unit":"devices/m2"},
                {"name":"CKPI-10","value":f"{RELIABILITY}","unit":"%"},
                {"name":"CKPI-11","value":f"{PACKET_ERROR_RATE}","unit":"%"},
                {"name":"CKPI-12","value":f"{JITTER}","unit":"ms"},
                {"name":"CKPI-13","value":f"{CAPACITY_UL}","unit":"MHz"},
                {"name":"CKPI-14","value":f"{CAPACITY_DL}","unit":"MHz"}
]
}
kpis_cpumem = {"kpis":[
                {"name":"CKPI-15","value":f"{AVAILEBILITY}","unit":"%"},    
                {"name":"PKPI-9","value":f"{MEC_CPU_USAGE}","unit":"%"},
                {"name":"PKPI-10","value":f"{MEC_MEM_USAGE}","unit":"%"}
]
}

ue_ip = {'10.7.0':'mda-go','10.6.66':'5G SA fbu'}
#ue_ip = {'10.7.0':'mda-go','10.6.66':'5G SA fbu','192.168.240':'VPN'}
ips={}
for i in ue_ip:
    ips[ue_ip[i]]=i


tcpdump_filter=f"net {ips['mda-go']}.0/24 or net {ips['5G SA fbu']}.0/24"
#tcpdump_filter=f"net {ips['mda-go']}.0/24 or net {ips['5G SA fbu']}.0/24 or net {ips['VPN']}.0/24"

def clean_osgetenv(s):
    try:
        if ord(s[0:1]) == 8220:
            return(s[1:-1])
    except:
        pass
    return s

def myprint(*args):
    line = ' '.join([str(a) for a in args])
    f = open(f'{G5Conf["Logpath"]}/nbi_measure.log','a')
    
    f.write(line+'\n')
    f.close()
    print(line)    

def mytime():
  now = datetime.now()
  return(str(now.date())+" "+str(now.time()).split('.')[0])



def logged(func):
    @wraps(func)
    def with_logging(*args, **kwargs):
        myprint(mytime(),"The function <"+func.__name__ + "> was called")
        return func(*args, **kwargs)
    return with_logging

def errorResponse(message, error):
    myprint(mytime(),f'{message}: {error}')
    return jsonify({'Status': 'Error', 'Message': message, 'Error': f'{error}'}), 403


def connect_redis(url):
    try:
        conn = redis.from_url(url)
        return conn
    except Exception as error:
        return errorResponse("Could not connect to redis",error)

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



      
#q = Queue('low',connection = connRedis(), default_timeout = 7200)


q_start = Queue('low',connection = connRedis(), default_timeout = 7200)
q_stop = Queue('default',connection = connRedis(), default_timeout = 7200)

if __name__ == '__main__':
    ss=f'tcpdump -i {G5Conf["nic"]} {tcpdump_filter} -w captest.cap'
    print(ss)
