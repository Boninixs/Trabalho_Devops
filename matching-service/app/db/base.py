"""
Esse arquivo é responsável por configurar a base de dados e importar os modelos para que as tabelas sejam criadas corretamente. 
"""
from app.models.common import Base

import app.models.item_projection  
import app.models.match_suggestion 
import app.models.outbox 
import app.models.processed_event 
