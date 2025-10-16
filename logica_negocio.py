# logica_negocio.py (VERSÃO COM CORREÇÃO DE FUSO E FILTRO DE DATA NA AGENDA)

from datetime import datetime, timedelta, timezone, date, time
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
    """Gera um PIN numérico de 6 dígitos."""
    return str(random.randint(100000, 999999))

def horario_esta_disponivel(profissional: str, data_hora_local: datetime, id_ignorada: str = None) -> bool:
    """Verifica a disponibilidade de um horário, opcionalmente ignorando um agendamento existente."""
    df = buscar_todos_agendamentos()
    if df.empty:
        return True
    
    conflitos = df[
        (df['profissional'] == profissional) &
        (df['horario'] == data_hora_local) &
        (df['status'] == "Confirmado")
    ]
    
    if id_ignorada and not conflitos.empty:
        conflitos = conflitos[conflitos['id'] != id_ignorada]

    return conflitos.empty

def processar_cancelamento_seguro(pin_code: str) -> bool:
    """Cancela um agendamento a partir do PIN do cliente."""
    agendamento = buscar_agendamento_por_pin(pin_code)
    if agendamento and agendamento['status'] == "Confirmado":
        return atualizar_status_agendamento(agendamento['id'], "Cancelado pelo Cliente")
    return False

def acao_admin_agendamento(agendamento_id: str, acao: str) -> bool:
    """Executa uma ação administrativa em um agendamento."""
    status_map = {"cancelar": "Cancelado (Admin)", "finalizar": "Finalizado", "no-show": "No-Show"}
    return atualizar_status_agendamento(agendamento_id, status_map[acao]) if acao in status_map else False

def processar_remarcacao(pin: str, agendamento_id: str, novo_horario_local: datetime) -> tuple[bool, str]:
    """Processa a lógica de remarcação de um agendamento pelo cliente."""
    agendamento_atual = buscar_agendamento_por_pin(pin)
    if not agendamento_atual:
        return False, "Agendamento original não encontrado."

    if novo_horario_local < datetime.now(TZ_SAO_PAULO):
        return False, "Não é possível agendar para uma data ou hora no passado."

    if not horario_esta_disponivel(agendamento_atual['profissional'], novo_horario_local, id_ignorada=agendamento_id):
        return False, "O novo horário escolhido já está ocupado."

    if atualizar_horario_agendamento(agendamento_id, novo_horario_local):
        return True, "Agendamento remarcado com sucesso!"
    else:
        return False, "Ocorreu um erro ao tentar salvar a remarcação."

def buscar_agendamentos_por_data(data_selecionada: date):
    """Busca todos os agendamentos confirmados para uma data específica (fuso de São Paulo)."""
    # Define o início e o fim do dia selecionado no fuso de São Paulo
    inicio_dia_local = datetime.combine(data_selecionada, time.min).replace(tzinfo=TZ_SAO_PAULO)
    fim_dia_local = datetime.combine(data_selecionada, time.max).replace(tzinfo=TZ_SAO_PAULO)
    
    # Converte os limites para UTC para consultar o banco de dados
    inicio_dia_utc = inicio_dia_local.astimezone(timezone.utc)
    fim_dia_utc = fim_dia_local.astimezone(timezone.utc)
    
    return pd.DataFrame(buscar_agendamentos_por_intervalo(inicio_dia_utc, fim_dia_utc))

def get_relatorio_no_show() -> pd.DataFrame:
    """Gera um relatório de faltas (no-show)."""
    df = buscar_todos_agendamentos()
    if df.empty: return pd.DataFrame()
    
    hoje_local = datetime.now(TZ_SAO_PAULO).date()
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

