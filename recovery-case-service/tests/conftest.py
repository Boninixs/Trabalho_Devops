from collections.abc import Generator
from datetime import date, datetime, timezone
from pathlib import Path
import os
import sys
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.db.session import get_db
from app.main import app
from app.schemas.item_service import (
    ItemOperationItemResponse,
    ItemRecoveryOperationResponse,
)
from app.services.item_service_client import get_item_recovery_client


class FakeItemRecoveryClient:
    def __init__(self) -> None:
        self.open_calls = []
        self.cancel_calls = []
        self.complete_calls = []
        self.fail_open = False
        self.fail_cancel = False
        self.fail_complete = False

    def open_recovery(self, payload):
        self.open_calls.append(payload)
        if self.fail_open:
            from app.core.exceptions import ItemServiceIntegrationError

            raise ItemServiceIntegrationError("falha simulada na abertura")
        return self._build_response("open", payload.item_ids, "IN_RECOVERY")

    def cancel_recovery(self, payload):
        self.cancel_calls.append(payload)
        if self.fail_cancel:
            from app.core.exceptions import ItemServiceIntegrationError

            raise ItemServiceIntegrationError("falha simulada no cancelamento")
        return self._build_response("cancel", payload.item_ids, payload.target_status)

    def complete_recovery(self, payload):
        self.complete_calls.append(payload)
        if self.fail_complete:
            from app.core.exceptions import ItemServiceIntegrationError

            raise ItemServiceIntegrationError("falha simulada na conclusão")
        return self._build_response("complete", payload.item_ids, "RECOVERED")

    def _build_response(self, operation: str, item_ids: list[UUID], status: str) -> ItemRecoveryOperationResponse:
        now = datetime.now(timezone.utc)
        return ItemRecoveryOperationResponse(
            operation=operation,
            items=[
                ItemOperationItemResponse(
                    id=item_id,
                    classification="LOST" if index == 0 else "FOUND",
                    title=f"Item {index}",
                    description=f"Descrição {index}",
                    category="Bolsa",
                    color="Preta",
                    location_description="Biblioteca central",
                    approximate_date=date(2026, 4, 10),
                    reporter_user_id=uuid4(),
                    status=status,
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
                for index, item_id in enumerate(item_ids)
            ],
        )


@pytest.fixture
def fake_item_client() -> FakeItemRecoveryClient:
    return FakeItemRecoveryClient()


@pytest.fixture
def client(fake_item_client: FakeItemRecoveryClient) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_item_recovery_client] = lambda: fake_item_client
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def integration_database_url() -> str:
    database_url = os.getenv("RECOVERY_CASE_SERVICE_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("RECOVERY_CASE_SERVICE_TEST_DATABASE_URL não configurada para testes de integração")
    return database_url


@pytest.fixture
def migrated_postgres_engine(integration_database_url: str):
    alembic_config = Config(str(BASE_DIR / "alembic.ini"))
    alembic_config.set_main_option("sqlalchemy.url", integration_database_url)
    alembic_config.set_main_option("script_location", str(BASE_DIR / "alembic"))
    command.upgrade(alembic_config, "head")

    engine = create_engine(integration_database_url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture
def postgres_session(migrated_postgres_engine) -> Generator[Session, None, None]:
    SessionLocal = sessionmaker(
        bind=migrated_postgres_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    with migrated_postgres_engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE case_events CASCADE"))
        connection.execute(text("TRUNCATE TABLE saga_steps CASCADE"))
        connection.execute(text("TRUNCATE TABLE recovery_cases CASCADE"))
        connection.execute(text("TRUNCATE TABLE outbox_events CASCADE"))
        connection.execute(text("TRUNCATE TABLE processed_events CASCADE"))

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def integration_client(
    postgres_session: Session,
    fake_item_client: FakeItemRecoveryClient,
) -> Generator[TestClient, None, None]:
    def override_get_db():
        try:
            yield postgres_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_item_recovery_client] = lambda: fake_item_client
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
