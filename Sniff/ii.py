import subprocess
import os, signal
import time
import shlex
import signal
import sys

    
#p1 = subprocess.Popen(shlex.split("/usr/sbin/iftop -i ens3f0 -t"),stdout=subprocess.PIPE)
#p2 = subprocess.Popen(["cat",">dump2.txt"],stdin=p1.stdout,stdout=subprocess.PIPE)

#proc1 = subprocess.Popen(shlex.split("/usr/sbin/iftop -i ens3f0 -t"),stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
proc1 = subprocess.Popen(shlex.split("/usr/sbin/iftop -i ens3f0 -t"),shell=False,stdout=sys.stdout,stderr=sys.stderr)
#proc1 = subprocess.check_output("/usr/sbin/iftop -i ens3f0 -t >dump1.txt",shell=True)
time.sleep(1)
proc1.communicate()

proc1.kill()
    
#print(proc1.stdout.read())

      

#while True:
#    line = proc1.stdout.readline()
#    print(line)
#    if line =='' and proc1.poll() !=None:
#        break
#    time.sleep(1)
#    n+=1
#    if n>5:
#        break
#print('proc1 = ', proc1.pid)
#proc1.kill()
