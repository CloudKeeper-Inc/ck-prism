import sys


def help_utility():
    help_content = '''
Welcome to ck-prism
======================================
This CLI tool authenticates with AWS and provides AWS credentials.

COMMANDS:
  configure           Configure authentication settings
  login               Authenticate and get AWS credentials
  credential-process  Output AWS credentials as JSON for credential_process
  profiles            Manage configured profiles
  setup-completions   Set up shell tab-completion (bash/zsh)
  help                Show this help message

USAGE:
  ck-prism configure
  ck-prism login [--profile PROFILE_NAME]
  ck-prism credential-process --profile PROFILE_NAME
  ck-prism profiles list
  ck-prism profiles remove [PROFILE_NAME] [-y|--yes]
  ck-prism profiles enable-credential-process [PROFILE_NAME]
  ck-prism profiles disable-credential-process [PROFILE_NAME]
  ck-prism profiles migrate-credential-process
  ck-prism help

EXAMPLES:
  # Configure a new profile (enables credential_process by default)
  ck-prism configure

  # Login with a specific profile
  ck-prism login --profile production

  # List all configured profiles
  ck-prism profiles list

  # Remove a profile
  ck-prism profiles remove production -y

  # Enable credential_process for a profile (auto-configures ~/.aws/config)
  ck-prism profiles enable-credential-process production

  # Disable credential_process for a profile
  ck-prism profiles disable-credential-process production

  # Migrate all profiles to use credential_process
  ck-prism profiles migrate-credential-process

  # Set up shell tab-completion
  ck-prism setup-completions

For more information, visit: https://www.cloudkeeper.com/
    '''
    print(help_content)
