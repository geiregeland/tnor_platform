import os
import sys
from flask import jsonify
import redis
from rq import Worker, Queue, Connection
from config import clean_osgetenv,myprint,errorResponse
from config import G5Conf



    
    
if __name__ == '__main__':
    def connect_redis(url):
        try:
            conn = redis.from_url(url)
            return conn
        except Exception as error:
            return errorResponse("Could not connect to redis",error)

    def connRedis():
        try:
            #redisPort=get_redisport()
            #redis_url = os.getenv('REDIS_URL', 'redis://localhost:'+redisPort)
            host = G5Conf['redishost']
            port = G5Conf['redisport']
            #host = clean_osgetenv(os.getenv('REDIS_HOST'))
            #port = clean_osgetenv(os.getenv('REDIS_PORT'))
            redis_url = f'redis://{host}:{port}'
            myprint("Connecting to redis: ",redis_url)
            return connect_redis(redis_url)
    
        except Exception as error:
            return errorResponse("Failed main redis connection",error)


    conn = connRedis()
    listen = ['low']
    
    #with Connection(conn):
    #worker = Worker(map(Queue, listen))
    queue = Queue('low',connection = connRedis(), default_timeout = 7200)

    worker = Worker(queue,connection=conn)
    worker.work(with_scheduler=True)
