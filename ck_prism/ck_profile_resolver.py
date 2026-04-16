class ProfileResolutionError(Exception):
    pass


def resolve_profile(explicit, config, last_profile, is_tty):
    if explicit is not None:
        if explicit not in config:
            raise ProfileResolutionError(
                f"Profile '{explicit}' not found. Run 'ck-prism configure' to create it."
            )
        return explicit, False

    if not config:
        raise ProfileResolutionError(
            "No profiles configured. Run 'ck-prism configure' to create one."
        )

    if len(config) == 1:
        only_name = next(iter(config))
        return only_name, False

    valid_last = last_profile if last_profile in config else None

    if is_tty:
        return valid_last, True

    if valid_last is not None:
        return valid_last, False

    raise ProfileResolutionError(
        "Multiple profiles configured and no last-used profile on record. "
        "Specify --profile NAME."
    )
