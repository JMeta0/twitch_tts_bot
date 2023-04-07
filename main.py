import asyncio
import os
import sys
import re
import urllib.parse
from platform import system
from simpleSound import play
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.types import AuthScope
from twitchAPI.pubsub import PubSub
from twitchAPI.twitch import Twitch
from twitchAPI.helper import first
import json
from uuid import UUID
import logging
import time
from functools import partial
from oauth import generate_token, read_token
from fixNumbers import fix_numbers
from split_message import split_message
from list_sounds import list_sounds
from parsedConfig import parsed_config
from pydub import AudioSegment
from clean_tmp import clean_tmp

# Meme config
cfg = parsed_config()

# Read config
APP_ID = cfg.twitch.client_id
APP_SECRET = cfg.twitch.client_secret
TARGET_CHANNEL = cfg.twitch.channel
USER_SCOPE = [AuthScope.CHAT_READ, AuthScope.CHANNEL_READ_REDEMPTIONS]
AUTH_FILE = cfg.twitch.auth_file
REWARD_NAME = cfg.tts.reward_name
system = system()

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

    if callback["data"]["redemption"]["reward"]["title"] == REWARD_NAME:
        print(f'{sender} said: {message}')
        await sound_queue.put(message)
        log.debug(f'soundPlay - Added {message} to queue. Queue size: {sound_queue.qsize()}')


async def callback_wrapped_priv(sound_queue: asyncio.Queue, uuid: UUID, data: dict) -> None:
    callback = json.loads(json.dumps(data))
    message = callback["data_object"]["body"]

    await sound_queue.put(message)
    log.debug(f'soundPlay - Added {message} to queue. Queue size: {sound_queue.qsize()}')


async def soundPlay(sound_queue, cancel_event):
    while True:
        try:
            log.debug('soundPlay - waiting for item in queue.')

            message = await asyncio.wait_for(sound_queue.get(), timeout=1)
            log.debug(f'soundPlay - Executing {message} from queue. Queue size: {sound_queue.qsize()}')

            # Split message and potential sounds,
            sentence_array = split_message(message)
            log.debug(f"sentence_array - {sentence_array}")
            wavs = []
            log.debug(f"working on sentences - {sentence_array}")

            for index, sentence in enumerate(sentence_array):
                if sentence_array[index] in sounds_list:
                    log.debug("found sentence in sounds array")
                    wavs.append(f'sounds/{sentence[1:-1]}.wav')
                else:
                    # Fix numbers
                    sentence = fix_numbers(sentence)
                    # Add symbol at message end if it doesn't exist
                    if not bool(re.match(".*(\.|!|\?)$", sentence)):
                        sentence += "."

                    log.debug(sentence)

                    url = f"http://localhost:5002/api/tts?text={urllib.parse.quote_plus(sentence)}"
                    os.system(f'curl -s {url} -o tmp/{index}.wav')
                    wavs.append(f'tmp/{index}.wav')
            log.debug(f"soundPlay - files are {wavs}")

            combined_sounds = AudioSegment.empty()
            log.debug("soundPlay - combining output")
            for path in wavs:
                combined_sounds += AudioSegment.from_wav(path)
            log.debug("soundPlay - exporting output")
            combined_sounds.export("output.wav", format="wav")

            # Play
            if system == 'Windows':
                log.debug(f'soundPlay - Playing sound on {system}')
                play('./output.wav')
                os.remove('./output.wav')
            if system == 'Linux':
                log.debug(f'soundPlay - Playing sound on {system}')
                os.system('aplay -q ./output.wav')
                os.remove('./output.wav')
            clean_tmp()
            # Remove item from queue
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

        # callback = partial(callback_wrapped, sound_queue)
        # uuid = await pubsub.listen_channel_points(user.id, callback)

        # Whispers for test
        callback = partial(callback_wrapped_priv, sound_queue)
        uuid = await pubsub.listen_whispers(user.id, callback)

        print("Ready")
        # Loop so function won't die
        while True:
            await asyncio.sleep(3600)
            token = await twitch.get_refreshed_user_auth_token()
            log.debug(f"Refreshing - {token}")
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
clean_tmp()
sounds_list = list_sounds()
loop = asyncio.get_event_loop()
try:
    cancel_event = asyncio.Event()
    asyncio.run(main(cancel_event))
except KeyboardInterrupt:
    log.info("Caught keyboard interrupt. Canceling tasks...")
    cancel_event.set()
finally:
    log.info("Cleaning up...")
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.close()
