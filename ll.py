import time
import sniff as ss
s = ss.SampleCPUMEM()
m={'use_case':'UC2','test_case':'TC1','test_case_id':'11'}
s.init(m)
s.cpu_sample()
time.sleep(5)
s.mem_sample()
time.sleep(5)
s.cpu_sample()
time.sleep(5)
s.mem_sample()
time.sleep(5)
s.cpu_sample()
time.sleep(5)
s.mem_sample()
s.stop()
print(s.results)
