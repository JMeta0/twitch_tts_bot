import asyncio
import configparser
import os
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

# Read config
config = configparser.ConfigParser()
config.read('config.txt')
system=system()

# Set values
APP_ID = config['twitch']['client_id']
APP_SECRET = config['twitch']['client_secret']
TARGET_CHANNEL = config['twitch']['channel']
USER_SCOPE = [AuthScope.CHAT_READ, AuthScope.CHANNEL_READ_REDEMPTIONS]
AUTH_FILE=config['twitch']['auth_file']
# this will be called when the event READY is triggered, which will be on bot start

async def callback(uuid: UUID, data: dict) -> None:
    callback = json.loads(json.dumps(data, indent=2))
    message = callback["data"]["redemption"]["user_input"]
    sender = callback["data"]["redemption"]["user"]["display_name"]

    if callback["data"]["redemption"]["reward"]["title"] == config['tts']['reward_name']:
        if not bool(re.match(".*(\.|!|\?)$", message)):
            message+="."
        print(f'{sender} said: {message}')
        url = "http://localhost:5002/api/tts?text=" + urllib.parse.quote_plus(message)

        if system == "Windows":
            os.system('curl -s "' + url + '" -o output.wav')
            play("./output.wav")
            os.remove("./output.wav")
        if system == "Linux":
            os.system('curl -s "' + url + '" --get --output - | aplay -q')

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
            print(f"Validating token. Expires in: {time_format(expiration)}")
            if expiration < 5400:
                try:
                    authenticated_twitch = await refresh_token(twitch)
                except Exception as e1:
                    print(f"Refreshing token failed: {e1}")
                    authenticated_twitch = await generate_token(twitch, auth)
        except Exception as e:
            print(e)
            authenticated_twitch = await generate_token(twitch, auth)
        # authenticated_twitch = await handle_tokens(twitch, auth)
        # create chat instance
        pubsub = PubSub(authenticated_twitch)
        pubsub.start()
        uuid = await pubsub.listen_channel_points(user.id, callback)
        ## Attempt to check if new token will be used
        while True:
            await asyncio.sleep(3600)
            expiration = await validate_token(twitch)
            print(f"Validating token. Expires in {time_format(expiration)}")
            if expiration < 5400:
                print("Refreshing token")
                try:
                    authenticated_twitch = await refresh_token(twitch)
                except Exception as e1:
                    print(f"Refreshing token failed: {e1}")
                    authenticated_twitch = await generate_token(twitch, auth)
                pubsub = PubSub(authenticated_twitch)
    except KeyboardInterrupt:
        print("Received exit, exiting")
    finally:
        # stopping both eventsub as well as gracefully closing the connection to the API
        await pubsub.unlisten(uuid)
        pubsub.stop()
        await twitch.close()
# lets run our setup
asyncio.run(run_chat())