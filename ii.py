import subprocess
import os, signal
import time
import shlex
import signal
import sys
import statistics

def ping_addr(destlist):
    main_rtt=[]
    main_std=[]
    for dest in destlist:
        m_results=[]
        try:
            process = subprocess.Popen(shlex.split(f"ping -c 12 -i 0.3 {dest}"),stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

            pipe=process.stdout

            for line in pipe:
                line = line.decode('utf-8')
                if 'ttl' in line:
                    line=line.split("time=")[1].split(" ms")[0]
                    
                    m_results.append(float(line))
            m_results.sort()
            if len(m_results):
                main_rtt.append(statistics.mean(m_results[1:-1]))
                main_std.append(statistics.stdev(m_results[1:-1]))
        except Exception as error:
            print(f"Error in process: {error}")
            #print(mainr,results)
            return 0
    print(main_std)
    return min(main_rtt),min(main_std)

if __name__ == "__main__":
    l=["10.5.1.2"]
    ma,mi=ping_addr(l)
    print(ma,mi)
