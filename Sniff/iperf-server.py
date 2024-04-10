import iperf3 as ip3
import os
import pandas as pd
from pathlib import Path
from datetime import datetime


Logfile = "./Logs"


ServerPort = os.getenv('IPERF_PORT')
ServerAddress = os.getenv('IPERF_ADDRESS')

def iperf3Throughput():
    s = ip3.Server()
    s.port = ServerPort
    s.bind_address = ServerAddress
    s.json_output = True

    results=s.run()
    l=results.json
    uplink=l['end']['streams'][0]['receiver']['bits_per_second']

    print(f"uplink:{uplink}")

    results=s.run()
    l=results.json
    downlink=l['end']['streams'][0]['sender']['bits_per_second']

    print(f"downlink:{downlink}")
    return {'Date':[datetime.now().strftime("%Y-%d-%m %H:%M:%S")],'Uplink':[uplink],'Downlink':[downlink]}

def Sample(uid):
    try:
        os.makedirs(Logfile,exist_ok=True)
    except OSError as error:
        print(f'Directory {Logfile} can not be created')

    if not os.path.exists(f'{Logfile}/iperf.csv'):
        df = pd.DataFrame({'Date': pd.Series(dtype='str'),
                   'Uplink': pd.Series(dtype='float'),
                   'Downlink': pd.Series(dtype='float')})
        df['Date']=pd.to_datetime(df.Date)
        df.to_csv(f'{Logfile}/iperf.csv', sep=',', encoding='utf-8',index=False)

    else:
        df = pd.read_csv(f'{Logfile}/iperf.csv',sep=',')
    sample = iperf3Throughput()
    df = pd.concat([df,pd.DataFrame(sample,columns=['Date','Uplink','Downlink'])])
    df.to_csv(f'{Logfile}/iperf.csv', sep=',', encoding='utf-8',index=False)
    print(df)

if __name__ == '__main__':
    Sample()



    

#results=s.run()
#for i in results.json['end']:
#    if i == 'sum_sent_bidir_reverse':
     #   print(f"downlink:{results.json['end'][i]['bits_per_second']}")
        


