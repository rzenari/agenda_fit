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
    adicionar_feriado,
    buscar_agendamentos_por_intervalo
)

TZ_SAO_PAULO = ZoneInfo('America/Sao_Paulo')
DIAS_SEMANA_PT = {0: "Segunda", 1: "Terça", 2: "Quarta", 3: "Quinta", 4: "Sexta", 5: "Sábado", 6: "Domingo"}


def gerar_token_unico():
    """Gera um código PIN numérico de 6 dígitos."""
    return str(random.randint(100000, 999999))

def verificar_disponibilidade_com_duracao(clinic_id: str, profissional_nome: str, data_hora_inicio: datetime, duracao: int, agendamento_id_excluir: str = None):
    """Verifica se um slot de tempo específico está disponível, considerando a duração."""
    from database import buscar_agendamentos_por_data_e_profissional, listar_profissionais, listar_feriados
    
    profissionais = listar_profissionais(clinic_id)
    profissional_data = next((p for p in profissionais if p['nome'] == profissional_nome), None)
    if not profissional_data:
        return False, "Profissional não encontrado."

    horarios_trabalho = profissional_data.get('horario_trabalho', {})
    dias_map = {0: "seg", 1: "ter", 2: "qua", 3: "qui", 4: "sex", 5: "sab", 6: "dom"}
    dia_key = dias_map[data_hora_inicio.weekday()]
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
    
    if agendamento_id_excluir and not agendamentos_existentes.empty:
        agendamentos_existentes = agendamentos_existentes[agendamentos_existentes['id'] != agendamento_id_excluir]

    if not agendamentos_existentes.empty:
        for _, ag in agendamentos_existentes.iterrows():
            if ag['status'] == 'Confirmado':
                dt_inicio_existente = ag['horario']
                # CORREÇÃO: Usar um valor padrão (30) se a duração não estiver presente
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
    Gera uma lista de horários disponíveis verificando cada slot de tempo do dia.
    """
    from database import buscar_agendamentos_por_data_e_profissional, listar_profissionais, listar_feriados

    # 1. Validações iniciais (feriado, profissional, horário de trabalho)
    feriados = listar_feriados(clinic_id)
    if any(f['data'] == data_selecionada for f in feriados):
        return []

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

    try:
        inicio_expediente = datetime.strptime(horario_dia['inicio'], "%H:%M").time()
        fim_expediente = datetime.strptime(horario_dia['fim'], "%H:%M").time()
        inicio_expediente_dt = datetime.combine(data_selecionada, inicio_expediente, tzinfo=TZ_SAO_PAULO)
        fim_expediente_dt = datetime.combine(data_selecionada, fim_expediente, tzinfo=TZ_SAO_PAULO)
    except (ValueError, KeyError):
        return []

    # 2. Mapear todos os blocos ocupados do dia
    agendamentos_existentes_df = buscar_agendamentos_por_data_e_profissional(clinic_id, profissional_nome, data_selecionada)
    if agendamento_id_excluir and not agendamentos_existentes_df.empty:
        agendamentos_existentes_df = agendamentos_existentes_df[agendamentos_existentes_df['id'] != agendamento_id_excluir]

    blocos_ocupados = []
    if not agendamentos_existentes_df.empty:
        df_confirmados = agendamentos_existentes_df[agendamentos_existentes_df['status'] == 'Confirmado']
        for _, ag in df_confirmados.iterrows():
            inicio = ag['horario']
            duracao = int(ag.get('duracao_min', 30))
            fim = inicio + timedelta(minutes=duracao)
            blocos_ocupados.append((inicio, fim))

    # 3. Gerar horários verificando cada slot possível (lógica robusta)
    horarios_disponiveis = []
    intervalo_minimo = 15  # Define a granularidade da busca (ex: 9:00, 9:15, 9:30...)
    slot_candidato = inicio_expediente_dt

    while slot_candidato + timedelta(minutes=duracao_servico) <= fim_expediente_dt:
        fim_slot_candidato = slot_candidato + timedelta(minutes=duracao_servico)
        conflito = False

        # Para cada slot candidato, verifica se ele se sobrepõe a algum agendamento
        for inicio_ocupado, fim_ocupado in blocos_ocupados:
            # Lógica de sobreposição: (InícioA < FimB) E (FimA > InícioB)
            if slot_candidato < fim_ocupado and fim_slot_candidato > inicio_ocupado:
                conflito = True
                break  # Se encontrou conflito, para de verificar este slot

        if not conflito:
            horarios_disponiveis.append(slot_candidato.time())

        slot_candidato += timedelta(minutes=intervalo_minimo)

    horarios_unicos = sorted(list(set(horarios_disponiveis)))

    # 4. Se a data for hoje, remover horários que já passaram
    if data_selecionada == datetime.now(TZ_SAO_PAULO).date():
        hora_atual = datetime.now(TZ_SAO_PAULO).time()
        horarios_futuros = [h for h in horarios_unicos if h >= hora_atual]
        return horarios_futuros
    
    return horarios_unicos


# --- Funções para Visões de Agenda ---
def gerar_visao_semanal(clinic_id: str, profissional_nome: str, start_of_week: date):
    end_of_week = start_of_week + timedelta(days=6)
    df_agendamentos = buscar_agendamentos_por_intervalo(clinic_id, start_of_week, end_of_week)
    
    if df_agendamentos.empty:
        return pd.DataFrame()

    df_prof = df_agendamentos[
        (df_agendamentos['profissional_nome'] == profissional_nome) &
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
    
    # Ordenar colunas pela semana
    dias_ordem = [DIAS_SEMANA_PT[i] for i in range(7)]
    cols_presentes = [col for col in dias_ordem if col in pivot_table.columns]
    return pivot_table[cols_presentes]


def gerar_visao_comparativa(clinic_id: str, data: date, nomes_profissionais: list):
    df_agendamentos = buscar_agendamentos_por_intervalo(clinic_id, data, data)

    if df_agendamentos.empty:
        return pd.DataFrame(index=[], columns=nomes_profissionais).fillna('')
    
    df_dia = df_agendamentos[df_agendamentos['status'] == 'Confirmado'].copy()
    
    if df_dia.empty:
        return pd.DataFrame(index=[], columns=nomes_profissionais).fillna('')

    df_dia['hora'] = df_dia['horario'].dt.strftime('%H:%M')
    
    pivot = df_dia.pivot_table(
        index='hora',
        columns='profissional_nome',
        values='cliente',
        aggfunc='first'
    ).fillna('')

    # Adicionar profissionais sem agendamentos como colunas vazias
    for prof in nomes_profissionais:
        if prof not in pivot.columns:
            pivot[prof] = ''
            
    return pivot[nomes_profissionais]

