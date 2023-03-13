import asyncio
import configparser
import os
import sys
import re
import urllib.parse
from platform import system
from simpleSound import play
from twitchAPI import Twitch
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.types import AuthScope
from twitchAPI.pubsub import PubSub
from twitchAPI.twitch import Twitch
from twitchAPI.helper import first
from twitchAPI.types import AuthScope
from twitchAPI.oauth import UserAuthenticator
import asyncio
import json
from pprint import pprint
from uuid import UUID
from time_formatter import time_format
from oauth import generate_token, read_token, refresh_token, validate_token
import logging
import time
# Read config
config = configparser.ConfigParser()
config.read('config.txt')
system=system()

# Set values
APP_ID = config['twitch']['client_id']
APP_SECRET = config['twitch']['client_secret']
TARGET_CHANNEL = config['twitch']['channel']
USER_SCOPE = [AuthScope.CHAT_READ, AuthScope.CHANNEL_READ_REDEMPTIONS, AuthScope.WHISPERS_READ]
AUTH_FILE=config['twitch']['auth_file']
# this will be called when the event READY is triggered, which will be on bot start
# Debug logs
log_level = logging.DEBUG if "dev".lower() in sys.argv else logging.INFO
log = logging.getLogger()
logging.basicConfig(level=log_level, format="%(name)s - %(message)s", datefmt="%X")

### Debug ###
async def callback_whisper(uuid: UUID, data: dict) -> None:
    if log_level == logging.DEBUG:
        url = "http://localhost:5002/api/tts?text=" + urllib.parse.quote_plus('o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. o. ')
        soundPlay(url)
##############

def fire_and_forget(f):
    def wrapped(*args, **kwargs):
        return asyncio.get_event_loop().run_in_executor(None, f, *args, *kwargs)
    return wrapped

async def callback(uuid: UUID, data: dict) -> None:
    data = json.loads(json.dumps(data, indent=2))

    if data["data"]["redemption"]["user_input"]:
        message = data["data"]["redemption"]["user_input"]
    if data["data"]["redemption"]["user"]["display_name"]:
        sender = data["data"]["redemption"]["user"]["display_name"]

    if data["data"]["redemption"]["reward"]["title"] == config['tts']['reward_name']:
        if not bool(re.match(".*(\.|!|\?)$", message)):
            message+="."
        print(f'{sender} said: {message}')
        url = "http://localhost:5002/api/tts?text=" + urllib.parse.quote_plus(message)
        soundPlay(url)

@fire_and_forget
def soundPlay(url: str):
        if system == "Windows":
            currentTime = str(time.time())
            os.system(f'curl -s {url} -o output-{currentTime}.wav')
            play(f'./output-{currentTime}.wav')
            os.remove(f'./output-{currentTime}.wav')
        if system == "Linux":
            os.system(f'curl -s {url} --get --output - | aplay -q')

# this is where we set up the bot
async def run_chat():
    try:
        # set up twitch api instance and add user authentication with some scopes
        twitch = await Twitch(APP_ID, APP_SECRET)
        auth = UserAuthenticator(twitch, USER_SCOPE)
        user = await first(twitch.get_users(logins=TARGET_CHANNEL))

        # Handle authentication
        try:
            authenticated_twitch, expiration = await read_token(twitch)
        except Exception as e:
            print(e)
            authenticated_twitch = await generate_token(twitch, auth)
        # authenticated_twitch = await handle_tokens(twitch, auth)
        # create chat instance
        pubsub = PubSub(authenticated_twitch)
        pubsub.start()
        uuid = await pubsub.listen_channel_points(user.id, callback)
        uuid1 = await pubsub.listen_whispers(user.id, callback_whisper)
        ## Attempt to check if new token will be used
        while True:
            await asyncio.sleep(3600)
            expiration = await validate_token(twitch)
            print(f"Validating token. Expires in {time_format(expiration)}")

    except KeyboardInterrupt:
        print("Received exit, exiting")
    finally:
        # stopping both eventsub as well as gracefully closing the connection to the API
        await pubsub.unlisten(uuid)
        await pubsub.unlisten(uuid1)
        pubsub.stop()
        await twitch.close()
# lets run our setup
asyncio.run(run_chat())