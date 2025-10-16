# logica_negocio.py (VERSÃO FINAL COM CORREÇÃO DE FUSO HORÁRIO)

import uuid
from datetime import datetime, date, time, timedelta
import pandas as pd
import random 
import pytz # Importa a biblioteca de fuso horário

# Importações de funções de DB
from database import (
    buscar_todos_agendamentos, atualizar_status_agendamento, 
    buscar_agendamento_por_pin, buscar_agendamento_por_id, 
    buscar_agendamentos_por_intervalo
)

# Define o fuso horário padrão para São Paulo
TZ_SAO_PAULO = pytz.timezone('America/Sao_Paulo')

def gerar_token_unico():
    """Gera um código PIN numérico de 6 dígitos."""
    return str(random.randint(100000, 999999))

def horario_esta_disponivel(profissional: str, data_hora_local: datetime) -> bool:
    """Verifica a disponibilidade de um horário, considerando o fuso horário."""
    df = buscar_todos_agendamentos()
    if df.empty:
        return True
    
    # Os horários no DataFrame já estão localizados para SP, então a comparação é direta.
    conflito = df[
        (df['profissional'] == profissional) &
        (df['horario'] == data_hora_local) & 
        (df['status'].isin(["Confirmado", "Em Andamento"]))
    ]
    
    return conflito.empty

def processar_cancelamento_seguro(pin_code: str) -> bool:
    agendamento = buscar_agendamento_por_pin(pin_code)
    if agendamento and agendamento['status'] == "Confirmado":
        return atualizar_status_agendamento(agendamento['id'], "Cancelado pelo Cliente")
    return False

def acao_admin_agendamento(agendamento_id: str, acao: str) -> bool:
    status_map = {
        "cancelar": "Cancelado (Admin)",
        "finalizar": "Finalizado",
        "no-show": "No-Show",
    }
    novo_status = status_map.get(acao)
    if novo_status:
        return atualizar_status_agendamento(agendamento_id, novo_status)
    return False

def get_relatorio_no_show() -> pd.DataFrame:
    df = buscar_todos_agendamentos()
    if df.empty:
        return pd.DataFrame()
    
    # Compara a data do agendamento com a data atual no fuso correto
    hoje_local = date.today()
    df['horario_date'] = df['horario'].dt.date
    df = df[df['horario_date'] <= hoje_local]
    
    df_grouped = df.groupby('profissional').agg(
        total_atendimentos=('status', 'size'),
        total_faltas=('status', lambda x: (x == 'No-Show').sum()),
        total_cancelados=('status', lambda x: (x.str.contains('Cancelado', na=False)).sum()),
        total_finalizados=('status', lambda x: (x == 'Finalizado').sum())
    )
    
    df_grouped['Taxa No-Show (%)'] = (
        df_grouped['total_faltas'] / df_grouped['total_atendimentos'].replace(0, 1)
    ) * 100
    
    return df_grouped.sort_values(by='Taxa No-Show (%)', ascending=False).reset_index()

def buscar_agendamentos_hoje():
    """Busca os agendamentos de hoje, calculando o intervalo de data no fuso de São Paulo."""
    
    # Pega a data/hora atual no fuso correto
    agora_local = datetime.now(TZ_SAO_PAULO)
    
    # Define o início e o fim do dia de HOJE no fuso de São Paulo
    inicio_dia_local = agora_local.replace(hour=0, minute=0, second=0, microsecond=0)
    fim_dia_local = inicio_dia_local + timedelta(days=1)
    
    # Converte o intervalo para UTC para fazer a query no Firestore
    inicio_dia_utc = inicio_dia_local.astimezone(pytz.utc)
    fim_dia_utc = fim_dia_local.astimezone(pytz.utc)
    
    return buscar_agendamentos_por_intervalo(inicio_dia_utc, fim_dia_utc)

