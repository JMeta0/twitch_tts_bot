import os
import sys
import json
import asyncio
import traceback
import time
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


class TwitchTTSBot:
    """
    Main class for the Twitch TTS Bot application.
    Handles Twitch connection, authentication, and event subscription.
    """

    def __init__(self):
        """Initialize the TwitchTTSBot with configuration and system settings."""
        # Load configuration
        self.cfg = parsed_config()

        # Check if configuration is valid
        if not self.cfg:
            logger.error("Invalid configuration. Exiting.")
            sys.exit(1)

        # Twitch configuration
        self.default_runner = self.cfg.twitch.default_runner
        self.app_id = self.cfg.twitch.client_id
        self.app_secret = self.cfg.twitch.client_secret
        self.target_channel = self.cfg.twitch.channel
        self.auth_file = self.cfg.twitch.auth_file
        self.reward_name = self.cfg.tts.reward_name

        # Auth scopes
        self.pubsub_scope = [AuthScope.CHAT_READ, AuthScope.CHANNEL_READ_REDEMPTIONS, AuthScope.WHISPERS_READ]
        self.eventsub_scope = [AuthScope.CHANNEL_READ_REDEMPTIONS]

        # System detection
        self.system = system()

        # Determine curl command based on platform
        if self.system == 'Windows':
            self.curl_command = "curl.exe"
        else:
            self.curl_command = "curl"

        # Twitch API objects
        self.twitch = None
        self.pubsub = None
        self.eventsub = None

        # Queue for sound messages
        self.sound_queue = asyncio.Queue()

        # Connection state
        self.running = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 5  # Initial delay in seconds

        # Load available sounds
        self.sounds_list = list_sounds()

    async def callback_wrapped(self, uuid: UUID, data: dict) -> None:
        """
        Callback for PubSub events.

        Args:
            uuid (UUID): Event UUID
            data (dict): Event data
        """
        try:
            callback = json.loads(json.dumps(data))
            logger.debug(callback)

            if 'whispers'.lower() in sys.argv:
                if 'body' in callback['data_object']:
                    message = callback['data_object']['body']
                    logger.info(f'message: {message}')
                    await self.sound_queue.put(message)
                    logger.debug(f'callback_wrapped_priv - Added "{message}" to queue. Queue size: {self.sound_queue.qsize()}')
            else:
                if callback['data']['redemption']['reward']['title'] == self.reward_name:
                    message = callback['data']['redemption']['user_input']
                    sender = callback['data']['redemption']['user']['display_name']
                    logger.info(f'{sender} said: {message}')
                    await self.sound_queue.put(message)
                    logger.debug(f'callback_wrapped - Added "{message}" to queue. Queue size: {self.sound_queue.qsize()}')
        except KeyError as e:
            logger.error(f'callback_wrapped - Error in message Body - {callback}: {e}')
        except Exception as e:
            logger.error(f'callback_wrapped - Unexpected error: {e}')

    async def eventsub_on_bezio(self, data: ChannelPointsCustomRewardRedemptionAddEvent) -> None:
        """
        Callback for EventSub events.

        Args:
            data (ChannelPointsCustomRewardRedemptionAddEvent): Event data
        """
        try:
            callback = json.loads(json.dumps(data.to_dict()))
            logger.debug(callback)

            if 'title' in callback['event']['reward']:
                if callback['event']['reward']['title'] == self.reward_name:
                    sender = callback['event']['user_name']
                    message = callback['event']['user_input']
                    logger.info(f'{sender} said: {message}')
                    await self.sound_queue.put(message)
                    logger.debug(f'eventsub_on_bezio - Added "{message}" to queue. Queue size: {self.sound_queue.qsize()}')
        except KeyError as e:
            logger.error(f'eventsub_on_bezio - Error in message Body: {e}')
        except Exception as e:
            logger.error(f'eventsub_on_bezio - Unexpected error: {e}')

    async def connect_to_twitch(self):
        """
        Connect to Twitch API and set up event subscriptions.

        Returns:
            bool: True if connection was successful, False otherwise
        """
        try:
            # Reset Twitch API objects if they exist
            if self.twitch:
                await self.twitch.close()
                self.twitch = None

            if self.pubsub:
                await self.pubsub.stop()
                self.pubsub = None

            if self.eventsub:
                await self.eventsub.stop()
                self.eventsub = None

            # Determine API endpoints based on mode
            if 'local'.lower() in sys.argv:
                base_url = 'http://localhost:8080/mock/'
                auth_base_url = 'http://localhost:8080/auth/'
                connection_url = 'ws://127.0.0.1:8080/ws'
                subscription_url = 'http://127.0.0.1:8080/'
            else:
                base_url = 'https://api.twitch.tv/helix/'
                auth_base_url = 'https://id.twitch.tv/oauth2/'
                connection_url = None
                subscription_url = None

            # Initialize Twitch API
            self.twitch = await Twitch(self.app_id, self.app_secret, base_url=base_url, auth_base_url=auth_base_url)

            # Set up authentication and subscription based on runner
            if self.default_runner == 'eventsub':
                # Local mode authentication
                if 'local'.lower() in sys.argv:
                    self.twitch.auto_refresh_auth = False
                    authenticated_twitch = UserAuthenticator(self.twitch, self.eventsub_scope, auth_base_url=auth_base_url)
                    token = await authenticated_twitch.mock_authenticate('91072779')  # Use mock user ID
                    await self.twitch.set_user_authentication(token, self.eventsub_scope)
                    user = await first(self.twitch.get_users())
                # Production mode authentication
                else:
                    authenticated_twitch = UserAuthenticationStorageHelper(self.twitch, self.eventsub_scope, storage_path=self.auth_file)
                    await authenticated_twitch.bind()
                    user = await first(self.twitch.get_users(logins=self.target_channel))

                # Set up EventSub
                self.eventsub = EventSubWebsocket(self.twitch, connection_url=connection_url, subscription_url=subscription_url)
                callback = partial(self.eventsub_on_bezio)
                self.eventsub.start()
                await self.eventsub.listen_channel_points_custom_reward_redemption_add(user.id, callback)

            elif self.default_runner == 'pubsub':
                # Authentication for PubSub
                authenticated_twitch = UserAuthenticationStorageHelper(self.twitch, self.pubsub_scope, storage_path=self.auth_file)
                await authenticated_twitch.bind()
                user = await first(self.twitch.get_users(logins=self.target_channel))

                # Set up PubSub
                self.pubsub = PubSub(self.twitch)
                self.pubsub.start()

                callback = partial(self.callback_wrapped)
                if 'whispers'.lower() in sys.argv:
                    await self.pubsub.listen_whispers(user.id, callback)
                else:
                    await self.pubsub.listen_channel_points(user.id, callback)
            else:
                logger.error('No valid DEFAULT_RUNNER config found!')
                return False

            # Connection successful
            logger.info('Connected to Twitch successfully')
            self.reconnect_attempts = 0
            self.reconnect_delay = 5
            return True

        except Exception as e:
            logger.error(f'Failed to connect to Twitch: {e}')
            logger.debug(traceback.format_exc())
            return False

    async def run_chat(self):
        """
        Main loop for handling Twitch connection, with automatic reconnection.
        """
        self.running = True

        while self.running:
            try:
                # Attempt to connect to Twitch
                if not await self.connect_to_twitch():
                    await self.handle_reconnect()
                    continue

                logger.info('Ready')

                # Keep connection alive
                while self.running:
                    try:
                        # Refresh auth token periodically
                        await asyncio.sleep(1800)  # 30 minutes
                        await self.twitch.get_refreshed_user_auth_token()
                    except PubSubListenTimeoutException:
                        logger.warning("PubSub connection timeout. Reconnecting...")
                        break
                    except asyncio.CancelledError:
                        self.running = False
                        break
                    except Exception as e:
                        logger.error(f"Error in connection: {e}")
                        logger.debug(traceback.format_exc())
                        break

            except asyncio.CancelledError:
                self.running = False
                break
            except Exception as e:
                logger.error(f"Unexpected error in run_chat: {e}")
                logger.debug(traceback.format_exc())
                await self.handle_reconnect()

        # Clean up on exit
        await self.cleanup()

    async def handle_reconnect(self):
        """
        Handle reconnection with exponential backoff.
        """
        self.reconnect_attempts += 1

        if self.reconnect_attempts > self.max_reconnect_attempts:
            logger.error(f"Maximum reconnection attempts ({self.max_reconnect_attempts}) reached. Giving up.")
            self.running = False
            return

        # Calculate delay with exponential backoff (capped at 5 minutes)
        delay = min(self.reconnect_delay * (2 ** (self.reconnect_attempts - 1)), 300)

        logger.warning(f"Connection failed. Reconnecting in {delay} seconds (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})...")

        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            self.running = False

    async def cleanup(self):
        """
        Clean up resources on shutdown.
        """
        logger.info("Cleaning up resources...")

        try:
            if self.eventsub:
                await self.eventsub.stop()

            if self.pubsub:
                await self.pubsub.stop()

            if self.twitch:
                await self.twitch.close()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    async def start_tasks(self):
        """
        Start all required tasks.
        """
        # Create tasks for chat and sound processing
        chat_task = asyncio.create_task(self.run_chat())
        sound_task = asyncio.create_task(sound_play(self.sound_queue, self.sounds_list))

        tasks = [chat_task, sound_task]

        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except asyncio.CancelledError:
            logger.info("Tasks cancelled")
        except Exception as e:
            logger.error(f"Error in tasks: {e}")
            logger.debug(traceback.format_exc())


async def main():
    """
    Main entry point for the application.
    """
    # Initialize the bot
    bot = TwitchTTSBot()

    # Start the bot
    await bot.start_tasks()


# Main thread #
if __name__ == "__main__":
    # Check folders and config existence
    dir_paths = ["sounds", "tmp"]
    for dir_path in dir_paths:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

    # Check for SoX on Windows
    if system() == 'Windows' and not os.path.exists('sox/sox.exe'):
        logger.error('SoX not found - add to path or download SoX to sox folder!')
        input("Press enter to proceed...")

    # Clean temporary files
    clean_tmp()

    # Get event loop
    loop = asyncio.new_event_loop()

    try:
        # Run the main function
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info('Exiting BezioBot. Canceling tasks...')
        for task in asyncio.all_tasks(loop):
            task.cancel()
        loop.run_until_complete(asyncio.gather(*asyncio.all_tasks(loop), return_exceptions=True))
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        logger.error(traceback.format_exc())
    finally:
        loop.close()