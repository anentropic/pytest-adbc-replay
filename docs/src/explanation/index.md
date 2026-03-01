# Explanation

These articles explain the reasoning behind the plugin's design. They cover the "why" rather than the "how." For instructions and task guidance, see the [Tutorial](../tutorial/index.md) and [How-To Guides](../how-to/index.md).

## Articles

- [Cassette format rationale](cassette-format-rationale.md) — why cassettes are files on disk, why Arrow IPC for results, why human-readable SQL
- [SQL normalisation design](sql-normalisation-design.md) — why normalisation is needed, what sqlglot does, and how per-test dialect override works
- [Record mode semantics](record-mode-semantics.md) — when to use each of the four modes and how they fit different development workflows

## What explanation articles are for

Explanation articles are understanding-oriented. They do not tell you how to do something — they explain why things work the way they do.

Reading these articles is optional. The plugin works without understanding its internals. But understanding the design helps when something unexpected happens: a cassette miss you did not expect, a normalisation warning you do not understand, or a decision about which record mode to use in an edge case.

If you find yourself asking "why does the cassette file contain that SQL?" or "why does the plugin have four record modes instead of one?", these articles have the answers.

For lookup-style information (exact defaults, accepted values, error messages), see the [Reference](../reference/index.md) section.

For step-by-step task guidance, the [How-To Guides](../how-to/index.md) cover the most common tasks in a concise, goal-oriented format.
