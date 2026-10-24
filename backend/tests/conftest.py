from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db, make_engine
from app.main import app
from app.services.fixtures import datasets

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def content():
    return (ROOT / "detections/windows/powershell/suspicious_powershell.yml").read_text()


@pytest.fixture
def fixtures():
    return datasets()


@pytest.fixture
def client(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)

    def database():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = database
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    engine.dispose()
