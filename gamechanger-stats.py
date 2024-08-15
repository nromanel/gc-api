
import os.path
import json
import logging
import sys
import signal
import GameChanger


TEAM_NAME = "Test 8U"

logging.basicConfig(stream=sys.stdout, level=logging.INFO,format='%(asctime)s %(levelname)-8s %(message)s')

log=logging.getLogger(__name__)


def main():
    
    with open('gc-creds.json') as f:
        d = json.load(f)
        GC_USERNAME= d["GC_USERNAME"]
        GC_PASSWORD= d["GC_PASSWORD"]

    gc_client = GameChanger.GameChanger(username=GC_USERNAME,password=GC_PASSWORD)
    teams = gc_client.get_team_details()
    team_id = ""
    for team in teams:
        if TEAM_NAME in team["name"]:
            team_id = team["id"]
            break
    
    if len(team_id) == 0:
        raise Exception("Unable to Find Team ID")
    
    current_game_summary = gc_client.get_live_game_summary(team_id)
    if len(current_game_summary) == 0:
        raise Exception("Unable to find Live Game")

    log.info(current_game_summary)
    game_events = gc_client.get_events(current_game_summary["id"])


def signal_handler(sig, frame):
    print('You pressed Ctrl+C!')
    sys.exit(0)

if __name__=="__main__": 
    main()
