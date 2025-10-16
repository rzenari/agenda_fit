# logica_negocio.py (VERSÃO COM ZONEINFO)

from datetime import datetime, date, time, timedelta, timezone
import pandas as pd
import random
from zoneinfo import ZoneInfo # BIBLIOTECA MODERNA DE FUSO HORÁRIO

# Importações de funções de DB
from database import (
    buscar_todos_agendamentos, atualizar_status_agendamento,
    buscar_agendamento_por_pin, buscar_agendamento_por_id,
    buscar_agendamentos_por_intervalo
)

# Define o fuso horário padrão para São Paulo
TZ_SAO_PAULO = ZoneInfo('America/Sao_Paulo')

def gerar_token_unico():
    """Gera um código PIN numérico de 6 dígitos."""
    return str(random.randint(100000, 999999))

def horario_esta_disponivel(profissional: str, data_hora_local: datetime) -> bool:
    """Verifica a disponibilidade de um horário."""
    df = buscar_todos_agendamentos()
    if df.empty:
        return True

    # Compara diretamente os horários já localizados
    conflito = df[
        (df['profissional'] == profissional) &
        (df['horario'] == data_hora_local) &
        (df['status'].isin(["Confirmado"]))
    ]
    return conflito.empty

def processar_cancelamento_seguro(pin_code: str) -> bool:
    agendamento = buscar_agendamento_por_pin(pin_code)
    if agendamento and agendamento['status'] == "Confirmado":
        return atualizar_status_agendamento(agendamento['id'], "Cancelado pelo Cliente")
    return False

def acao_admin_agendamento(agendamento_id: str, acao: str) -> bool:
    status_map = {
        "cancelar": "Cancelado (Admin)", "finalizar": "Finalizado", "no-show": "No-Show",
    }
    novo_status = status_map.get(acao)
    return atualizar_status_agendamento(agendamento_id, novo_status) if novo_status else False

def get_relatorio_no_show() -> pd.DataFrame:
    df = buscar_todos_agendamentos()
    if df.empty: return pd.DataFrame()
    
    hoje_local = date.today()
    df['horario_date'] = df['horario'].dt.date
    df_passado = df[df['horario_date'] <= hoje_local].copy()

    if df_passado.empty: return pd.DataFrame()

    df_grouped = df_passado.groupby('profissional').agg(
        total_sessoes=('status', 'size'),
        faltas=('status', lambda x: (x == 'No-Show').sum()),
        cancelados=('status', lambda x: (x.str.contains('Cancelado', na=False)).sum()),
        finalizados=('status', lambda x: (x == 'Finalizado').sum())
    ).reset_index()

    if 'total_sessoes' in df_grouped.columns and 'faltas' in df_grouped.columns:
        df_grouped['taxa_no_show_%'] = (
            df_grouped['faltas'] / df_grouped['total_sessoes'].replace(0, 1) * 100
        ).round(2)
    return df_grouped


def buscar_agendamentos_hoje():
    """Busca os agendamentos de hoje, calculando o intervalo no fuso de São Paulo."""
    agora_local = datetime.now(TZ_SAO_PAULO)
    inicio_dia_local = agora_local.replace(hour=0, minute=0, second=0, microsecond=0)
    fim_dia_local = inicio_dia_local + timedelta(days=1)

    # Converte para UTC para a query
    inicio_dia_utc = inicio_dia_local.astimezone(timezone.utc)
    fim_dia_utc = fim_dia_local.astimezone(timezone.utc)

    # Retorna os dados já em formato de DataFrame
    return pd.DataFrame(buscar_agendamentos_por_intervalo(inicio_dia_utc, fim_dia_utc))

