import os
import tempfile

import pytest

# Isolate the test DB from the dev DB.
_tmp = tempfile.mkdtemp()
os.environ["ROOMBRIDGE_DB_PATH"] = os.path.join(_tmp, "test_runs.db")


@pytest.fixture(scope="session", autouse=True)
def _db():
    from roombridge.config import settings
    from pathlib import Path
    settings.db_path = Path(_tmp) / "test_runs.db"
    from roombridge.domain.db import init_db
    from roombridge.scenarios.loader import load_all
    init_db()
    load_all()
    yield
