import sys
from ck_prism.ck_completions import setup_completions_utility
from ck_prism.ck_configuration import configure_utility
from ck_prism.ck_help import help_utility
from ck_prism.ck_login import login_utility, credential_process_utility
from ck_prism.ck_profiles import (
    list_profiles_utility,
    remove_profile_utility,
    enable_credential_process_utility,
    disable_credential_process_utility,
    migrate_credential_process_utility,
)


def _dispatch_profiles():
    if len(sys.argv) < 3:
        print("ERROR: 'profiles' requires a subcommand.\nRun ck-prism help for more information.")
        sys.exit(1)

    subcommand = sys.argv[2]
    if subcommand == 'list':
        list_profiles_utility()
    elif subcommand == 'remove':
        remove_profile_utility()
    elif subcommand == 'enable-credential-process':
        enable_credential_process_utility()
    elif subcommand == 'disable-credential-process':
        disable_credential_process_utility()
    elif subcommand == 'migrate-credential-process':
        migrate_credential_process_utility()
    else:
        print(f"ERROR: Unknown 'profiles' subcommand: {subcommand}\nRun ck-prism help for more information.")
        sys.exit(1)


def main():
    if len(sys.argv) == 1:
        print('ERROR: ck-prism requires one of: configure, login, credential-process, profiles, setup-completions, or help.\nRun ck-prism help for more information.')
        return

    command = sys.argv[1]

    if command == 'profiles':
        _dispatch_profiles()
        return

    if len(sys.argv) > 4:
        print('ERROR: Too many arguments. Run ck-prism help for more information.')
        return

    if command == 'configure':
        configure_utility()
    elif command == 'login':
        login_utility()
    elif command == 'credential-process':
        credential_process_utility()
    elif command == 'setup-completions':
        setup_completions_utility()
    elif command == 'help':
        help_utility()
    else:
        print("Invalid arguments. Run ck-prism help for more information.")


if __name__ == "__main__":
    main()
