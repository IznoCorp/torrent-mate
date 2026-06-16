"""HTTP entrypoint layer — the ``kanban serve`` webhook receiver (ingress-multiproject §4).

``http`` sits at the TOP of the import hierarchy alongside ``cli`` and ``daemon`` (DESIGN §4.1):
it may import ``app`` / ``adapters`` / ``core`` but NOT the sibling entrypoints, so the receiver
is a thin standalone front-door while ``core`` stays pure (enforced by ``tests/test_layering.py``).

The receiver verifies a GitHub webhook HMAC, identifies WHICH project the event belongs to, and
bumps that runtime root's daemon-wake nudge sentinel — it does NOT synthesize Transitions. The
daemon then runs its normal ``tick → snapshot → diff → decide → execute``, so the webhook is
"slot in behind the same BoardReader boundary" achieved by a sub-second wake, idempotent by
construction (a webhook nudge and the safety sweep converge on the same diff against persisted
state).
"""
