import asyncio
import configparser
import os
import re
import urllib.parse
from platform import system
from simpleSound import play
from twitchAPI import Twitch
from twitchAPI.chat import Chat, ChatCommand, ChatMessage, ChatSub, EventData
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.types import AuthScope, ChatEvent

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
USER_SCOPE = [AuthScope.CHAT_READ]
AUTH_FILE=config['twitch']['auth_file']
# this will be called when the event READY is triggered, which will be on bot start
async def on_ready(ready_event: EventData):
    print('Joining channels')
    # join our target channel, if you want to join multiple, either call join for each individually
    # or even better pass a list of channels as the argument
    await ready_event.chat.join_room(TARGET_CHANNEL)
    # you can do other bot initialization things in here
    print("Ready")

# this will be called whenever a message in a channel was send by either the bot OR another user
async def on_message(msg: ChatMessage):
    if not bool(re.match(".*(\.|!|\?)$", msg.text)):
        msg.text+="."
    print(f'{msg.user.name} said: {msg.text}')

    url = "http://localhost:5002/api/tts?text=" + urllib.parse.quote_plus(msg.text)

    if system == "Windows":
        os.system('curl -s "' + url + '" -o output.wav')
        play("./output.wav")
        os.remove("./output.wav")
    if system == "Linux":
        os.system('curl -s "' + url + '" --get --output - | aplay -q')

# this is where we set up the bot
async def run_chat():
    # set up twitch api instance and add user authentication with some scopes
    twitch = await Twitch(APP_ID, APP_SECRET)
    auth = UserAuthenticator(twitch, USER_SCOPE)

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
    chat = await Chat(authenticated_twitch)

    # register the handlers for the events you want
    # listen to when the bot is done starting up and ready to join channels
    chat.register_event(ChatEvent.READY, on_ready)
    # listen to chat messages
    chat.register_event(ChatEvent.MESSAGE, on_message)
    # listen to channel subscriptions
    # we are done with our setup, lets start this bot up!

    chat.start()
    ## Attempt to check if new token will be used
    try:
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
                chat = await Chat(authenticated_twitch)
    except KeyboardInterrupt:
        print("Received exit, exiting")
    finally:
        # stopping both eventsub as well as gracefully closing the connection to the API
        await chat.stop()
        await twitch.close()
# lets run our setup
asyncio.run(run_chat())