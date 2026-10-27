"""CassetteState: record/replay state shared by every cursor writing one cassette in a test."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections import deque

    import pyarrow as pa


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
        replay_queue: Recorded results per cassette key, in recorded order, loaded
            once per test on its first replaying execute(). Shared so that a
            query repeated across connections replays each recording in turn,
            as it was recorded, rather than every connection replaying the first.
            None until loaded.
        recorded_schemas: Result schema of the first recording of each cassette
            key, filled with replay_queue and never popped, so a schema lookup
            still answers after another connection consumed the recordings.
        write_lock: Serialises cassette writes, the replay-queue load and pops so
            concurrent cursors never take the same interaction index or result.
    """

    wiped: bool = False
    once_replay: bool | None = None
    replay_queue: dict[tuple[str, str], deque[pa.Table]] | None = field(default=None, repr=False)
    recorded_schemas: dict[tuple[str, str], pa.Schema] = field(default_factory=dict, repr=False)
    write_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
