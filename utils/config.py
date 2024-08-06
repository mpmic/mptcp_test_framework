import contextlib
import os
import time
from pathlib import Path

from pyconfigparser import Config, ConfigError, configparser
from schema import And, Optional, Schema, Use


@contextlib.contextmanager
# temporarily change to a different working directory
def temporaryWorkingDirectory(path):
    _oldCWD = os.getcwd()
    os.chdir(os.path.abspath(path))

    try:
        yield
    finally:
        os.chdir(_oldCWD)


def config_to_dict(config):
    """
    Recursively convert a pyconfigparser.Config object to a dictionary.

    Args:
        config (pyconfigparser.Config or list): The configuration object or list.

    Returns:
        dict or list: The converted dictionary or list.
    """

    def convert(value):
        if isinstance(value, Config):
            return config_to_dict(value)
        elif isinstance(value, list):
            return [convert(item) for item in value]
        else:
            return value

    if isinstance(config, list):
        return [convert(item) for item in config]
    else:
        return {key: convert(value) for key, value in dict(config).items()}


CONFIG_DIR = Path(__file__).resolve().parent
MAIN_DIR = CONFIG_DIR.parent
# Define the schema for validation
# SCHEMA_CONFIG = Schema({
#     'name': And(str, len),
#     'network_env': And(str, lambda s: s in ['mininet', 'physical', 'mininet_custom']),
#     'topology': {
#         'mininet': {
#             'server_ip': And(str, len),
#             'links': [{
#                 'name': And(str, len),
#                 'client_ip': And(str, len),
#                 'bw': And(Use(float), lambda n: n > 0),
#                 'delay': And(str, len),  # Changed to str as delay is given in ms as string
#                 'loss': And(Use(float), lambda n: 0 <= n <= 100),
#                 Optional('jitter'): And(str, len)
#             }]
#         },
#         'physical': {
#             'client': {
#                 'hostname': And(str, len),
#                 'username': And(str, len),
#                 'password': And(str, len),
#                 Optional('ssh_key'): And(str, len)
#             },
#             'server': {
#                 'hostname': And(str, len),
#                 'username': And(str, len),
#                 'password': And(str, len),
#                 Optional('ssh_key'): And(str, len)
#             }
#         }
#     },
#     'schedulers': And(list, [{
#         And(str, len): {
#             Optional('train'): And(Use(int), lambda n: n > 0),
#             Optional('param2'): And(str, len)
#         } | str
#     }]),
#     'test': {
#         'num_iterations': And(Use(int), lambda n: n > 0),
#         'file_size': And(str, len)
#     },
#     'results': {
#         'dir': And(str, len),
#         'plot': {
#             'figsize': [And(Use(int), lambda n: n > 0), And(Use(int), lambda n: n > 0)],
#             'title': And(str, len),
#             'xlabel': And(str, len),
#             'ylabel': And(str, len)
#         }
#     },
#     'logging': {
#         'level': And(str, len)
#     }
# })

# Load and validate the configuration

with temporaryWorkingDirectory(path=MAIN_DIR):
    config = configparser.get_config(config_dir="")


def result_dir_publish(config):
    result_dir_config = Path(config.results.dir)
    result_dir = (
        MAIN_DIR / result_dir_config
        if not result_dir_config.is_absolute()
        else result_dir_config
    )

    test_campaign_name = config.name
    date_stamp = time.strftime("%Y%m%d-%H%M%S")
    RESULT_DIR = result_dir / test_campaign_name / date_stamp
    RESULT_DIR.mkdir(exist_ok=True, parents=True)

    return RESULT_DIR


RESULT_DIR = result_dir_publish(config)
