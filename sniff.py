import sys
import string
from threading import Thread
import pcapy
from pcapy import findalldevs, open_live
import impacket
from impacket.ImpactDecoder import EthDecoder, LinuxSLLDecoder,IPDecoder
import time
import datetime
from config import G5Conf,tcpdump_filter,ue_ip,ips
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

from cpumem import _cpu_usage as system_cpu_usage
from cpumem import _host_num_cpus as host_num_cpus
from cpumem import get_num_cpus as get_num_vcpus
from cpumem import get_idle as idle_cpu 
from cpumem import ssh_conn,ssh_cmd,ssh_close
from cpumem import para_ssh_conn

from config import G5Conf
from config import tnor_stats,kpis_all,kpis_txrx,kpis_cpumem,myprint
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

try:
    FREQ  = float(os.getenv('FREQ'))
except:
    FREQ=1
    
Experiments={}

def get_timestamp():
    return datetime.utcnow().isoformat().split('.')[0]+'Z'

def human(num):
    for x in ['', 'k', 'M', 'G']:
        if num < 1000:
            return f'{num*8:3.1f} {x}bps'
        num = num/1000
    return  f'{num*8:3.1f} {x}bps'


class ExperimentObj():
    def __init__(self,meta):
        self.meta = meta
        self.use_case = meta['use_case']
        self.test_case = meta['test_case']
        self.test_case_id = meta['test_case_id']
        self.sniffer=None
        self.txrx_sampler=None
        self.cpumem_sampler=None
        self.active=False
        self.txrx_results={}
        self.cpumem_results={}

    def start(self):
        p = open_live(nic, 100, 1, 100)
        p.setfilter(tcpdump_filter)
        
        #print("Listening on %s: net=%s, mask=%s, linktype=%d" % (dev, p.getnet(), p.getmask(), p.datalink()))

        # Start sniffing thread and finish main thread.
        print(f'Starting sniffing for test id: {self.test_case_id}')
        self.sniffer=DecoderThread(p,nic)
        self.txrx_sampler=SampleTXRX(self.sniffer)
        self.txrx_sampler.init(self.meta)
        self.cpumem_sampler=SampleCPUMEM()
        self.cpumem_sampler.init(self.meta)
        self.sniffer.start()
        self.txrx_sampler.start()
        self.cpumem_sampler.start()

    def stop(self):
        print("Stopping experiment")
        self.txrx_sampler.stop()
        self.txrx_sampler.registerkpi()
        time.sleep(0.1)
        self.cpumem_sampler.stop()
        self.cpumem_sampler.registerkpi()
        
        self.txrx_results=self.txrx_sampler.get_results()
        self.sniffer.stop()
        #for i,m in self.sniffer.tcpdump.items():
        #    p_max=human(m.max())
        #    p_min=human(m.min())
        #    p_mean=human(m.mean())
        #print(p_max, p_min, p_mean)
        #print(self.sampler.get_results())


class Measure:
    def __init__(self,src_dst,t_stamp,p_len):
        self.srcdst=src_dst
        self.t_start=t_stamp
        self.t_end=0
        self.t_len=p_len        
        self.totlen=p_len
        self.samples=[]

        
    def add(self,p_len,t_stamp):
        self.t_len+= p_len        
        self.t_end = t_stamp
        self.totlen+= p_len
        
    def flush(self):
        self.t_len=0

    def mean(self):
        return self.totlen/(self.t_end-self.t_start)

    def max(self):
        if len(self.samples):
            return max(self.samples)
        else:
            return 0
        
    def min(self):
        if len(self.samples):
            return min(self.samples)
        else:
            return 0

