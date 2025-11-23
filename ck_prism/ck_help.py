import sys


def help_utility():
    help_content = '''
Welcome to ck-prism
======================================
This CLI tool authenticates with AWS and provides AWS credentials.

COMMANDS:
  configure  Configure authentication settings
  login      Authenticate and get AWS credentials
  help       Show this help message

USAGE:
  ck-prism configure
  ck-prism login --profile PROFILE_NAME
  ck-prism help

EXAMPLES:
  # Configure a new profile
  ck-prism configure

  # Login with a specific profile
  ck-prism login --profile production

For more information, visit: https://www.cloudkeeper.com/
    '''
    print(help_content)