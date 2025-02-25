import os
from logger import logger
from config_pyrser import manager, fields


config_path = 'config.txt'


def validate_config(cfg):
    """
    Validate that all required configuration fields are present.
    
    Args:
        cfg: The configuration object to validate
        
    Returns:
        bool: True if config is valid, False otherwise
    """
    required_fields = {
        'twitch': ['default_runner', 'channel', 'client_id', 'client_secret', 'auth_file'],
        'tts': ['reward_name', 'sound_cap', 'max_effect_repetitions']
    }
    
    is_valid = True
    
    for section, fields_list in required_fields.items():
        if not hasattr(cfg, section):
            logger.error(f"Missing section in config: {section}")
            is_valid = False
            continue
            
        section_obj = getattr(cfg, section)
        for field in fields_list:
            if not hasattr(section_obj, field) or getattr(section_obj, field) is None:
                logger.error(f"Missing or empty field in config: {section}.{field}")
                is_valid = False
    
    return is_valid


def parsed_config():
    """
    Parse the configuration file and validate it.
    
    Returns:
        object: Config object with parsed configuration
    """
    if not os.path.exists(config_path):
        logger.error(f'{config_path} not found - copy and input correct data to config file!')
        example_path = f"{config_path}.EXAMPLE"
        if os.path.exists(example_path):
            logger.info(f"You can copy {example_path} to {config_path} and edit it.")
        input("Press enter to proceed...")
        
    # Twitch config
    class Twitch_config(manager.Section):
        default_runner = fields.Field()
        channel = fields.Field()
        client_id = fields.Field()
        client_secret = fields.Field()
        auth_file = fields.Field()

    class Tts_config(manager.Section):
        reward_name = fields.Field()
        sound_cap = fields.IntField()
        max_effect_repetitions = fields.IntField()

    class Config(manager.Config):
        twitch = Twitch_config()
        tts = Tts_config()

    try:
        cfg = Config(path=config_path)
        
        # Validate config
        if not validate_config(cfg):
            logger.error("Configuration is invalid. Please fix the issues and restart.")
            input("Press enter to proceed...")
            
        return cfg
        
    except Exception as e:
        logger.error(f"Error parsing config: {e}")
        input("Press enter to proceed...")
        return None


def parsed_tokens(path: str):
    """
    Parse authentication tokens from a file.
    
    Args:
        path (str): Path to the tokens file
        
    Returns:
        object: Auth object with parsed tokens or None if parsing failed
    """
    try:
        class Auth_config(manager.Section):
            token = fields.Field()
            refresh_token = fields.Field()

        class Config(manager.Config):
            auth = Auth_config()

        auth = Config(path=path)
        
        # Validate tokens
        if not hasattr(auth, 'auth') or not hasattr(auth.auth, 'token') or not auth.auth.token:
            logger.error(f"Missing or invalid token in {path}")
            return None
            
        return auth
        
    except Exception as e:
        logger.error(f'Error parsing tokens from {path}: {e}')
        return None
