# logica_negocio.py (VERSÃO MULTI-CLINICA COM HORÁRIOS DINÂMICOS)

import uuid
from datetime import datetime, date, time, timedelta
import pandas as pd
import random 
from zoneinfo import ZoneInfo
import requests # Para buscar feriados

# Importações de funções de DB
from database import (
    atualizar_status_agendamento, 
    buscar_agendamento_por_pin,
    atualizar_horario_agendamento,
    listar_profissionais,
    adicionar_feriado
)

TZ_SAO_PAULO = ZoneInfo('America/Sao_Paulo')
DIAS_SEMANA_PT = {0: "Segunda-feira", 1: "Terça-feira", 2: "Quarta-feira", 3: "Quinta-feira", 4: "Sexta-feira", 5: "Sábado", 6: "Domingo"}


def gerar_token_unico():
    """Gera um código PIN numérico de 6 dígitos."""
    return str(random.randint(100000, 999999))

def horario_esta_disponivel(clinic_id: str, profissional_nome: str, data_hora: datetime):
    from database import buscar_agendamentos_por_data_e_profissional # Importação local para evitar ciclo
    
    # 1. Checar se está dentro do horário de trabalho e se não é feriado
    profissionais = listar_profissionais(clinic_id)
    profissional_data = next((p for p in profissionais if p['nome'] == profissional_nome), None)
    
    if not profissional_data:
        return False, "Profissional não encontrado."

    # Checagem do dia da semana
    horarios_trabalho = profissional_data.get('horario_trabalho', {})
    dias_map = {0: "seg", 1: "ter", 2: "qua", 3: "qui", 4: "sex", 5: "sab", 6: "dom"}
    dia_key = dias_map[data_hora.weekday()]
    horario_dia = horarios_trabalho.get(dia_key)

    if not horario_dia or not horario_dia.get('ativo'):
        dia_semana_nome = DIAS_SEMANA_PT[data_hora.weekday()]
        return False, f"O profissional não trabalha neste dia da semana ({dia_semana_nome})."

    # Checagem do horário de expediente
    try:
        inicio_expediente = datetime.strptime(horario_dia['inicio'], "%H:%M").time()
        fim_expediente = datetime.strptime(horario_dia['fim'], "%H:%M").time()
        if not (inicio_expediente <= data_hora.time() < fim_expediente):
            return False, f"Fora do horário de expediente ({horario_dia['inicio']} - {horario_dia['fim']})."
    except (ValueError, KeyError):
        return False, "Horário de trabalho do profissional não configurado corretamente."

    # 2. Checar se a data é um feriado/folga cadastrado
    from database import listar_feriados
    feriados = listar_feriados(clinic_id)
    if any(f['data'] == data_hora.date() for f in feriados):
        return False, "O dia selecionado é um feriado ou folga."

    # 3. Checar conflitos com outros agendamentos
    agendamentos_existentes = buscar_agendamentos_por_data_e_profissional(clinic_id, profissional_nome, data_hora.date())
    
    conflito = any(
        ag['horario'].time() == data_hora.time() and ag['status'] == "Confirmado"
        for _, ag in agendamentos_existentes.iterrows()
    )
    
    if conflito:
        return False, "Este horário já está ocupado."
        
    return True, "Horário disponível."


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

def get_relatorio_no_show(clinic_id: str) -> pd.DataFrame:
    from database import buscar_todos_agendamentos_clinica
    df = buscar_todos_agendamentos_clinica(clinic_id)
    if df.empty:
        return pd.DataFrame()
    
    df_passado = df[df['horario'].dt.date <= date.today()].copy()
    if df_passado.empty:
        return pd.DataFrame()

    df_grouped = df_passado.groupby('profissional_nome').agg(
        total_sessoes=('status', 'size'),
        faltas=('status', lambda x: (x == 'No-Show').sum()),
        cancelados_cliente=('status', lambda x: (x == 'Cancelado pelo Cliente').sum()),
        finalizados=('status', lambda x: (x == 'Finalizado').sum())
    ).reset_index()

    df_grouped['taxa_no_show_%'] = (
        df_grouped['faltas'] / df_grouped['total_sessoes'].replace(0, 1) * 100
    ).round(2)
    
    return df_grouped

