import time
import subprocess
import statistics
import shlex
import iperf3 as ip3
import os
import pandas as pd
from pathlib import Path
from datetime import datetime
import requests
import math
import pickle
import random
from rq import get_current_job
from rq.job import Job
from scapy.all import rdpcap,IP

from cpumem import _cpu_usage as vcpu
from cpumem import _system_usage as cpu
from cpumem import _system_mem as total_mem
from cpumem import _virtual_mem as virtual_mem
from cpumem import _used_mem as used_mem
from cpumem import availebility
from cpumem import get_data as cpumem
from cpumem import cpu_percent as cpupercent

from config import G5Conf
from config import tnor_stats,kpis,myprint
from config import ue_ip
from config import tcpdump_filter
from config import logged, mytime,errorResponse
from config import clean_osgetenv
from config import connRedis as myredis
from config import q_start, q_stop
from config import expq

Logfile = G5Conf['Logpath']
Logpath = G5Conf['Logpath']
ServerPort = G5Conf['iperfport']
ServerAddress = G5Conf['iperfhost']
MeasurePort = G5Conf['mport']
nic = G5Conf['nic']


timestamps={}
throughput={}
first = 0


def gstate(data):
    return data['state']



def Stop(uid):
    job = q_start.fetch_job('startq')
    job.meta['q'][uid]['active']=0
    job.meta['q'][uid]['state']='END'
    job.save_meta()
    
