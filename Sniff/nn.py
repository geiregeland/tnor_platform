from kubernetes import client, config

import time


#config.load_kube_config()
c = client.ApiClient(configuration=config.load_kube_config())

Configuration = client.Configuration()
Configuration.api_client=c
Configuration.verify_ssl = False
#Configuration.host = 'https//127.0.0.1:16443'

api = client.CoreV1Api(Configuration)
ret = api.list_pod_for_all_namespaces(watch=False)
for i in ret.items:
    print(i.status.pod_ip)
#pod = api.read_namespaced_pod(name='mosaic',namespace='ektacom-stream-selecto')


