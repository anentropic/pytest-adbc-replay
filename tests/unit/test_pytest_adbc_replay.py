"""Basic tests for pytest_adbc_replay."""

import pytest_adbc_replay


def test_import():
    assert hasattr(pytest_adbc_replay, "__all__")
