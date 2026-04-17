# Changelog

## [1.5.0] 2026-04-17
- Added `ck-prism profiles enable-credential-process` and `disable-credential-process` to automate AWS `credential_process` setup
- Added `ck-prism profiles migrate-credential-process` to enable credential_process for all profiles at once
- `ck-prism configure` now prompts to enable credential_process by default for new profiles
- `ck-prism login` skips login for profiles configured with credential_process and informs the user
- Added `ck-prism setup-completions` for bash/zsh tab-completion of commands, subcommands, and profile names
- Shell completions are set up automatically during `ck-prism configure`

## [1.4.0] 2026-04-16
- Added `ck-prism profiles list` to list all configured profiles
- Added `ck-prism profiles remove [NAME] [-y|--yes]` to remove a profile, its cached tokens, and its AWS credentials section
- Fewer browser prompts when switching between profiles on the same Prism tenant — a single login now covers all profiles that share the same Prism domain and tenant
- Existing profile token files are migrated transparently on first use

## [1.3.0] 2026-04-01
- Added `ck-prism credential-process` subcommand for use with AWS `credential_process`

## [1.2.0] 2026-03-16
- Added interactive fuzzy selection for account and role prompts

## [1.1.1] 2025-11-26
- Fixed prompt=consent issue to unblock non-admin SSO users
- Improved callback UI
- Removed redundant print statement

## [1.1.0] 2025-11-25
- Added support for self-hosted Prism instances

## [1.0.2] 2025-11-24
- Enhance role fetching to display account names while configuring a profile.
- Added support for Prism EU instance

## [1.0.1] 2025-11-23
- Initial release
