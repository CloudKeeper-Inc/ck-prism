import sys
import json
import os
import configparser
import subprocess
import time
import hashlib
import base64
import secrets
import urllib.parse
import http.server
import socketserver
import threading
import requests

from ck_prism.ck_paths import get_home_dir
from ck_prism.ck_profile_resolver import resolve_profile, ProfileResolutionError
from ck_prism.ck_prompt import interactive_select
from ck_prism.ck_state import read_last_profile, write_last_profile
from ck_prism import ck_token_store

# Default domain configuration
DEFAULT_PRISM_DOMAIN = 'prism.cloudkeeper.com'

def get_prism_base_url(prism_domain=DEFAULT_PRISM_DOMAIN):
    """Get the login base URL for the given Prism domain."""
    return f'https://login.{prism_domain}'

def get_api_endpoint(prism_domain=DEFAULT_PRISM_DOMAIN):
    """Get the API endpoint for the given Prism domain."""
    return f'https://cli.{prism_domain}/exchange'

def get_home_directory():
    return get_home_dir()

def login_utility():
    directory = get_home_directory()

    explicit_profile = None
    if len(sys.argv) == 2:
        pass
    elif len(sys.argv) == 4:
        if sys.argv[2] == '--profile':
            explicit_profile = sys.argv[3]
        else:
            print(f'Invalid flag {sys.argv[2]}. Acceptable flag is --profile.')
            exit(1)
    else:
        print('Invalid arguments. Usage: ck-prism login [--profile NAME]')
        exit(1)

    config_path = os.path.join(directory, '.ck-prism', 'config.json')
    if not os.path.exists(config_path):
        print('Configuration not found. Run ck-prism configure')
        exit(1)

    try:
        with open(config_path, 'r') as f:
            raw_config = json.load(f)
    except json.JSONDecodeError:
        print('Configuration file is invalid or empty. Run ck-prism configure')
        exit(1)

    profile_entries = {k: v for k, v in raw_config.items() if isinstance(v, dict)}

    last_profile = read_last_profile()
    is_tty = sys.stdin.isatty() and sys.stdout.isatty()

    try:
        suggested, should_prompt = resolve_profile(
            explicit=explicit_profile,
            config=profile_entries,
            last_profile=last_profile,
            is_tty=is_tty,
        )
    except ProfileResolutionError as e:
        print(str(e))
        exit(1)

    if should_prompt:
        choices = [{"name": n, "value": n} for n in sorted(profile_entries.keys())]
        profile = interactive_select(
            message="Select a profile to log in with:",
            choices=choices,
            default=suggested,
        )
    else:
        profile = suggested
        if explicit_profile is not None:
            print(f'Using {profile} profile')
        elif len(profile_entries) == 1:
            print(f'Using profile: {profile}')
        else:
            print(f'Using last profile: {profile} (use --profile to switch)')

    profile_config = profile_entries[profile]

    if profile_config.get('credential_process_enabled'):
        print(f"\nProfile '{profile}' is configured to use credential_process.")
        print(f"AWS CLI will fetch credentials automatically — no manual login needed.")
        print(f"\nTo switch back to manual login, run:")
        print(f"  ck-prism profiles disable-credential-process {profile}")
        return

    prism_domain = profile_config.get('prism_domain', DEFAULT_PRISM_DOMAIN)
    profile_config['keycloak_base_url'] = get_prism_base_url(prism_domain)
    profile_config['api_endpoint'] = get_api_endpoint(prism_domain)

    tokens = get_or_refresh_tokens(profile_config, directory, profile)

    if 'role_arn' not in profile_config:
        print(f"Error: Profile '{profile}' is missing 'role_arn'. Please run 'ck-prism configure' again.")
        exit(1)

    get_aws_credentials(profile_config, tokens['access_token'], profile_config['role_arn'], profile, directory)

    try:
        write_last_profile(profile)
    except OSError:
        pass

