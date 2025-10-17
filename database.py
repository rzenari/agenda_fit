# database.py (VERSÃO COM GESTÃO DE CLIENTES E SERVIços)

import streamlit as st
import pandas as pd
from datetime import datetime, time, date, timedelta
import json
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from zoneinfo import ZoneInfo

# --- Configuração ---
TZ_SAO_PAULO = ZoneInfo('America/Sao_Paulo')

# --- Inicialização da Conexão ---
@st.cache_resource
def get_firestore_client():
    try:
        json_credenciais = st.secrets["firestore"]["json_key_string"]
        credenciais_dict = json.loads(json_credenciais)
        return firestore.Client.from_service_account_info(credenciais_dict)
    except Exception as e:
        st.error(f"Erro ao conectar ao Google Firestore: {e}")
        return None

db = get_firestore_client()
if db is None:
    st.stop()

# --- Funções de Autenticação e Gestão de Clínicas ---
def buscar_clinica_por_login(username, password):
    """Busca uma clínica pelo username e password."""
    try:
        clinicas_ref = db.collection('clinicas')
        query = clinicas_ref.where(filter=FieldFilter('username', '==', username)).where(filter=FieldFilter('password', '==', password)).limit(1)
        docs = query.stream()
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None
    except Exception as e:
        print(f"ERRO AO BUSCAR CLÍNICA: {e}")
        return None

# --- Funções de Gestão de Profissionais ---
def listar_profissionais(clinic_id: str):
    """Lista todos os profissionais de uma clínica específica."""
    try:
        profissionais_ref = db.collection('clinicas').document(clinic_id).collection('profissionais')
        docs = profissionais_ref.order_by('nome').stream()
        profissionais = []
        for doc in docs:
            prof = doc.to_dict()
            prof['id'] = doc.id
            profissionais.append(prof)
        return profissionais
    except Exception as e:
        print(f"ERRO AO LISTAR PROFISSIONAIS: {e}")
        return []

def adicionar_profissional(clinic_id: str, nome: str):
    """Adiciona um novo profissional a uma clínica."""
    try:
        profissionais_ref = db.collection('clinicas').document(clinic_id).collection('profissionais')
        profissionais_ref.add({'nome': nome, 'horario_trabalho': {}})
        return True
    except Exception as e:
        print(f"ERRO AO ADICIONAR PROFISSIONAL: {e}")
        return False

def remover_profissional(clinic_id: str, profissional_id: str):
    """Remove um profissional de uma clínica."""
    try:
        db.collection('clinicas').document(clinic_id).collection('profissionais').document(profissional_id).delete()
        st.success("Profissional removido com sucesso!")
        st.rerun() 
    except Exception as e:
        print(f"ERRO AO REMOVER PROFISSIONAL: {e}")
        st.error("Erro ao remover profissional.")

def atualizar_horario_profissional(clinic_id: str, prof_id: str, horarios: dict):
    """Atualiza a configuração de horário de um profissional."""
    try:
        prof_ref = db.collection('clinicas').document(clinic_id).collection('profissionais').document(prof_id)
        prof_ref.update({'horario_trabalho': horarios})
        return True
    except Exception as e:
        print(f"ERRO AO ATUALIZAR HORÁRIO: {e}")
        return False

# --- Funções de Gestão de Agendamentos ---
def salvar_agendamento(clinic_id: str, dados: dict, pin_code: str):
    """Cria um novo agendamento para uma clínica."""
    try:
        agendamentos_ref = db.collection('agendamentos')
        data_para_salvar = {
            'clinic_id': clinic_id,
            'pin_code': pin_code,
            'profissional_nome': dados['profissional_nome'],
            'cliente': dados['cliente'],
            'telefone': dados['telefone'],
            'horario': dados['horario'],
            'status': "Confirmado",
            'servico_nome': dados.get('servico_nome', 'Não especificado'), # Salva o nome do serviço
        }
        agendamentos_ref.add(data_para_salvar)
        return True
    except Exception as e:
        return str(e)

def buscar_agendamento_por_pin(pin_code: str):
    """Busca um agendamento pelo PIN (Query NoSQL)."""
    try:
        query = db.collection('agendamentos').where(filter=FieldFilter('pin_code', '==', pin_code)).limit(1)
        docs = query.stream()
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            if 'horario' in data and isinstance(data['horario'], datetime):
                data['horario'] = data['horario'].astimezone(TZ_SAO_PAULO)
            return data
        return None
    except Exception as e:
        print(f"ERRO NA BUSCA POR PIN: {e}")
        return None

