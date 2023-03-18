import json
import os

from config_pyrser import MissingFieldError
from parsedConfig import parsed_config, parsed_tokens
import requests
from twitchAPI.types import AuthScope

# Meme config
cfg = parsed_config()

# Read config
APP_ID = cfg.twitch.client_id
APP_SECRET = cfg.twitch.client_secret
TARGET_CHANNEL = cfg.twitch.channel
USER_SCOPE = [AuthScope.CHAT_READ, AuthScope.CHANNEL_READ_REDEMPTIONS]
AUTH_FILE = cfg.twitch.auth_file
REWARD_NAME = cfg.tts.reward_name


# Functions

def save_token(new_token, new_refresh_token):
    # Save them to file
    f = open(AUTH_FILE, "w")
    f.write("[auth]\n")
    f.write(f"token = {new_token}\n")
    f.write(f"refresh_token = {new_refresh_token}")
    f.close()


async def generate_token(twitch: dict, auth: dict):
    print("Generating new token")
    # Get token and refresh token
    try:
        token, refresh_token = await auth.authenticate()
    except Exception as e:
        raise Exception(f"Failed to generate new token: {e}")
        exit(1)
    await twitch.set_user_authentication(token, USER_SCOPE, refresh_token)
    # Save them to file
    save_token(token, refresh_token)
    print("Successfully generated new token")
    return twitch


async def read_token(twitch: dict):
    if os.path.isfile(AUTH_FILE):
        # Read token and refresh_token from file
        auth = parsed_tokens(cfg.twitch.auth_file)
        try:
            token = auth.auth.token
            refresh_token = auth.auth.refresh_token
            print(f'Successfully read {AUTH_FILE}')
        except (KeyError, MissingFieldError):
            print(f'{AUTH_FILE} is malformed')
        # Set them
        await twitch.set_user_authentication(token, USER_SCOPE, refresh_token)

        expiration = await validate_token(twitch)
        return twitch, expiration
    else:
        raise Exception("No token file found")


async def validate_token(twitch: dict):
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
