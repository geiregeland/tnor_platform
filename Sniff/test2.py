sample_interval = 10
filename="capture.cap"

from scapy.all import *
from collections import Counter
import subprocess
import time


traffic = Counter()
hosts = {}

def ff(src,dst):
    return f'{src}:{dst}'

timestamps={}
throughput={}
first = 0

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
            return f'{num:3.1f} {x}bps'
        num /= 1000.
    return  f'{num:3.1f} {x}bps'

def traffic_monitor_callback(pkt):
    if IP in pkt:
        pkt = pkt[IP]
        traffic.update({tuple(sorted(map(atol, (pkt.src, pkt.dst)))): pkt.len})

        update(pkt.src,pkt.dst,pkt.time,pkt.len)

#p = subprocess.Popen(['tcpdump',  '-i', 'en0',
 #                 '-w', 'cap.pcap'], stdout=subprocess.PIPE)

#time.sleep(10)
#p.terminate()
print("ending monitoring")

# A trick I like: don't use rdpcap() that would waste your memory;
# iterate over a PcapReader object instead.
for p in PcapReader("cap.pcap"):
    traffic_monitor_callback(p)

for (h1, h2), total in traffic.most_common():
    h1, h2 = map(ltoa, (h1, h2))
    for host in (h1, h2):
        if host not in hosts:
            try:
                rhost = socket.gethostbyaddr(host)
                hosts[host] = rhost[0]
            except:
                hosts[host] = None

    if hosts[h1] is not None:
        h1=f'{hosts[h1]} ({h1})'
    else:
        h1=f'{h1} ({h1})'

    if hosts[h2] is not None:
        h2=f'{hosts[h2]} ({h2})'
    else:
        h2=f'{h2} ({h2})'
    
    #h2 = "%s (%s)" % (hosts[h2], h2) if hosts[h2] is not None else h2
    #h1 = "%s (%s)" % (hosts[h1], h1) #if hosts[h1] is not None else h1
    #h2 = "%s (%s)" % (hosts[h2], h2) #if hosts[h2] is not None else h2
    print("%s/s: %s - %s total: %s" % (human(float(total*8)/sample_interval), h1, h2,total))

for i in throughput:
    if throughput[i]['peak']>0:
        #print(f'{i} - peak: {human(throughput[i]["peak"])}, average:{human(throughput[i]["data"]*8/sample_interval)} - total:{throughput[i]["data"]}')
        print(f'{i} - peak: {human(throughput[i]["peak"])}, average:{human(throughput[i]["data"]*8/(throughput[i]["last_t"]-throughput[i]["first_t"]))} - total:{throughput[i]["data"]}')


