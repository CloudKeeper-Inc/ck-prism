import sys
import json
import subprocess
import os
from ck_prism.ck_login import interactive_login, fetch_available_roles, DEFAULT_PRISM_DOMAIN, get_prism_base_url, get_api_endpoint

def configure_utility():
    if sys.platform.startswith('linux') or sys.platform.startswith('darwin'):
        cmd = 'echo $HOME'
    elif sys.platform.startswith('win'):
        cmd = 'echo %USERPROFILE%'
    else:
        print(f'Unsupported platform: {sys.platform}')
        exit(1)

    directory = subprocess.run(cmd, shell=True, capture_output=True)
    directory = directory.stdout.decode('utf-8').strip()

    print("\nConfiguring ck-prism")
    print("=" * 50)

    # 1. Ask for Prism Domain
    print(f"\n  Examples: prism.cloudkeeper.com, prism-eu.cloudkeeper.com, myprism.xyz.in")

    prism_domain = input(f'\nEnter Prism domain [example - {DEFAULT_PRISM_DOMAIN}]: ').strip() or DEFAULT_PRISM_DOMAIN

    print(f"Using Prism domain: {prism_domain}")

    # 2. Ask for Realm
    realm = input(f'Enter Prism tenant [example - for sso.{prism_domain}, enter \'sso\']: ').strip() or 'sso'
    realm = realm.strip("'")
    # 3. Perform Login
    print(f"\nLogging in to realm '{realm}' to fetch available roles...")
    temp_config = {
        'realm': realm,
        'client_id': 'ckauth-cli', # Default client ID
        'keycloak_base_url': get_prism_base_url(prism_domain),
        'api_endpoint': get_api_endpoint(prism_domain)
    }
    
    tokens = interactive_login(temp_config)
    access_token = tokens['access_token']
    
    # 3. Fetch Roles
    print("\nFetching available roles...")
    roles, account_names = fetch_available_roles(temp_config, access_token)
    
    if not roles:
        print("No roles found for this user.")
        exit(1)
        
    # 4. Group Roles by Account
    accounts = {}
    for role in roles:
        # Parse role ARN format: {role_arn},{idp_arn} or just {role_arn}
        if isinstance(role, str):
            full_arn = role
            role_arn = role.split(',')[0]
        elif isinstance(role, dict):
            full_arn = role.get('role_arn', role.get('arn', str(role)))
            role_arn = full_arn.split(',')[0] if ',' in full_arn else full_arn
        else:
            full_arn = str(role)
            role_arn = full_arn.split(',')[0]
            
        # Extract Account ID (4th component in ARN: arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME)
        try:
            parts = role_arn.split(':')
            if len(parts) >= 5:
                account_id = parts[4]
                role_name = parts[5].replace('role/', '')
                
                if account_id not in accounts:
                    accounts[account_id] = []
                
                accounts[account_id].append({
                    'name': role_name,
                    'full_arn': full_arn,
                    'role_arn': role_arn
                })
        except Exception:
            continue

    if not accounts:
        print("Could not parse any roles.")
        exit(1)

    # 5. Prompt for Account
    print(f"\nAvailable Accounts: {len(accounts)}")
    sorted_accounts = sorted(accounts.keys())
    
    for idx, acc_id in enumerate(sorted_accounts, 1):
        acc_name = account_names.get(acc_id) if 'account_names' in locals() else None
        if acc_name:
            print(f"{idx}. {acc_id} ({acc_name})")
        else:
            print(f"{idx}. {acc_id}")
        
    while True:
        try:
            selection = input('\nSelect an account (enter number): ').strip()
            selected_idx = int(selection) - 1
            if 0 <= selected_idx < len(sorted_accounts):
                selected_account_id = sorted_accounts[selected_idx]
                break
            else:
                print(f'Please enter a number between 1 and {len(sorted_accounts)}')
        except ValueError:
            print('Please enter a valid number')
        except KeyboardInterrupt:
            print('\nOperation cancelled')
            exit(0)

    # 6. Prompt for Role
    account_roles = accounts[selected_account_id]
    print(f"\nAvailable Roles for Account {selected_account_id}:")
    
    for idx, role in enumerate(account_roles, 1):
        print(f"{idx}. {role['name']}")
        
    while True:
        try:
            selection = input('\nSelect a role (enter number): ').strip()
            selected_idx = int(selection) - 1
            if 0 <= selected_idx < len(account_roles):
                selected_role = account_roles[selected_idx]
                break
            else:
                print(f'Please enter a number between 1 and {len(account_roles)}')
        except ValueError:
            print('Please enter a valid number')
        except KeyboardInterrupt:
            print('\nOperation cancelled')
            exit(0)
            
    print(f"\nSelected Role: {selected_role['name']} ({selected_role['role_arn']})")

    # 7. Ask for Profile Name
    default_profile_name = f"{selected_account_id}-{selected_role['name']}"
    profile_name = input(f'\nEnter Profile Name [{default_profile_name}]: ').strip() or default_profile_name
    
    # Ask for Region
    region = input('Enter AWS Region [us-east-1]: ').strip() or 'us-east-1'

    # 8. Save Configuration
    config_dir = os.path.join(directory, '.ck-prism')
    os.makedirs(config_dir, exist_ok=True)
    config_file_path = os.path.join(config_dir, 'config.json')
    
    config = {}
    if os.path.exists(config_file_path):
        try:
            with open(config_file_path, 'r') as f:
                config = json.load(f)
        except json.JSONDecodeError:
            pass
            
    config[profile_name] = {
        'prism_domain': prism_domain,
        'realm': realm,
        'client_id': 'ckauth-cli',
        'region': region,
        'output': 'json',
        'role_arn': selected_role['full_arn'], # Save full ARN for exchange
        'account_id': selected_account_id,
        'role_name': selected_role['name']
    }
    
    with open(config_file_path, 'w') as f:
        json.dump(config, f, indent=2)
        
    # Save the tokens we just got so we don't need to login again immediately
    tokens_dir = os.path.join(config_dir, 'tokens')
    os.makedirs(tokens_dir, exist_ok=True)
    token_file = os.path.join(tokens_dir, f'{profile_name}_tokens.json')
    
    with open(token_file, 'w') as f:
        json.dump(tokens, f, indent=2)
    os.chmod(token_file, 0o600)

    print(f"\nConfiguration saved for profile '{profile_name}'!")
    print(f"You can now login using: ck-prism login --profile {profile_name}")