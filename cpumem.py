import logging
from config import G5Conf,mytime,errorResponse
import subprocess
from netmiko import ConnectHandler
import os

logger = logging.getLogger(__name__)

CPU_USAGE_PATH = "/sys/fs/cgroup/cpuacct/cpuacct.usage"
CPU_USAGE_PATH_V2 = "/sys/fs/cgroup/cpu.stat"
PROC_STAT_PATH = "/proc/stat"

MEM_USAGE_PATH='/sys/fs/cgroup/memory/memory.usage_in_bytes'
MEM_USAGE_PATH_V2='/sys/fs/cgroup/memory/kubepods/memory.usage_in_bytes'
#MEM_TOTAL_PATH='/proc/meminfo'
MEM_TOTAL_PATH='/sys/fs/cgroup/memory/kubepods/memory.limit_in_bytes'


container_num_cpus = None
host_num_cpus = None

last_cpu_usage = None
last_system_usage = None

PLATFORM = os.getenv('Platform')

#------------------------ustack functions
if PLATFORM == 'INTEL1':

    mediahub_passNO = {
            'device_type': 'linux',
            'ip': '',
            'username': '',
            'password': '',
            'port': 22,
            'verbose':True
            }


def ssh_connect(linux):
  connection = ConnectHandler(**linux)
  return connection
def ssh_cmd(connection,cmd):
  output = connection.send_command(cmd)
  return output
def ssh_close(connection):
  connection.disconnect()

def sshcmd(cmd,vm):
  #print(mytime(),f"sshcmd" ,cmd)
  medipass = mediahub_passNO
  medipass['ip'] = vm['IP']
  medipass['username'] = os.getenv('MS_USER')
  medipass['password'] = os.getenv('MS_PASSWORD')
      
  try:
    connection = ssh_connect(medipass)
    output = ssh_cmd(connection,cmd)
    ssh_close(connection)
    return output 
  except Exception as error:
    return errorResponse("Failed to run sshcmd",error)

def _ustackcpu(uc):
  c = 0
  for i in G5Conf['ustack']:
    #print(i,G5Conf['ustack'][i])
    ct = sshcmd('cat /sys/fs/cgroup/cpu/cpuacct.usage',G5Conf['ustack'][i])
    #print(ct)
    c+=int(ct)
  return c

#microstack.openstack flavor list - vCPU allocated
def _get_ustack_cpus():
  c = 0
  for i in G5Conf['ustack']:
    c += G5Conf['ustack'][i]['cpu']
  return c

#microstack.openstack flavor list - RAM allocated
def _get_ustack_mem():
  c = 0
  for i in G5Conf['ustack']:
    c += G5Conf['ustack'][i]['ram']
  return c*8*1e6


def _ustackmem(uc):
  c = 0
  for i in G5Conf['ustack']:
    ct = sshcmd('cat /sys/fs/cgroup/memory/memory.usage_in_bytes',G5Conf['ustack'][i])
    c+=int(ct)
  return c
#-----------------------------------end ustack functions

def _kubecpu(i,uc):
    return f'microk8s.kubectl exec -it {i} -n {G5Conf[f"{uc}-netapp"]} -- /usr/bin/cat /sys/fs/cgroup/cpu/cpuacct.usage'
def _kubemem(i,uc):
    return f'microk8s.kubectl exec -it {i} -n {G5Conf[f"{uc}-netapp"]} -- /usr/bin/cat /sys/fs/cgroup/memory/memory.usage_in_bytes'
    

def get_data(uc,measure):
    lsum = 0
    if os.getenv('PLATFORM') == 'INTEL1':
        if measure == "MEM":
            lsum = _ustackmem(uc)
        elif measure == "CPU":
            lsum = _ustackcpu(uc)
    elif os.getenv('PLATFORM') == 'HP4': 
        cmd = f'/snap/bin/microk8s.kubectl describe pods -n {G5Conf[f"{uc}-netapp"]} |/usr/bin/grep ^Name:|/usr/bin/sed "s/.*://" | /usr/bin/tr -d " "'
        r= subprocess.run([f'{cmd}'], capture_output=True, shell=True,text=True)
        for i in r.stdout.split('\n')[0:-1]:
            if measure == "MEM":
                cc = _kubemem(i,uc)
                #f'microk8s.kubectl exec -it {i} -n {G5Conf[f"{uc}-netapp"]} -- /usr/bin/cat /sys/fs/cgroup/cpu/cpuacct.usage'
            elif measure == "CPU":
                cc = _kubecpu(i,uc)
        r = subprocess.run([f'{cc}'], capture_output=True, shell=True,text=True)
        if r.stdout != '':
            lsum+= int(r.stdout)
    return lsum



