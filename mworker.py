import os
import sys
from flask import jsonify
import redis
from rq import Worker, Queue, Connection
from nbi_measure import clean_osgetenv
from config import G5Conf



def errorResponse(message, error):
    print(f'{message}: {error}')
    return jsonify({'Status': 'Error', 'Message': message, 'Error': f'{error}'}), 403

    
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
        print(redis_url)
        return connect_redis(redis_url)
    
    except Exception as error:
        return errorResponse("Failed main redis connection",error)

    
if __name__ == '__main__':

    conn = connRedis()
    listen = ['low']
    
    with Connection(conn):
        worker = Worker(map(Queue, listen))
        worker.work()
