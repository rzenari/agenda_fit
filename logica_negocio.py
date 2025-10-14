import uuid
from datetime import datetime
from database import get_session, Agendamento
import pandas as pd
from sqlalchemy import extract

def gerar_token_unico():
    """Gera um UUID seguro para links de gestão do cliente."""
    return str(uuid.uuid4())

def horario_esta_disponivel(session, profissional: str, data_hora: datetime) -> bool:
    """Verifica se o horário está livre, ignorando agendamentos cancelados."""
    # Filtra por status que bloqueiam a agenda e horário exato
    conflito = session.query(Agendamento).filter(
        Agendamento.profissional == profissional,
        Agendamento.horario == data_hora,
        Agendamento.status.in_(["Confirmado", "Em Andamento"]) 
    ).first()
    
    return conflito is None

def processar_cancelamento_seguro(token: str) -> bool:
    """Cancela o agendamento apenas se o token for válido e o status for 'Confirmado'."""
    session = get_session()
    try:
        agendamento = session.query(Agendamento).filter(
            Agendamento.token_unico == token,
            Agendamento.status == "Confirmado"
        ).first()
        
        if agendamento:
            agendamento.status = "Cancelado pelo Cliente"
            session.commit()
            return True
        return False
    finally:
        session.close()

def get_relatorio_no_show() -> pd.DataFrame:
    """
    Função Python/Pandas para calcular e retornar a taxa de No-Show por profissional.
    """
    session = get_session()
    try:
        # Puxa todos os dados de agendamento
        todos_agendamentos = pd.read_sql(session.query(Agendamento).statement, session.bind)
        
        if todos_agendamentos.empty:
            return pd.DataFrame()
        
        # Filtra agendamentos que já deveriam ter ocorrido ou ocorreram
        df = todos_agendamentos[
            todos_agendamentos['horario'].dt.date <= datetime.now().date()
        ]
        
        # Agrupa e calcula as métricas
        df_grouped = df.groupby('profissional').agg(
            total_atendimentos=('status', 'size'),
            total_faltas=('status', lambda x: (x == 'No-Show').sum()),
            total_cancelados=('status', lambda x: (x == 'Cancelado pelo Cliente').sum()),
            total_finalizados=('status', lambda x: (x == 'Finalizado').sum())
        )
        
        # O cálculo mais preciso é sobre o total que deveria ter ocorrido
        df_grouped['Taxa No-Show (%)'] = (
            df_grouped['total_faltas'] / df_grouped['total_atendimentos'].replace(0, 1)
        ) * 100
        
        return df_grouped.sort_values(by='Taxa No-Show (%)', ascending=False).reset_index()
    
    except Exception as e:
        print(f"Erro ao gerar relatório: {e}")
        return pd.DataFrame()
    finally:
        session.close()