class uStackObj(Thread):
    def __init__(self,netapp):
        self.id=[]
        self.netapp=netapp
        self.active=True
        self.t_start=time.time()
        Thread.__init__(self)

    def run(self):
        while self.active:
            self.get_config()
            time.sleep(FREQ)

    def stop(self):
        self.active=0

    def get_data(self,data):
        res=[]
        for i in self.id:
            res.append(i[data])
        return res
        
                    
    def get_config(self):
        id=[]
        cmd=f'microstack.openstack flavor list|grep {self.netapp}'
        r=subprocess.run(cmd,capture_output=True,shell=True,text=True)
        for i in r.stdout.split('\n')[0:-1]:
            d=i.split('|')
            vm={}
            vm['id']=''
            vm['ram'] = int(d[3])
            vm['vcpu'] = int(d[6])
            name=d[2].replace(' ','')
            vm['name']=name
            id.append(vm)
        print(id)
        for i,j in enumerate(id):
            cmd=f'microstack.openstack server list |grep {j["name"]}'
            r=subprocess.run(cmd,capture_output=True,shell=True,text=True)
            idd=r.stdout.split('|')[1].replace(' ','')
            print(idd)
            id[i]['id'] = idd
        print(id)
        for j,i in enumerate(id):
            cmd=f'microstack.openstack server show {i["id"]} |grep OS-EXT-SRV-ATTR:instance_name'
            r=subprocess.run(cmd,capture_output=True,shell=True,text=True)
            instance = r.stdout.split("|")[2]
            cmd2=f'ls /sys/fs/cgroup/cpuacct/machine/|grep {instance}'
            r=subprocess.run(cmd2,capture_output=True,shell=True,text=True)
            d=r.stdout.split('\n')[0]
            #print(f'{i["name"]}',open(f'/sys/fs/cgroup/cpuacct/machine/{d}/cpuacct.usage').read())
            id[j]['cpuacct']=f'/sys/fs/cgroup/cpuacct/machine/{d}/cpuacct.usage'
        self.id=id
        print(self.id)
    
