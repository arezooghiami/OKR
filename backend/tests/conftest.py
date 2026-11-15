import os

os.environ["OKR_DATABASE_URL"] = "postgresql+psycopg://okr:okr_dev_password@localhost:5433/okr_test"

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

import app.models
from app.core.db import Base, get_engine
from app.main import app
from app.models import User
from tests import demo_seed as seed


@pytest.fixture(scope="session", autouse=True)
def _db():
    with psycopg.connect("postgresql://okr:okr_dev_password@localhost:5433/okr", autocommit=True) as c:
        if not c.execute("select 1 from pg_database where datname='okr_test'").fetchone():
            c.execute("create database okr_test")
    eng = get_engine()
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    with sessionmaker(bind=eng)() as db:
        seed.seed(db)
    yield


@pytest.fixture()
def db():
    with sessionmaker(bind=get_engine())() as s:
        yield s


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


def _username(full_name: str) -> str:
    with sessionmaker(bind=get_engine())() as s:
        return s.scalars(select(User).where(User.full_name == full_name)).one().username


@pytest.fixture()
def login(client):
    def _login(full_name: str) -> dict:
        r = client.post("/api/v1/auth/login", json={"username": _username(full_name), "password": seed.DEMO_PASSWORD})
        assert r.status_code == 200, r.text
        return {"Authorization": "Bearer " + r.json()["access_token"]}
    return _login