def cpu_percent(uc):
    """Estimate CPU usage percent for Ray pod managed by Kubernetes
    Operator.
    Computed by the following steps
       (1) Replicate the logic used by 'docker stats' cli command.
           See https://github.com/docker/cli/blob/c0a6b1c7b30203fbc28cd619acb901a95a80e30e/cli/command/container/stats_helpers.go#L166.
       (2) Divide by the number of CPUs available to the container, so that
           e.g. full capacity use of 2 CPUs will read as 100%,
           rather than 200%.
    Step (1) above works by
        dividing delta in cpu usage by
        delta in total host cpu usage, averaged over host's cpus.
    Since deltas are not initially available, return 0.0 on first call.
    """  # noqa
    global last_system_usage
    global last_cpu_usage
    try:
        cpu_usage = get_data(uc,"CPU")
        system_usage = _system_usage()
        # Return 0.0 on first call.
        if last_system_usage is None:
            cpu_percent = 0.0
        else:
            cpu_delta = cpu_usage - last_cpu_usage
            # "System time passed." (Typically close to clock time.)
            system_delta = (system_usage - last_system_usage) / _host_num_cpus()

            quotient = cpu_delta / system_delta
            #cpu_percent = round(quotient * 100 , 1)
            cpu_percent = round(quotient * 100 / get_num_cpus(uc), 1)
        last_system_usage = system_usage
        last_cpu_usage = cpu_usage
        # Computed percentage might be slightly above 100%.
        #return cpu_percent
        return min(cpu_percent, 100.0)
    except Exception:
        logger.exception("Error computing CPU usage of Ray Kubernetes pod.")
        return 0.0

def get_num_cpus(uc):
  if os.getenv('PLATFORM') != 'INTEL1':
    if uc == "UC1":
        return 1
    else:
        return 6
  else:
    return _get_ustack_cpus()

    
    #return _host_num_cpus()

def _cpu_usage():
    """Compute total cpu usage of the container in nanoseconds
    by reading from cpuacct in cgroups v1 or cpu.stat in cgroups v2."""
    try:
        # cgroups v1

        return int(open(CPU_USAGE_PATH).read())
    except FileNotFoundError:
        # cgroups v2
        cpu_stat_text = open(CPU_USAGE_PATH_V2).read()
        # e.g. "usage_usec 16089294616"
        cpu_stat_first_line = cpu_stat_text.split("\n")[0]
        # get the second word of the first line, cast as an integer
        # this is the CPU usage is microseconds
        cpu_usec = int(cpu_stat_first_line.split()[1])
        # Convert to nanoseconds and return.
        return cpu_usec * 1000

def _system_usage():
    """
    Computes total CPU usage of the host in nanoseconds.
    Logic taken from here:
    https://github.com/moby/moby/blob/b42ac8d370a8ef8ec720dff0ca9dfb3530ac0a6a/daemon/stats/collector_unix.go#L31
    See also the /proc/stat entry here:
    https://man7.org/linux/man-pages/man5/proc.5.html
    """  # noqa
    cpu_summary_str = open(PROC_STAT_PATH).read().split("\n")[0]
    parts = cpu_summary_str.split()
    assert parts[0] == "cpu"
    usage_data = parts[1:8]
    total_clock_ticks = sum(int(entry) for entry in usage_data)
    # 100 clock ticks per second, 10^9 ns per second
    usage_ns = total_clock_ticks * 10 ** 7
    return usage_ns

def _system_mem():
  if os.getenv('PLATFORM') == 'INTEL1':
    tot = _get_ustack_mem()
  else:
    mem_summary_str = open(MEM_TOTAL_PATH).read().split("\n")[0]
    #get total of memory installed
    #tot = mem_summary_str.split(' ')[-2:-1][0]
    tot=mem_summary_str
    #return mem in bytes
  return int(tot)


def _virtual_mem():
    mem_summary_str = open(MEM_USAGE_PATH_V2).read().split("\n")[0]
    return int(mem_summary_str)

def _used_mem():
    mem_summary_str = open(MEM_USAGE_PATH).read().split("\n")[0]
    return int(mem_summary_str)

    
def availebility():
    up = open('/proc/uptime').read().split(" ")[0]
    #assuming that the server is unavailable for 10 minutes when rebooted 
    a = (float(up)-600)/float(up)
    return a

def _host_num_cpus():
    """Number of physical CPUs, obtained by parsing /proc/stat."""
    global host_num_cpus
    if host_num_cpus is None:
        proc_stat_lines = open(PROC_STAT_PATH).read().split("\n")
        split_proc_stat_lines = [line.split() for line in proc_stat_lines]
        cpu_lines = [
            split_line
            for split_line in split_proc_stat_lines
            if len(split_line) > 0 and "cpu" in split_line[0]
        ]
        # Number of lines starting with a word including 'cpu', subtracting
        # 1 for the first summary line.
        host_num_cpus = len(cpu_lines) - 1
    return host_num_cpus


