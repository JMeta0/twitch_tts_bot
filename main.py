import os
import sys
import json
import asyncio
from clean_tmp import clean_tmp
from functools import partial
from list_sounds import list_sounds
from logger import logger
from parsed_config import parsed_config
from platform import system
from sound_play import sound_play
from twitchAPI.helper import first
from twitchAPI.oauth import UserAuthenticator, UserAuthenticationStorageHelper
from twitchAPI.pubsub import PubSub, PubSubListenTimeoutException
from twitchAPI.twitch import Twitch
from twitchAPI.type import AuthScope
from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.object.eventsub import ChannelPointsCustomRewardRedemptionAddEvent
from uuid import UUID

# Meme config
cfg = parsed_config()

# Read config
MOCK_USER_ID = '91072779'
DEFAULT_RUNNER = cfg.twitch.default_runner
APP_ID = cfg.twitch.client_id
APP_SECRET = cfg.twitch.client_secret
TARGET_CHANNEL = cfg.twitch.channel
PUBSUB_SCOPE = [AuthScope.CHAT_READ, AuthScope.CHANNEL_READ_REDEMPTIONS, AuthScope.WHISPERS_READ]
EVENTSUB_SCOPE = [AuthScope.CHANNEL_READ_REDEMPTIONS]
REWARD_NAME = cfg.tts.reward_name
AUTH_FILE = cfg.twitch.auth_file
system = system()

if system == 'Windows':
    curl_command = "curl.exe"
else:
    curl_command = "curl"


async def callback_wrapped(sound_queue: asyncio.Queue, uuid: UUID, data: dict) -> None:
    try:
        callback = json.loads(json.dumps(data))
        logger.debug(callback)
        if 'whispers'.lower() in sys.argv:
            if 'body' in callback['data_object']:
                message = callback['data_object']['body']
                logger.info(f'message: {message}')
                await sound_queue.put(message)
                logger.debug(f'callback_wrapped_priv - Added "{message}" to queue. Queue size: {sound_queue.qsize()}')
        else:
            if callback['data']['redemption']['reward']['title'] == REWARD_NAME:
                message = callback['data']['redemption']['user_input']
                sender = callback['data']['redemption']['user']['display_name']
                logger.info(f'{sender} said: {message}')
                await sound_queue.put(message)
                logger.debug(f'callback_wrapped - Added "{message}" to queue. Queue size: {sound_queue.qsize()}')
    except KeyError:
        logger.error(f'callback_wrapped - Error in message Body - {callback}')

async def eventsub_on_bezio(sound_queue: asyncio.Queue, data: ChannelPointsCustomRewardRedemptionAddEvent) -> None:
    try:
        callback = json.loads(json.dumps(data.to_dict()))
        logger.debug(callback)
        if 'title' in callback['event']['reward']:
            if callback['event']['reward']['title'] == REWARD_NAME:
                    sender = callback['event']['user_name']
                    message = callback['event']['user_input']
                    logger.info(f'{sender} said: {message}')
                    await sound_queue.put(message)
                    logger.debug(f'eventsub_on_bezio - Added "{message}" to queue. Queue size: {sound_queue.qsize()}')
    except KeyError:
        logger.error(f'eventsub_on_bezio - Error in message Body')


async def start_run_chat(sound_queue):
    await asyncio.sleep(1)
    task = asyncio.create_task(run_chat(sound_queue))
    await task


async def run_chat(sound_queue: asyncio.Queue):
    try:
        # Auth
        if 'local'.lower() in sys.argv:
            base_url = 'http://localhost:8080/mock/'
            auth_base_url = 'http://localhost:8080/auth/'
            connection_url='ws://127.0.0.1:8080/ws'
            subscription_url='http://127.0.0.1:8080/'
        else:
            base_url = 'https://api.twitch.tv/helix/'
            auth_base_url = 'https://id.twitch.tv/oauth2/'
            connection_url = None
            subscription_url = None
        twitch = await Twitch(APP_ID, APP_SECRET, base_url=base_url, auth_base_url=auth_base_url)
        # Subscription
        if DEFAULT_RUNNER == 'eventsub':
            # Local
            if 'local'.lower() in sys.argv:
                twitch.auto_refresh_auth = False
                authenticated_twitch = UserAuthenticator(twitch, EVENTSUB_SCOPE, auth_base_url=auth_base_url)
                token = await authenticated_twitch.mock_authenticate(MOCK_USER_ID)
                await twitch.set_user_authentication(token, EVENTSUB_SCOPE)
                user = await first(twitch.get_users())
            # Prod
            else:
                authenticated_twitch = UserAuthenticationStorageHelper(twitch, EVENTSUB_SCOPE, storage_path=AUTH_FILE)
                await authenticated_twitch.bind()
                user = await first(twitch.get_users(logins=TARGET_CHANNEL))
            eventsub = EventSubWebsocket(twitch, connection_url=connection_url, subscription_url=subscription_url)
            callback = partial(eventsub_on_bezio, sound_queue)
            eventsub.start()
            await eventsub.listen_channel_points_custom_reward_redemption_add(user.id, callback)

        elif DEFAULT_RUNNER == 'pubsub':
            authenticated_twitch = UserAuthenticationStorageHelper(twitch, PUBSUB_SCOPE, storage_path=AUTH_FILE)
            await authenticated_twitch.bind()
            user = await first(twitch.get_users(logins=TARGET_CHANNEL))
            pubsub = PubSub(twitch)
            pubsub.start()
            if 'whispers'.lower() in sys.argv:
                callback = partial(callback_wrapped, sound_queue)
                await pubsub.listen_whispers(user.id, callback)
            else:
                callback = partial(callback_wrapped, sound_queue)
                await pubsub.listen_channel_points(user.id, callback)
        else:
            logger.error('No valid DEFAULT_RUNNER config found!')

        logger.info('Ready')

        # Loop so function won't die
        while True:
            await asyncio.sleep(1800)
            await twitch.get_refreshed_user_auth_token()

    except asyncio.CancelledError:
        if DEFAULT_RUNNER == 'eventsub':
            await eventsub.stop()
        elif DEFAULT_RUNNER == 'pubsub':
            await pubsub.stop()

        await twitch.close()


async def main(sounds_list):
    sound_queue = asyncio.Queue()

    chat_task = asyncio.create_task(start_run_chat(sound_queue))  # Call start_run_chat
    sound_task = asyncio.create_task(sound_play(sound_queue, sounds_list))

    tasks = [chat_task, sound_task]

    await asyncio.gather(*tasks, return_exceptions=True)


# Main thread #

# Check folders and config existance
dir_paths = ["sounds", "tmp"]
for dir_path in dir_paths:
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
if not os.path.exists('sox/sox.exe'):
    logger.error('SoX not found - add to path or download SoX to sox folder!')
    input("Press enter to proceed...")


clean_tmp()
sounds_list = list_sounds()

# loop = asyncio.get_event_loop() python 3.11 fix
loop = asyncio.new_event_loop()
try:
    loop.run_until_complete(main(sounds_list))
except KeyboardInterrupt:
    logger.info('Exiting BezioBot. Canceling tasks...')
    for task in asyncio.all_tasks(loop):
        task.cancel()
    loop.run_until_complete(asyncio.gather(*asyncio.all_tasks(loop), return_exceptions=True))
    loop.close()
except Exception:
    import traceback
    logger.error(traceback.format_exc())