def Start(meta):
    results={}
    myprint(mytime(),meta)
    uid=meta['test_case_id']
    
    job = get_current_job()
    results['start_time'] = get_timestamp()
    results['uid'] = meta['test_case_id']
    use_case = meta['use_case']
    uid = meta['test_case_id']
  
    process = subprocess.Popen(shlex.split(f'cat /sys/class/net/{nic}/statistics/tx_bytes'),stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    for line in process.stdout:
        results['tx'] = 8*int(line)
  
    process = subprocess.Popen(shlex.split(f'cat /sys/class/net/{nic}/statistics/rx_bytes'),stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    for line in process.stdout:
        results['rx'] = 8*int(line)
    results['tx_max'] = 0
    results['rx_max'] = 0
    results['MEC CPU max'] = round(cpupercent(use_case),5)
    results['MEC MEM max'] = round(100*cpumem(use_case,"MEM")/total_mem(),5)
    results['availebility'] = availebility()
    

    timer = 3600
    p_tcpdump={}
    
    while len(job.meta['q'])>0 and timer>0:
        act=0
        endjobs=[]
        
        for key,value in job.meta['q'].items():
            if gstate(value) == 'RUN':
                act+=1
                results = value['results']
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
      
                tmp = round(cpupercent(use_case),5)
                if tmp > results['MEC CPU max']:
                    results['MEC CPU max'] = tmp

                tmp = round(100*cpumem(use_case,"MEM")/total_mem(),5)
                if tmp > results['MEC MEM max']:
                    results['MEC MEM max'] = tmp
                results['availebility'] = availebility()
                
                #job.meta['q'][key]['results'] = results.copy()
                #job.save_meta()
                #do_measure()
                #job.meta['q'][key]['checked']='OK'
                #job.save_meta()
            #elif gstat(value) == 'RUN_REPORT':
            #    p_tcpdump[key].terminate()
            #    report_job = Job.create(register_kpi,args=[meta],id=i,connection=myredis())
            #    r=q_stop.enqueue_job(report_job)
            #    ii=int(value['report_index'])
            #TODO: set report_index if RUN_REPORT
            #    ii+=1
            #    value['report_index']=ii
            #    p = subprocess.Popen(['tcpdump',  '-i', nic, '-s96',tcpdump_filter,'-w', f'{Logpath}/cap_{key}_{ii}.pcap'], stdout=subprocess.PIPE)
   #             p_tcpdump[key] = p

                
            elif gstate(value) == 'START':
                myprint(mytime(),"New job started: ",meta)

                job.meta['q'][key]['state'] = 'RUN'
                results['uid']=key
                job.meta['q'][key]['results'] = results.copy()
                p = subprocess.Popen(['tcpdump',  '-i', nic, '-s96',tcpdump_filter,'-w', f'{Logpath}/cap_{key}.pcap'], stdout=subprocess.PIPE)
                p_tcpdump[key] = p

                job.save_meta()
                myprint(mytime(),"Job queue: ",job.meta['q'])
            elif gstate(value) == 'END':
                myprint(mytime(),f'Ending test_case_id:{key}')
                endjobs.append(key)
            else:
                print("no match")
                
        myprint(mytime(),f'Number of measurements in Q:{len(job.meta["q"])}, Active jobs:{act}')
        time.sleep(1.0)
        job.refresh()
        for key,value in job.meta['q'].items():
            if job.meta['q'][key]['state'] == 'RUN':
                job.meta['q'][key]['results'] = results.copy()
                job.save_meta()
        
        #check if tcpdump should be stopped
      
        myprint(mytime(),"tcpdump queue",p_tcpdump)
        for i in endjobs:
            p_tcpdump[i].terminate()
            p_tcpdump.pop(i)
            meta=job.meta['q'].pop(i)
            job.save_meta()
            stop_job = Job.create(register_kpi,args=[meta],id=i,connection=myredis())
            r=q_stop.enqueue_job(stop_job)
            

        job.refresh()

        
        #print(job.meta['q'])
        timer-=1
        
    return
    #p.terminate()

    
@logged
def register_kpi(meta):
    uid=meta['test_case_id']
    results=meta['results']
    job = get_current_job()
    try:
        os.makedirs(f'{Logpath}',exist_ok=True)
        for p in rdpcap(f'{Logpath}/cap_{uid}.pcap'):
            if p:
                traffic(p)
    except Exception as error:
        myprint(mytime(),f'no packets captured for throughput measurement')
        #print(mytime(),f'No packets captured in file: {Logpath}/cap_{uid}.pcap')


    peak_ul = 0
    peak_dl = 0
    ip_dl=''
    ip_ul=''
    for i in throughput:
        if len(throughput[i].series)>0:
            src,dst = i.split(':')
            for j in ue_ip:
                if j in src:
                    peak = throughput[i].max()
                    if peak > peak_ul:
                        peak_ul = peak
                        ip_ul=src
                if j in dst:
                    peak = throughput[i].max()
                    if peak > peak_dl:
                        peak_dl = peak
                        ip_dl = dst

    #call update here and read tcpdump pcap file for finding peak UL/DL per IP dst
    tnor_stats['CKPI-1'] = round(peak_ul*8/1000000,2)
    tnor_stats['CKPI-2'] = round(peak_dl*8/1000000,2)
    #tnor_stats['CKPI-1'] = results['rx_max']/1000000
    #tnor_stats['CKPI-2'] = results['tx_max']/1000000
    tnor_stats['CKPI-15'] = round(results['availebility'],2)
    tnor_stats['PKPI-11'] = round(results['MEC CPU max'],2)
    tnor_stats['PKPI-12'] = round(results['MEC MEM max'],2)

    uc_kpi = kpis.copy()
  
    for i in tnor_stats:
        for j in uc_kpi["kpis"]:
            if j["name"] == i:
                j["value"] = tnor_stats[i]

    meta['kpis'] = uc_kpi
    if meta['regkpi']:
        registerkpis(meta)
    job.meta['data'] = meta.copy()
    job.save_meta()
    
    myprint(mytime(),f'Ending job.......')
    myprint(mytime(), tnor_stats)
    myprint(mytime(),f'{ip_dl}: UL:{human(peak_ul)} - {ip_ul}:DL:{human(peak_dl)}')
    file = open(f'{G5Conf["Logpath"]}/{G5Conf["logfiletemp"]}','wb')
    myprint(uc_kpi)
    pickle.dump(uc_kpi,file)
    file.close()

    if os.path.isfile(f'{Logpath}/cap_{uid}.pcap'):
        os.remove(f'{Logpath}/cap_{uid}.pcap')

    
@logged
def get_kpis():
  return kpis

def ff(src,dst):
    return f'{src}:{dst}'



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
        if num < 1000:
            return f'{num*8:3.1f} {x}bps'
        num = num/1000
    return  f'{num*8:3.1f} {x}bps'


def traffic_monitor_callback(pkt):
    if IP in pkt:
        pkt = pkt[IP]
        #traffic.update({tuple(sorted(map(atol, (pkt.src, pkt.dst)))): pkt.len})
        #print(f'time:{pkt.time}, src:{pkt.src}, dest:{pkt.dst}, len:{pkt.len}, atol:{atol(pkt.src)}')
        for i in ue_ip:
          if i in pkt.src or i in pkt.dst:
            update(pkt.src,pkt.dst,pkt.time,pkt.len)

class Measure:
    def __init__(self,src_dst):
        self.ss=0
        self.t_prev=0
        self.prev=0
        self.series=[]
        self.srcdst=src_dst
        self.t_start=0
        self.t_end=0
        self.t_max=0
        self.t_min=0
        self.t_mean=0
        self.t_len=0
        
    def time_delta_one_ms(self,pkt):
        return self.ss+(pkt.time-self.prev)*1000<100        
    def add_to_time_window(self,pkt):
        self.ss+=(pkt.time-self.prev)*1000
        self.t_prev+=int(pkt[IP].len)
        self.t_len+=int(pkt[IP].len)
        return

    def add_series(self,pkt):
        if self.ss!=0:
            self.series.append(self.t_prev*1000/self.ss)
        else:
            delta=(pkt.time-self.prev)*1000
            self.series.append(self.t_prev*1000/delta)
        self.ss=(pkt.time-self.prev)*1000
        self.t_prev=int(pkt[IP].len)

        return
    def set_prev(self,pkt):
        self.prev=pkt.time
        return
    def set_start(self,pkt):
        self,t_start=pkt.time
    def set_end(self,pkt):
        self.t_end=0
    def max(self):
        if len(self.series)>2:
            t=self.series
            t.sort()
            return float(str(t[-2:-1][0]))
            #return max(self.series)
        else:
            return 0
    def peak(self):
        if len(self.series):
            return max(self.series)
        else:
            return 0
    def min(self):
        if len(self.series):
            return float(str(min(self.series)))
        else:
            return 0
    def mean(self):
        if len(self.series):
            return self.t_len/(self.t_end-self.t_start)
            #return sum(self.series)/len(self.series)
        else:
            return 0
    def bytes(self):
        return self.t_len
    
def traffic(pkt):
    global throughput
    
    if IP in pkt:
        ip = pkt[IP]
        for i in ue_ip:
            if i in ip.src or i in ip.dst:
                index=ff(ip.src,ip.dst)
                if index not in throughput:
                    throughput[index] = Measure(pkt)
                    throughput[index].t_start=pkt.time
                if throughput[index].prev>0:
                    if throughput[index].time_delta_one_ms(pkt):
                        throughput[index].add_to_time_window(pkt)
                    else:
                        throughput[index].add_series(pkt)

                throughput[index].prev=pkt.time
                throughput[index].t_end=pkt.time
                break


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
    print(meta)
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
