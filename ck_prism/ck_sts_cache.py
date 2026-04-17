"""On-disk cache for AWS STS credentials returned by credential_process.

Without this cache every `aws` CLI invocation would re-run credential_process
and hit Prism's exchange endpoint, generating one audit-log event per command.
Cached entries are keyed by (prism_domain, realm, role_arn) so profiles that
assume the same role on the same tenant share a single mint.
"""

import hashlib
import json
import os
import time
from datetime import datetime

from ck_prism.ck_paths import get_sts_cache_dir


DEFAULT_PRISM_DOMAIN = 'prism.cloudkeeper.com'

# Treat creds as expired this many seconds before their actual Expiration.
EXPIRY_BUFFER_SECONDS = 300


def _cache_key(profile_config, role_arn):
    domain = profile_config.get('prism_domain', DEFAULT_PRISM_DOMAIN)
    realm = profile_config['realm']
    raw = f'{domain}|{realm}|{role_arn}'.encode('utf-8')
    return hashlib.sha256(raw).hexdigest()[:32]


def _cache_file(profile_config, role_arn):
    return os.path.join(get_sts_cache_dir(), f'{_cache_key(profile_config, role_arn)}.json')


def _parse_expiration(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace('Z', '+00:00')
    try:
        return datetime.fromisoformat(s).timestamp()
    except ValueError:
        return None


def load_creds(profile_config, role_arn):
    """Return cached credential_process output if still valid, else None."""
    path = _cache_file(profile_config, role_arn)
    if not os.path.exists(path):
        return None

    try:
        with open(path, 'r') as f:
            creds = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    expire_ts = _parse_expiration(creds.get('Expiration'))
    if expire_ts is None or expire_ts <= time.time() + EXPIRY_BUFFER_SECONDS:
        return None

    return creds


def save_creds(profile_config, role_arn, creds):
    """Persist credential_process output for future invocations."""
    directory = get_sts_cache_dir()
    os.makedirs(directory, exist_ok=True)
    path = _cache_file(profile_config, role_arn)
    tmp = f'{path}.tmp'
    with open(tmp, 'w') as f:
        json.dump(creds, f)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def remove_creds(profile_config, role_arn):
    """Delete the cache file for a given (tenant, role_arn). Safe if absent."""
    path = _cache_file(profile_config, role_arn)
    if os.path.exists(path):
        try:
            os.remove(path)
            return True
        except OSError:
            return False
    return False
