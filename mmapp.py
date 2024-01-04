import time
from functools import wraps
import subprocess
import statistics
import shlex
#from worker import errorResponse
import iperf3 as ip3
import os
import pandas as pd
from pathlib import Path
from datetime import datetime
import requests
from config import G5Conf
import math
import pickle
from rq import get_current_job
from cpumem import _cpu_usage as vcpu
from cpumem import _system_usage as cpu

from cpumem import _system_mem as total_mem
from cpumem import _virtual_mem as virtual_mem
from cpumem import _used_mem as used_mem
from cpumem import availebility
from scapy.all import *

from config import tnor_stats,kpis,myprint
from config import ue_ip

Logfile = G5Conf['Logpath']
Logpath = G5Conf['Logpath']
ServerPort = G5Conf['iperfport']
ServerAddress = G5Conf['iperfhost']
MeasurePort = G5Conf['mport']
owping = G5Conf['owping']
nic = G5Conf['nic']
duration = 5 #5s if iperf

timestamps={}
throughput={}
first = 0

def ff(src,dst):
    return f'{src}:{dst}'


def mytime():
  now = datetime.now()
  return(str(now.date())+" "+str(now.time()).split('.')[0])



def logged(func):
    @wraps(func)
    def with_logging(*args, **kwargs):
        myprint(mytime(),"The function <"+func.__name__ + "> was called")
        return func(*args, **kwargs)
    return with_logging


def update(src,dst,t,data):
    global first
    try:
        current = throughput[ff(src,dst)]
        delta = t - timestamps[ff(src,dst)] #sec since epoch
        new = data/delta
        if new > current['peak']:
            throughput[ff(src,dst)]['peak'] = new
        timestamps[ff(src,dst)] = t
        throughput[ff(src,dst)]['stamp'] = t
        throughput[ff(src,dst)]['last_t'] = t
        throughput[ff(src,dst)]['data'] += data
    except:
        if not first:
            first = t
        item={}
        item['first_t'] = first
        item['stamp'] = t
        item['last_t'] = t
        item['data'] = data
        item['peak'] = 0
        timestamps[ff(src,dst)] = t
        throughput[ff(src,dst)] = item


def human(num):
    for x in ['', 'k', 'M', 'G']:
        if num < 1000.:
            return f'{num*8:3.1f} {x}bps'
        num /= 1000.
    return  f'{num*8:3.1f} {x}bps'


def traffic_monitor_callback(pkt):
    if IP in pkt:
        pkt = pkt[IP]
        #traffic.update({tuple(sorted(map(atol, (pkt.src, pkt.dst)))): pkt.len})
        #print(f'time:{pkt.time}, src:{pkt.src}, dest:{pkt.dst}, len:{pkt.len}, atol:{atol(pkt.src)}')
        for i in ue_ip:
          if i in pkt.src or i in pkt.dst:
            update(pkt.src,pkt.dst,pkt.time,pkt.len)


