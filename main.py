import os
import sys
import json
import asyncio
from clean_tmp import clean_tmp
from functools import partial
from list_sounds import list_sounds
from logger import logger
from oauth import generate_token, read_token, save_token
from parsed_config import parsed_config
from platform import system
from sound_play import sound_play
from twitchAPI.helper import first
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.pubsub import PubSub, PubSubListenTimeoutException
from twitchAPI.twitch import Twitch
from twitchAPI.types import AuthScope
from uuid import UUID

# Meme config
cfg = parsed_config()

# Read config
APP_ID = cfg.twitch.client_id
APP_SECRET = cfg.twitch.client_secret
TARGET_CHANNEL = cfg.twitch.channel
USER_SCOPE = [AuthScope.CHAT_READ, AuthScope.CHANNEL_READ_REDEMPTIONS, AuthScope.WHISPERS_READ]
REWARD_NAME = cfg.tts.reward_name
system = system()

if system == 'Windows':
    curl_command = "curl.exe"
else:
    curl_command = "curl"


async def callback_wrapped(sound_queue: asyncio.Queue, uuid: UUID, data: dict) -> None:
    try:
        callback = json.loads(json.dumps(data))

        if 'whispers'.lower() in sys.argv:
            if "body" in callback['data_object']:
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


# Temp attempt to fix PubSubListenTimeoutException
class CustomPubSub(PubSub):
    def __init__(self, token: str, twitch, callback=None):
        super().__init__(token)
        self.callback = callback
        self.twitch = twitch

    async def _PubSub__handle_reconnect(self):
        while True:
            try:
                await self.__connect()
            except PubSubListenTimeoutException:
                logger.error('Restarting run_chat...')
                self.stop()  # Stop pubsub
                await self.twitch.close()  # Close twitch connection
                if self.callback:
                    self.callback()
                break
            except Exception as e:
                logger.error(f'CustomPubSub - Unexpected error: {e}')
                await asyncio.sleep(5)  # Sleep for a short time before retrying
            else:
                break


async def start_run_chat(sound_queue):
    await asyncio.sleep(1)
    task = asyncio.create_task(run_chat(sound_queue))
    await task


async def run_chat(sound_queue: asyncio.Queue):
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
            logger.error(e)
            authenticated_twitch = await generate_token(twitch, auth)

        pubsub = CustomPubSub(authenticated_twitch, twitch, start_run_chat)  # Pass the twitch object
        pubsub.start()

        if 'whispers'.lower() in sys.argv:
            callback = partial(callback_wrapped, sound_queue)
            await pubsub.listen_whispers(user.id, callback)
        else:
            callback = partial(callback_wrapped, sound_queue)
            await pubsub.listen_channel_points(user.id, callback)

        logger.info('Ready')
        # Loop so function won't die
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pubsub.stop()
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
