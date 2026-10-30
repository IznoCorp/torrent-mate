"""PersonalScraper — Media pipeline automation.

Automates the full media workflow: ingest from qBittorrent, sort by type,
scrape metadata from TMDB/TVDB, verify quality, and dispatch to storage disks.
"""

# Load .env into os.environ at package import time so any subsequent module
# that reads credentials (api/_activation.py, api/torrent/_factory.py, etc.)
# sees them. Without this, the CLI starts without .env and every provider
# activation fails with "Missing required credentials". The legacy Settings
# class auto-loaded .env via pydantic-settings; the api-unify code path reads
# os.environ directly and so requires explicit bootstrap here.
#
# An explicit PERSONALSCRAPER_ENV_FILE names an environment's whole secret set
# (the preprod's .env-staging) and is loaded ALONE, as config.py does for Settings:
# the checkout it runs from may carry another environment's .env, whose secrets
# must not reach os.environ. A named file that is missing loads nothing rather
# than falling back to the local .env. Variables already exported still win.
import os as _os

from dotenv import load_dotenv as _load_dotenv

_explicit_env_file = _os.environ.get("PERSONALSCRAPER_ENV_FILE")
if not _explicit_env_file:
    _load_dotenv()
elif _os.path.isfile(_explicit_env_file):
    _load_dotenv(_explicit_env_file, override=False)

__version__ = "0.98.222"
