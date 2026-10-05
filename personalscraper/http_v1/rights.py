"""The right every v1 operation asks for: one table, every contract operation, served or not.

A lot never decides a right: it copies it from here. The source is the ``x-rights``
the contract ``contract/openapi.json`` stamps on each operation;
``tests/http_v1/test_rights_table.py`` compares the two. Two ruled corrections to the
contract's session acts: the sign-in operations are :class:`Public`, and the account's
own writes are ``SignedIn(write=True)``.

A list is « any of »: a read opened by several rights. A write names exactly one
right, so an instance ceiling subtracts it by name; piloting (own or any) is the
one exception, the target deciding which of the two applies (``OWN_SCOPED``).
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from personalscraper.app.accounts.rights import AnyOf, Public, Requirement, Right, SignedIn, holds

# The acquisition section's own door: requesting, or seeing everyone's.
_ACQUISITION: Final[AnyOf] = AnyOf(frozenset({Right.ACQUISITION_REQUEST, Right.ACQUISITION_SEE_OTHERS}))
# Piloting a tunnel: one's own, or any.
_PILOT: Final[AnyOf] = AnyOf(frozenset({Right.ACQUISITION_PILOT_OWN, Right.ACQUISITION_PILOT_ANY}))

#: The operations v1 serves before the contract names them: none since gap G-4 closed.
PENDING_OPERATIONS: Final[frozenset[str]] = frozenset()

#: Every contract ``operationId`` and every pending one → what it asks for.
OPERATION_RIGHTS: Final[Mapping[str, Requirement]] = MappingProxyType(
    {
        # The session's own acts: every identity, under any ceiling; the sign-in doors ask no session.
        "readAccount": SignedIn(),
        "signIn": Public(),
        "signOut": SignedIn(),
        "signInWithPlex": Public(),
        # The server-run PIN's first step: before any session, like the two sign-ins.
        "startPlexSignIn": Public(),
        "readVersion": SignedIn(),
        # One's own password, on one's own account: a session act, no right to name; a write,
        # refused on a read-only instance (the account's own writes, ruling of 2026-10-03).
        "changeOwnPassword": SignedIn(write=True),
        # One's own language, chosen in Profil: the same session act, the same refusal on a
        # read-only instance (FG-1 B, ruling of 2026-10-03).
        "setOwnLanguage": SignedIn(write=True),
        # The account's own notification choices and devices: a session act, no right; the
        # writes are refused on a read-only instance (ruling of 2026-10-03).
        "readNotificationPreferences": SignedIn(),
        "updateNotificationPreference": SignedIn(write=True),
        "registerPushDevice": SignedIn(write=True),
        # The roster: Comptes manages it; the reassign chooser reads it narrowly.
        "readAccounts": AnyOf(frozenset({Right.ACCOUNTS_MANAGE, Right.ACQUISITION_REASSIGN})),
        "createAccount": holds(Right.ACCOUNTS_MANAGE),
        "updateAccount": holds(Right.ACCOUNTS_MANAGE),
        "resetAccountPassword": holds(Right.ACCOUNTS_MANAGE),
        "setAccountAccess": holds(Right.ACCOUNTS_MANAGE),
        "createRole": holds(Right.ACCOUNTS_MANAGE),
        "updateRole": holds(Right.ACCOUNTS_MANAGE),
        "deleteRole": holds(Right.ACCOUNTS_MANAGE),
        "readLibraryItems": holds(Right.LIBRARY_READ),
        "readLibraryCategories": holds(Right.LIBRARY_READ),
        "readLibraryRecent": holds(Right.LIBRARY_READ),
        "readLibraryIncomplete": holds(Right.LIBRARY_READ),
        "readLibraryMembership": holds(Right.LIBRARY_READ),
        "readMediaSheet": holds(Right.LIBRARY_READ),
        "readMediaSeasons": holds(Right.LIBRARY_READ),
        "readMediaPoster": holds(Right.LIBRARY_READ),
        "deleteLibraryItems": holds(Right.LIBRARY_DELETE),
        "rescrapeMedia": holds(Right.LIBRARY_RESCRAPE),
        # The acquisition reads are scopes, never doors: the service filters by right.
        "readFollows": SignedIn(),
        "readFollowCompleteness": SignedIn(),
        "readAcquisitionQueue": SignedIn(),
        "readAcquisitionStatus": SignedIn(),
        "readJourney": SignedIn(),
        "readDecisions": _ACQUISITION,
        "readStaging": _ACQUISITION,
        "readStagedMediaCopies": _ACQUISITION,
        "readStagingDestinations": _ACQUISITION,
        "readSuggestions": holds(Right.ACQUISITION_REQUEST),
        "searchProviders": holds(Right.ACQUISITION_REQUEST),
        "searchProviderById": holds(Right.ACQUISITION_REQUEST),
        "readReleases": _PILOT,
        "createFollow": holds(Right.ACQUISITION_REQUEST),
        "updateFollow": holds(Right.ACQUISITION_FOLLOW),
        "deleteFollow": holds(Right.ACQUISITION_FOLLOW),
        "restoreFollow": holds(Right.ACQUISITION_FOLLOW),
        "searchForFollow": _PILOT,
        "grabForFollow": _PILOT,
        "grabSeasonForFollow": _PILOT,
        "requeueJourney": _PILOT,
        # The account's own seen mark on a closed tunnel: a session act, as the contract states;
        # a write, refused on a read-only instance (the account's own writes, ruling of 2026-10-03).
        "dismissClosure": SignedIn(write=True),
        "rescrapeJourney": _PILOT,
        "setAcquisitionQuality": holds(Right.ACQUISITION_QUALITY_OWN),
        "setAcquisitionPause": holds(Right.ACQUISITION_PAUSE_OWN),
        "reassignRequester": holds(Right.ACQUISITION_REASSIGN),
        "runDetection": holds(Right.PIPELINE_CONTROL),
        "deleteStagedMedia": holds(Right.PIPELINE_CONTROL),
        "continueStagedMedia": holds(Right.PIPELINE_CONTROL),
        "discardStagedMedia": holds(Right.PIPELINE_CONTROL),
        "reclassifyStagedMedia": holds(Right.PIPELINE_CONTROL),
        "restoreReclassifiedMedia": holds(Right.PIPELINE_CONTROL),
        "resolvePlexMatch": holds(Right.PIPELINE_CONTROL),
        "resolveDecision": holds(Right.PIPELINE_CONTROL),
        "reopenDecision": holds(Right.PIPELINE_CONTROL),
        "enqueueForResolution": holds(Right.PIPELINE_CONTROL),
        "dismissDecision": holds(Right.PIPELINE_CONTROL),
        "searchForDecision": holds(Right.PIPELINE_CONTROL),
        "runPipeline": holds(Right.PIPELINE_CONTROL),
        "pausePipeline": holds(Right.PIPELINE_CONTROL),
        "resumePipeline": holds(Right.PIPELINE_CONTROL),
        "killPipeline": holds(Right.PIPELINE_CONTROL),
        "setWatcher": holds(Right.PIPELINE_CONTROL),
        "runMaintenanceAction": holds(Right.PIPELINE_CONTROL),
        "readPipeline": holds(Right.SYSTEM_VIEW),
        "readPipelineHistory": holds(Right.SYSTEM_VIEW),
        "readRun": holds(Right.SYSTEM_VIEW),
        "readServices": holds(Right.SYSTEM_VIEW),
        "readDependencies": holds(Right.SYSTEM_VIEW),
        "readErrors": holds(Right.SYSTEM_VIEW),
        "readSchedulers": holds(Right.SYSTEM_VIEW),
        "readDisks": holds(Right.SYSTEM_VIEW),
        "readIndexHealth": holds(Right.SYSTEM_VIEW),
        "readMaintenanceActions": holds(Right.SYSTEM_VIEW),
        "readDeletionJournal": holds(Right.SYSTEM_VIEW),
        "readLocks": holds(Right.SYSTEM_VIEW),
        "readTrackers": holds(Right.TRACKERS_VIEW),
        "readDownloads": holds(Right.TRACKERS_VIEW),
        "readObligations": holds(Right.TRACKERS_VIEW),
        # The media sheet's block summarises the Trackers page: the same right.
        "readMediaCrossSeed": holds(Right.TRACKERS_VIEW),
        "removeDownload": holds(Right.TRACKERS_CONTROL),
        "markBrokenObligationSeen": holds(Right.TRACKERS_CONTROL),
        "cutCrossSeed": holds(Right.TRACKERS_CONTROL),
        "searchCrossSeed": holds(Right.TRACKERS_CONTROL),
        # Publishing at a third party is its own right, never implied by trackers.control.
        "uploadCrossSeed": holds(Right.TRACKERS_UPLOAD),
        "writeCrossSeedExclusion": holds(Right.TRACKERS_CONTROL),
        "undoCrossSeedExclusion": holds(Right.TRACKERS_CONTROL),
        "readSettings": AnyOf(frozenset({Right.CONFIGURATION_VIEW, Right.TRACKERS_VIEW, Right.SYSTEM_VIEW})),
        "readConfigurationStatus": AnyOf(frozenset({Right.CONFIGURATION_VIEW, Right.SYSTEM_VIEW})),
        "readSecrets": holds(Right.CONFIGURATION_VIEW),
        "readConfigurationFiles": holds(Right.CONFIGURATION_VIEW),
        "readConfigurationFile": holds(Right.CONFIGURATION_VIEW),
        "updateSecrets": holds(Right.CONFIGURATION_WRITE),
        "updateConfigurationFile": holds(Right.CONFIGURATION_WRITE),
        "restartWeb": holds(Right.CONFIGURATION_WRITE),
        "previewRanking": holds(Right.CONFIGURATION_WRITE),
    }
)

#: The operations acting on ONE acquisition whose target decides « own or any »: the
#: perimeter checks ``acquisition.pilot.own`` or ``.any``, the service checks
#: ``actor.is_requester(...)`` (DESIGN C.6, ownership).
OWN_SCOPED: Final[frozenset[str]] = frozenset(
    {
        "searchForFollow",
        "grabForFollow",
        "grabSeasonForFollow",
        "requeueJourney",
        "rescrapeJourney",
        "updateFollow",
        "deleteFollow",
    }
)
