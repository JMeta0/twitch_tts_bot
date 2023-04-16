from config_pyrser import manager, fields
from os import path

config_path = 'config.txt'
if not path.exists(config_path):
    print(f'{config_path} not found - copy and input correct data to config file!')
    input("Press enter to proceed...")


def parsed_config():
    # Meme config
    class Twitch_config(manager.Section):
        channel = fields.Field()
        client_id = fields.Field()
        client_secret = fields.Field()
        auth_file = fields.Field()

    class Tts_config(manager.Section):
        reward_name = fields.Field()
        sound_cap = fields.IntField()

    class Config(manager.Config):
        twitch = Twitch_config()
        tts = Tts_config()

    cfg = Config(path=config_path)

    return cfg


def parsed_tokens(path: str):
    try:
        class Auth_config(manager.Section):
            token = fields.Field()
            refresh_token = fields.Field()

        class Config(manager.Config):
            auth = Auth_config()

        auth = Config(path=path)

        return auth
    except AttributeError:
        print(f'{path} is malformed')
