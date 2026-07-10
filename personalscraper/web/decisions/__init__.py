"""Web decision runner — scrapes a decision via detached subprocess (S5 scrape-arbiter).

Package contents:

* :mod:`personalscraper.web.decisions.runner` — subprocess wrapper spawned
  by the resolve POST handler.  Mirrors the S3 maintenance runner pattern:
  env contract, pipeline_run row, detached child (``start_new_session=True``),
  Redis streaming + 64 KiB ring buffer, row finalization on every exit path.
"""
