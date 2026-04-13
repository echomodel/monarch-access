"""Pytest configuration and fixtures.

Test data is generated from test_data_seed.json, which is the only
file that needs to be committed and reviewed. The generated test_data.json
is gitignored and regenerated as needed.
"""

import shutil
from pathlib import Path

import pytest

from monarch.providers.local import LocalProvider


FIXTURES_DIR = Path(__file__).parent / "fixtures"
TEST_DATA_SEED = FIXTURES_DIR / "test_data_seed.json"
TEST_DATA_FILE = FIXTURES_DIR / "test_data.json"


def _ensure_test_data_exists():
    """Generate test data from seed if it doesn't exist."""
    if not TEST_DATA_FILE.exists():
        from generate_test_data import generate_test_data
        generate_test_data(TEST_DATA_FILE)


@pytest.fixture
def test_db_path(tmp_path):
    """Copy test data to temp directory and return path."""
    _ensure_test_data_exists()
    dest = tmp_path / "test_data.json"
    shutil.copy(TEST_DATA_FILE, dest)
    return dest


@pytest.fixture
def local_provider(test_db_path):
    """Create a LocalProvider with test data."""
    provider = LocalProvider(db_path=test_db_path)
    yield provider
    provider.close()
