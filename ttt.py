import subprocess,os
from config import uc as UC
MEM_TOTAL_PATH='/sys/fs/cgroup/memory/kubepods/memory.limit_in_bytes'

#cmd =f'microk8s.kubectl get pods -n ektacom-stream-selector -o yaml|grep selfLink -A1|grep uid'

def kubemem(uc):
    myuc=uc+'-netapp'
    cmd =f'microk8s.kubectl get pods -n {UC[myuc]} -o yaml|grep selfLink -A1|grep uid'

    r=subprocess.run(cmd,capture_output=True,shell=True,text=True)
    kubes=[]


    for i in r.stdout.split("\n")[0:-1]:
        uid=i.split('uid: ')[1]
        kubes.append(uid)


    mfile=f'/sys/fs/cgroup/memory/kubepods'
    mem={'usage_in_bytes':0,'kmem.usage_in_bytes':0,'limit_in_bytes':0}

    for index in mem:
        for i in kubes: 
            if os.path.isfile(f'{mfile}/pod{i}/memory.{index}'):
                cmd = f'cat {mfile}/pod{i}/memory.{index}'
            else:
                cmd = f'cat {mfile}/besteffort/pod{i}/memory.{index}'

            r=subprocess.run(cmd,capture_output=True,shell=True,text=True)
            for j in r.stdout.split("\n")[0:-1]:
                mem[index]+=int(j)

    if uc =="UC1":
        mem_summary_str = open(MEM_TOTAL_PATH).read().split("\n")[0]
        tot=mem_summary_str
        mem['limit_in_bytes'] = int(tot)
    return(mem)

if __name__ == '__main__':
    print(kubemem("UC1"))
    print(kubemem("UC2"))
    print(kubemem("UC3"))
    
    
