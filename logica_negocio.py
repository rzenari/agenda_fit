# logica_negocio.py (VERSÃO COM LÓGICA DE REMARCAÇÃO)

from datetime import datetime, timedelta, timezone, date
import pandas as pd
import random
from zoneinfo import ZoneInfo

from database import (
    buscar_todos_agendamentos, atualizar_status_agendamento,
    buscar_agendamento_por_pin, buscar_agendamentos_por_intervalo,
    atualizar_horario_agendamento
)

TZ_SAO_PAULO = ZoneInfo('America/Sao_Paulo')

def gerar_token_unico():
    return str(random.randint(100000, 999999))

def horario_esta_disponivel(profissional: str, data_hora_local: datetime, id_ignorada: str = None) -> bool:
    """Verifica a disponibilidade, opcionalmente ignorando um agendamento existente (para remarcação)."""
    df = buscar_todos_agendamentos()
    if df.empty:
        return True
    
    # Filtra por profissional, horário e status
    conflitos = df[
        (df['profissional'] == profissional) &
        (df['horario'] == data_hora_local) &
        (df['status'] == "Confirmado")
    ]
    
    # Se estamos remarcando, remove o próprio agendamento da checagem de conflito
    if id_ignorada and not conflitos.empty:
        conflitos = conflitos[conflitos['id'] != id_ignorada]

    return conflitos.empty

def processar_cancelamento_seguro(pin_code: str) -> bool:
    agendamento = buscar_agendamento_por_pin(pin_code)
    if agendamento and agendamento['status'] == "Confirmado":
        return atualizar_status_agendamento(agendamento['id'], "Cancelado pelo Cliente")
    return False

def acao_admin_agendamento(agendamento_id: str, acao: str) -> bool:
    status_map = {"cancelar": "Cancelado (Admin)", "finalizar": "Finalizado", "no-show": "No-Show"}
    return atualizar_status_agendamento(agendamento_id, status_map[acao]) if acao in status_map else False

def processar_remarcacao(pin: str, agendamento_id: str, novo_horario_local: datetime) -> tuple[bool, str]:
    """Processa a lógica de remarcação de um agendamento."""
    agendamento_atual = buscar_agendamento_por_pin(pin)
    if not agendamento_atual:
        return False, "Agendamento original não encontrado."

    profissional = agendamento_atual['profissional']
    
    if novo_horario_local < datetime.now(TZ_SAO_PAULO):
        return False, "Não é possível agendar para uma data ou hora no passado."

    if not horario_esta_disponivel(profissional, novo_horario_local, id_ignorada=agendamento_id):
        return False, "O novo horário escolhido já está ocupado."

    if atualizar_horario_agendamento(agendamento_id, novo_horario_local):
        return True, "Agendamento remarcado com sucesso!"
    else:
        return False, "Ocorreu um erro ao tentar salvar a remarcação."

def buscar_agendamentos_hoje():
    agora_local = datetime.now(TZ_SAO_PAULO)
    inicio_dia_local = agora_local.replace(hour=0, minute=0, second=0, microsecond=0)
    fim_dia_local = inicio_dia_local + timedelta(days=1)
    
    inicio_dia_utc = inicio_dia_local.astimezone(timezone.utc)
    fim_dia_utc = fim_dia_local.astimezone(timezone.utc)
    
    return pd.DataFrame(buscar_agendamentos_por_intervalo(inicio_dia_utc, fim_dia_utc))

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

