from flask import Flask, Response, request
import os.path
import json
import logging
import sys
import signal
import GameChanger


TEAM_NAME = "Test 8U"

logging.basicConfig(stream=sys.stdout, level=logging.INFO,format='%(asctime)s %(levelname)-8s %(message)s')

log=logging.getLogger(__name__)

app = Flask(__name__)

with open('gc-creds.json') as f:
        d = json.load(f)
        GC_USERNAME= d["GC_USERNAME"]
        GC_PASSWORD= d["GC_PASSWORD"]

gc_client = GameChanger.GameChanger(username=GC_USERNAME,password=GC_PASSWORD,team_name=TEAM_NAME)

@app.route('/')
def home():
    return gc_client.get_live_game_summary()


def signal_handler(sig, frame):
    print('You pressed Ctrl+C!')
    sys.exit(0)

if __name__=="__main__": 
    app.run(host='0.0.0.0',port="7777")
