"""Tenant-keyed token storage.

Tokens are cached per (prism_domain, realm) pair rather than per profile,
so multiple profiles on the same Prism tenant share a single browser
authentication. Legacy per-profile token files are migrated on first read.
"""

import json
import os
import re

from ck_prism.ck_paths import get_token_file_path, get_tokens_dir


DEFAULT_PRISM_DOMAIN = 'prism.cloudkeeper.com'


def _safe(s):
    return re.sub(r'[^A-Za-z0-9._-]', '_', str(s))


def tenant_key(profile_config):
    domain = profile_config.get('prism_domain', DEFAULT_PRISM_DOMAIN)
    realm = profile_config['realm']
    return (domain, realm)


def token_file_for(profile_config):
    domain, realm = tenant_key(profile_config)
    filename = f'{_safe(domain)}__{_safe(realm)}.json'
    return os.path.join(get_tokens_dir(), filename)


def _legacy_token_path(profile):
    return get_token_file_path(profile)


def _write_tokens(path, tokens):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(tokens, f, indent=2)
    os.chmod(path, 0o600)


def _remove_legacy_if_present(profile):
    legacy = _legacy_token_path(profile)
    if os.path.exists(legacy):
        try:
            os.remove(legacy)
        except OSError:
            pass


def load_tokens(profile_config, profile):
    shared = token_file_for(profile_config)

    if os.path.exists(shared):
        with open(shared, 'r') as f:
            tokens = json.load(f)
        _remove_legacy_if_present(profile)
        return tokens

    legacy = _legacy_token_path(profile)
    if os.path.exists(legacy):
        with open(legacy, 'r') as f:
            tokens = json.load(f)
        _write_tokens(shared, tokens)
        _remove_legacy_if_present(profile)
        return tokens

    return None


def save_tokens(profile_config, profile, tokens):
    shared = token_file_for(profile_config)
    _write_tokens(shared, tokens)
    _remove_legacy_if_present(profile)


def remove_legacy_token_file(profile):
    legacy = _legacy_token_path(profile)
    if not os.path.exists(legacy):
        return False
    os.remove(legacy)
    return True


def remove_tokens_if_unused(removed_profile_config, remaining_configs):
    """Remove the shared token file only if no remaining profile uses the
    same (prism_domain, realm). Returns (deleted, sibling_count)."""
    key = tenant_key(removed_profile_config)
    siblings = sum(
        1 for cfg in remaining_configs.values()
        if isinstance(cfg, dict) and tenant_key(cfg) == key
    )

    shared = token_file_for(removed_profile_config)

    if siblings > 0:
        return (False, siblings)

    if os.path.exists(shared):
        os.remove(shared)
        return (True, 0)

    return (False, 0)
