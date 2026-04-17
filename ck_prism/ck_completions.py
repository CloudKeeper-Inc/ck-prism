"""Shell completion setup for ck-prism."""

import os
import sys

from ck_prism.ck_paths import get_config_dir


BASH_SCRIPT = r'''# ck-prism bash completions
_ck_prism_completions() {
    local cur prev words cword
    _init_completion || return

    local commands="configure login credential-process profiles help setup-completions"
    local profiles_subcmds="list remove enable-credential-process disable-credential-process migrate-credential-process"

    # Read profile names from config
    _ck_prism_profiles() {
        local config="$HOME/.ck-prism/config.json"
        if [ -f "$config" ]; then
            python3 -c "import json; print('\n'.join(json.load(open('$config')).keys()))" 2>/dev/null
        fi
    }

    case "$cword" in
        1)
            COMPREPLY=( $(compgen -W "$commands" -- "$cur") )
            ;;
        2)
            case "${words[1]}" in
                profiles)
                    COMPREPLY=( $(compgen -W "$profiles_subcmds" -- "$cur") )
                    ;;
                login|credential-process)
                    COMPREPLY=( $(compgen -W "--profile" -- "$cur") )
                    ;;
            esac
            ;;
        3)
            case "${words[1]}" in
                login|credential-process)
                    if [ "${words[2]}" = "--profile" ]; then
                        COMPREPLY=( $(compgen -W "$(_ck_prism_profiles)" -- "$cur") )
                    fi
                    ;;
                profiles)
                    case "${words[2]}" in
                        remove|enable-credential-process|disable-credential-process)
                            COMPREPLY=( $(compgen -W "$(_ck_prism_profiles)" -- "$cur") )
                            ;;
                    esac
                    ;;
            esac
            ;;
    esac
}

complete -F _ck_prism_completions ck-prism
'''

ZSH_SCRIPT = r'''# ck-prism zsh completions
_ck_prism() {
    local -a commands profiles_subcmds

    commands=(
        'configure:Configure authentication settings'
        'login:Authenticate and get AWS credentials'
        'credential-process:Output AWS credentials as JSON'
        'profiles:Manage configured profiles'
        'help:Show help message'
        'setup-completions:Set up shell completions'
    )

    profiles_subcmds=(
        'list:List all configured profiles'
        'remove:Remove a profile'
        'enable-credential-process:Enable credential_process for a profile'
        'disable-credential-process:Disable credential_process for a profile'
        'migrate-credential-process:Enable credential_process for all profiles'
    )

    _ck_prism_profiles() {
        local config="$HOME/.ck-prism/config.json"
        if [ -f "$config" ]; then
            local names
            names=(${(f)"$(python3 -c "import json; print('\n'.join(json.load(open('$config')).keys()))" 2>/dev/null)"})
            compadd -a names
        fi
    }

    case "$CURRENT" in
        2)
            _describe 'command' commands
            ;;
        3)
            case "${words[2]}" in
                profiles)
                    _describe 'subcommand' profiles_subcmds
                    ;;
                login|credential-process)
                    compadd -- --profile
                    ;;
            esac
            ;;
        4)
            case "${words[2]}" in
                login|credential-process)
                    if [ "${words[3]}" = "--profile" ]; then
                        _ck_prism_profiles
                    fi
                    ;;
                profiles)
                    case "${words[3]}" in
                        remove|enable-credential-process|disable-credential-process)
                            _ck_prism_profiles
                            ;;
                    esac
                    ;;
            esac
            ;;
    esac
}

compdef _ck_prism ck-prism
'''


def _get_completions_dir():
    return os.path.join(get_config_dir(), 'completions')


def _detect_shell():
    shell = os.environ.get('SHELL', '')
    if 'zsh' in shell:
        return 'zsh'
    return 'bash'


def _shell_profile_path(shell):
    home = os.path.expanduser('~')
    if shell == 'zsh':
        return os.path.join(home, '.zshrc')
    return os.path.join(home, '.bashrc')


def _source_line(script_path):
    return f'source "{script_path}"'


def _already_sourced(profile_path, source_line):
    if not os.path.exists(profile_path):
        return False
    with open(profile_path, 'r') as f:
        return source_line in f.read()


def setup_completions_utility(silent=False):
    shell = _detect_shell()
    script = ZSH_SCRIPT if shell == 'zsh' else BASH_SCRIPT
    ext = 'zsh' if shell == 'zsh' else 'bash'

    completions_dir = _get_completions_dir()
    os.makedirs(completions_dir, exist_ok=True)

    script_path = os.path.join(completions_dir, f'ck-prism.{ext}')
    with open(script_path, 'w') as f:
        f.write(script)

    source_line = _source_line(script_path)
    profile_path = _shell_profile_path(shell)

    if _already_sourced(profile_path, source_line):
        if not silent:
            print(f"Shell completions already configured in {profile_path}.")
            print(f"Completion script updated at {script_path}.")
        return

    with open(profile_path, 'a') as f:
        f.write(f'\n# ck-prism shell completions\n{source_line}\n')

    if not silent:
        print(f"\nShell completions installed for {shell}!")
        print(f"  Script: {script_path}")
        print(f"  Added to: {profile_path}")
        print(f"\nRestart your terminal or run: {source_line}")