class SampleCPUMEM(Thread):
    def __init__(self):
        self.active=True
        self.sample=time.time()
        self.t_start=time.time()
        self.t_reg=time.time()
        self.last_cpu_usage=None
        self.last_system_usage=None
        Thread.__init__(self)
        
    def run(self):
        cpu=True
        while self.active:
            if time.time()-self.sample>FREQ/12:
                if cpu:
                    self.cpu_sample()
                    cpu=False
                else:
                    self.mem_sample()
                    cpu=True
                if time.time()-self.t_reg>FREQ-1:
                    self.registerkpi()
                    self.clear_results()
                    self.t_reg=time.time()
                self.sample=time.time()
            if time.time()-self.t_start>3600:
                self.active=0
    def stop(self):
        self.active=0
        if os.getenv('PLATFORM') == 'INTEL1':
            for ssh_session in self.sshconnections:
                ssh_session.close()
        
    def init(self,meta):
        self.results={}
        self.results['start_time'] = get_timestamp()
        self.results['uid'] = meta['test_case_id']
        self.test_case_id = meta['test_case_id']
        self.use_case = meta['use_case']
        self.uid = meta['test_case_id']
        self.meta=meta.copy()
        self.results['MEC CPU max'] = 0.0 #round(cpupercent(self.use_case),5)
        self.results['MEC MEM max'] = 0.0 #round(100*cpumem(self.use_case,"MEM")/total_mem(self.use_case),5)
        self.results['availebility'] = 0.0 #100*availebility()
        if os.getenv('PLATFORM') == 'INTEL1':
            self.sshconnections = []
            for i in G5Conf['ustack']:
                conn = para_ssh_conn(G5Conf['ustack'][i])
                self.sshconnections.append(conn)
    

    def clear_results(self):
        self.results['start_time'] = get_timestamp()
        self.results['MEC CPU max'] = 0
        self.results['MEC MEM max'] = 0
        self.results['availebility'] = 0


    def cpu_sample(self):
        
        cpu_usage = cpumem(self.use_case,"CPU")
        system_usage= system_cpu_usage()
        idle = idle_cpu(self.use_case)

        
        if self.last_system_usage is None:
            cpu_percent=0.0
        else:
            cpu_delta = (cpu_usage - self.last_cpu_usage)
            system_delta = (system_usage - self.last_system_usage)
            idle_delta = (idle - self.last_idle)

            
            #print(get_num_vcpus(self.use_case),host_num_cpus())
            quotient = cpu_delta/(system_delta+idle_delta)
            #cpu_percent = round(quotient * 100 ,1)
            cpu_percent = round(quotient * 100,1)
            print("usage_delta ",cpu_delta,"sys_delta ",system_delta,"idle_delta ",idle_delta,"per% ",cpu_percent)
        self.last_system_usage = system_usage
        self.last_cpu_usage = cpu_usage
        self.last_idle = idle

        #try:
            #print(cpu_percent,quotient,cpu_delta,system_delta)
        #except:
            #print("first")
        if self.results['MEC CPU max'] < cpu_percent:
            self.results['MEC CPU max'] = cpu_percent
        #msample = round(100*cpumem(self.use_case,"MEM")/total_mem(self.use_case),5)
        #if self.results['MEC MEM max'] < msample:
        #    self.results['MEC MEM max'] = msample
        #if self.results['availebility'] < 100*availebility():
         #   self.results['availebility'] = 100*availebility()

        #print(f"cpu:{self.results['MEC CPU max']}, mem:{self.results['MEC MEM max']},A:{self.results['availebility']}")

    def mem_sample(self):
        if os.getenv('PLATFORM') == 'INTEL1':
            c=0
            for ssh in self.sshconnections:
                stdin, stdout, stderr = ssh.exec_command('cat /sys/fs/cgroup/memory/memory.usage_in_bytes /sys/fs/cgroup/memory/memory.kmem.usage_in_bytes')
                ct = stdout.read().decode("utf-8")    

                #ct = ssh_cmd(i,'cat /sys/fs/cgroup/memory/memory.usage_in_bytes /sys/fs/cgroup/memory/memory.kmem.usage_in_bytes')
                temp=ct.split("\n")
                c+=int(temp[0])
                c+=int(temp[1])

            msample = round(100*c/total_mem(self.use_case),5)
        else:
            
            msample = round(100*cpumem(self.use_case,"MEM")/total_mem(self.use_case),5)
        if self.results['MEC MEM max'] < msample:
            self.results['MEC MEM max'] = msample
        if self.results['availebility'] < 100*availebility():
            self.results['availebility'] = 100*availebility()

        #print(f"cpu:{self.results['MEC CPU max']}, mem:{self.results['MEC MEM max']},A:{self.results['availebility']}")
    
    def registerkpi(self):
        #print(self.results)
        meta=self.meta
        meta['results']=self.results.copy()
        #register_kpi(meta,True)

        stop_job = Job.create(register_kpi,args=[self.meta.copy(),True],id=self.test_case_id+"MEM",connection=myredis())
        r=q_stop.enqueue_job(stop_job)

