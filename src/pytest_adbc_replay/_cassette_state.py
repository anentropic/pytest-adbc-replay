"""CassetteState: record/replay state shared by every cursor writing one cassette in a test."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class CassetteState:
    """
    Per-test state for one cassette, shared across connections, clones and cursors.

    A test can reach the same cassette through several cursors and connections
    (a connection pool opens one per query). Decisions about the cassette as a
    whole must be made once per test, not once per cursor, or a later cursor
    sees the recording an earlier one just made.

    Attributes:
        wiped: 'all' mode: the cassette directory was already wiped in this test.
        once_replay: 'once' mode: whether this test replays (True) or records
            (False). Decided on the test's first execute() from whether the
            cassette had interactions then; None until that first execute().
        write_lock: Serialises interaction writes so concurrent cursors never
            take the same interaction index.
    """

    wiped: bool = False
    once_replay: bool | None = None
    write_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
