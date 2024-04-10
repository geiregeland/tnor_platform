from config import G5Conf
import subprocess
import statistics
import shlex
#from worker import errorResponse

uc="UC1"





def _kubecpu(i,uc):
    return f'microk8s.kubectl exec -it {i} -n {G5Conf[f"{uc}-netapp"]} -- /usr/bin/cat /sys/fs/cgroup/cpu/cpuacct.usage'
def _kubemem(i,uc):
    return f'microk8s.kubectl exec -it {i} -n {G5Conf[f"{uc}-netapp"]} -- /usr/bin/cat /sys/fs/cgroup/memory/memory.usage_in_bytes'
    

def get_data(uc,measure):
    cmd = f'/snap/bin/microk8s.kubectl describe pods -n {G5Conf[f"{uc}-netapp"]} |/usr/bin/grep ^Name:|/usr/bin/sed "s/.*://" | /usr/bin/tr -d " "'
    r= subprocess.run([f'{cmd}'], capture_output=True, shell=True,text=True)
    lsum=0
    
    for i in r.stdout.split('\n')[0:-1]:
        if measure == "MEM":
            cc = _kubemem(i,uc)
            #f'microk8s.kubectl exec -it {i} -n {G5Conf[f"{uc}-netapp"]} -- /usr/bin/cat /sys/fs/cgroup/cpu/cpuacct.usage'
        elif measure == "CPU":
            cc = _kubecpu(i,uc)
            
        r = subprocess.run([f'{cc}'], capture_output=True, shell=True,text=True)
        if r.stdout != '':

            lsum+= int(r.stdout)
    print(f'use case:{uc}:{lsum}')
            

if __name__ == '__main__':
    get_data("UC1","MEM")
    get_data("UC2","MEM")
    get_data("UC3","MEM")

    get_data("UC1","CPU")
    get_data("UC2","CPU")
    get_data("UC3","CPU")

    #process = subprocess.Popen(f'{KUBECMD}',shell=False,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
#for line in process.stdout:
#    print(line)
  
