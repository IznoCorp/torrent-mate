"""The push channel's server side: the subscription store and the per-account dispatcher.

The sender itself is a provider client (``personalscraper.api.notify.fcm``); this package
keeps WHO can be reached (``store``) and fans one message out to an account's devices
(``dispatch``). The trigger, the recipients and the words are K5's.
"""