def buscar_agendamentos_intervalo(clinic_id: str, start_date: date, end_date: date):
    """Busca todos os agendamentos de uma clínica dentro de um intervalo de datas."""
    try:
        start_dt_naive = datetime.combine(start_date, time.min)
        end_dt_naive = datetime.combine(end_date, time.max)
        
        # CORREÇÃO: Usando .replace(tzinfo=...) em vez de .localize(...)
        start_dt_aware = start_dt_naive.replace(tzinfo=TZ_SAO_PAULO)
        end_dt_aware = end_dt_naive.replace(tzinfo=TZ_SAO_PAULO)

        start_dt_utc = start_dt_aware.astimezone(ZoneInfo('UTC'))
        end_dt_utc = end_dt_aware.astimezone(ZoneInfo('UTC'))

        query = db.collection('agendamentos').where(filter=FieldFilter('clinic_id', '==', clinic_id))\
                                             .where(filter=FieldFilter('horario', '>=', start_dt_utc))\
                                             .where(filter=FieldFilter('horario', '<=', end_dt_utc))
        docs = query.stream()
        data = []
        for doc in docs:
            item = doc.to_dict()
            item['id'] = doc.id
            if 'horario' in item and isinstance(item['horario'], datetime):
                item['horario'] = item['horario'].astimezone(TZ_SAO_PAULO)
            data.append(item)
        return pd.DataFrame(data)
    except Exception as e:
        print(f"ERRO NA BUSCA DE AGENDAMENTOS POR INTERVALO: {e}")
        return pd.DataFrame()

def buscar_agendamentos_por_data_e_profissional(clinic_id: str, profissional_nome: str, data_selecionada: date):
    """Busca agendamentos para um profissional específico em uma data específica."""
    try:
        start_dt_naive = datetime.combine(data_selecionada, time.min)
        end_dt_naive = datetime.combine(data_selecionada, time.max)
        
        # CORREÇÃO: Usando .replace(tzinfo=...) em vez de .localize(...)
        start_dt_aware = start_dt_naive.replace(tzinfo=TZ_SAO_PAULO)
        end_dt_aware = end_dt_naive.replace(tzinfo=TZ_SAO_PAULO)

        start_dt_utc = start_dt_aware.astimezone(ZoneInfo('UTC'))
        end_dt_utc = end_dt_aware.astimezone(ZoneInfo('UTC'))

        query = db.collection('agendamentos').where(filter=FieldFilter('clinic_id', '==', clinic_id))\
            .where(filter=FieldFilter('profissional_nome', '==', profissional_nome))\
            .where(filter=FieldFilter('horario', '>=', start_dt_utc))\
            .where(filter=FieldFilter('horario', '<=', end_dt_utc))
        
        docs = query.stream()
        data = []
        for doc in docs:
            item = doc.to_dict()
            item['id'] = doc.id
            if 'horario' in item and isinstance(item['horario'], datetime):
                item['horario'] = item['horario'].astimezone(TZ_SAO_PAULO)
            data.append(item)
        return pd.DataFrame(data)
    except Exception as e:
        print(f"ERRO NA BUSCA POR DATA E PROFISSIONAL: {e}")
        return pd.DataFrame()

def atualizar_status_agendamento(id_agendamento: str, novo_status: str):
    """Atualiza o status de um agendamento específico."""
    try:
        doc_ref = db.collection('agendamentos').document(id_agendamento)
        doc_ref.update({'status': novo_status})
        return True
    except Exception as e:
        print(f"ERRO AO ATUALIZAR STATUS: {e}")
        return False

def atualizar_horario_agendamento(id_agendamento: str, novo_horario: datetime):
    """Atualiza o horário de um agendamento (usado na remarcação)."""
    try:
        doc_ref = db.collection('agendamentos').document(id_agendamento)
        novo_horario_utc = novo_horario.astimezone(ZoneInfo('UTC'))
        doc_ref.update({'horario': novo_horario_utc})
        return True
    except Exception as e:
        print(f"ERRO AO ATUALIZAR HORÁRIO: {e}")
        return False
        
