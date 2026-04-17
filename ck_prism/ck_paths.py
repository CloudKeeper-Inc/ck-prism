import os
import subprocess
import sys


def get_home_dir():
    if sys.platform.startswith('linux') or sys.platform.startswith('darwin'):
        cmd = 'echo $HOME'
    elif sys.platform.startswith('win'):
        cmd = 'echo %USERPROFILE%'
    else:
        print(f'Unsupported platform: {sys.platform}')
        exit(1)

    result = subprocess.run(cmd, shell=True, capture_output=True)
    return result.stdout.decode('utf-8').strip()


def get_config_dir():
    return os.path.join(get_home_dir(), '.ck-prism')


def get_config_path():
    return os.path.join(get_config_dir(), 'config.json')


def get_tokens_dir():
    return os.path.join(get_config_dir(), 'tokens')


def get_token_file_path(profile):
    return os.path.join(get_tokens_dir(), f'{profile}_tokens.json')


def get_aws_credentials_path():
    return os.path.join(get_home_dir(), '.aws', 'credentials')


def get_aws_config_path():
    return os.path.join(get_home_dir(), '.aws', 'config')


def get_state_path():
    return os.path.join(get_config_dir(), 'state.json')


def get_sts_cache_dir():
    return os.path.join(get_config_dir(), 'sts-cache')