class SampleTXRX(Thread):
    def __init__(self, sniffer):
        # Query the type of the link and instantiate a decoder accordingly.
        self.sniffer = sniffer
        self.active=True
        self.sample=time.time()
        self.samples={}
        self.t_reg=time.time()
        self.t_start=time.time()
        self.src_ip=[]
        Thread.__init__(self)
        
    def init(self,meta):
        self.results={}
        self.results['start_time'] = get_timestamp()
        self.results['uid'] = meta['test_case_id']
        self.test_case_id = meta['test_case_id']
        self.use_case = meta['use_case']
        self.uid = meta['test_case_id']
        self.meta=meta.copy()
        self.results['tx_max'] = 0
        self.results['rx_max'] = 0
        self.results['src_ip'] = []
        
        #self.results['MEC CPU max'] = round(cpupercent(self.use_case),5)
        #self.results['MEC MEM max'] = round(100*cpumem(self.use_case,"MEM")/total_mem(),5)
        #self.results['availebility'] = availebility()

    def clear_results(self):
        self.results['start_time'] = get_timestamp()
        self.results['tx_max'] = 0
        self.results['rx_max'] = 0
        self.results['srs_ip'] = []
        self.src_ip=[]
        
        #self.results['MEC CPU max'] = 0
        #self.results['MEC MEM max'] = 0
        #self.results['availebility'] = 0
        

        

    def run(self):
        while self.active:
            if time.time()-self.sample>FREQ/12:
                tx_samples=[]
                rx_samples=[]
                for i,m in self.sniffer.tcpdump.items():
                    p_mean=m.t_len/(time.time()-self.sample)
                    m.samples.append(p_mean)
                    src,dst=i.split(":")
                    for j in ue_ip:
                        if j  in src:
                            self.src_ip.append(src)
                            tx_samples.append(p_mean)
                        if j in dst:
                            rx_samples.append(p_mean)
                    
                    m.flush()
                    #print(f'{i}, mean:{human(p_mean)}, {self.uid}, delta:{time.time()-self.sample}')
                if len(tx_samples):
                    if self.results['tx_max'] < max(tx_samples):
                        self.results['tx_max'] = max(tx_samples)
                if len(rx_samples):
                    if self.results['rx_max'] < max(rx_samples):
                        self.results['rx_max'] = max(rx_samples)
                #self.memcpu_sample()
                if time.time()-self.t_reg>FREQ-1:
                    for ss in self.src_ip:
                        if ss not in self.results['src_ip']:
                            self.results['src_ip'].append(ss)
                    #self.results['src_ip']=self.src_ip.copy()
                    self.registerkpi()
                    self.clear_results()
                    self.t_reg=time.time()

                else:
                    for ss in self.src_ip:
                        if ss not in self.results['src_ip']:
                            self.results['src_ip'].append(ss)
                
                self.sample=time.time()
                if time.time()-self.t_start>3600:
                    self.active=0


    def get_results(self):
        return self.results
    
    def registerkpi(self):
        #self.get_txrx()
        #self.memcpu_sample()
        #print(self.results)
        meta=self.meta
        meta['results']=self.results.copy()
        #return
        #register_kpi(meta,False)
        print("Register_kpi queued")
        stop_job = Job.create(register_kpi,args=[self.meta.copy(),False],id=self.test_case_id+"TXRX",connection=myredis())
        r=q_stop.enqueue_job(stop_job)

    def stop(self):
        print("stopping sniff")
        self.active=False
        
class DecoderThread(Thread):
    def __init__(self, pcapObj,dev):
        # Query the type of the link and instantiate a decoder accordingly.
        self.ipdec=0

        datalink = pcapObj.datalink()
        if pcapy.DLT_EN10MB == datalink:
            self.decoder = EthDecoder()
        elif pcapy.DLT_LINUX_SLL == datalink:
            self.decoder = LinuxSLLDecoder()
        elif "utun" in dev:
            self.decoder=IPDecoder()
            self.ipdec=1
        else:
            raise Exception("Datalink type not supported: " % datalink)
        self.pcap = pcapObj
        self.active=True
        self.tcpdump={}
        self.dev=dev
        self.t_start=time.time()
        
        Thread.__init__(self)

    def run(self):
        sample=time.time()
        #self.pcap.loop(0, self.packetHandler)
        while self.active:
            (header,packet) = self.pcap.next()
            if header !=None:
                ts=header.getts()
                if self.ipdec:
                    ip = self.decoder.decode(packet[4:])
                else:                    
                    ip = self.decoder.decode(packet).child()
                try:
                    src=ip.get_ip_src()
                    dst=ip.get_ip_dst()
                    p_len=ip.get_ip_len()
                    t_stamp=float(f'{ts[0]}.{ts[1]}')
                    index=f'{src}:{dst}'
                    if index not in self.tcpdump:
                        self.tcpdump[index]=Measure(index,t_stamp,p_len)
                    else:
                        self.tcpdump[index].add(p_len,t_stamp)
                except:
                    continue
            if time.time()-self.t_start>3600:
                self.active=False
  
    def stop(self):
        self.active=False
        

