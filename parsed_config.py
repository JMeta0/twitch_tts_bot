import os
import configparser
from logger import logger


config_path = 'config.txt'


class ConfigSection:
    """
    Class to represent a section of the configuration.
    This mimics the behavior of the original config_pyrser Section classes.
    """
    def __init__(self, section_dict=None):
        if section_dict:
            for key, value in section_dict.items():
                setattr(self, key, value)


class Config:
    """
    Class to represent the entire configuration.
    This mimics the behavior of the original config_pyrser Config class.
    """
    def __init__(self):
        self.twitch = ConfigSection()
        self.tts = ConfigSection()

    @classmethod
    def from_dict(cls, config_dict):
        """
        Create a Config object from a dictionary.

        Args:
            config_dict (dict): Dictionary with configuration sections and values

        Returns:
            Config: Config object with parsed configuration
        """
        config = cls()

        for section, values in config_dict.items():
            if hasattr(config, section):
                setattr(config, section, ConfigSection(values))

        return config


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

    # Optional fields that should be present with default values if not specified
    optional_fields = {
        'twitch': {
            'mock_user_id': '1234567890'  # Default mock user ID
        }
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

    # Set default values for optional fields if they don't exist
    for section, fields_dict in optional_fields.items():
        if hasattr(cfg, section):
            section_obj = getattr(cfg, section)
            for field, default_value in fields_dict.items():
                if not hasattr(section_obj, field):
                    setattr(section_obj, field, default_value)

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

    try:
        # Use configparser to read the configuration file
        parser = configparser.ConfigParser()
        parser.read(config_path)

        # Convert to dictionary
        config_dict = {}
        for section in parser.sections():
            config_dict[section] = {}
            for key, value in parser.items(section):
                # Convert numeric values
                if section == 'tts' and key in ['sound_cap', 'max_effect_repetitions']:
                    config_dict[section][key] = int(value)
                else:
                    config_dict[section][key] = value

        # Create config object
        cfg = Config.from_dict(config_dict)

        # Validate config
        if not validate_config(cfg):
            logger.error("Configuration is invalid. Please fix the issues and restart.")
            input("Press enter to proceed...")

        return cfg

    except Exception as e:
        logger.error(f"Error parsing config: {e}")
        input("Press enter to proceed...")
        return None


class AuthConfig:
    """
    Class to represent the authentication configuration.
    """
    def __init__(self):
        self.auth = ConfigSection()

    @classmethod
    def from_dict(cls, config_dict):
        """
        Create an AuthConfig object from a dictionary.

        Args:
            config_dict (dict): Dictionary with configuration sections and values

        Returns:
            AuthConfig: AuthConfig object with parsed configuration
        """
        config = cls()

        if 'auth' in config_dict:
            config.auth = ConfigSection(config_dict['auth'])

        return config


def parsed_tokens(path: str):
    """
    Parse authentication tokens from a file.

    Args:
        path (str): Path to the tokens file

    Returns:
        object: Auth object with parsed tokens or None if parsing failed
    """
    try:
        # Use configparser to read the tokens file
        parser = configparser.ConfigParser()
        parser.read(path)

        # Convert to dictionary
        config_dict = {}
        for section in parser.sections():
            config_dict[section] = {}
            for key, value in parser.items(section):
                config_dict[section][key] = value

        # Create auth object
        auth = AuthConfig.from_dict(config_dict)

        # Validate tokens
        if not hasattr(auth, 'auth') or not hasattr(auth.auth, 'token') or not auth.auth.token:
            logger.error(f"Missing or invalid token in {path}")
            return None

        return auth

    except Exception as e:
        logger.error(f'Error parsing tokens from {path}: {e}')
        return None
