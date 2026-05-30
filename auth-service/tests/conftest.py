""""
Esse arquivo é responsável por configurar os fixtures do pytest para os testes de unidade e integração. 
Ele inclui a configuração de um banco de dados de teste, a aplicação das migrações do Alembic e a 
criação de um cliente de teste para a API.
"""
from collections.abc import Generator
from pathlib import Path
import os
import sys

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


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """"
    Cria um cliente de teste para a aplicação FastAPI.
    """
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def integration_database_url() -> str:
    """"
    Obtém a URL do banco de dados de teste a partir da variável de ambiente. Se não estiver configurada,
    os testes serão ignorados.
    """
    database_url = os.getenv("AUTH_SERVICE_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("AUTH_SERVICE_TEST_DATABASE_URL não configurada para testes de integração")

    return database_url


@pytest.fixture
def migrated_postgres_engine(integration_database_url: str):
    """"
    Aplica as migrações do Alembic ao banco de dados de teste e retorna um engine SQLAlchemy para conexão.
    """
    alembic_config = Config(str(BASE_DIR / "alembic.ini"))
    alembic_config.set_main_option("sqlalchemy.url", integration_database_url)
    alembic_config.set_main_option("script_location", str(BASE_DIR / "alembic"))
    command.upgrade(alembic_config, "head")

    engine = create_engine(integration_database_url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture
def postgres_session(migrated_postgres_engine) -> Generator[Session, None, None]:
    """"
    Cria uma sessão de banco de dados para os testes de integração trunkando as tabelas.
    """
    SessionLocal = sessionmaker(
        bind=migrated_postgres_engine,
        autoflush=False,
        autocommit=False,
    )

    with migrated_postgres_engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE"))
        connection.execute(text("TRUNCATE TABLE outbox_events RESTART IDENTITY CASCADE"))
        connection.execute(text("TRUNCATE TABLE processed_events RESTART IDENTITY CASCADE"))

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def integration_client(postgres_session: Session) -> Generator[TestClient, None, None]:
    """"
    Cria um cliente de teste para a aplicação FastAPI usando uma sessão de banco de dados migrada.
    """
    def override_get_db():
        try:
            yield postgres_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
