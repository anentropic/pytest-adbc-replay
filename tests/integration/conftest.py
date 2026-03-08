"""Shared fixtures for integration tests (testcontainers, Foundry drivers)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture(scope="session")
def mysql_container() -> Generator[Any, None, None]:
    """Session-scoped fixture that starts a MySQL container via testcontainers."""
    assert shutil.which("docker"), "Docker CLI not found on PATH"

    from testcontainers.mysql import MySqlContainer  # pyright: ignore[reportMissingImports]

    container = MySqlContainer("mysql:8.0")
    container.start()

    yield container

    container.stop()


@pytest.fixture(scope="session")
def mysql_dsn(mysql_container: Any) -> str:
    """Extract the MySQL connection URI from the running testcontainer."""
    host = mysql_container.get_container_host_ip()
    port = mysql_container.get_exposed_port(3306)
    username = mysql_container.username
    password = mysql_container.password
    dbname = mysql_container.dbname
    return f"mysql://{username}:{password}@{host}:{port}/{dbname}"


def _find_adbc_driver_path() -> str | None:
    """Detect the dbc driver install path for ADBC_DRIVER_PATH."""
    if os.environ.get("ADBC_DRIVER_PATH"):
        return os.environ["ADBC_DRIVER_PATH"]

    # Try asking dbc where drivers are installed
    try:
        result = subprocess.run(
            ["dbc", "install", "mysql"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in result.stdout.splitlines():
            if "already installed at" in line:
                return line.split("already installed at")[-1].strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Platform-specific default paths
    home = Path.home()
    candidates = [
        home / "Library" / "Application Support" / "ADBC" / "Drivers",  # macOS
        home / ".local" / "share" / "adbc" / "drivers",  # Linux
    ]
    for path in candidates:
        if path.is_dir():
            return str(path)

    return None


@pytest.fixture(scope="session")
def adbc_driver_path() -> str | None:
    """Resolve ADBC driver path so pytester subprocesses can find Foundry drivers."""
    return _find_adbc_driver_path()
