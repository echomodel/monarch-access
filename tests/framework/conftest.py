import pytest
from monarch import app as my_app


@pytest.fixture(scope="session")
def app():
    return my_app
