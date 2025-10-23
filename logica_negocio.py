# logica_negocio.py (VERSÃO COM LÓGICA DE TURMAS)
# Nenhuma alteração foi necessária neste arquivo para as solicitações.

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
    adicionar_feriado,
    buscar_agendamentos_por_intervalo,
    # Funções para turmas
    contar_agendamentos_turma_dia
)

TZ_SAO_PAULO = ZoneInfo('America/Sao_Paulo')
DIAS_SEMANA_PT = {0: "Segunda", 1: "Terça", 2: "Quarta", 3: "Quinta", 4: "Sexta", 5: "Sábado", 6: "Domingo"}
DIAS_MAP_WEEKDAY_TO_KEY = {0: "seg", 1: "ter", 2: "qua", 3: "qui", 4: "sex", 5: "sab", 6: "dom"}

def gerar_token_unico():
    """Gera um código PIN numérico de 6 dígitos."""
    return str(random.randint(100000, 999999))

def verificar_disponibilidade_com_duracao(clinic_id: str, profissional_nome: str, data_hora_inicio: datetime, duracao: int, agendamento_id_excluir: str = None):
    """Verifica se um slot de tempo específico está disponível para agendamento INDIVIDUAL."""
    from database import buscar_agendamentos_por_data_e_profissional, listar_profissionais, listar_feriados
    
    profissionais = listar_profissionais(clinic_id)
    profissional_data = next((p for p in profissionais if p['nome'] == profissional_nome), None)
    if not profissional_data:
        return False, "Profissional não encontrado."

    horarios_trabalho = profissional_data.get('horario_trabalho', {})
    dia_key = DIAS_MAP_WEEKDAY_TO_KEY[data_hora_inicio.weekday()]
    horario_dia = horarios_trabalho.get(dia_key)

    if not horario_dia or not horario_dia.get('ativo'):
        dia_semana_nome = DIAS_SEMANA_PT.get(data_hora_inicio.weekday(), '')
        return False, f"O profissional não trabalha neste dia da semana ({dia_semana_nome})."

    try:
        inicio_expediente = datetime.strptime(horario_dia['inicio'], "%H:%M").time()
        fim_expediente = datetime.strptime(horario_dia['fim'], "%H:%M").time()
        
        dt_inicio_novo = data_hora_inicio
        dt_fim_novo = dt_inicio_novo + timedelta(minutes=duracao)

        if not (inicio_expediente <= dt_inicio_novo.time() and dt_fim_novo.time() <= fim_expediente):
            return False, f"Fora do horário de expediente ({horario_dia['inicio']} - {horario_dia['fim']})."
    except (ValueError, KeyError):
        return False, "Horário de trabalho do profissional não configurado corretamente."

    feriados = listar_feriados(clinic_id)
    if any(f['data'] == data_hora_inicio.date() for f in feriados):
        return False, "O dia selecionado é um feriado ou folga."

    agendamentos_existentes = buscar_agendamentos_por_data_e_profissional(clinic_id, profissional_nome, data_hora_inicio.date())
    
    # CORREÇÃO: Verifica se a coluna 'turma_id' existe antes de filtrar.
    # Se não existir, todos os agendamentos são considerados individuais.
    if agendamentos_existentes.empty or 'turma_id' not in agendamentos_existentes.columns:
        agendamentos_individuais = agendamentos_existentes.copy()
    else:
        agendamentos_individuais = agendamentos_existentes[agendamentos_existentes['turma_id'].isnull()]

    if agendamento_id_excluir and not agendamentos_individuais.empty:
        agendamentos_individuais = agendamentos_individuais[agendamentos_individuais['id'] != agendamento_id_excluir]

    if not agendamentos_individuais.empty:
        for _, ag in agendamentos_individuais.iterrows():
            if ag['status'] == 'Confirmado':
                dt_inicio_existente = ag['horario']
                duracao_existente = int(ag.get('duracao_min', 30))
                dt_fim_existente = dt_inicio_existente + timedelta(minutes=duracao_existente)
                
                if data_hora_inicio < dt_fim_existente and dt_inicio_existente < dt_fim_novo:
                    return False, f"Conflito com agendamento das {dt_inicio_existente.strftime('%H:%M')}."

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

def get_dados_dashboard(clinic_id: str, start_date: date, end_date: date) -> pd.DataFrame:
    """Busca e prepara os dados para o dashboard."""
    df = buscar_agendamentos_por_intervalo(clinic_id, start_date, end_date)
    if df.empty:
        return pd.DataFrame()
    return df

