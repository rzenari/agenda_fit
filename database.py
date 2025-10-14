from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

# Conexão com SQLite no mesmo diretório
DATABASE_URL = "sqlite:///agenda.db"
Base = declarative_base()

# --- Definição da Tabela (Modelo de Dados) ---
class Agendamento(Base):
    __tablename__ = 'agendamentos'
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Segurança e Rastreamento
    token_unico = Column(String, unique=True, index=True) 
    
    # Dados da Sessão
    profissional = Column(String, index=True)
    cliente = Column(String)
    telefone = Column(String) 
    horario = Column(DateTime, index=True)
    
    # Status
    status = Column(String, default="Confirmado") # Confirmado, Cancelado, No-Show, Finalizado
    
    # Gestão de Pacotes (Novo Recurso)
    is_pacote_sessao = Column(Boolean, default=False)
    sessao_pacote_id = Column(String, nullable=True) # ID do grupo de sessões

    def __repr__(self):
        return f"Agendamento(ID={self.id}, Cliente={self.cliente})"

# --- Funções de Operação no Banco de Dados ---

def iniciar_db():
    """Cria o arquivo agenda.db e a tabela se não existirem."""
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    return engine

def get_session():
    """Retorna uma sessão para interagir com o DB."""
    engine = iniciar_db()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()