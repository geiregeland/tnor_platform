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
prev=0
ss=0
t_prev=0
series=[]

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
            return t[-2:-1][0]
            return max(self.series)
        else:
            return 0
    def peak(self):
        if len(self.series):
            return max(self.series)
        else:
            return 0
    def min(self):
        if len(self.series):
            return min(self.series)
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
        
def human(num):
    for x in ['', 'k', 'M', 'G']:
        if num < 1000:
            return f'{num*8:3.1f} {x}bps'
        num = num/1000
    return  f'{num*8:3.1f} {x}bps'

def fromunix(t):
    return datetime.fromtimestamp(t).strftime('%H:%M:%S')

def traffic_monitor_callback(pkt):
    global prev,ss,t_prev,throughput
    
    if IP in pkt:
        pkt = pkt[IP]
        for i in ue_ip:
            if i in pkt.src or i in pkt.dst:
                index=ff(pkt.src,pkt.dst)
                if index not in throughput:
                    throughput[index] = {'ss':0,'t_prev':0,'prev':0,'series':[]}
                print(f'{fromunix(pkt.time)}: delta={(pkt.time-throughput[index]["prev"])*1000}ms, IP_src={pkt.src}, IP_dst={pkt.dst}, LEN={pkt.len}')
                if throughput[index]['prev']>0:
                    if throughput[index]['ss']+(pkt.time-throughput[index]['prev'])*1000<1:
                        throughput[index]['ss']+=(pkt.time-throughput[index]['prev'])*1000
                        throughput[index]['t_prev']+=pkt.len
                    else:
                        if throughput[index]['ss']!=0:
                            throughput[index]['series'].append(throughput[index]['t_prev']*1000/throughput[index]['ss'])
                        else:
                            delta=(pkt.time-throughput[index]['prev'])*1000
                            throughput[index]['series'].append(throughput[index]['t_prev']*1000/delta)
                            
                        throughput[index]['ss']=(pkt.time-throughput[index]['prev'])*1000
                        throughput[index]['t_prev']=pkt.len

                throughput[index]['prev']=pkt.time
                
        #traffic.update({tuple(sorted(map(atol, (pkt.src, pkt.dst)))): pkt.len})
        #print(f'time:{pkt.time}, src:{pkt.src}, dest:{pkt.dst}, len:{pkt.len}, atol:{atol(pkt.src)}')
        #for i in ue_ip:
        #  if i in pkt.src or i in pkt.dst:
        #    update(pkt.src,pkt.dst,pkt.time,pkt.len)

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

def ff(src,dst):
    return f'{src}:{dst}'



if __name__ =='__main__':

    os.makedirs(f'{Logpath}',exist_ok=True)
    tt=True
    for p in rdpcap(f'captest.pcap'):
        if p:
            #traffic_monitor_callback(p)
            traffic(p)
    print("end",p.time)
    peak_ul=0
    peak_dl=0
    for key in throughput:
        #print(key)
        src,dst=key.split(":")
        for j in ue_ip:
            if j in src:
                peak=throughput[key].max()
                if peak >peak_ul:
                    peak_ul=peak
            if j in dst:
                peak=throughput[key].max()
                if peak >peak_dl:
                    peak_dl=peak
            
        print(f'{key.replace(":","->")}, {human(throughput[key].max())}, avg:{human(throughput[key].mean())}, bytes:{throughput[key].bytes()}')
        print(human(peak_dl),human(peak_ul))
        #print(f'{key}, max:{max(value["series"])}')
    #print(throughput)
        
