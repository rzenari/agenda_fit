# logica_negocio.py (Com Gerador de PIN)

import uuid
from datetime import datetime, date
import pandas as pd
import random # Novo import para gerar o PIN

# Importações de funções de DB
from database import buscar_todos_agendamentos, atualizar_status_agendamento, buscar_agendamento_por_pin as buscar_agendamento_por_token, buscar_agendamento_por_id

def gerar_token_unico():
    """NOVA FUNÇÃO: Gera um código PIN numérico de 6 dígitos."""
    return str(random.randint(100000, 999999))

def horario_esta_disponivel(profissional: str, data_hora: datetime) -> bool:
    # [Função de bloqueio de horário omitida, permanece a mesma]
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
    """Cancela o agendamento apenas se o PIN for válido e o status for 'Confirmado'."""
    
    agendamento = buscar_agendamento_por_pin(pin_code)
    
    if agendamento and agendamento['status'] == "Confirmado":
        # Chama a função de atualização do DB usando o ID real do agendamento
        atualizar_status_agendamento(agendamento['id'], "Cancelado pelo Cliente")
        return True
        
    return False

# NOVAS FUNÇÕES PARA O ADMIN
def acao_admin_agendamento(agendamento_id: int, acao: str) -> bool:
    """Executa ações rápidas (Finalizar/Cancelar/No-Show) pelo painel Admin."""
    
    status_map = {
        "cancelar": "Cancelado (Admin)",
        "finalizar": "Finalizado",
        "no-show": "No-Show",
    }
    novo_status = status_map.get(acao)
    
    if novo_status:
        # Chama a função de atualização do DB usando o ID
        atualizar_status_agendamento(agendamento_id, novo_status)
        return True
    return False


def get_relatorio_no_show():
    # [Função de relatório omitida, permanece a mesma]
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
    # [Função de busca de hoje omitida, permanece a mesma]
    df = buscar_todos_agendamentos()
    if df.empty:
        return pd.DataFrame()
        
    hoje = datetime.now().date()
    df_hoje = df[
        (df['horario'].dt.date == hoje) & 
        (df['status'] == 'Confirmado')
    ]
    return df_hoje.sort_values(by='horario')

