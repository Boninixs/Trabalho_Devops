""""
Esse arquivo é responsável pela configuração de conexão com o banco de dados.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db():
    """
    Fornece uma sessão de banco de dados por requisição, utilizado como dependência no 
    FastAPI.
    args:
        None
    returns:
        Generator que fornece uma sessão de banco de dados e garante que ela seja fechada após o uso.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