@logged    
def Stop(meta):
    global Experiments
    test_case_id = meta['test_case_id']
    
    try:
        Experiments[test_case_id].stop()
        Experiments.pop(test_case_id)
        return 0
    except:
        myprint(mytime(),f'Stop error - no test_case_id found:{test_case_id}')
    return -1



@logged    
def Start(meta):
    global Experiments
    try:
        # to save resources, use only one open_live process.
        
        #if len(Experiments):
         #   sniffer_p=Expperiments[0].sniffer.pcap
            
        test_case_id = meta['test_case_id']

    
        experiment=ExperimentObj(meta)
    
        experiment.start()
    
        myprint(mytime(),"New measurement started: ",test_case_id)
        
        Experiments[test_case_id]=experiment
        return 0
    except:
        myprint(mytime(), f'Could not start experiment {test_case_id}')
    return -1

@logged
def ping_addr(destlist):
    mainr=[]
    main_std=[]
    for dest in destlist:
        results=[]
        try:
            process = subprocess.Popen(shlex.split(f"ping -c 12 -i 0.3 -s 800 {dest}"),stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

            pipe=process.stdout

            for line in pipe:
                line = line.decode('utf-8')
                if 'ttl' in line:
                    line=line.split("time=")[1].split(" ms")[0]

                    results.append(float(line))
            results.sort()
            if len(results):
                mainr.append(statistics.mean(results[1:-1]))
                main_std.append(statistics.stdev(results[1:-1]))
        except Exception as error:
            print(mytime(),f"Error in process: {error}")
            return 0
    if len(mainr):
        return min(mainr),min(main_std)
    else:
        return(-1,-1)

@logged
def register_kpi(meta,mem):
    print("start to register KPIs")
    uid=meta['test_case_id']
    results=meta['results']
    print(results)
    if not mem:
        print("register TXRX")
        destlist=results['src_ip']
        print(f"destlist:{destlist}")
        if len(destlist):
            min_rtt,min_stdev=ping_addr(destlist)
        tnor_stats['CKPI-1'] = round(results['tx_max']*8/1000000,2)
        tnor_stats['CKPI-2'] = round(results['rx_max']*8/1000000,2)
        if len(destlist) and min_rtt>0:
            tnor_stats['CKPI-5'] = round(min_rtt/2,2)
            tnor_stats['CKPI-12'] = round(min_stdev/2,5)
            tnor_stats['CKPI-6'] = round(min_rtt/2-2.5,2)
    else:
        tnor_stats['CKPI-15'] = round(results['availebility'],2)
        tnor_stats['PKPI-9'] = round(results['MEC CPU max'],2)
        tnor_stats['PKPI-10'] = round(results['MEC MEM max'],2)
    if mem:
        uc_kpi = kpis_cpumem.copy()
    else:
        uc_kpi = kpis_txrx.copy()
        
    for i in tnor_stats:
        for j in uc_kpi["kpis"]:
            if j["name"] == i:
                j["value"] = tnor_stats[i]
        
    meta['kpis'] = uc_kpi
    if meta['regkpi']:
        registerkpis(meta)
    #myprint(mytime(),f'Ending experiment.......')
    #myprint(mytime(), meta)
    #file = open(f'{G5Conf["Logpath"]}/{G5Conf["logfiletemp"]}','wb')
    myprint(mytime(),uc_kpi)
    #pickle.dump(uc_kpi,file)
    #file.close()

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
        myprint(mytime(),response.reason)
        return errorResponse("Failed <get_token>",error)


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


#if __name__ == '__main__':
#    meta={}
#    meta['use_case']='UC1'
#    meta['test_case']='TC1'
#    meta['test_case_id']='test99'
#    meta['regkpi']=True
#    time.sleep(1)
#    r=Start(meta)
    #mm=meta.copy()
    #mm['test_case_id']='test100'
    #time.sleep(1)
    #r=Start(mm)
    #print(Experiments)
#    time.sleep(20)
#    r=Stop(meta)
    #print(Experiments)
    #time.sleep(2)
    #r=Stop(mm)


    #print(f'{i}, max:{p_max},min:{p_min},mean:{p_mean}')

