# logica_negocio.py (VERSÃO COM LÓGICA DE REMARCAÇÃO)

from datetime import datetime, timedelta, timezone
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

def processar_remarcacao(pin: str, agendamento_id: str, novo_horario_local: datetime) -> (bool, str):
    """Processa a lógica de remarcação de um agendamento."""
    agendamento_atual = buscar_agendamento_por_pin(pin)
    if not agendamento_atual:
        return False, "Agendamento original não encontrado."

    profissional = agendamento_atual['profissional']
    
    # Verifica se o novo horário está disponível, ignorando o agendamento atual
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

def get_relatorio_no_show():
    # A lógica de relatório pode ser expandida aqui
    return pd.DataFrame()

