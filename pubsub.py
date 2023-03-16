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
from oauth import generate_token, read_token
from fixNumbers import fix_numbers
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
# Logs
log = logging.getLogger()
if "debug".lower() in sys.argv:
    log_level = logging.DEBUG
else:
    log_level = logging.ERROR

logging.basicConfig(level=log_level, format="%(name)s - %(message)s", datefmt="%X")

async def callback_wrapped(sound_queue: asyncio.Queue, uuid: UUID, data: dict) -> None:
    callback = json.loads(json.dumps(data, indent=2))
    message = callback["data"]["redemption"]["user_input"]
    sender = callback["data"]["redemption"]["user"]["display_name"]

    if callback["data"]["redemption"]["reward"]["title"] == config['tts']['reward_name']:
        message=fix_numbers(message)
        if not bool(re.match(".*(\.|!|\?)$", message)):
            message+="."
        print(f'{sender} said: {message}')

        url = "http://localhost:5002/api/tts?text=" + urllib.parse.quote_plus(message)
        await sound_queue.put(url)
        log.debug(f'soundPlay - Added {url} to queue. Queue size: {sound_queue.qsize()}')

async def soundPlay(sound_queue, cancel_event):
    while True:
        try:
            log.debug(f'soundPlay - waiting for item in queue.')
            url = await asyncio.wait_for(sound_queue.get(), timeout=60)
            log.debug(f'soundPlay - Executing {url} from queue. Queue size: {sound_queue.qsize()}')

            if system == 'Windows':
                log.debug(f'Executing task.')
                fileName = f"output-{time.time()}.wav"
                os.system(f'curl -s {url} -o {fileName}')
                play(f'./{fileName}')
                os.remove(f'./{fileName}')
            if system == 'Linux':
                os.system(f'curl -s {url} --get --output - | aplay -q')
            sound_queue.task_done()
            log.debug(f'soundPlay - Task done. Queue size: {sound_queue.qsize()}')
        except asyncio.TimeoutError:
            pass
        except KeyboardInterrupt:
            log.error('soundPlay - Received exit, exiting')
            cancel_event.set()
            return

async def run_chat(sound_queue: asyncio.Queue, cancel_event):
    try:
        twitch = await Twitch(APP_ID, APP_SECRET)
        auth = UserAuthenticator(twitch, USER_SCOPE)
        user = await first(twitch.get_users(logins=TARGET_CHANNEL))

        # Handle authentication
        try:
            authenticated_twitch, expiration = await read_token(twitch)
        except Exception as e:
            log.error(e)
            authenticated_twitch = await generate_token(twitch, auth)

        # create chat instance
        pubsub = PubSub(authenticated_twitch)
        pubsub.start()

        callback = partial(callback_wrapped, sound_queue)
        uuid = await pubsub.listen_channel_points(user.id, callback)

        # Loop so function won't die
        log.info("Ready")
        while True:
            await asyncio.sleep(3600)

            # TODO Re add saving token to file
    except KeyboardInterrupt:
        cancel_event.set()
    except Exception as e:
        log.error(f'Error: {e}')
    finally:
        await pubsub.unlisten(uuid)
        pubsub.stop()
        await twitch.close()

async def main(cancel_event):
    sound_queue = asyncio.Queue()

    chat_task = asyncio.create_task(run_chat(sound_queue, cancel_event))
    sound_task = asyncio.create_task(soundPlay(sound_queue, cancel_event))

    try:
        await asyncio.wait([chat_task, sound_task], return_when=asyncio.ALL_COMPLETED)
    finally:
        chat_task.cancel()
        sound_task.cancel()
        await asyncio.gather(chat_task, sound_task, return_exceptions=True)

# Main thread
loop = asyncio.get_event_loop()
try:
    cancel_event = asyncio.Event()
    asyncio.run(main(cancel_event))
except KeyboardInterrupt:
    log.error("Caught keyboard interrupt. Canceling tasks...")
    cancel_event.set()
finally:
    log.info("Cleaning up...")
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.close()