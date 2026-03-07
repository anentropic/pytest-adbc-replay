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


def _docker_available() -> bool:
    """Check if Docker CLI is available on the system."""
    return shutil.which("docker") is not None


def _dbc_available() -> bool:
    """Check if the dbc CLI (columnar.tech) is available on the system."""
    return shutil.which("dbc") is not None


@pytest.fixture(scope="session")
def mysql_container() -> Generator[Any, None, None]:
    """
    Session-scoped fixture that starts a MySQL container via testcontainers.

    Skips the test if:
    - testcontainers is not installed
    - Docker is not available
    """
    if not _docker_available():
        pytest.skip("Docker not available")

    try:
        from testcontainers.mysql import MySqlContainer  # pyright: ignore[reportMissingImports]
    except ImportError:
        pytest.skip("testcontainers[mysql] not installed")

    try:
        container = MySqlContainer("mysql:8.0")
        container.start()
    except Exception as exc:
        pytest.skip(f"Failed to start MySQL container: {exc}")

    yield container

    container.stop()


@pytest.fixture(scope="session")
def mysql_dsn(mysql_container: Any) -> str:
    """
    Extract the MySQL connection URI from the running testcontainer.

    Returns a URI suitable for ADBC driver connection (mysql:// scheme).
    """
    host = mysql_container.get_container_host_ip()
    port = mysql_container.get_exposed_port(3306)
    username = mysql_container.username
    password = mysql_container.password
    dbname = mysql_container.dbname
    return f"mysql://{username}:{password}@{host}:{port}/{dbname}"


@pytest.fixture(scope="session")
def dbc_mysql_available() -> bool:
    """
    Session-scoped fixture that checks if dbc CLI and MySQL Foundry driver are available.

    Returns True if available, skips the test otherwise.
    """
    if not _dbc_available():
        pytest.skip("dbc CLI not installed (install from https://columnar.tech)")

    # Check that adbc_driver_manager is importable (it's a project dependency, so it should be)
    try:
        import adbc_driver_manager.dbapi as _  # noqa: F401  # pyright: ignore[reportMissingModuleSource]
    except ImportError:
        pytest.skip("adbc_driver_manager not installed")

    return True


def _find_adbc_driver_path() -> str | None:
    """Detect the dbc driver install path for ADBC_DRIVER_PATH."""
    # Check if already set
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
        # Output like: "Driver mysql 0.3.0 already installed at /path/to/drivers"
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
