import configparser
import json
import os

import requests
from twitchAPI.oauth import refresh_access_token
from twitchAPI.types import AuthScope

from time_formatter import time_format

# Read config
config = configparser.ConfigParser()
config.read('config.txt')

# Set values
APP_ID = config['twitch']['client_id']
APP_SECRET = config['twitch']['client_secret']
TARGET_CHANNEL = config['twitch']['channel']
USER_SCOPE = [AuthScope.CHAT_READ]
AUTH_FILE=config['twitch']['auth_file']

# Functions
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
        f = open("tokens.tmp", "w")
        f.write("[auth]\n")
        f.write(f"token = {token}\n")
        f.write(f"refresh_token = {refresh_token}")
        f.close()
        print("Successfully generated new token")
        return twitch

async def read_token(twitch: dict):
    if os.path.isfile(AUTH_FILE):
        # Read token and refresh_token from file
        auth_info = configparser.ConfigParser()
        auth_info.read(AUTH_FILE)
        try:
            token=auth_info['auth']['token']
            refresh_token=auth_info['auth']['refresh_token']
            print(f"Successfully read {AUTH_FILE}")
        except:
            raise Exception(f"{AUTH_FILE} is malformed")
        # Set them
        await twitch.set_user_authentication(token, USER_SCOPE, refresh_token)

        expiration = await validate_token(twitch)
        print(f"Token expires in: {time_format(expiration)}")
        return twitch, expiration
    else:
        raise Exception("No token file found")

async def validate_token(twitch: dict):
    print("Validating token")
    token = str(twitch._Twitch__user_auth_token)
    try:
        response = requests.get("https://id.twitch.tv/oauth2/validate", headers={f"Authorization": f"OAuth {token}"})
    except Exception as e:
        print(f"Validation failed: {e}")
    response_parsed = json.loads(response.text)
    expiration = response_parsed["expires_in"]
    return expiration

async def refresh_token(twitch: dict):
    print("Refreshing token")
    token = str(twitch._Twitch__user_auth_refresh_token)
    # Get new token and new refresh token
    new_token, new_refresh_token = await refresh_access_token(token, APP_ID, APP_SECRET)

    # Save them to file
    f = open(AUTH_FILE, "w")
    f.write("[auth]\n")
    f.write(f"token = {new_token}\n")
    f.write(f"refresh_token = {new_refresh_token}")
    f.close()

    await twitch.set_user_authentication(new_token, USER_SCOPE, new_refresh_token)
    return twitch
    print("Successfully refreshed token")
