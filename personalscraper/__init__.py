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
from dotenv import load_dotenv as _load_dotenv

_load_dotenv()

__version__ = "0.49.14"
