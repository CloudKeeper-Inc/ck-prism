import configparser
import json
import os
import sys

from ck_prism.ck_paths import (
    get_aws_config_path,
    get_aws_credentials_path,
    get_config_path,
)
from ck_prism.ck_prompt import interactive_select
from ck_prism import ck_token_store


def _load_config():
    config_path = get_config_path()
    if not os.path.exists(config_path):
        return {}, config_path
    try:
        with open(config_path, 'r') as f:
            return json.load(f), config_path
    except json.JSONDecodeError:
        print("Configuration file is invalid. Run 'ck-prism configure' to recreate it.")
        sys.exit(1)


def list_profiles_utility():
    if len(sys.argv) > 3:
        print("ERROR: Too many arguments. Usage: ck-prism profiles list")
        sys.exit(1)

    config, _ = _load_config()
    if not config:
        print("No profiles configured. Run 'ck-prism configure' to create one.")
        return

    for name in sorted(config.keys()):
        print(name)


def _parse_remove_args(args):
    name = None
    assume_yes = False
    for arg in args:
        if arg in ('-y', '--yes'):
            if assume_yes:
                print(f"ERROR: Duplicate flag {arg}.")
                sys.exit(1)
            assume_yes = True
        elif arg.startswith('-'):
            print(f"ERROR: Unknown flag {arg}. Usage: ck-prism profiles remove [NAME] [-y]")
            sys.exit(1)
        else:
            if name is not None:
                print("ERROR: Only one profile name may be specified.")
                sys.exit(1)
            name = arg
    return name, assume_yes


def _remove_config_entry(config, config_path, name):
    del config[name]
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)


def _aws_config_section_name(profile):
    return profile if profile == 'default' else f'profile {profile}'


def _remove_section(path, section):
    if not os.path.exists(path):
        return False

    parser = configparser.ConfigParser()
    parser.read(path)

    if not parser.has_section(section):
        return False

    parser.remove_section(section)
    with open(path, 'w') as f:
        parser.write(f)
    return True


def _remove_aws_credentials_section(name):
    return _remove_section(get_aws_credentials_path(), name)


def _remove_aws_config_section(name):
    return _remove_section(get_aws_config_path(), _aws_config_section_name(name))


def remove_profile_utility():
    name, assume_yes = _parse_remove_args(sys.argv[3:])

    config, config_path = _load_config()
    if not config:
        print("No profiles configured. Nothing to remove.")
        return

    if name is None:
        choices = [{"name": n, "value": n} for n in sorted(config.keys())]
        name = interactive_select(
            message="Select a profile to remove:",
            choices=choices,
        )

    if name not in config:
        print(f"Profile '{name}' not found.")
        sys.exit(1)

    if not assume_yes:
        prompt = (
            f"Remove profile '{name}'? This deletes the config entry, "
            f"cached tokens, and the matching sections in ~/.aws/credentials "
            f"and ~/.aws/config. [y/N]: "
        )
        answer = input(prompt).strip().lower()
        if answer != 'y' and answer != 'yes':
            print("Aborted.")
            return

    removed_profile_config = config[name]

    had_error = False
    results = []

    try:
        _remove_config_entry(config, config_path, name)
        results.append("config entry removed")
    except OSError as e:
        had_error = True
        results.append(f"config entry FAILED: {e}")

    try:
        deleted, siblings = ck_token_store.remove_tokens_if_unused(
            removed_profile_config, config
        )
        if deleted:
            results.append("cached tokens removed")
        elif siblings > 0:
            plural = "" if siblings == 1 else "s"
            results.append(
                f"cached tokens kept (shared with {siblings} other profile{plural})"
            )
        else:
            results.append("cached tokens skipped (not found)")
    except OSError as e:
        had_error = True
        results.append(f"cached tokens FAILED: {e}")

    try:
        if ck_token_store.remove_legacy_token_file(name):
            results.append("legacy per-profile token file removed")
    except OSError as e:
        had_error = True
        results.append(f"legacy per-profile token file FAILED: {e}")

    try:
        if _remove_aws_credentials_section(name):
            results.append("aws credentials section removed")
        else:
            results.append("aws credentials section skipped (not found)")
    except OSError as e:
        had_error = True
        results.append(f"aws credentials section FAILED: {e}")

    try:
        if _remove_aws_config_section(name):
            results.append("aws config section removed")
        else:
            results.append("aws config section skipped (not found)")
    except OSError as e:
        had_error = True
        results.append(f"aws config section FAILED: {e}")

    print(f"\nRemoved profile '{name}':")
    for line in results:
        print(f"  - {line}")

    if had_error:
        sys.exit(1)
