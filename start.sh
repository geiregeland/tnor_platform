#!/bin/bash
# flask settings
export FLASK_APP=/home/tnor/5GMediahub/Measurements/5GMediaMeasure/nbi_measure.py
export FLASK_DEBUG=0

export IPERF_PORT=30955
export IPERF_ADDRESS=10.5.1.2
export REDIS_PORT=30379
export REDIS_HOST=10.5.1.2

flask run --host=0.0.0.0 --port=9055
