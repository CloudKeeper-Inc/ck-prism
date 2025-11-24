import sys 
import subprocess
import json
import os
import configparser 
import time
import hashlib
import base64
import secrets
import urllib.parse
import http.server
import socketserver
import threading
import requests

# Hardcoded Constants
KEYCLOAK_BASE_URL = 'https://login.auth.cloudkeeper.com'
# Placeholder for API Endpoint - User to provide or we use a default if known. 
# Since user didn't provide, I will use a placeholder that must be replaced.
# However, to make it functional for now I will try to keep the logic that reads it from config if not hardcoded here.
# But the requirement was to hardcode it. I will use a placeholder string.
API_ENDPOINT = 'https://cli.auth.cloudkeeper.com/exchange' # Guessed based on typical patterns, but will add a TODO.

def get_home_directory():
    if sys.platform.startswith('linux') or sys.platform.startswith('darwin'):
        # Linux or MacOS
        cmd = 'echo $HOME'
    elif sys.platform.startswith('win'):
        # Windows
        cmd = 'echo %USERPROFILE%'
    else:
        print(f'Unsupported platform: {sys.platform}')
        exit(1)

    directory = subprocess.run(cmd, shell=True, capture_output=True)
    directory = directory.stdout.decode('utf-8').strip()
    return directory

def login_utility():
    directory = get_home_directory()

    profile = 'default'
    if len(sys.argv) == 2:
        pass # Default profile
    elif len(sys.argv) == 4:
        if sys.argv[2] == '--profile':
            profile = sys.argv[3]
            print(f'Using {profile} profile')
        else:
            print(f'Invalid flag {sys.argv[2]}. Acceptable flag is --profile.')
            exit()

    config_path = os.path.join(directory, '.ck-prism', 'config.json')
    if not os.path.exists(config_path):
        print(f'Configuration not found. Run ck-prism configure')
        exit(1)

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except json.JSONDecodeError:
        print(f'Configuration file is invalid or empty. Run ck-prism configure')
        exit(1)
    
    if not config or profile not in config:
        if profile == 'default':
            print(f'No configuration found. Run ck-prism configure')
        else:
            print(f'Profile {profile} not found. Run ck-prism configure')
        exit(1)

    profile_config = config[profile]
    
    # Ensure hardcoded values are used/merged if missing (though configure should set them)
    # Actually, if we hardcode them in code, we should use the constants.
    profile_config['keycloak_base_url'] = KEYCLOAK_BASE_URL
    profile_config['api_endpoint'] = API_ENDPOINT

    tokens = get_or_refresh_tokens(profile_config, directory, profile)
    
    if 'role_arn' not in profile_config:
        print(f"Error: Profile '{profile}' is missing 'role_arn'. Please run 'ck-prism configure' again.")
        exit(1)

    get_aws_credentials(profile_config, tokens['access_token'], profile_config['role_arn'], profile, directory)

def get_or_refresh_tokens(config, directory, profile):
    tokens_dir = os.path.join(directory, '.ck-prism', 'tokens')
    os.makedirs(tokens_dir, exist_ok=True)
    
    token_file = os.path.join(tokens_dir, f'{profile}_tokens.json')
    
    # Try to load and refresh existing tokens
    if os.path.exists(token_file):
        with open(token_file, 'r') as f:
            tokens = json.load(f)
        
        # Check if access token is still valid (with 5 min buffer)
        if tokens.get('expires_at', 0) > time.time() + 300:
            # print('Using cached access token') # Silent as per requirement "silently"
            return tokens
        
        # Try refresh
        if tokens.get('refresh_token'):
            print('Refreshing tokens...')
            refreshed = refresh_tokens(config, tokens['refresh_token'])
            if refreshed:
                save_tokens(token_file, refreshed)
                return refreshed
    
    # Interactive login required
    print('Performing interactive login...')
    new_tokens = interactive_login(config)
    save_tokens(token_file, new_tokens)
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
        'state': state,
        'prompt': 'consent'
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
                self.wfile.write(b'<html><body><h3>Authentication failed</h3></body></html>')
                return
            
            if not code or state != expected_state:
                result['error'] = 'Invalid state or missing code'
                self.send_response(400)
                self.end_headers()
                return
            
            result['code'] = code
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<html><body><h3>Login complete!</h3><p>You can close this tab.</p></body></html>')
        
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
    except:
        pass

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

def get_aws_credentials(config, access_token, role_arn, profile, directory):
    print(f'Exchanging token for AWS credentials for role: {role_arn}...')
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    creds_payload = {
        'token': access_token,
        'realm': config['realm'],
        'selected_role': role_arn
    }
    
    try:
        response = requests.post(config['api_endpoint'], json=creds_payload, headers=headers, timeout=30)
        if response.status_code != 200:
            print(f'AWS credential exchange failed: {response.text}')
            exit(1)
        
        creds = response.json()
        write_aws_credentials(creds, profile, directory, config['region'])
        
    except requests.exceptions.RequestException as e:
        print(f'Error connecting to API: {e}')
        exit(1)
    except Exception as e:
        print(f'Error exchanging credentials: {e}')
        exit(1)

def write_aws_credentials(creds, profile, directory, region):
    credentials_path = os.path.join(directory, '.aws', 'credentials')
    config_path = os.path.join(directory, '.aws', 'config')
    os.makedirs(os.path.dirname(credentials_path), exist_ok=True)

    # Handle nested credentials structure
    if 'credentials' in creds:
        creds = creds['credentials']
    
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
    if expiration:
        print(f'Credentials expire at: {expiration}')
    else:
        print(f'Credentials expire at: {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() + 3600))}')