@logged
def StartExp(uid):
  results = {}
  job = get_current_job()
  myprint(mytime(),f'{job.meta["active"]}')
  results['start_time'] = datetime.now()
  results['uid'] = uid
  process = subprocess.Popen(shlex.split(f'cat /sys/class/net/{nic}/statistics/tx_bytes'),stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
  for line in process.stdout:
    results['tx'] = 8*int(line)
  
  process = subprocess.Popen(shlex.split(f'cat /sys/class/net/{nic}/statistics/rx_bytes'),stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
  for line in process.stdout:
    results['rx'] = 8*int(line)

  results['tx_max'] = 0
  results['rx_max'] = 0
  results['MEC CPU max'] = round(vcpu()/cpu()*100,5)
  results['MEC MEM max'] = round(virtual_mem()/total_mem()*100,5)
  results['Availebility'] = availebility()

  #kill measurement after 1 hour
  runtime = 3600

  p = subprocess.Popen(['tcpdump',  '-i', nic, '-w', f'{Logpath}/cap.pcap'], stdout=subprocess.PIPE)
  
  while job.meta['active'] and runtime>0:
    #print(mytime(),f'Job is active {job.meta["active"]}')
    time.sleep(1)
    job.refresh()
    runtime-=1

    #check if tcpdump should be stopped
    process = subprocess.Popen(shlex.split(f'cat /sys/class/net/{nic}/statistics/tx_bytes'),stdout=subprocess.PIPE,stderr=subprocess.STDOUT)    
    for line in process.stdout:
      tmp  = 8*int(line)
    if tmp - results['tx'] > results['tx_max']:
      results['tx_max'] = tmp - results['tx']
      results['tx'] = tmp
      
    process = subprocess.Popen(shlex.split(f'cat /sys/class/net/{nic}/statistics/rx_bytes'),stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    for line in process.stdout:
      tmp  = 8*int(line)
    if tmp - results['rx'] > results['rx_max']:
      results['rx_max'] = tmp - results['rx']
      results['rx'] = tmp

      
    tmp = round(vcpu()/cpu()*100,5)
    if tmp > results['MEC CPU max']:
      results['MEC CPU max'] = tmp

    tmp = round(virtual_mem()/total_mem()*100,5)
    if tmp > results['MEC MEM max']:
      results['MEC MEM max'] = tmp
    results['availebility'] = availebility()

  p.terminate()
  for p in PcapReader(f'{Logpath}/cap.pcap'):
    traffic_monitor_callback(p)

  peak_ul = 0
  peak_dl = 0
  ip_dl=''
  ip_ul=''
  for i in throughput:
      if throughput[i]['peak']>0:
          src,dst = i.split(':')
          for j in ue_ip:
              if j in src:
                  peak = throughput[i]['peak']
                  if peak > peak_ul:
                      peak_ul = peak
                      ip_ul=src
              if j in dst:
                  peak = throughput[i]['peak']
                  if peak > peak_dl:
                      peak_dl = peak
                      ip_dl = dst

  #call update here and read tcpdump pcap file for finding peak UL/DL per IP dst
  tnor_stats['CKPI-1'] = round(peak_ul*8/1000000,2)
  tnor_stats['CKPI-2'] = round(peak_dl*8/1000000,2)
  #tnor_stats['CKPI-1'] = results['rx_max']/1000000
  #tnor_stats['CKPI-2'] = results['tx_max']/1000000
  tnor_stats['CKPI-15'] = results['availebility']
  tnor_stats['PKPI-9'] = results['MEC CPU max']
  tnor_stats['PKPI-10'] = results['MEC MEM max']

  uc_kpi = kpis.copy()
  
  for i in tnor_stats:
    for j in uc_kpi["kpis"]:
      if j["name"] == i:
        j["value"] = tnor_stats[i]
  job.meta['kpis'] = uc_kpi
  job.save_meta()
  job.refresh()
    
  myprint(mytime(),f'Ending job.......')
  myprint(mytime(), tnor_stats)
  myprint(mytime(),f'{ip_dl}: UL:{human(peak_ul)} - {ip_ul}:DL:{human(peak_dl)}')
  file = open(f'{G5Conf["Logpath"]}/{G5Conf["logfiletemp"]}','wb')
  myprint(results)
  pickle.dump(results,file)
  file.close()

@logged
def get_kpis():
  return kpis
  
#----------------------- old stuff below -------------------------


def rxtx(uid):
    return 0

def getLogfile():
    try:
        os.makedirs(Logfile,exist_ok=True)
    except Exception as error:
        print(mytime(),f'Directory {Logfile} can not be created')

    if not os.path.exists(f'{Logfile}/iperf.csv'):
        df = pd.DataFrame({'Date': pd.Series(dtype='str'),
                           'Id':pd.Series(dtype=str),
                   'Uplink': pd.Series(dtype='float'),
                   'Downlink': pd.Series(dtype='float'),
                   'peak_tx': pd.Series(dtype='float'),
                   'peak_rx': pd.Series(dtype='float'),
                   'rx_std': pd.Series(dtype='float'),
                   'tx_std': pd.Series(dtype='float'),
                   'average_rx': pd.Series(dtype='float'),
                   'average_tx': pd.Series(dtype='float'),
                   'RTT':pd.Series(dtype='float')})
        df['Date']=pd.to_datetime(df.Date)
        df.to_csv(f'{Logfile}/iperf.csv', sep=',', encoding='utf-8',index=False)

    else:
        df = pd.read_csv(f'{Logfile}/iperf.csv',sep=',')
        print(mytime(),f'Reading file {Logfile}/iperf.csv')


        
@logged
def iperfclient():
    print(mytime(),f"Starting iperf3 server - Server:{ServerAddress}:{MeasurePort}")
    r= requests.get(f'http://{ServerAddress}:{MeasurePort}/startiperf3')
    
    uid = r.content.decode('utf-8').split(':')[1]

    if not 'starteiperf3: ok' in r.content.decode('utf-8'):
        print(mytime(),"Could not start iperf3 server")
  
    time.sleep(1)

    client = ip3.Client()
    client.server_hostname = ServerAddress
    client.zerocopy = True
    client.verbose = False
    client.reverse = False
    client.duration = duration
    print(f'Serverport: {ServerPort}')
    client.port = ServerPort
    #client.num_streams = 10
    print(mytime(),"Starting iperf3 client run 1")
    results = client.run()

    l=results.json
    print(l)

    time.sleep(5)
    client.reverse=True

    print(mytime(),"Starting iperf3 client run 2")

    results=client.run()
    l=results.json
    print(l)

    time.sleep(2)
    print(mytime(),"Starting ping test")

    rtt=ping_addr(ServerAddress)

    print(mytime(),f'Registering RTT result: {rtt}')

    r = requests.get(f'http://{ServerAddress}:{MeasurePort}/registerping/{uid}', json={'RTT':f'{rtt}'})

    if not 'registerping: ok' in r.content.decode('utf-8'):
        print(mytime(),f"Could not register RTT: {r.content}")

    return

    results = owamp(ServerAddress)

    print(mytime(),f'Registering OWAMP result: {results}')

    r = requests.get(f'http://{ServerAddress}:{MeasurePort}/registerowamp/{uid}', json={'availebility':f'{results["A"]}','delay':f'{results["mmedi"]}','jitter':f'{results["jitter"]}'})
    #register 
    #print(str(r.content.decode('utf-8')))
    #print('registerowamp: ok')
    if 'registerowamp: ok' != str(r.content.decode('utf-8')):
        print(mytime(),"Could not register OWAMP")



@logged
def ping_addr(dest):
    results=[]
    try:
        process = subprocess.Popen(shlex.split(f"ping -c 12 -i 0.3 {dest}"),stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        pipe=process.stdout

        for line in pipe:
            line = line.decode('utf-8')
            if 'ttl' in line:
                line=line.split("time=")[1].split(" ms")[0]

                results.append(float(line))
        results.sort()
        return statistics.mean(results[1:-1])
    except Exception as error:
        print(mytime(),f"Error in process: {error}")
        return 0

@logged
def owamp(dest):
    results={}
    try:
        process = subprocess.Popen(shlex.split(f'{owping} -c100 -i0.1 -L10 -s0 -t -AO -nm {dest}'),stdout=subprocess.PIPE,stderr=subprocess.STDOUT)

        pipe=process.stdout
        for line in pipe:
            line = line.decode('utf-8')
            if 'sent' in line:
                tmp=line.split(',')
                sent=tmp[0].split(' ')[0].strip()
                loss=tmp[1].split(' ')[1].strip()
                results['sent'] = sent
                results['loss'] = loss
            if 'delay' in line:
                tmp=line.split('max =')[1]
                mmin=tmp.split('/')[0].strip()
                mmedi=tmp.split('/')[1].strip()
                mmax=tmp.split('/')[2].split(' ms')[0].strip()
                results['mmedi'] = mmedi
            if 'jitter' in line:
                tmp=line.split(' = ')[1]
                jitter=tmp.split(' ms')[0].strip()
                results['jitter'] = jitter

    except Exception as error:
        print(mytime(),f"Error in owping process: {error}")
        return 0
    #calculate awailebility
    A  = (float(sent)-float(loss))/float(sent)
    results['A'] = A

    return results


        
@logged
def iperf3Throughput(uid):
    time.sleep(1)
    s = ip3.Server()
    s.port = ServerPort
    print("starting iperfserver at:",ServerAddress)
    s.bind_address = ServerAddress
    s.json_output = True

    results=s.run()
    l=results.json
    uplink=l['end']['streams'][0]['receiver']['bits_per_second']

    print(mytime(),f"uplink:{uplink}")

    results=s.run()
    l=results.json
    downlink=l['end']['streams'][0]['sender']['bits_per_second']

    print(mytime(),f"downlink:{downlink}")
    return {'Date':[datetime.now().strftime("%Y-%d-%m %H:%M:%S")],'Uplink':[uplink],'Downlink':[downlink],'Id':uid}





def Startsample(uid):
    df = getLogfile()

    sample = iperf3Throughput(uid)
    #s = ip3.Server()
    #s.port = ServerPort
    #print("starting iperfserver at:",ServerAddress)
    #s.bind_address = ServerAddress
    #s.json_output = True

    #results=s.run()
    #l=results.json
    #uplink=l['end']['streams'][0]['receiver']['bits_per_second']

    #print(mytime(),f"uplink:{uplink}")

    #results=s.run()
    #l=results.json
    #downlink=l['end']['streams'][0]['sender']['bits_per_second']

    #print(mytime(),f"downlink:{downlink}")
    #sample= {'Date':[datetime.now().strftime("%Y-%d-%m %H:%M:%S")],'Uplink':[uplink],'Downlink':[downlink]}

    df = pd.concat([df,pd.DataFrame(sample,columns=['Date','Uplink','Downlink','RTT','Id'])])
    df.to_csv(f'{Logfile}/iperf.csv', sep=',', encoding='utf-8',index=False)
    print(mytime(),df)

    #df.loc[df['sample_id'] == 'uuid','jitter']=jitter
    #df.loc[df['sample_id'] == 'uuid','RTT']=RTT

def getjitter():
        df = pd.read_csv(f'Logs/iperf2.csv',sep=';')
        jitter = 0
        print(df['Jitter'].tail(10).mean())

        return jitter


#if __name__=='__main__':
   #owamp(ServerAddress)
   # getjitter()
   #iperfclient()
