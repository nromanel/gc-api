
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import requests
import os.path
import email
import base64
import time
import re
from datetime import datetime
import json
import logging
import sys

GC_LOGIN = "https://web.gc.com/?redirect=%2Fteams"

logging.basicConfig(stream=sys.stdout, level=logging.INFO,format='%(asctime)s %(levelname)-8s %(message)s')
log=logging.getLogger(__name__)


class GameChanger(object):

    def __init__(self,username=None,password=None,gmail_token='token.json',gmail_creds='google-creds.json',chrome_data_dir="./chrome-data"):
        log.info("Initializing GC Session")
        options = Options()
        options.add_argument('--headless=new')
        options.add_argument("--user-data-dir={}".format(chrome_data_dir))
        options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
        
        self.request_session = requests.Session()
        self.driver = webdriver.Chrome(options=options)

        self.driver.get(GC_LOGIN)
        time.sleep(2)


        log.info("Find Existing GC Session")
        gc_tokens = self.find_gc_token()
        if "gc-token" in gc_tokens and ("redirect" not in self.driver.current_url and "teams" in self.driver.current_url):
            log.info("Existing Session Found!")
            log.info(gc_tokens)
            self.tokens = gc_tokens
            self.request_session.headers.update(gc_tokens)
        else:
            log.info("No Existing GC Session Found. Logging in.")
            gc_tokens = self.auth_gc(username,password,gmail_token,gmail_creds)
            self.tokens = gc_tokens
            self.request_session.headers.update(gc_tokens)

        log.info("GC Session Established")

    def get_team_details(self):
        TEAM_DETAILS_URL = "https://api.team-manager.gc.com/me/teams?include=user_team_associations"
        result = self.request_session.get(TEAM_DETAILS_URL)
        output = []
        for team in result.json():
            if team["archived"] == False:
                output.append({ "id" : team["id"],
                                "name" : team["name"],
                                "season_year" : team["season_year"],
                                "season_name" : team["season_name"]})
        return output

    def get_live_game_summary(self,team_id):
        GAME_SUMMARIES_URL = "https://api.team-manager.gc.com/teams/{}/game-summaries".format(team_id)
        result = self.request_session.get(GAME_SUMMARIES_URL)
        output = {}
        for game in result.json():
            if game["game_status"] == "live":
                output["id"] = game["event_id"]
                output["home_away"] = game["home_away"]
                output["owning_team_score"] = game["owning_team_score"]
                output["opponent_team_score"] = game["opponent_team_score"]
                output["current_inning"] = game["sport_specific"]["bats"]["inning_details"]["inning"]
                output["current_outs"] = game["sport_specific"]["bats"]["total_outs"] % 3
                break
        return output
    
    def get_game_stream(self,game_id):
        STREAM_URL = "https://api.team-manager.gc.com/events/{}/best-game-stream-id".format(game_id)
        result = self.request_session.get(STREAM_URL)
        return result.json()["game_stream_id"]

    def get_events(self,game_id):
        EVENTS_URL = "https://api.team-manager.gc.com/game-streams/{}/events".format(self.get_game_stream(game_id))
        result = self.request_session.get(EVENTS_URL)
        output = [] 
        for event in result.json():
            event_data = json.loads(event["event_data"])
            event_data["sequence_number"] = event["sequence_number"]
            output.append(event_data)
        return output

    def auth_gc(self,username=None,password=None,gmail_token='token.json',gmail_creds='google-creds.json'):

        self.driver.get(GC_LOGIN)
        log.warn(self.driver.current_url)
        WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.ID, "email"))).send_keys(username)
        self.driver.find_element('xpath','//button[@data-testid="sign-in-button"]').click()
        WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.ID, "password"))).send_keys(password)
        try:
            self.driver.get_screenshot_as_file('gc-code.png') 
            WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.ID, "code")))
            log.info("Prompted for Code! Checking e-mail")
            time.sleep(10)
            code_found = False
            loop = 1
            code = ""
            while not code_found:
                code_result = self.getcode(gmail_token,gmail_creds)
                if "code" in code_result:
                    if(code_result["date"]+300 > time.time()):
                        log.info("Found Code in Email: {}".format(code_result["code"]))
                        code_found = True
                        code = code_result["code"]
                    else:
                        log.warn("Code e-mail found older then 5 minutes. Waiting for new email")
                        loop = loop + 1
                        sleep(30)
                else:
                    log.warn("Code e-mail not found. Waiting for new email")
                    loop = loop + 1
                    sleep(30)
                
                if loop > 5:
                    raise Exception("Unable to Retrieve Code to continue login")
            WebDriverWait(self.driver, 1).until(EC.element_to_be_clickable((By.ID, "code"))).send_keys(code)

        except NoSuchElementException:
            log.info("No Code Challenge - Continuing Login")

        log.info("Clicking Signin")
        self.driver.find_element('xpath','//button[@data-testid="sign-in-button"]').click()
        try:
            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, "//span[@data-testid='teams-title']")))
            log.info("GameChange Session Established")

            gc_tokens = self.find_gc_token()
            if "gc-token" in  gc_tokens:
                return gc_tokens
            else:
                raise Exception("Unable to Capture Tokens after login")


        except:
            raise Exception("Unable to Login")

    def find_gc_token(self):
        logs_raw = self.driver.get_log("performance")
        logs = [json.loads(lr["message"])["message"] for lr in logs_raw]
        for req in reversed(logs):
            if req["method"] == "Network.requestWillBeSent" and "api.team-manager.gc.com" in req["params"]["request"]["url"] and set(["gc-app-name","gc-device-id","gc-token"]).issubset(set(req["params"]["request"]["headers"])):
                return { "gc-app-name" : req["params"]["request"]["headers"]["gc-app-name"],
                        "gc-device-id" : req["params"]["request"]["headers"]["gc-device-id"],
                        "gc-token" : req["params"]["request"]["headers"]["gc-token"]}
        log.warn("No GC Token Found in Logs")
        return {}


    def authgmail(self,token='token.json',credentials='google-creds.json'):
        SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
        creds = None
        if os.path.exists(token):
            creds = Credentials.from_authorized_user_file(token, SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except:
                    flow = InstalledAppFlow.from_client_secrets_file(
                    credentials, SCOPES)
                    creds = flow.run_local_server(port=0)
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials, SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(token, 'w') as token:
                token.write(creds.to_json())
        return creds


    def getcode(self,token='token.json',credentials='google-creds.json'):
        try:
            service = build('gmail', 'v1', credentials=self.authgmail(token,credentials))
            search_id = service.users().messages().list(userId='me',q='from:gamechanger-noreply@info.gc.com').execute()
            number_result = search_id['resultSizeEstimate']
            if number_result>0:
                message_list=service.users().messages().get(userId='me', id=search_id['messages'][0]['id'], format='raw').execute()
                msg_raw = base64.urlsafe_b64decode(message_list['raw'].encode('ASCII'))
                msg_str = email.message_from_bytes(msg_raw)
                content_types = msg_str.get_content_maintype()
                if content_types == 'multipart':
                    part1, part2 = msg_str.get_payload()
                    code = re.search('=3D=3D (.*) =3D=3D', part1.get_payload(), re.M).group(1)
                    log.info("Found Code: {} - {}".format(message_list["internalDate"][:-3] , code))
                    return {"date" : int(message_list["internalDate"][:-3]), "code" : code}
                else:
                    log.error("Unable to Find Code in Email")
                    return {}

            else:
                log.error('There were 0 Code emails found')
                return {}

        except HttpError as error:
            log.error(f'An error occurred: {error}')
            return {}