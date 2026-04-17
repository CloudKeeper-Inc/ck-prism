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
from ck_prism import ck_sts_cache


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


def _save_config(config, config_path):
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)


def _resolve_profile_name(args, usage_hint):
    name = None
    for arg in args:
        if arg.startswith('-'):
            print(f"ERROR: Unknown flag {arg}. Usage: {usage_hint}")
            sys.exit(1)
        if name is not None:
            print("ERROR: Only one profile name may be specified.")
            sys.exit(1)
        name = arg
    return name


def enable_credential_process(name, config, config_path):
    """Enable credential_process for a single profile. Returns list of result strings."""
    profile_config = config[name]
    results = []

    # 1. Write credential_process to ~/.aws/config
    aws_config_path = get_aws_config_path()
    os.makedirs(os.path.dirname(aws_config_path), exist_ok=True)
    parser = configparser.ConfigParser()
    parser.read(aws_config_path)

    section = _aws_config_section_name(name)
    if not parser.has_section(section):
        parser[section] = {}

    parser[section]['credential_process'] = f'ck-prism credential-process --profile {name}'
    parser[section]['region'] = profile_config.get('region', 'us-east-1')
    parser[section]['output'] = profile_config.get('output', 'json')

    with open(aws_config_path, 'w') as f:
        parser.write(f)
    results.append("~/.aws/config: credential_process line added")

    # 2. Remove static credentials that would shadow credential_process
    if _remove_aws_credentials_section(name):
        results.append("~/.aws/credentials: static entry removed (would have shadowed credential_process)")
    else:
        results.append("~/.aws/credentials: skipped (no static entry)")

    # 3. Update ck-prism config flag
    profile_config['credential_process_enabled'] = True
    _save_config(config, config_path)

    return results


def disable_credential_process(name, config, config_path):
    """Disable credential_process for a single profile. Returns list of result strings."""
    results = []

    aws_config_path = get_aws_config_path()
    if os.path.exists(aws_config_path):
        parser = configparser.ConfigParser()
        parser.read(aws_config_path)

        section = _aws_config_section_name(name)
        if parser.has_section(section) and parser.has_option(section, 'credential_process'):
            parser.remove_option(section, 'credential_process')
            # Remove section if only empty or has just region/output
            remaining = dict(parser.items(section))
            if not remaining:
                parser.remove_section(section)
            with open(aws_config_path, 'w') as f:
                parser.write(f)
            results.append("~/.aws/config: credential_process line removed")
        else:
            results.append("~/.aws/config: no credential_process line found")
    else:
        results.append("~/.aws/config: file not found")

    config[name]['credential_process_enabled'] = False
    _save_config(config, config_path)

    return results


def enable_credential_process_utility():
    name = _resolve_profile_name(
        sys.argv[3:],
        "ck-prism profiles enable-credential-process [NAME]"
    )
    config, config_path = _load_config()
    if not config:
        print("No profiles configured. Run 'ck-prism configure' to create one.")
        return

    if name is None:
        choices = [{"name": n, "value": n} for n in sorted(config.keys())]
        name = interactive_select(
            message="Select a profile to enable credential_process for:",
            choices=choices,
        )

    if name not in config:
        print(f"Profile '{name}' not found.")
        sys.exit(1)

    results = enable_credential_process(name, config, config_path)
    print(f"\nEnabled credential_process for '{name}':")
    for line in results:
        print(f"  - {line}")


def disable_credential_process_utility():
    name = _resolve_profile_name(
        sys.argv[3:],
        "ck-prism profiles disable-credential-process [NAME]"
    )
    config, config_path = _load_config()
    if not config:
        print("No profiles configured.")
        return

    if name is None:
        choices = [{"name": n, "value": n} for n in sorted(config.keys())]
        name = interactive_select(
            message="Select a profile to disable credential_process for:",
            choices=choices,
        )

    if name not in config:
        print(f"Profile '{name}' not found.")
        sys.exit(1)

    results = disable_credential_process(name, config, config_path)
    print(f"\nDisabled credential_process for '{name}':")
    for line in results:
        print(f"  - {line}")


def _is_aws_config_in_sync(name):
    """Check if ~/.aws/config has a correct credential_process entry for the profile."""
    aws_config_path = get_aws_config_path()
    if not os.path.exists(aws_config_path):
        return False

    parser = configparser.ConfigParser()
    parser.read(aws_config_path)

    section = _aws_config_section_name(name)
    if not parser.has_section(section):
        return False

    expected = f'ck-prism credential-process --profile {name}'
    actual = parser.get(section, 'credential_process', fallback=None)
    return actual == expected


def migrate_credential_process_utility():
    config, config_path = _load_config()
    if not config:
        print("No profiles configured.")
        return

    migrated = 0
    repaired = 0
    skipped = 0

    for name in sorted(config.keys()):
        profile = config[name]
        if not isinstance(profile, dict):
            continue

        flag_enabled = profile.get('credential_process_enabled')
        aws_in_sync = _is_aws_config_in_sync(name)

        if flag_enabled and aws_in_sync:
            print(f"  [skip] {name} (already enabled)")
            skipped += 1
            continue

        if flag_enabled and not aws_in_sync:
            enable_credential_process(name, config, config_path)
            print(f"  [repair] {name}")
            repaired += 1
            continue

        enable_credential_process(name, config, config_path)
        print(f"  [done] {name}")
        migrated += 1

    parts = [f"{migrated} migrated"]
    if repaired:
        parts.append(f"{repaired} repaired")
    parts.append(f"{skipped} already enabled")
    print(f"\n{', '.join(parts)}.")


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

    role_arn = removed_profile_config.get('role_arn')
    if role_arn:
        try:
            if ck_sts_cache.remove_creds(removed_profile_config, role_arn):
                results.append("cached AWS credentials removed")
        except OSError as e:
            had_error = True
            results.append(f"cached AWS credentials FAILED: {e}")

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
