import os
from dotenv import load_dotenv


load_dotenv()


os_platform = os.getenv('PLATFORM')

def Merge(dict1, dict2):
    res = {**dict1, **dict2}

    return res


if os_platform == 'DOCKER':
    RedisConf = {'redishost':'172.240.20.3', 'redisport':6379}
    IperfConf = {'iperfhost':'172.240.20.2','iperfport':30955}

    LocalConf = {'Logpath':'/root/5GMediaMeasure-main/Logs','logfile1':'iperf.cvs','logfile2':'iperf2.cvs','logfiletemp':'logfiletmp','nic':'eth0'}
    owampConf = {'owping':'/root/inst/bin/owping','owconf':'-c100 -i0.1 -L10 -s0 -t -AO -nm','owampdest':f'{IperfConf["iperfhost"]}'}


elif os_platform == 'INTEL1':
    RedisConf = {'redishost':'10.5.1.2', 'redisport':30379}
    IperfConf = {'iperfhost':'10.5.1.2','iperfport':30955}

    LocalConf = {'Logpath':'/home/tnor/5GMediahub/Measurements/Service/Logs','logfile1':'iperf.cvs','logfile2':'iperf2.cvs','logfiletemp':'logfiletmp','nic':'ensf260c'}
    owampConf = {'owping':'/opt/bin/owping','owconf':'-c100 -i0.1 -L10 -s0 -t -AO -nm','owampdest':f'{IperfConf["iperfhost"]}'}

elif os_platform == 'HP4':
    RedisConf = {'redishost':'10.5.1.4', 'redisport':30379}
    IperfConf = {'iperfhost':'10.5.1.4','iperfport':30955}

    LocalConf = {'Logpath':'/home/tnor/5GMediahub/Measurements/Service/Logs','logfile1':'iperf.cvs','logfile2':'iperf2.cvs','logfiletemp':'logfiletmp','nic':'ens3f0'}
    owampConf = {'owping':'/opt/bin/owping','owconf':'-c100 -i0.1 -L10 -s0 -t -AO -nm','owampdest':f'{IperfConf["iperfhost"]}'}


pingConf = {'clientcmd':'ping -c 12 -i 0.3','mport':9055}

G5Conf = Merge(RedisConf,IperfConf)
G5Conf = Merge(G5Conf,LocalConf)
G5Conf = Merge(G5Conf,owampConf)
G5Conf = Merge(G5Conf,pingConf)

PEAK_UL = 126
PEAK_DL= 794
MAX_UL = 130.0
MAX_DL = 800.0
E2E_LATENCY = 10
TN_LATENCY = 0.144
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


kpis = {"kpis":[{"name":"CKPI-1","value":f"{PEAK_UL}","unit":"Mbps"},

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

def myprint(*args):
    line = ' '.join([str(a) for a in args])
    f = open(f'{G5Conf["Logpath"]}/nbi_measure.log','a')
    
    f.write(line+'\n')
    f.close()
    print(line)    
    
