# Single source of truth for the version, kept in sync with pyproject.toml
# by hand. importlib.metadata (used elsewhere) can't find package metadata
# inside the bundled .app, so this is the fallback for that case.
__version__ = "0.2.2"
