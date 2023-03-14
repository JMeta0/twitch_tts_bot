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
from uuid import UUID
from oauth import generate_token, read_token
import logging
import time
from functools import partial
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
# Debug logs
log_level = logging.DEBUG if "dev".lower() in sys.argv else print
log = logging.getLogger()
logging.basicConfig(level=log_level, format="%(name)s - %(message)s", datefmt="%X")

### Debug ###
async def callback_wrapped(sound_queue: asyncio.Queue, uuid: UUID, data: dict) -> None:
    callback = json.loads(json.dumps(data, indent=2))
    message = callback["data"]["redemption"]["user_input"]
    sender = callback["data"]["redemption"]["user"]["display_name"]

    if callback["data"]["redemption"]["reward"]["title"] == config['tts']['reward_name']:
        if not bool(re.match(".*(\.|!|\?)$", message)):
            message+="."
        print(f'{sender} said: {message}')

        url = "http://localhost:5002/api/tts?text=" + urllib.parse.quote_plus(message)
        await sound_queue.put(url)
        logging.DEBUG(f'soundPlay - Added task to queue. Queue size: {sound_queue.qsize()}')
##############

async def soundPlay(sound_queue):
    while True:
        try:
            item = await asyncio.wait_for(sound_queue.get(), timeout=1)
            logging.DEBUG(f'soundPlay - Executing task from queue. Queue size: {sound_queue.qsize()}')
            # Sysmtem sound play logic
            if system == "Windows":
                time = time.time()
                os.system('curl -s "' + item + '" -o output{time}.wav')
                play("./output.wav")
                os.remove("./output{time}.wav")
            if system == "Linux":
                os.system('curl -s "' + item + '" --get --output - | aplay -q')
            logging.DEBUG(f'soundPlay - Task done. Queue size: {sound_queue.qsize()}')
            sound_queue.task_done()
        except asyncio.TimeoutError:
            pass
        except asyncio.CancelledError:
            return
        except KeyboardInterrupt:
            print("soundPlay - Received exit, exiting")

# this is where we set up the bot
async def run_chat(sound_queue: asyncio.Queue):
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

        # create chat instance
        pubsub = PubSub(authenticated_twitch)
        pubsub.start()

        callback = partial(callback_wrapped, sound_queue)
        uuid = await pubsub.listen_channel_points(user.id, callback)

        # Loop so function won't die
        while True:
            await asyncio.sleep(60)
    except asyncio.TimeoutError:
        pass
    except asyncio.CancelledError:
        return
    except KeyboardInterrupt:
        print("run_chat - Received exit, exiting")
    finally:
        # stopping both eventsub as well as gracefully closing the connection to the API
        await pubsub.unlisten(uuid)
        pubsub.stop()
        await twitch.close()

# lets run our setup
async def main():
    sound_queue = asyncio.Queue()
    # Run the chat and sound play tasks concurrently
    chat_task = asyncio.create_task(run_chat(sound_queue))
    sound_task = asyncio.create_task(soundPlay(sound_queue))

    # Wait for both tasks to complete before stopping the event loop
    await asyncio.wait([chat_task, sound_task], return_when=asyncio.ALL_COMPLETED)

# Create the event loop and run the main coroutine
loop = asyncio.get_event_loop()
try:
    loop.create_task(main())
    loop.run_forever()
except KeyboardInterrupt:
    print("main - Received exit, exiting")
finally:
    loop.close()