def get_or_refresh_tokens(config, directory, profile):
    tokens = ck_token_store.load_tokens(config, profile)

    if tokens:
        # Check if access token is still valid (with 5 min buffer)
        if tokens.get('expires_at', 0) > time.time() + 300:
            return tokens

        # Try refresh
        if tokens.get('refresh_token'):
            print('Refreshing tokens...')
            refreshed = refresh_tokens(config, tokens['refresh_token'])
            if refreshed:
                ck_token_store.save_tokens(config, profile, refreshed)
                return refreshed

    # Interactive login required
    print('Performing interactive login...')
    new_tokens = interactive_login(config)
    ck_token_store.save_tokens(config, profile, new_tokens)
    return new_tokens

def refresh_tokens(config, refresh_token):
    token_url = f"{config['keycloak_base_url']}/realms/{config['realm']}/protocol/openid-connect/token"
    
    data = {
        'grant_type': 'refresh_token',
        'client_id': config['client_id'],
        'refresh_token': refresh_token
    }
    
    try:
        response = requests.post(token_url, data=data, timeout=30)
        if response.status_code == 200:
            token_data = response.json()
            return {
                'access_token': token_data['access_token'],
                'refresh_token': token_data.get('refresh_token', refresh_token),
                'id_token': token_data.get('id_token'),
                'expires_at': time.time() + token_data.get('expires_in', 300)
            }
    except Exception as e:
        print(f'Token refresh failed: {e}')
    return None

def interactive_login(config):
    # Generate PKCE challenge
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).decode('utf-8').rstrip('=' )
    code_verifier = ''.join(c for c in code_verifier if c.isalnum() or c in '-._~')[:128]
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode('utf-8').rstrip('=')
    
    state = secrets.token_hex(16)
    
    # Start callback server
    code_result = {'code': None, 'error': None}
    server, port = start_callback_server(state, code_result)
    
    redirect_uri = f'http://127.0.0.1:{port}/cb'
    
    # Build auth URL
    auth_params = {
        'response_type': 'code',
        'client_id': config['client_id'],
        'redirect_uri': redirect_uri,
        'scope': 'openid profile email offline_access',
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256',
        'state': state
    }
    
    auth_url = f"{config['keycloak_base_url']}/realms/{config['realm']}/protocol/openid-connect/auth?" + urllib.parse.urlencode(auth_params)
    
    print('\nOpening browser for authentication...')
    open_browser(auth_url)
    print(f'\nIf browser did not open, visit:\n{auth_url}\n')
    
    # Wait for callback
    print('Waiting for authentication...')
    for _ in range(180):
        if code_result['code'] or code_result['error']:
            break
        time.sleep(1)
    
    server.shutdown()
    
    if code_result['error']:
        print(f"Authentication failed: {code_result['error']}")
        exit(1)
    
    if not code_result['code']:
        print('Authentication timed out')
        exit(1)
    
    # Exchange code for tokens
    token_url = f"{config['keycloak_base_url']}/realms/{config['realm']}/protocol/openid-connect/token"
    
    data = {
        'grant_type': 'authorization_code',
        'client_id': config['client_id'],
        'code': code_result['code'],
        'redirect_uri': redirect_uri,
        'code_verifier': code_verifier
    }
    
    response = requests.post(token_url, data=data, timeout=30)
    if response.status_code != 200:
        print(f'Token exchange failed: {response.text}')
        exit(1)
    
    token_data = response.json()
    print('Authentication successful!')
    
    return {
        'access_token': token_data['access_token'],
        'refresh_token': token_data.get('refresh_token'),
        'id_token': token_data.get('id_token'),
        'expires_at': time.time() + token_data.get('expires_in', 300)
    }

