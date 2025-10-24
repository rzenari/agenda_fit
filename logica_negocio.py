# logica_negocio.py (VERSÃO COM LÓGICA DE TURMAS E PACOTES)
# ATUALIZADO:
# 1. Novas importações de 'database' para pacotes.
# 2. Nova função: buscar_pacotes_validos_cliente
# 3. Nova função: associar_pacote_cliente
# --- INÍCIO DAS NOVAS ATUALIZAÇÕES ---
# 4. (Feature 4) `acao_admin_agendamento`: Adicionado "confirmar_cliente" ao status_map.
# 5. (Feature 2c) Nova função: `processar_desligamento_profissional`.
# 6. (Feature 2c) Importadas novas funções de DB: `db_remover_profissional`, `buscar_agendamentos_futuros_por_profissional`, `desassociar_profissional_agendamento`.
# 7. (Feature 5) `buscar_agendamentos_por_data`: Modificado para filtrar por 'Confirmado' E 'Pendente'.
# --- FIM DAS NOVAS ATUALIZAÇÕES ---

import uuid
from datetime import datetime, date, time, timedelta
import pandas as pd
import random
from zoneinfo import ZoneInfo
import requests # Para buscar feriados
import sys # Para logs

# Importações de funções de DB
from database import (
    atualizar_status_agendamento, 
    buscar_agendamento_por_pin,
    atualizar_horario_agendamento,
    listar_profissionais,
    adicionar_feriado,
    buscar_agendamentos_por_intervalo,
    # Funções para turmas
    contar_agendamentos_turma_dia,
    # <-- NOVAS IMPORTAÇÕES PARA PACOTES -->
    listar_pacotes_modelos,
    listar_pacotes_do_cliente,
    associar_pacote_ao_cliente as db_associar_pacote_ao_cliente,
    listar_servicos, # Necessário para buscar_pacotes_validos
    # --- (Feature 2c) Novas Importações ---
    remover_profissional as db_remover_profissional,
    buscar_agendamentos_futuros_por_profissional,
    desassociar_profissional_agendamento
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
    
    if agendamentos_existentes.empty or 'turma_id' not in agendamentos_existentes.columns:
        agendamentos_individuais = agendamentos_existentes.copy()
    else:
        agendamentos_individuais = agendamentos_existentes[agendamentos_existentes['turma_id'].isnull()]

    if agendamento_id_excluir and not agendamentos_individuais.empty:
        agendamentos_individuais = agendamentos_individuais[agendamentos_individuais['id'] != agendamento_id_excluir]

    if not agendamentos_individuais.empty:
        # (Feature 4) Verifica conflito com Pendentes E Confirmados
        status_conflito = ['Confirmado', 'Pendente']
        for _, ag in agendamentos_individuais.iterrows():
            if ag['status'] in status_conflito:
                dt_inicio_existente = ag['horario']
                duracao_existente = int(ag.get('duracao_min', 30))
                dt_fim_existente = dt_inicio_existente + timedelta(minutes=duracao_existente)
                
                if data_hora_inicio < dt_fim_existente and dt_inicio_existente < dt_fim_novo:
                    return False, f"Conflito com agendamento das {dt_inicio_existente.strftime('%H:%M')} (Status: {ag['status']})."

    return True, "Horário disponível."

def processar_cancelamento_seguro(pin_code: str) -> bool:
    agendamento = buscar_agendamento_por_pin(pin_code)
    # (Feature 4) Permite cancelar se estiver Pendente OU Confirmado
    if agendamento and agendamento['status'] in ["Confirmado", "Pendente"]:
        return atualizar_status_agendamento(agendamento['id'], "Cancelado pelo Cliente")
    return False

def acao_admin_agendamento(agendamento_id: str, acao: str) -> bool:
    
    status_map = {
        "cancelar": "Cancelado (Admin)",
        "finalizar": "Finalizado",
        "no-show": "No-Show",
        "confirmar_cliente": "Confirmado" # (Feature 4) Nova ação
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
    
    # (Feature 4) Filtro modificado para incluir Pendentes
    filtro = (todos_agendamentos['horario'].dt.date == data_selecionada) & \
             (todos_agendamentos['status'].isin(['Confirmado', 'Pendente']))
             
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
        # (Feature 4) Ao remarcar, confirma automaticamente
        acao_admin_agendamento(agendamento_id, "confirmar_cliente")
        return True, "Agendamento remarcado e confirmado com sucesso!"
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
        print(f"Erro ao buscar feriados da API: {e}", file=sys.stderr)
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
    
    if agendamentos_existentes_df.empty or 'turma_id' not in agendamentos_existentes_df.columns:
        agendamentos_individuais_df = agendamentos_existentes_df.copy()
    else:
        agendamentos_individuais_df = agendamentos_existentes_df[agendamentos_existentes_df['turma_id'].isnull()]
        
    if agendamento_id_excluir and not agendamentos_individuais_df.empty:
        agendamentos_individuais_df = agendamentos_individuais_df[agendamentos_individuais_df['id'] != agendamento_id_excluir]

    blocos_ocupados = []
    if not agendamentos_individuais_df.empty:
        # (Feature 4) Bloqueia horários Pendentes E Confirmados
        df_ocupados = agendamentos_individuais_df[agendamentos_individuais_df['status'].isin(['Confirmado', 'Pendente'])]
        for _, ag in df_ocupados.iterrows():
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
        
        if data_selecionada == datetime.now(TZ_SAO_PAULO).date():
            if horario_obj <= datetime.now(TZ_SAO_PAULO).time():
                continue

        # (Feature 4) contar_agendamentos_turma_dia agora conta Pendentes + Confirmados
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
        (df_agendamentos['turma_id'].isnull()) & 
        (df_agendamentos['status'].isin(['Confirmado', 'Pendente'])) # (Feature 4) Mostra pendentes
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
        (df_agendamentos['status'].isin(['Confirmado', 'Pendente'])) & # (Feature 4) Mostra pendentes
        (df_agendamentos['turma_id'].isnull())
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

# --- (Feature 2c) Nova Função ---
def processar_desligamento_profissional(clinic_id: str, prof_id: str, prof_nome: str):
    """
    Localiza agendamentos futuros (pendentes/confirmados) de um profissional,
    marca-os como '[Sem Profissional]' e, em seguida, remove o profissional.
    """
    try:
        # 1. Buscar agendamentos futuros
        agendamentos_futuros = buscar_agendamentos_futuros_por_profissional(clinic_id, prof_nome)
        
        if not agendamentos_futuros:
            print(f"LOG: Nenhum agendamento futuro encontrado para {prof_nome}. Removendo diretamente.", file=sys.stderr)
        
        # 2. Desassociar agendamentos
        count_desassociados = 0
        for ag in agendamentos_futuros:
            if desassociar_profissional_agendamento(ag['id']):
                count_desassociados += 1
        
        print(f"LOG: {count_desassociados} agendamentos foram desassociados de {prof_nome}.", file=sys.stderr)

        # 3. Remover o profissional da coleção 'profissionais'
        if db_remover_profissional(clinic_id, prof_id):
            print(f"LOG: Profissional {prof_nome} (ID: {prof_id}) removido com sucesso.", file=sys.stderr)
            return True, f"Profissional '{prof_nome}' removido. {count_desassociados} agendamentos futuros foram marcados como 'Sem Profissional'."
        else:
            return False, "Erro ao remover o cadastro do profissional, mas os agendamentos podem ter sido desassociados."

    except Exception as e:
        print(f"ERRO GERAL no processar_desligamento_profissional para {prof_nome
