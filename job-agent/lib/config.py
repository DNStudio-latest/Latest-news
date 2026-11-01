import yaml
from . import paths


def load(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def preferences():
    return load(paths.PREFERENCES)


def scoring():
    return load(paths.SCORING)


def trusted():
    return load(paths.TRUSTED)


def profile():
    return load(paths.PROFILE)


def sources():
    return load(paths.SOURCES_CFG)