SUCCESS_PAGE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Login Successful - CK Prism</title>
<script>history.replaceState(null, '', '/cb');</script>
<link href="https://fonts.googleapis.com/css2?family=Bitter:wght@600;700&display=swap" rel="stylesheet">
<style>
  @import url('https://fonts.cdnfonts.com/css/metropolis-2');
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Metropolis', -apple-system, BlinkMacSystemFont, sans-serif; min-height: 100vh; display: flex; align-items: center; justify-content: center; background: #F9FBFD; color: #333333; }
  .card { text-align: center; background: #FFFFFF; padding: 48px 40px; border-radius: 6px; border: 1px solid #E5E5E5; box-shadow: 0 2px 12px rgba(0,0,0,0.08); max-width: 420px; width: 90%; animation: fadeUp 0.4s cubic-bezier(0.22, 1, 0.36, 1) both; }
  @keyframes fadeUp { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: translateY(0); } }
  .icon { width: 56px; height: 56px; background: rgba(39,174,96,0.1); border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; margin-bottom: 24px; }
  .icon svg { width: 28px; height: 28px; color: #27AE60; }
  h1 { font-family: 'Bitter', serif; font-size: 22px; font-weight: 600; color: #253E66; margin-bottom: 8px; letter-spacing: -0.01em; }
  p { font-size: 14px; font-weight: 400; color: #999999; line-height: 1.6; }
  .divider { width: 40px; height: 3px; background: #4698D3; border-radius: 2px; margin: 24px auto 20px; }
  .brand { font-size: 11px; font-weight: 600; color: #BDBDBD; letter-spacing: 1.5px; }
</style>
</head>
<body>
<div class="card">
  <div class="icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg></div>
  <h1>Login Successful</h1>
  <p>Authentication complete. You can close this tab and return to your terminal.</p>
  <div class="divider"></div>
  <div class="brand">CK PRISM</div>
</div>
</body>
</html>'''

ERROR_PAGE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Login Failed - CK Prism</title>
<script>history.replaceState(null, '', '/cb');</script>
<link href="https://fonts.googleapis.com/css2?family=Bitter:wght@600;700&display=swap" rel="stylesheet">
<style>
  @import url('https://fonts.cdnfonts.com/css/metropolis-2');
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Metropolis', -apple-system, BlinkMacSystemFont, sans-serif; min-height: 100vh; display: flex; align-items: center; justify-content: center; background: #F9FBFD; color: #333333; }
  .card { text-align: center; background: #FFFFFF; padding: 48px 40px; border-radius: 6px; border: 1px solid #E5E5E5; box-shadow: 0 2px 12px rgba(0,0,0,0.08); max-width: 420px; width: 90%; animation: fadeUp 0.4s cubic-bezier(0.22, 1, 0.36, 1) both; }
  @keyframes fadeUp { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: translateY(0); } }
  .icon { width: 56px; height: 56px; background: rgba(231,76,60,0.1); border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; margin-bottom: 24px; }
  .icon svg { width: 28px; height: 28px; color: #E74C3C; }
  h1 { font-family: 'Bitter', serif; font-size: 22px; font-weight: 600; color: #253E66; margin-bottom: 8px; letter-spacing: -0.01em; }
  p { font-size: 14px; font-weight: 400; color: #999999; line-height: 1.6; }
  .divider { width: 40px; height: 3px; background: #E74C3C; border-radius: 2px; margin: 24px auto 20px; }
  .brand { font-size: 11px; font-weight: 600; color: #BDBDBD; letter-spacing: 1.5px; }
</style>
</head>
<body>
<div class="card">
  <div class="icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></div>
  <h1>Authentication Failed</h1>
  <p>Something went wrong during login. Please try again from your terminal.</p>
  <div class="divider"></div>
  <div class="brand">CK PRISM</div>
</div>
</body>
</html>'''


def start_callback_server(expected_state, result):
    class CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != '/cb':
                self.send_response(404)
                self.end_headers()
                return
            
            params = urllib.parse.parse_qs(parsed.query)
            code = params.get('code', [None])[0]
            state = params.get('state', [None])[0]
            error = params.get('error', [None])[0]
            
            if error:
                result['error'] = error
                self.send_response(400)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(ERROR_PAGE.encode())
                return

            if not code or state != expected_state:
                result['error'] = 'Invalid state or missing code'
                self.send_response(400)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(ERROR_PAGE.encode())
                return

            result['code'] = code
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(SUCCESS_PAGE.encode())
        
        def log_message(self, *args, **kwargs):
            pass
    
    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True
    
    server = ReusableTCPServer(('127.0.0.1', 0), CallbackHandler)
    port = server.server_address[1]
    
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    
    return server, port

def open_browser(url):
    try:
        if sys.platform.startswith('linux'):
            subprocess.run(['xdg-open', url], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif sys.platform.startswith('darwin'):
            subprocess.run(['open', url], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif sys.platform.startswith('win'):
            os.startfile(url)
    except (OSError, FileNotFoundError) as e:
        print(f'(could not auto-open browser: {e})', file=sys.stderr)

def save_tokens(token_file, tokens):
    with open(token_file, 'w') as f:
        json.dump(tokens, f, indent=2)
    os.chmod(token_file, 0o600)

def fetch_available_roles(config, access_token):
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'token': access_token,
        'realm': config['realm']
    }
    
    try:
        response = requests.post(config['api_endpoint'], json=payload, headers=headers, timeout=30)
        if response.status_code != 200:
            print(f'Failed to fetch available roles: {response.text}')
            exit(1)
        
        roles_data = response.json()
        
        # Extract roles
        if 'available_roles' in roles_data:
            roles = roles_data['available_roles']
        elif 'roles' in roles_data:
            roles = roles_data['roles']
        elif isinstance(roles_data, list):
            roles = roles_data
        else:
            print(f'Unexpected response format: {roles_data}')
            exit(1)
        
        # Extract account names if present
        account_names = {}
        if isinstance(roles_data, dict) and 'account_names' in roles_data and isinstance(roles_data['account_names'], dict):
            account_names = roles_data['account_names']
        
        return roles, account_names
            
    except requests.exceptions.RequestException as e:
        print(f'Error connecting to API: {e}')
        exit(1)

def exchange_credentials(config, access_token, role_arn):
    """Exchange a Prism access token for AWS credentials. Returns the credentials dict."""
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    creds_payload = {
        'token': access_token,
        'realm': config['realm'],
        'selected_role': role_arn
    }

    response = requests.post(config['api_endpoint'], json=creds_payload, headers=headers, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(f'AWS credential exchange failed: {response.text}')

    creds = response.json()

    # Handle nested credentials structure
    if 'credentials' in creds:
        creds = creds['credentials']

    return creds

def get_aws_credentials(config, access_token, role_arn, profile, directory):
    print('Exchanging token for AWS credentials...')

    try:
        creds = exchange_credentials(config, access_token, role_arn)
        write_aws_credentials(creds, profile, directory, config['region'])

    except requests.exceptions.RequestException as e:
        print(f'Error connecting to API: {e}')
        exit(1)
    except Exception as e:
        print(f'Error exchanging credentials: {e}')
        exit(1)

def _format_expires_in(expiration):
    if not expiration:
        return "~1 hour"

    try:
        if isinstance(expiration, (int, float)):
            expire_ts = float(expiration)
        else:
            from datetime import datetime, timezone
            s = str(expiration).strip().replace('Z', '+00:00')
            expire_ts = datetime.fromisoformat(s).timestamp()
    except (ValueError, TypeError):
        return str(expiration)

    seconds = int(expire_ts - time.time())
    if seconds <= 0:
        return "less than a minute (already expired?)"

    hours, rem = divmod(seconds, 3600)
    minutes = rem // 60

    if hours == 0:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    if minutes == 0:
        return f"{hours} hour{'s' if hours != 1 else ''}"
    return f"{hours} hour{'s' if hours != 1 else ''} {minutes} minute{'s' if minutes != 1 else ''}"


def write_aws_credentials(creds, profile, directory, region):
    credentials_path = os.path.join(directory, '.aws', 'credentials')
    config_path = os.path.join(directory, '.aws', 'config')
    os.makedirs(os.path.dirname(credentials_path), exist_ok=True)

    # Handle both snake_case and PascalCase key formats
    access_key = creds.get('access_key_id') or creds.get('AccessKeyId')
    secret_key = creds.get('secret_access_key') or creds.get('SecretAccessKey')
    session_token = creds.get('session_token') or creds.get('SessionToken')
    expiration = creds.get('expiration') or creds.get('Expiration')
    
    if not access_key or not secret_key or not session_token:
        print(f'Error: Invalid credentials format received: {creds}')
        exit(1)

    # Write credentials
    parser = configparser.ConfigParser()
    parser.read(credentials_path)

    new_creds = {
        'aws_access_key_id': access_key,
        'aws_secret_access_key': secret_key,
        'aws_session_token': session_token
    }

    if parser.has_section(profile):
        parser.remove_section(profile)

    parser[profile] = new_creds

    with open(credentials_path, 'w') as f:
        parser.write(f)
    
    # Write config
    config_parser = configparser.ConfigParser()
    config_parser.read(config_path)
    
    profile_key = f'profile {profile}' if profile != 'default' else profile
    
    if not config_parser.has_section(profile_key):
        config_parser[profile_key] = {}
    
    config_parser[profile_key]['region'] = region
    config_parser[profile_key]['output'] = 'json'
    
    with open(config_path, 'w') as f:
        config_parser.write(f)

    print(f'\nAWS credentials written to ~/.aws/credentials')
    expires_in = _format_expires_in(expiration)
    print(f'Credentials expire in {expires_in}')

def credential_process_utility():
    """Output AWS credentials as JSON for use with AWS credential_process."""
    # Redirect stdout to stderr so all print() calls during token
    # acquisition don't pollute the JSON output on stdout.
    real_stdout = sys.stdout
    sys.stdout = sys.stderr

    try:
        directory = get_home_directory()

        profile = 'default'
        if len(sys.argv) == 2:
            pass
        elif len(sys.argv) == 4:
            if sys.argv[2] == '--profile':
                profile = sys.argv[3]
            else:
                print(f'Invalid flag {sys.argv[2]}. Acceptable flag is --profile.', file=sys.stderr)
                exit(1)

        config_path = os.path.join(directory, '.ck-prism', 'config.json')
        if not os.path.exists(config_path):
            print('Configuration not found. Run ck-prism configure', file=sys.stderr)
            exit(1)

        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except json.JSONDecodeError:
            print('Configuration file is invalid or empty. Run ck-prism configure', file=sys.stderr)
            exit(1)

        if not config or profile not in config:
            if profile == 'default':
                print('No configuration found. Run ck-prism configure', file=sys.stderr)
            else:
                print(f'Profile {profile} not found. Run ck-prism configure', file=sys.stderr)
            exit(1)

        profile_config = config[profile]
        prism_domain = profile_config.get('prism_domain', DEFAULT_PRISM_DOMAIN)
        profile_config['keycloak_base_url'] = get_prism_base_url(prism_domain)
        profile_config['api_endpoint'] = get_api_endpoint(prism_domain)

        tokens = get_or_refresh_tokens(profile_config, directory, profile)

        if 'role_arn' not in profile_config:
            print(f"Error: Profile '{profile}' is missing 'role_arn'. Please run 'ck-prism configure' again.", file=sys.stderr)
            exit(1)

        creds = exchange_credentials(profile_config, tokens['access_token'], profile_config['role_arn'])

        # Map to AWS credential_process output format
        access_key = creds.get('access_key_id') or creds.get('AccessKeyId')
        secret_key = creds.get('secret_access_key') or creds.get('SecretAccessKey')
        session_token = creds.get('session_token') or creds.get('SessionToken')
        expiration = creds.get('expiration') or creds.get('Expiration')

        if not access_key or not secret_key:
            print(f'Error: Invalid credentials format received', file=sys.stderr)
            exit(1)

        output = {
            'Version': 1,
            'AccessKeyId': access_key,
            'SecretAccessKey': secret_key,
        }
        if session_token:
            output['SessionToken'] = session_token
        if expiration:
            output['Expiration'] = expiration

        # Restore stdout and write the JSON
        sys.stdout = real_stdout
        print(json.dumps(output))

    except requests.exceptions.RequestException as e:
        sys.stdout = real_stdout
        print(f'Error connecting to API: {e}', file=sys.stderr)
        exit(1)
    except Exception as e:
        sys.stdout = real_stdout
        print(f'Error: {e}', file=sys.stderr)
        exit(1)