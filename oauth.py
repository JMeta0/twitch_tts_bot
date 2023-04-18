import json
import sys
import os
import logging
from config_pyrser import MissingFieldError
from parsed_config import parsed_config, parsed_tokens
import requests
from twitchAPI.types import AuthScope

# Meme config
cfg = parsed_config()

# Read config
APP_ID = cfg.twitch.client_id
APP_SECRET = cfg.twitch.client_secret
TARGET_CHANNEL = cfg.twitch.channel
USER_SCOPE = [AuthScope.CHAT_READ, AuthScope.CHANNEL_READ_REDEMPTIONS, AuthScope.WHISPERS_READ]
AUTH_FILE = cfg.twitch.auth_file
REWARD_NAME = cfg.tts.reward_name

# Logs
log = logging.getLogger()
if "debug".lower() in sys.argv:
    log_level = logging.DEBUG
elif "info".lower() in sys.argv:
    log_level = logging.INFO
else:
    log_level = logging.ERROR

logging.basicConfig(level=log_level, format="%(name)s - %(message)s", datefmt="%X")


def save_token(new_token, new_refresh_token):
    log.debug("oauth - save_token - Saving token to file")
    with open(AUTH_FILE, "w") as f:
        f.write("[auth]\n")
        f.write(f"token = {new_token}\n")
        f.write(f"refresh_token = {new_refresh_token}")


async def generate_token(twitch, auth):
    print("Generating new token")
    try:
        token, refresh_token = await auth.authenticate()
    except Exception as e:
        raise Exception(f"Failed to generate new token: {e}")
        exit(1)
    await twitch.set_user_authentication(token, USER_SCOPE, refresh_token)
    save_token(token, refresh_token)
    print("Successfully generated new token")
    return twitch


async def read_token(twitch):
    if os.path.isfile(AUTH_FILE):
        auth = parsed_tokens(cfg.twitch.auth_file)
        try:
            token = auth.auth.token
            refresh_token = auth.auth.refresh_token
            print('Successfully read token')
        except (KeyError, MissingFieldError):
            print(f'{AUTH_FILE} is malformed')

        await twitch.set_user_authentication(token, USER_SCOPE, refresh_token)
        expiration = await validate_token(twitch)
        return twitch, expiration
    else:
        raise Exception("No token file found")


async def validate_token(twitch):
    token = str(twitch._Twitch__user_auth_token)
    try:
        response = requests.get(
            "https://id.twitch.tv/oauth2/validate",
            headers={"Authorization": f"OAuth {token}"})
    except Exception as e:
        print(f"Validation failed: {e}")
    response_parsed = json.loads(response.text)
    expiration = response_parsed["expires_in"]
    return expiration
