import json
import os
from datetime import datetime, timezone

from ck_prism.ck_paths import get_config_dir, get_state_path


def read_last_profile():
    path = get_state_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r') as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    value = data.get('last_profile')
    if not isinstance(value, str) or not value:
        return None
    return value


def write_last_profile(profile):
    os.makedirs(get_config_dir(), exist_ok=True)
    path = get_state_path()
    tmp_path = path + '.tmp'

    payload = {
        'last_profile': profile,
        'last_profile_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }

    with open(tmp_path, 'w') as f:
        json.dump(payload, f, indent=2)
    os.chmod(tmp_path, 0o600)
    os.replace(tmp_path, path)
