# logica_negocio.py (MODIFICAÇÃO TEMPORÁRIA DE DEBUG)

import uuid
from datetime import datetime, date, time, timedelta
import pandas as pd
import random 

# Importações de funções de DB
from database import buscar_todos_agendamentos, atualizar_status_agendamento, buscar_agendamento_por_pin, buscar_agendamento_por_id, buscar_agendamentos_por_intervalo

def gerar_token_unico():
    """Gera um código PIN numérico de 6 dígitos."""
    return str(random.randint(100000, 999999))

def horario_esta_disponivel(profissional: str, data_hora: datetime) -> bool:
# [Código omitido, permanece o mesmo]
    df = buscar_todos_agendamentos()
    if df.empty:
        return True
    
    data_hora_naive = data_hora.replace(tzinfo=None)
        
    conflito = df[
        (df['profissional'] == profissional) &
        (df['horario'] == data_hora_naive) & 
        (df['status'].isin(["Confirmado", "Em Andamento"]))
    ]
    
    return conflito.empty

def processar_cancelamento_seguro(pin_code: str) -> bool:
# [Código omitido, permanece o mesmo]
    agendamento = buscar_agendamento_por_pin(pin_code)
    
    if agendamento and agendamento['status'] == "Confirmado":
        atualizar_status_agendamento(agendamento['id'], "Cancelado pelo Cliente")
        return True
        
    return False

def acao_admin_agendamento(agendamento_id: str, acao: str) -> bool:
# [Código omitido, permanece o mesmo]
    status_map = {
        "cancelar": "Cancelado (Admin)",
        "finalizar": "Finalizado",
        "no-show": "No-Show",
    }
    novo_status = status_map.get(acao)
    
    if novo_status:
        atualizar_status_agendamento(agendamento_id, novo_status)
        return True
    return False

def get_relatorio_no_show() -> pd.DataFrame:
# [Código omitido, permanece o mesmo]
    df = buscar_todos_agendamentos()
    
    if df.empty:
        return pd.DataFrame()
    
    df['horario_date'] = df['horario'].dt.date
    df = df[
        df['horario_date'] <= date.today()
    ]
    
    df_grouped = df.groupby('profissional').agg(
        total_atendimentos=('status', 'size'),
        total_faltas=('status', lambda x: (x == 'No-Show').sum()),
        total_cancelados=('status', lambda x: (x == 'Cancelado pelo Cliente').sum()),
        total_finalizados=('status', lambda x: (x == 'Finalizado').sum())
    )
    
    df_grouped['Taxa No-Show (%)'] = (
        df_grouped['total_faltas'] / df_grouped['total_atendimentos'].replace(0, 1)
    ) * 100
    
    return df_grouped.sort_values(by='Taxa No-Show (%)', ascending=False).reset_index()

def buscar_agendamentos_hoje():
    """
    ***MUDANÇA TEMPORÁRIA PARA DEBUG***
    Retorna TODOS os agendamentos para isolar o problema de filtro de data.
    """
    return buscar_todos_agendamentos()
