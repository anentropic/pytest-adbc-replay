---
phase: quick-02
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/pytest_adbc_replay/_session.py
  - tests/unit/test_cassette_path.py
autonomous: true
requirements: [QUICK-02]
must_haves:
  truths:
    - "Short driver names like 'mysql' or 'databricks' pass through unchanged as differentiator segments"
    - "Absolute .so paths like '/path/to/libadbc_driver_snowflake.so' are sanitized to stem 'libadbc_driver_snowflake'"
    - "Relative paths with extensions like 'drivers/libfoo.so' are sanitized to stem 'libfoo'"
    - "Path.joinpath() never receives an absolute path from differentiator values"
  artifacts:
    - path: "src/pytest_adbc_replay/_session.py"
      provides: "Sanitized differentiator segment extraction"
      contains: "Path.*stem"
    - path: "tests/unit/test_cassette_path.py"
      provides: "Tests for sanitization edge cases"
  key_links:
    - from: "src/pytest_adbc_replay/_session.py"
      to: "Path.joinpath()"
      via: "_extract_differentiator_segments returns sanitized segments"
      pattern: "Path.*\\.stem"
---

<objective>
Fix cassette path resolution for pool-based connections where differentiator values
can be absolute .so paths (e.g. `/path/to/libadbc_driver_snowflake.so`).

Purpose: `Path.joinpath()` with an absolute path replaces the entire path, causing
cassette paths to point outside the project. Sanitize differentiator segment values
using `Path(value).stem` so only the filename stem is used as a path component.

Output: Safe `_extract_differentiator_segments` that handles short names, absolute
paths, and relative paths with extensions.
</objective>

<execution_context>
@/Users/paul/.claude/get-shit-done/workflows/execute-plan.md
@/Users/paul/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@src/pytest_adbc_replay/_session.py
@tests/unit/test_cassette_path.py
@_notes/pool-cassette-path-bug.md
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add sanitization tests for differentiator segment values</name>
  <files>tests/unit/test_cassette_path.py</files>
  <behavior>
    - Test: short driver name "mysql" passes through unchanged as differentiator segment
    - Test: short driver name "databricks" passes through unchanged
    - Test: absolute .so path "/usr/lib/libadbc_driver_snowflake.so" is sanitized to "libadbc_driver_snowflake"
    - Test: relative path with extension "drivers/libfoo.so" is sanitized to "libfoo"
    - Test: value with multiple dots "lib.driver.v2.so" produces stem "lib.driver.v2"
    - Test: plain value without path separators or extension (e.g. "databricks") is unchanged
  </behavior>
  <action>
Add a new test class `TestDifferentiatorSegmentSanitization` to `tests/unit/test_cassette_path.py`.
These tests exercise `_extract_differentiator_segments` indirectly via `node_id_to_cassette_path` by
passing differentiator_segments that simulate what `_extract_differentiator_segments` would return
AFTER sanitization.

However, since `_extract_differentiator_segments` is on `ReplaySession`, the real unit tests should
test the method directly. Add a new test file or add tests in the existing test file that:

1. Import `ReplaySession` from `pytest_adbc_replay._session`
2. Create a minimal `ReplaySession` instance (mode="none")
3. Call `_extract_differentiator_segments` with db_kwargs containing:
   - `{"driver": "mysql"}` with keys `("driver",)` -> expects `("mysql",)`
   - `{"driver": "/usr/lib/libadbc_driver_snowflake.so"}` with keys `("driver",)` -> expects `("libadbc_driver_snowflake",)`
   - `{"driver": "drivers/libfoo.so"}` with keys `("driver",)` -> expects `("libfoo",)`
   - `{"driver": "databricks"}` with keys `("driver",)` -> expects `("databricks",)`
   - `None` db_kwargs -> expects `()`
   - `{}` db_kwargs -> expects `()`

Add these as a new `TestDifferentiatorSegmentSanitization` class in `tests/unit/test_cassette_path.py`
(since this file already tests differentiator segments conceptually).

Run the tests -- they MUST fail (RED phase) because sanitization is not yet implemented.
  </action>
  <verify>
    <automated>cd /Users/paul/Documents/Dev/Personal/pytest-adbc-replay && python -m pytest tests/unit/test_cassette_path.py::TestDifferentiatorSegmentSanitization -x 2>&1 | tail -5</automated>
  </verify>
  <done>New test class exists with 6+ test cases covering short names, absolute paths, relative paths, and edge cases. All tests fail because sanitization is not yet implemented.</done>
</task>

<task type="auto">
  <name>Task 2: Sanitize differentiator values with Path.stem in _extract_differentiator_segments</name>
  <files>src/pytest_adbc_replay/_session.py</files>
  <action>
In `_extract_differentiator_segments` (line 49-63 of `_session.py`), change the return statement
to sanitize each value using `Path(str_value).stem` before returning it as a segment.

Current code (line 63):
```python
return tuple(str(db_kwargs[k]) for k in keys if k in db_kwargs)
```

Replace with:
```python
return tuple(Path(str(db_kwargs[k])).stem for k in keys if k in db_kwargs)
```

This is the minimal fix. `Path.stem` behavior:
- `Path("mysql").stem` -> `"mysql"` (no change for simple names)
- `Path("databricks").stem` -> `"databricks"` (no change)
- `Path("/usr/lib/libadbc_driver_snowflake.so").stem` -> `"libadbc_driver_snowflake"` (strips dir + ext)
- `Path("drivers/libfoo.so").stem` -> `"libfoo"` (strips dir + ext)

`Path` is already imported at the top of `_session.py`.

Update the method docstring to mention the sanitization:
```
Returns an empty tuple when ``db_kwargs`` is ``None`` or no keys match.
Values are sanitized via ``Path(value).stem`` to strip directory
components and file extensions, preventing absolute paths from
corrupting the cassette directory layout.
```
  </action>
  <verify>
    <automated>cd /Users/paul/Documents/Dev/Personal/pytest-adbc-replay && python -m pytest tests/unit/test_cassette_path.py -x -v 2>&1 | tail -20</automated>
  </verify>
  <done>All tests in `test_cassette_path.py` pass including the new sanitization tests. The full test suite also passes (`python -m pytest tests/unit/ -x`).</done>
</task>

</tasks>

<verification>
```bash
# All unit tests pass
cd /Users/paul/Documents/Dev/Personal/pytest-adbc-replay && python -m pytest tests/unit/ -x -q

# Specifically verify the sanitization tests
cd /Users/paul/Documents/Dev/Personal/pytest-adbc-replay && python -m pytest tests/unit/test_cassette_path.py::TestDifferentiatorSegmentSanitization -v

# Verify existing differentiator tests still pass
cd /Users/paul/Documents/Dev/Personal/pytest-adbc-replay && python -m pytest tests/unit/test_cassette_path.py::TestDifferentiatorSegments -v
cd /Users/paul/Documents/Dev/Personal/pytest-adbc-replay && python -m pytest tests/unit/test_auto_patch.py::TestDifferentiatorKeysAutoPatch -v

# Type check passes
cd /Users/paul/Documents/Dev/Personal/pytest-adbc-replay && python -m pyright src/pytest_adbc_replay/_session.py
```
</verification>

<success_criteria>
- `_extract_differentiator_segments` sanitizes values via `Path(value).stem`
- Short driver names ("mysql", "databricks") pass through unchanged
- Absolute .so paths are sanitized to just the stem filename
- All existing tests continue to pass (no regressions)
- New tests cover the sanitization edge cases
</success_criteria>

<output>
After completion, create `.planning/quick/2-fix-cassette-path-resolution-broken-for-/2-SUMMARY.md`
</output>
