import asyncio
import logging
import sys
from os import makedirs, path
from clean_tmp import clean_tmp
from functools import partial
from list_sounds import list_sounds
from oauth import generate_token, read_token, save_token
from parsed_config import parsed_config
from platform import system
from sound_play import sound_play
from twitchAPI.helper import first
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.pubsub import PubSub
from twitchAPI.twitch import Twitch
from twitchAPI.types import AuthScope, PubSubListenTimeoutException
from uuid import UUID
import subprocess

# Meme config
cfg = parsed_config()

# Read config
APP_ID = cfg.twitch.client_id
APP_SECRET = cfg.twitch.client_secret
TARGET_CHANNEL = cfg.twitch.channel
USER_SCOPE = [AuthScope.CHAT_READ, AuthScope.CHANNEL_READ_REDEMPTIONS, AuthScope.WHISPERS_READ]
AUTH_FILE = cfg.twitch.auth_file
REWARD_NAME = cfg.tts.reward_name
system = system()

# Logs
log = logging.getLogger()
if 'debug'.lower() in sys.argv:
    log_level = logging.DEBUG
elif 'info'.lower() in sys.argv:
    log_level = logging.INFO
else:
    log_level = logging.ERROR

logging.basicConfig(level=log_level, format='%(name)s - %(message)s', datefmt='%X')


async def callback_wrapped(sound_queue: asyncio.Queue, uuid: UUID, data: dict) -> None:
    try:
        message = data['data']['redemption']['user_input']
        sender = data['data']['redemption']['user']['display_name']
        if data['data']['redemption']['reward']['title'] == REWARD_NAME:
            print(f'{sender} said: {message}')
            await sound_queue.put(message)
            log.debug(f'callback_wrapped - Added {message} to queue. Queue size: {sound_queue.qsize()}')
    except KeyError:
        log.error('callback_wrapped - Error in message Body')


async def callback_wrapped_priv(sound_queue: asyncio.Queue, uuid: UUID, data: dict) -> None:
    try:
        message = data['data_object']['body']
        await sound_queue.put(message)
        log.debug(f'callback_wrapped_priv - Added {message} to queue. Queue size: {sound_queue.qsize()}')
    except KeyError:
        log.error('callback_wrapped_priv - Error in message Body')


async def run_chat(sound_queue: asyncio.Queue):
    while True:
        try:
            twitch = await Twitch(APP_ID, APP_SECRET)
            auth = UserAuthenticator(twitch, USER_SCOPE)
            user = await first(twitch.get_users(logins=TARGET_CHANNEL))

            # Save token on refresh
            twitch.user_auth_refresh_callback = save_token

            # Handle authentication
            try:
                authenticated_twitch, _ = await read_token(twitch)
            except Exception as e:
                log.error(e)
                authenticated_twitch = await generate_token(twitch, auth)

            # create chat instance
            pubsub = PubSub(authenticated_twitch)
            pubsub.start()

            # callback = partial(callback_wrapped, sound_queue)
            # await pubsub.listen_channel_points(user.id, callback)

            # Whispers for debug
            callback = partial(callback_wrapped_priv, sound_queue)
            await pubsub.listen_whispers(user.id, callback)

            print('Ready')
            # Loop so function won't die
            while True:
                await asyncio.sleep(3600)
        except PubSubListenTimeoutException:
            pubsub.stop()
            await twitch.close()
            log.error('run_chat - Caught PubSubListenTimeoutException. Attempting to reconnect...')
        except asyncio.CancelledError:
            pubsub.stop()
            await twitch.close()
            break


async def main(sounds_list):
    sound_queue = asyncio.Queue()

    chat_task = asyncio.create_task(run_chat(sound_queue))
    sound_task = asyncio.create_task(sound_play(sound_queue, sounds_list))

    tasks = [chat_task, sound_task]

    await asyncio.gather(*tasks, return_exceptions=True)


# Main thread #

# Check folders and config existance
dir_paths = ["sounds", "tmp"]
for dir_path in dir_paths:
    if not path.exists(dir_path):
        makedirs(dir_path)
if not path.exists('ffmpeg.exe'):
    log.error('ffmpeg.exe not found - add to path or download ffmpeg to this folder!')
    input("Press enter to proceed...")
# Check if TTS server is working
try:
    subprocess.run('curl.exe -s http://localhost:5002', check=True, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
except subprocess.CalledProcessError:
    log.error('TTS server is not responding. Is it running?')
    input("Press enter to proceed...")
#

clean_tmp()
sounds_list = list_sounds()

loop = asyncio.get_event_loop()
try:
    loop.run_until_complete(main(sounds_list))
except KeyboardInterrupt:
    log.info('Caught keyboard interrupt. Canceling tasks...')
    for task in asyncio.all_tasks(loop):
        task.cancel()
    loop.run_until_complete(asyncio.gather(*asyncio.all_tasks(loop), return_exceptions=True))
    loop.close()
