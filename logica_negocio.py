import uuid
from datetime import datetime
from database import get_session, Agendamento
from sqlalchemy import extract
import pandas as pd

def gerar_token_unico():
    """Gera um UUID seguro para links de gestão do cliente."""
    return str(uuid.uuid4())

def horario_esta_disponivel(session, profissional: str, data_hora: datetime) -> bool:
    """Verifica se o horário está livre, ignorando agendamentos cancelados."""
    conflito = session.query(Agendamento).filter(
        Agendamento.profissional == profissional,
        Agendamento.horario == data_hora,
        Agendamento.status.in_(["Confirmado", "Em Andamento"]) # Apenas status que bloqueiam a agenda
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
    Função Python/Pandas para calcular e retornar a taxa de No-Show.
    (Implementação de Alto Valor)
    """
    session = get_session()
    try:
        # Puxa todos os dados de agendamento (Pode ser otimizado para produção)
        todos_agendamentos = pd.read_sql(session.query(Agendamento).statement, session.bind)
        
        if todos_agendamentos.empty:
            return pd.DataFrame()
        
        # Filtra apenas os agendamentos relevantes para o cálculo de taxa
        df = todos_agendamentos[todos_agendamentos['status'].isin(['Confirmado', 'No-Show', 'Finalizado', 'Cancelado pelo Cliente'])]
        
        # Agrupa e calcula as métricas (exemplo simples)
        df_grouped = df.groupby('profissional').agg(
            total_atendimentos=('status', lambda x: (x.isin(['Finalizado', 'No-Show'])).sum()),
            total_no_show=('status', lambda x: (x == 'No-Show').sum())
        )
        
        # Evita divisão por zero
        df_grouped['Taxa No-Show (%)'] = (
            df_grouped['total_no_show'] / df_grouped['total_atendimentos'].replace(0, 1)
        ) * 100
        
        return df_grouped.sort_values(by='Taxa No-Show (%)', ascending=False).reset_index()
    
    except Exception as e:
        print(f"Erro ao gerar relatório: {e}")
        return pd.DataFrame()
    finally:
        session.close()