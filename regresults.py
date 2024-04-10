import os
import time
from datetime import datetime,timedelta
from config import myprint,mytime,logged, errorResponse
import requests
from config import clean_osgetenv



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
        return errorResponse("Failed <get_token>",error)

@logged
def get_timestamp():
    return datetime.utcnow().isoformat().split('.')[0]+'Z'

@logged
def registerkpis(meta):
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

@logged
def registerkpis_test(data):
    headers={'Content-Type': 'application/json', 'Authorization':''}
    headers['Authorization'] = 'Bearer ' + get_token()
    
    
    myprint(mytime(),data)
    r=requests.post('http://5gmediahub.vvservice.cttc.es/5gmediahub/data-collector/kpis',headers=headers,json=data)
    myprint(mytime(),r)