def buscar_agendamentos_por_data(clinic_id: str, data_selecionada: date):
    """Busca agendamentos para uma data específica, de todos os profissionais."""
    todos_agendamentos = buscar_agendamentos_por_intervalo(clinic_id, data_selecionada, data_selecionada)
    if todos_agendamentos.empty:
        return pd.DataFrame()
    
    filtro = (todos_agendamentos['horario'].dt.date == data_selecionada) & (todos_agendamentos['status'] == 'Confirmado')
    agendamentos_do_dia = todos_agendamentos[filtro]
    
    return agendamentos_do_dia.sort_values(by='horario')

def processar_remarcacao(pin: str, agendamento_id: str, profissional_nome: str, novo_horario: datetime):
    agendamento_atual = buscar_agendamento_por_pin(pin)
    if not agendamento_atual:
        return False, "Agendamento original não encontrado."

    clinic_id = agendamento_atual['clinic_id']
    duracao = agendamento_atual.get('duracao_min', 30)
    
    disponivel, msg = verificar_disponibilidade_com_duracao(
        clinic_id, 
        profissional_nome, 
        novo_horario, 
        duracao,
        agendamento_id_excluir=agendamento_id
    )
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

def gerar_horarios_disponiveis(clinic_id: str, profissional_nome: str, data_selecionada: date, duracao_servico: int, agendamento_id_excluir: str = None):
    """
    Gera uma lista de horários disponíveis para atendimentos individuais.
    """
    from database import buscar_agendamentos_por_data_e_profissional, listar_profissionais, listar_feriados

    feriados = listar_feriados(clinic_id)
    if any(f['data'] == data_selecionada for f in feriados):
        return []

    profissionais = listar_profissionais(clinic_id)
    profissional_data = next((p for p in profissionais if p['nome'] == profissional_nome), None)
    if not profissional_data:
        return []

    horarios_trabalho = profissional_data.get('horario_trabalho', {})
    dia_key = DIAS_MAP_WEEKDAY_TO_KEY[data_selecionada.weekday()]
    horario_dia = horarios_trabalho.get(dia_key)

    if not horario_dia or not horario_dia.get('ativo'):
        return []

    try:
        inicio_expediente = datetime.strptime(horario_dia['inicio'], "%H:%M").time()
        fim_expediente = datetime.strptime(horario_dia['fim'], "%H:%M").time()
        inicio_expediente_dt = datetime.combine(data_selecionada, inicio_expediente, tzinfo=TZ_SAO_PAULO)
        fim_expediente_dt = datetime.combine(data_selecionada, fim_expediente, tzinfo=TZ_SAO_PAULO)
    except (ValueError, KeyError):
        return []

    agendamentos_existentes_df = buscar_agendamentos_por_data_e_profissional(clinic_id, profissional_nome, data_selecionada)
    
    # CORREÇÃO: Verifica se a coluna 'turma_id' existe antes de filtrar.
    # Se não existir, todos os agendamentos são considerados individuais.
    if agendamentos_existentes_df.empty or 'turma_id' not in agendamentos_existentes_df.columns:
        agendamentos_individuais_df = agendamentos_existentes_df.copy()
    else:
        agendamentos_individuais_df = agendamentos_existentes_df[agendamentos_existentes_df['turma_id'].isnull()]
    
    if agendamento_id_excluir and not agendamentos_individuais_df.empty:
        agendamentos_individuais_df = agendamentos_individuais_df[agendamentos_individuais_df['id'] != agendamento_id_excluir]

    blocos_ocupados = []
    if not agendamentos_individuais_df.empty:
        df_confirmados = agendamentos_individuais_df[agendamentos_individuais_df['status'] == 'Confirmado']
        for _, ag in df_confirmados.iterrows():
            inicio = ag['horario']
            duracao = int(ag.get('duracao_min', 30))
            fim = inicio + timedelta(minutes=duracao)
            blocos_ocupados.append((inicio, fim))

    horarios_disponiveis = []
    intervalo_minimo = 15
    slot_candidato = inicio_expediente_dt

    while slot_candidato + timedelta(minutes=duracao_servico) <= fim_expediente_dt:
        fim_slot_candidato = slot_candidato + timedelta(minutes=duracao_servico)
        conflito = False
        for inicio_ocupado, fim_ocupado in blocos_ocupados:
            if slot_candidato < fim_ocupado and fim_slot_candidato > inicio_ocupado:
                conflito = True
                break
        
        if not conflito:
            horarios_disponiveis.append(slot_candidato.time())
        
        slot_candidato += timedelta(minutes=intervalo_minimo)

    horarios_unicos = sorted(list(set(horarios_disponiveis)))
    
    if data_selecionada == datetime.now(TZ_SAO_PAULO).date():
        hora_atual = datetime.now(TZ_SAO_PAULO).time()
        horarios_futuros = [h for h in horarios_unicos if h >= hora_atual]
        return horarios_futuros
    
    return horarios_unicos

