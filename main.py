import asyncio
import json
import logging
import sys
from clean_tmp import clean_tmp
from functools import partial
from list_sounds import list_sounds
from oauth import generate_token, read_token
from parsed_config import parsed_config
from platform import system
from sound_play import sound_play
from twitchAPI.helper import first
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.pubsub import PubSub
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
    try:
        message = callback["data"]["redemption"]["user_input"]
        sender = callback["data"]["redemption"]["user"]["display_name"]
        if callback["data"]["redemption"]["reward"]["title"] == REWARD_NAME:
            print(f'{sender} said: {message}')
            await sound_queue.put(message)
            log.debug(f'callback_wrapped - Added {message} to queue. Queue size: {sound_queue.qsize()}')
    except KeyError:
        log.error('callback_wrapped - Error in message Body')
        return


async def callback_wrapped_priv(sound_queue: asyncio.Queue, uuid: UUID, data: dict) -> None:
    try:
        callback = json.loads(json.dumps(data))
        message = callback["data_object"]["body"]
        await sound_queue.put(message)
        log.debug(f'callback_wrapped_priv - Added {message} to queue. Queue size: {sound_queue.qsize()}')
    except KeyError:
        log.error('callback_wrapped_priv - Error in message Body')
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

        # Whispers for debug
        # callback = partial(callback_wrapped_priv, sound_queue)
        # uuid = await pubsub.listen_whispers(user.id, callback)

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


async def main(cancel_event, sounds_list):
    sound_queue = asyncio.Queue()

    chat_task = asyncio.create_task(run_chat(sound_queue, cancel_event))
    sound_task = asyncio.create_task(sound_play(sound_queue, cancel_event, sounds_list))

    try:
        await asyncio.gather(chat_task, sound_task, return_exceptions=True)
    finally:
        chat_task.cancel()
        sound_task.cancel()


# Main thread
clean_tmp()
sounds_list = list_sounds()
loop = asyncio.get_event_loop()
try:
    cancel_event = asyncio.Event()
    asyncio.run(main(cancel_event, sounds_list))
except KeyboardInterrupt:
    log.info("Caught keyboard interrupt. Canceling tasks...")
    cancel_event.set()
finally:
    log.info("Cleaning up...")
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.close()
