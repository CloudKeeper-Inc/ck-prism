import json
import os
from ck_prism.ck_completions import setup_completions_utility
from ck_prism.ck_login import interactive_login, fetch_available_roles, DEFAULT_PRISM_DOMAIN, get_prism_base_url, get_api_endpoint
from ck_prism.ck_paths import get_home_dir
from ck_prism.ck_profiles import enable_credential_process
from ck_prism.ck_prompt import interactive_select, clear_screen, Spinner
from ck_prism import ck_token_store

def configure_utility():
    directory = get_home_dir()

    print("\nConfiguring ck-prism")
    print("=" * 50)

    # 1. Ask for Prism Domain
    
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

    # Clear the browser auth URL clutter
    clear_screen()

    # 3. Fetch Roles
    with Spinner("Fetching available roles..."):
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
    sorted_accounts = sorted(accounts.keys())
    account_choices = []
    for acc_id in sorted_accounts:
        acc_name = account_names.get(acc_id)
        label = f"{acc_id} ({acc_name})" if acc_name else acc_id
        account_choices.append({"name": label, "value": acc_id})

    selected_account_id = interactive_select(
        message="Select an account:",
        choices=account_choices,
    )

    # 6. Prompt for Role
    account_roles = accounts[selected_account_id]
    role_choices = [
        {"name": role["name"], "value": role}
        for role in account_roles
    ]

    selected_role = interactive_select(
        message=f"Select a role for account {selected_account_id}:",
        choices=role_choices,
    )
            
    print(f"\nSelected Role: {selected_role['name']}")

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

    # Save the tokens we just got so we don't need to login again immediately.
    # Stored per tenant (prism_domain, realm), shared across profiles.
    ck_token_store.save_tokens(config[profile_name], profile_name, tokens)

    print(f"\nConfiguration saved for profile '{profile_name}'!")

    # 9. Offer to enable credential_process (default: yes)
    cp_answer = input('Enable credential_process for this profile? [Y/n]: ').strip().lower()
    if cp_answer in ('', 'y', 'yes'):
        results = enable_credential_process(profile_name, config, config_file_path)
        print(f"\nEnabled credential_process for '{profile_name}':")
        for line in results:
            print(f"  - {line}")
        print(f"\nAWS CLI will now fetch credentials automatically when you use --profile {profile_name}.")
    else:
        config[profile_name]['credential_process_enabled'] = False
        with open(config_file_path, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"You can now login using: ck-prism login --profile {profile_name}")

    # 10. Set up shell completions (silently if already done)
    setup_completions_utility(silent=True)