"""
Esse arquivo é responsável por configurar a base de dados e importar os modelos para que as tabelas sejam criadas corretamente. 
"""
from app.models.common import Base

import app.models.outbox  # noqa: F401
import app.models.processed_event  # noqa: F401
import app.models.user  # noqa: F401
