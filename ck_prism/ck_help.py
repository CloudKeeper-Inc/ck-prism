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
  help                Show this help message

USAGE:
  ck-prism configure
  ck-prism login --profile PROFILE_NAME
  ck-prism credential-process --profile PROFILE_NAME
  ck-prism help

EXAMPLES:
  # Configure a new profile
  ck-prism configure

  # Login with a specific profile
  ck-prism login --profile production

  # Use as AWS credential_process (in ~/.aws/config)
  # [profile production]
  # credential_process = ck-prism credential-process --profile production
  # region = us-east-1

For more information, visit: https://www.cloudkeeper.com/
    '''
    print(help_content)