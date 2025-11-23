import sys
from ck_prism.ck_configuration import configure_utility
from ck_prism.ck_help import help_utility
from ck_prism.ck_login import login_utility

def main():
    if len(sys.argv) == 1:
        print('ERROR: ck-prism requires one of: configure, login, or help.\nRun ck-prism help for more information.')
    elif len(sys.argv) > 4:
        print('ERROR: Too many arguments. Run ck-prism help for more information.')
    else: 
        if sys.argv[1] == 'configure':
            configure_utility()
        elif sys.argv[1] == 'login':
            login_utility()
        elif sys.argv[1] == 'help':
            help_utility()
        else:
            print("Invalid arguments. Run ck-prism help for more information.")

if __name__ == "__main__":
    main()
