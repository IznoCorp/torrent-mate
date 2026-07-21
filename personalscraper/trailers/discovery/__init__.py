"""Trailer discovery stack for PersonalScraper.

Owns the YouTube/yt-dlp discovery and download layer used by the trailers
pipeline: ``youtube_search`` (YouTube Data API + yt-dlp fallback search),
``trailer_finder`` (VideoProvider-first resolution with YouTube fallback),
``ytdlp_downloader`` (media download), and ``trailers_cache`` (TTL-backed
resolution cache). Previously homed under ``personalscraper.scraper``; moved
here so ``trailers/`` owns its full discovery stack (DESIGN T5).
"""
