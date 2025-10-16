# logica_negocio.py (FINAL)

import uuid
from datetime import datetime, date, time, timedelta # Adicionado 'time' e 'timedelta'
import pandas as pd
import random 

# Importações de funções de DB
from database import buscar_todos_agendamentos, atualizar_status_agendamento, buscar_agendamento_por_pin, buscar_agendamento_por_id, buscar_agendamentos_por_intervalo

def gerar_token_unico():
    """Gera um código PIN numérico de 6 dígitos."""
    return str(random.randint(100000, 999999))

def horario_esta_disponivel(profissional: str, data_hora: datetime) -> bool:
    """Verifica se o horário está livre, consultando o DB (DataFrame)."""
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
        atualizar_status_agendamento(agendamento['id'], "Cancelado pelo Cliente")
        return True
        
    return False

def acao_admin_agendamento(agendamento_id: str, acao: str) -> bool:
    """Executa ações rápidas (Finalizar/Cancelar/No-Show) pelo painel Admin."""
    
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
    """Função Python/Pandas para calcular e retornar a taxa de No-Show por profissional."""
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
    """Busca apenas os agendamentos confirmados para o dia de hoje, usando filtro por intervalo."""
    
    # 1. Define o intervalo de hoje (da 00:00:00 de hoje até 00:00:00 de amanhã)
    hoje_data = datetime.now().date()
    # Cria o objeto datetime naive no fuso local (00:00:00)
    start_of_day = datetime.combine(hoje_data, time.min) 
    end_of_day = start_of_day + timedelta(days=1)
    
    # 2. Chama a busca por intervalo (filtra no Firestore)
    df = buscar_agendamentos_por_intervalo(start_of_day, end_of_day)
    
    if df.empty:
        return pd.DataFrame()
        
    # 3. Filtra apenas os confirmados (se a query do DB não filtrou, fazemos aqui)
    df_hoje = df[df['status'] == 'Confirmado']
    
    return df_hoje.sort_values(by='horario')
