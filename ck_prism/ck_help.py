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
  profiles            Manage configured profiles (list, remove)
  help                Show this help message

USAGE:
  ck-prism configure
  ck-prism login --profile PROFILE_NAME
  ck-prism credential-process --profile PROFILE_NAME
  ck-prism profiles list
  ck-prism profiles remove [PROFILE_NAME] [-y|--yes]
  ck-prism help

EXAMPLES:
  # Configure a new profile
  ck-prism configure

  # Login with a specific profile
  ck-prism login --profile production

  # List all configured profiles
  ck-prism profiles list

  # Remove a profile (interactive picker if no name given)
  ck-prism profiles remove
  ck-prism profiles remove production -y

  # Use as AWS credential_process (in ~/.aws/config)
  # [profile production]
  # credential_process = ck-prism credential-process --profile production
  # region = us-east-1

For more information, visit: https://www.cloudkeeper.com/
    '''
    print(help_content)