# --- Funções de Gestão de Feriados ---
def adicionar_feriado(clinic_id: str, data_feriado: date, descricao: str):
    """Adiciona um feriado ou folga para uma clínica."""
    try:
        feriados_ref = db.collection('clinicas').document(clinic_id).collection('feriados')
        data_dt = datetime.combine(data_feriado, time.min)
        feriados_ref.add({'data': data_dt, 'descricao': descricao})
        return True
    except Exception as e:
        print(f"ERRO AO ADICIONAR FERIADO: {e}")
        return False

def listar_feriados(clinic_id: str):
    """Lista todos os feriados de uma clínica, ordenados por data."""
    try:
        feriados_ref = db.collection('clinicas').document(clinic_id).collection('feriados')
        docs = feriados_ref.order_by('data').stream()
        feriados = []
        for doc in docs:
            feriado = doc.to_dict()
            feriado['id'] = doc.id
            if 'data' in feriado and isinstance(feriado['data'], datetime):
                feriado['data'] = feriado['data'].date()
            feriados.append(feriado)
        return feriados
    except Exception as e:
        print(f"Erro ao listar feriados: {e}")
        return []

def remover_feriado(clinic_id: str, feriado_id: str):
    """Remove um feriado de uma clínica."""
    try:
        db.collection('clinicas').document(clinic_id).collection('feriados').document(feriado_id).delete()
        st.rerun()
    except Exception as e:
        st.error("Erro ao remover feriado.")
        print(f"ERRO AO REMOVER FERIADO: {e}")

# --- NOVAS FUNÇÕES: GESTÃO DE CLIENTES ---
def listar_clientes(clinic_id: str):
    """Lista todos os clientes de uma clínica."""
    try:
        clientes_ref = db.collection('clinicas').document(clinic_id).collection('clientes')
        docs = clientes_ref.order_by('nome').stream()
        clientes = []
        for doc in docs:
            cliente = doc.to_dict()
            cliente['id'] = doc.id
            clientes.append(cliente)
        return clientes
    except Exception as e:
        print(f"ERRO AO LISTAR CLIENTES: {e}")
        return []

def adicionar_cliente(clinic_id: str, nome: str, telefone: str, observacoes: str):
    """Adiciona um novo cliente a uma clínica."""
    try:
        clientes_ref = db.collection('clinicas').document(clinic_id).collection('clientes')
        clientes_ref.add({'nome': nome, 'telefone': telefone, 'observacoes': observacoes})
        return True
    except Exception as e:
        print(f"ERRO AO ADICIONAR CLIENTE: {e}")
        return False

def remover_cliente(clinic_id: str, cliente_id: str):
    """Remove um cliente de uma clínica."""
    try:
        db.collection('clinicas').document(clinic_id).collection('clientes').document(cliente_id).delete()
        st.success("Cliente removido com sucesso!")
        st.rerun()
    except Exception as e:
        print(f"ERRO AO REMOVER CLIENTE: {e}")
        st.error("Erro ao remover cliente.")

# --- NOVAS FUNÇÕES: GESTÃO DE SERVIÇOS ---
def listar_servicos(clinic_id: str):
    """Lista todos os serviços de uma clínica."""
    try:
        servicos_ref = db.collection('clinicas').document(clinic_id).collection('servicos')
        docs = servicos_ref.order_by('nome').stream()
        servicos = []
        for doc in docs:
            servico = doc.to_dict()
            servico['id'] = doc.id
            servicos.append(servico)
        return servicos
    except Exception as e:
        print(f"ERRO AO LISTAR SERVIÇOS: {e}")
        return []

def adicionar_servico(clinic_id: str, nome: str, duracao_min: int):
    """Adiciona um novo serviço a uma clínica."""
    try:
        servicos_ref = db.collection('clinicas').document(clinic_id).collection('servicos')
        servicos_ref.add({'nome': nome, 'duracao_min': duracao_min})
        return True
    except Exception as e:
        print(f"ERRO AO ADICIONAR SERVIÇO: {e}")
        return False

def remover_servico(clinic_id: str, servico_id: str):
    """Remove um serviço de uma clínica."""
    try:
        db.collection('clinicas').document(clinic_id).collection('servicos').document(servico_id).delete()
        st.success("Serviço removido com sucesso!")
        st.rerun()
    except Exception as e:
        print(f"ERRO AO REMOVER SERVIÇO: {e}")
        st.error("Erro ao remover serviço.")