def buscar_agendamentos_por_data(clinic_id: str, data_selecionada: date):
    from database import buscar_todos_agendamentos_clinica
    todos_agendamentos = buscar_todos_agendamentos_clinica(clinic_id)
    if todos_agendamentos.empty:
        return pd.DataFrame()
    
    # Filtra pela data e status diretamente no DataFrame
    filtro = (todos_agendamentos['horario'].dt.date == data_selecionada) & (todos_agendamentos['status'] == 'Confirmado')
    agendamentos_do_dia = todos_agendamentos[filtro]
    
    return agendamentos_do_dia.sort_values(by='horario')

def processar_remarcacao(pin: str, agendamento_id: str, profissional_nome: str, novo_horario: datetime):
    agendamento_atual = buscar_agendamento_por_pin(pin)
    if not agendamento_atual:
        return False, "Agendamento original não encontrado."

    clinic_id = agendamento_atual['clinic_id']
    
    disponivel, msg = horario_esta_disponivel(clinic_id, profissional_nome, novo_horario)
    if not disponivel:
        return False, f"Não foi possível remarcar: {msg}"
    
    if atualizar_horario_agendamento(agendamento_id, novo_horario):
        return True, "Agendamento remarcado com sucesso!"
    else:
        return False, "Ocorreu um erro ao tentar remarcar no banco de dados."

def importar_feriados_nacionais(clinic_id: str, ano: int):
    try:
        response = requests.get(f"https://brasilapi.com.br/api/feriados/v1/{ano}")
        response.raise_for_status()
        feriados_api = response.json()
        
        count = 0
        for feriado in feriados_api:
            data_feriado = datetime.strptime(feriado['date'], "%Y-%m-%d").date()
            if adicionar_feriado(clinic_id, data_feriado, feriado['name']):
                count += 1
        return count
    except requests.RequestException as e:
        print(f"Erro ao buscar feriados da API: {e}")
        return 0

def gerar_horarios_disponiveis(clinic_id: str, profissional_nome: str, data_selecionada: date):
    """
    Gera uma lista de horários (objetos time) disponíveis para um profissional em uma data.
    Considera o horário de trabalho, feriados e agendamentos existentes.
    """
    from database import buscar_agendamentos_por_data_e_profissional, listar_profissionais, listar_feriados

    # 1. Checar se a data é um feriado/folga
    feriados = listar_feriados(clinic_id)
    if any(f['data'] == data_selecionada for f in feriados):
        return []

    # 2. Obter horário de trabalho do profissional
    profissionais = listar_profissionais(clinic_id)
    profissional_data = next((p for p in profissionais if p['nome'] == profissional_nome), None)
    if not profissional_data:
        return []

    horarios_trabalho = profissional_data.get('horario_trabalho', {})
    dias_map = {0: "seg", 1: "ter", 2: "qua", 3: "qui", 4: "sex", 5: "sab", 6: "dom"}
    dia_key = dias_map[data_selecionada.weekday()]
    horario_dia = horarios_trabalho.get(dia_key)

    if not horario_dia or not horario_dia.get('ativo'):
        return []

    # 3. Gerar todos os slots de 30 minutos do dia
    try:
        inicio_expediente = datetime.strptime(horario_dia['inicio'], "%H:%M")
        fim_expediente = datetime.strptime(horario_dia['fim'], "%H:%M")
    except (ValueError, KeyError):
        return []

    horarios_possiveis = []
    horario_atual = inicio_expediente
    while horario_atual < fim_expediente:
        horarios_possiveis.append(horario_atual.time())
        horario_atual += timedelta(minutes=30)

    # 4. Obter horários já agendados
    agendamentos_existentes_df = buscar_agendamentos_por_data_e_profissional(clinic_id, profissional_nome, data_selecionada)
    if not agendamentos_existentes_df.empty:
        horarios_ocupados = {ag['horario'].time() for _, ag in agendamentos_existentes_df.iterrows() if ag['status'] == 'Confirmado'}
    else:
        horarios_ocupados = set()

    # 5. Filtrar e retornar apenas os horários disponíveis
    horarios_disponiveis = [h for h in horarios_possiveis if h not in horarios_ocupados]
    
    return horarios_disponiveis

