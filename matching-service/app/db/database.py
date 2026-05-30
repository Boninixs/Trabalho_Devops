"""
Esse arquivo é responsável pelo módulo de acesso central ao banco de dados.
"""
from app.db.base import Base
from app.db.session import engine

__all__ = ["Base", "engine"]

