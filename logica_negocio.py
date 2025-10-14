# logica_negocio.py (CORRIGIDO: REMOVIDA IMPORTAÇÃO OBSOLETA)

import uuid
from datetime import datetime, date
from database import buscar_todos_agendamentos, atualizar_status_agendamento, buscar_agendamento_por_token
import pandas as pd
# LINHA ABAIXO REMOVIDA: from sqlalchemy import extract

def gerar_token_unico():
    """Gera um UUID seguro para links de gestão do cliente."""
    return str(uuid.uuid4())

def horario_esta_disponivel(profissional: str, data_hora: datetime) -> bool:
    """Verifica se o horário está livre, consultando o DB (DataFrame)."""
    df = buscar_todos_agendamentos()
    if df.empty:
        return True
        
    # Filtra por profissional, horário exato e status que bloqueiam a agenda
    conflito = df[
        (df['profissional'] == profissional) &
        (df['horario'] == data_hora) &
        (df['status'].isin(["Confirmado", "Em Andamento"]))
    ]
    
    return conflito.empty

def processar_cancelamento_seguro(token: str) -> bool:
    """Cancela o agendamento apenas se o token for válido e o status for 'Confirmado'."""
    
    agendamento = buscar_agendamento_por_token(token)
    
    if agendamento and agendamento['status'] == "Confirmado":
        # Chama a função de atualização do DB
        # O ID é a chave primária da linha no Supabase
        atualizar_status_agendamento(agendamento['id'], "Cancelado pelo Cliente")
        return True
        
    return False

def get_relatorio_no_show() -> pd.DataFrame:
    """
    Função Python/Pandas para calcular e retornar a taxa de No-Show por profissional.
    """
    df = buscar_todos_agendamentos()
    
    if df.empty:
        return pd.DataFrame()
    
    # Adiciona a coluna de data para filtrar sessões que já deveriam ter ocorrido
    df['horario_date'] = df['horario'].dt.date
    df = df[
        df['horario_date'] <= date.today()
    ]
    
    # Agrupa e calcula as métricas
    df_grouped = df.groupby('profissional').agg(
        total_atendimentos=('status', 'size'),
        total_faltas=('status', lambda x: (x == 'No-Show').sum()),
        total_cancelados=('status', lambda x: (x == 'Cancelado pelo Cliente').sum()),
        total_finalizados=('status', lambda x: (x == 'Finalizado').sum())
    )
    
    # Cálculo da Taxa No-Show
    df_grouped['Taxa No-Show (%)'] = (
        df_grouped['total_faltas'] / df_grouped['total_atendimentos'].replace(0, 1)
    ) * 100
    
    return df_grouped.sort_values(by='Taxa No-Show (%)', ascending=False).reset_index()

def buscar_agendamentos_hoje():
    """Busca apenas os agendamentos confirmados para o dia de hoje."""
    df = buscar_todos_agendamentos()
    if df.empty:
        return pd.DataFrame()
        
    hoje = datetime.now().date()
    df_hoje = df[
        (df['horario'].dt.date == hoje) & 
        (df['status'] == 'Confirmado')
    ]
    return df_hoje.sort_values(by='horario')
