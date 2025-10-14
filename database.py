from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import pandas as pd

# Conexão com SQLite no mesmo diretório
# IMPORTANTE: O Streamlit Cloud vai criar este arquivo no deploy
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
    sessao_pacote_id = Column(String, nullable=True) 

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

def salvar_agendamento(session, dados: dict, token: str):
    """Cria um novo agendamento no DB."""
    novo = Agendamento(
        token_unico=token,
        profissional=dados['profissional'],
        cliente=dados['cliente'],
        telefone=dados['telefone'],
        horario=dados['horario'],
    )
    session.add(novo)
    session.commit()
    session.refresh(novo)
    return novo

def buscar_agendamento_por_token(session, token: str):
    """Busca um agendamento específico usando o token de segurança."""
    return session.query(Agendamento).filter(Agendamento.token_unico == token).first()

def buscar_agendamentos_hoje(session, profissional: str = None):
    """Busca todos os agendamentos confirmados para hoje."""
    data_hoje = datetime.now().date()
    
    query = session.query(Agendamento).filter(Agendamento.status == "Confirmado")
    
    if profissional:
        query = query.filter(Agendamento.profissional == profissional)
        
    # Retorna uma lista de agendamentos para a data de hoje
    # Usamos list comprehension para filtrar pela data (porque SQLite não suporta função DATE nativamente com SQLAlchemy)
    return [
        agendamento 
        for agendamento in query.all() 
        if agendamento.horario.date() == data_hoje
    ]