def gerar_turmas_disponiveis(clinic_id: str, data_selecionada: date, turmas_clinica: list):
    """
    Verifica as turmas do dia e retorna uma lista com as vagas disponíveis.
    """
    from database import listar_feriados
    
    feriados = listar_feriados(clinic_id)
    if any(f['data'] == data_selecionada for f in feriados):
        return []
    
    dia_semana_key = DIAS_MAP_WEEKDAY_TO_KEY.get(data_selecionada.weekday())
    if not dia_semana_key:
        return []

    turmas_do_dia = [t for t in turmas_clinica if dia_semana_key in t.get('dias_semana', [])]
    
    turmas_disponiveis = []
    for turma in turmas_do_dia:
        horario_obj = datetime.strptime(turma['horario'], '%H:%M').time()
        
        # Se for hoje, só mostra turmas futuras
        if data_selecionada == datetime.now(TZ_SAO_PAULO).date():
            if horario_obj <= datetime.now(TZ_SAO_PAULO).time():
                continue

        vagas_ocupadas = contar_agendamentos_turma_dia(clinic_id, turma['id'], data_selecionada)
        capacidade = turma.get('capacidade_maxima', 0)
        vagas_disponiveis = capacidade - vagas_ocupadas
        
        if vagas_disponiveis > 0:
            turma_info = turma.copy()
            turma_info['vagas_ocupadas'] = vagas_ocupadas
            turma_info['vagas_disponiveis'] = vagas_disponiveis
            turma_info['horario_str'] = turma['horario']
            turma_info['horario_obj'] = horario_obj
            turmas_disponiveis.append(turma_info)
            
    return sorted(turmas_disponiveis, key=lambda t: t['horario_obj'])

# --- Funções para Visões de Agenda ---
def gerar_visao_semanal(clinic_id: str, profissional_nome: str, start_of_week: date):
    end_of_week = start_of_week + timedelta(days=6)
    df_agendamentos = buscar_agendamentos_por_intervalo(clinic_id, start_of_week, end_of_week)
    
    if df_agendamentos.empty:
        return pd.DataFrame()

    df_prof = df_agendamentos[
        (df_agendamentos['profissional_nome'] == profissional_nome) &
        (df_agendamentos['turma_id'].isnull()) & # Apenas agendamentos individuais
        (df_agendamentos['status'] == 'Confirmado')
    ].copy()
    
    if df_prof.empty:
        return pd.DataFrame()
        
    df_prof['hora'] = df_prof['horario'].dt.strftime('%H:%M')
    df_prof['dia_semana'] = df_prof['horario'].dt.weekday.map(DIAS_SEMANA_PT)
    
    pivot_table = df_prof.pivot_table(
        index='hora', 
        columns='dia_semana', 
        values='cliente', 
        aggfunc='first'
    ).fillna('')
    
    dias_ordem = [DIAS_SEMANA_PT[i] for i in range(7)]
    cols_presentes = [col for col in dias_ordem if col in pivot_table.columns]
    return pivot_table[cols_presentes]

def gerar_visao_comparativa(clinic_id: str, data: date, nomes_profissionais: list):
    df_agendamentos = buscar_agendamentos_por_intervalo(clinic_id, data, data)

    if df_agendamentos.empty:
        return pd.DataFrame(index=[], columns=nomes_profissionais).fillna('')
    
    df_dia = df_agendamentos[
        (df_agendamentos['status'] == 'Confirmado') &
        (df_agendamentos['turma_id'].isnull()) # Apenas individuais
    ].copy()

    if df_dia.empty:
        return pd.DataFrame(index=[], columns=nomes_profissionais).fillna('')

    df_dia['hora'] = df_dia['horario'].dt.strftime('%H:%M')
    
    pivot = df_dia.pivot_table(
        index='hora',
        columns='profissional_nome',
        values='cliente',
        aggfunc='first'
    ).fillna('')

    for prof in nomes_profissionais:
        if prof not in pivot.columns:
            pivot[prof] = ''
            
    return pivot[nomes_profissionais]
