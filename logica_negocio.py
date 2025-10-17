# logica_negocio.py (VERSÃO MULTI-CLINICA COM GESTÃO DE HORÁRIOS E FERIADOS)

from datetime import datetime, timedelta, timezone, date, time
import pandas as pd
import random
from zoneinfo import ZoneInfo
import requests

from database import (
    buscar_todos_agendamentos, atualizar_status_agendamento,
    buscar_agendamento_por_pin, atualizar_horario_agendamento,
    listar_profissionais, listar_feriados, adicionar_feriado
)

TZ_SAO_PAULO = ZoneInfo('America/Sao_Paulo')
DIAS_SEMANA_MAP = {0: "seg", 1: "ter", 2: "qua", 3: "qui", 4: "sex", 5: "sab", 6: "dom"}
DIAS_SEMANA_PT = {0: "Segunda-feira", 1: "Terça-feira", 2: "Quarta-feira", 3: "Quinta-feira", 4: "Sexta-feira", 5: "Sábado", 6: "Domingo"}


def gerar_token_unico():
    """Gera um PIN numérico de 6 dígitos."""
    return str(random.randint(100000, 999999))

def horario_esta_disponivel(clinic_id: str, profissional_nome: str, data_hora_local: datetime, id_ignorada: str = None) -> tuple[bool, str]:
    """
    Verifica a disponibilidade de um horário, considerando o expediente do profissional,
    feriados e outros agendamentos.
    """
    # 1. Verificar se o horário é no passado
    if data_hora_local < datetime.now(TZ_SAO_PAULO):
        return False, "Não é possível agendar em datas ou horários passados."

    # 2. Verificar dia de trabalho e expediente do profissional
    profissionais = listar_profissionais(clinic_id)
    prof_selecionado = next((p for p in profissionais if p['nome'] == profissional_nome), None)
    
    if not prof_selecionado or 'horario_trabalho' not in prof_selecionado:
        return False, "Não foi possível encontrar a configuração de horários para este profissional."

    dia_semana_key = DIAS_SEMANA_MAP[data_hora_local.weekday()]
    expediente_dia = prof_selecionado['horario_trabalho'].get(dia_semana_key)

    if not expediente_dia or not expediente_dia.get('ativo'):
        dia_pt = DIAS_SEMANA_PT[data_hora_local.weekday()]
        return False, f"O profissional não trabalha neste dia da semana ({dia_pt})."
    
    hora_inicio = datetime.strptime(expediente_dia['inicio'], "%H:%M").time()
    hora_fim = datetime.strptime(expediente_dia['fim'], "%H:%M").time()

    if not (hora_inicio <= data_hora_local.time() < hora_fim):
        return False, f"O horário selecionado está fora do expediente do profissional ({hora_inicio.strftime('%H:%M')} - {hora_fim.strftime('%H:%M')})."

    # 3. Verificar Feriados e Folgas
    feriados = listar_feriados(clinic_id)
    datas_feriados = [f['data'] for f in feriados]
    if data_hora_local.date() in datas_feriados:
        return False, "Não é possível agendar em um feriado ou dia de folga configurado."

    # 4. Verificar conflitos com outros agendamentos (lógica existente)
    df = buscar_todos_agendamentos(clinic_id)
    if not df.empty:
        df['horario'] = pd.to_datetime(df['horario']).dt.tz_convert(TZ_SAO_PAULO)
        conflitos = df[
            (df['profissional_nome'] == profissional_nome) &
            (df['horario'] == data_hora_local) &
            (df['status'] == "Confirmado")
        ]
        if id_ignorada and not conflitos.empty:
            conflitos = conflitos[conflitos['id'] != id_ignorada]
        
        if not conflitos.empty:
            return False, "Este horário já está ocupado por outro agendamento."

    return True, "Horário disponível."

def importar_feriados_nacionais(clinic_id: str, ano: int) -> int:
    """Busca feriados nacionais em uma API e salva no DB para a clínica."""
    try:
        response = requests.get(f"https://brasilapi.com.br/api/feriados/v1/{ano}")
        if response.status_code == 200:
            feriados_api = response.json()
            feriados_atuais = listar_feriados(clinic_id)
            datas_atuais = [f['data'] for f in feriados_atuais]
            count = 0
            for feriado in feriados_api:
                data_feriado = datetime.strptime(feriado['date'], "%Y-%m-%d").date()
                if data_feriado not in datas_atuais:
                    adicionar_feriado(clinic_id, data_feriado, f"Feriado Nacional - {feriado['name']}")
                    count += 1
            return count
    except Exception as e:
        print(f"Erro ao importar feriados: {e}")
    return 0

# --- Funções de Processamento (maioria sem alterações) ---

def processar_cancelamento_seguro(pin_code: str) -> bool:
    agendamento = buscar_agendamento_por_pin(pin_code)
    if agendamento and agendamento['status'] == "Confirmado":
        return atualizar_status_agendamento(agendamento['id'], "Cancelado pelo Cliente")
    return False

def acao_admin_agendamento(agendamento_id: str, acao: str) -> bool:
    status_map = {"cancelar": "Cancelado (Admin)", "finalizar": "Finalizado", "no-show": "No-Show"}
    return atualizar_status_agendamento(agendamento_id, status_map.get(acao)) if acao in status_map else False

def processar_remarcacao(pin: str, agendamento_id: str, profissional_nome: str, novo_horario_local: datetime) -> tuple[bool, str]:
    agendamento_atual = buscar_agendamento_por_pin(pin)
    if not agendamento_atual:
        return False, "Agendamento original não encontrado."
    
    clinic_id = agendamento_atual['clinic_id']
    
    disponivel, msg = horario_esta_disponivel(clinic_id, profissional_nome, novo_horario_local, id_ignorada=agendamento_id)
    if not disponivel:
        return False, msg

    if atualizar_horario_agendamento(agendamento_id, novo_horario_local):
        return True, "Agendamento remarcado com sucesso!"
    else:
        return False, "Ocorreu um erro ao tentar salvar a remarcação."

def buscar_agendamentos_por_data(clinic_id: str, data_selecionada: date):
    df_total = buscar_todos_agendamentos(clinic_id)
    if df_total.empty: return pd.DataFrame()
    df_total['horario'] = pd.to_datetime(df_total['horario']).dt.tz_convert(TZ_SAO_PAULO)
    df_filtrado = df_total[
        (df_total['horario'].dt.date == data_selecionada) &
        (df_total['status'] == 'Confirmado')
    ]
    if not df_filtrado.empty:
        df_filtrado = df_filtrado.sort_values(by='horario')
    return df_filtrado

def get_relatorio_no_show(clinic_id: str) -> pd.DataFrame:
    df = buscar_todos_agendamentos(clinic_id)
    if df.empty: return pd.DataFrame()
    hoje_local = datetime.now(TZ_SAO_PAULO).date()
    df['horario_date'] = df['horario'].dt.date
    df_passado = df[df['horario_date'] <= hoje_local].copy()
    if df_passado.empty: return pd.DataFrame()
    df_grouped = df_passado.groupby('profissional_nome').agg(
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

