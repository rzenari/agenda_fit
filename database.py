# database.py (VERSÃO MULTI-CLINICA COM GESTÃO DE HORÁRIOS E FERIADOS)

import streamlit as st
import pandas as pd
from datetime import datetime, timezone, date
import json
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from zoneinfo import ZoneInfo

TZ_SAO_PAULO = ZoneInfo('America/Sao_Paulo')

@st.cache_resource
def get_firestore_client():
    """Inicializa e retorna o cliente do Firestore."""
    try:
        credenciais = json.loads(st.secrets["firestore"]["json_key_string"])
        return firestore.Client.from_service_account_info(credenciais)
    except Exception as e:
        st.error(f"Erro ao conectar ao Firestore: {e}")
        st.stop()

db = get_firestore_client()

# --- FUNÇÕES DE AUTENTICAÇÃO E GERENCIAMENTO DE CLÍNICAS ---
def buscar_clinica_por_login(username, password):
    """Busca uma clínica pelo username e password."""
    try:
        clinicas_ref = db.collection("clinicas")
        query = clinicas_ref.where('username', '==', username).where('password', '==', password).limit(1)
        docs = query.get()
        if docs:
            clinica_data = docs[0].to_dict()
            clinica_data['id'] = docs[0].id
            return clinica_data
        return None
    except Exception as e:
        print(f"Erro ao buscar clínica: {e}")
        return None

# --- FUNÇÕES DE GERENCIAMENTO DE PROFISSIONAIS (POR CLÍNICA) ---
def adicionar_profissional(clinic_id, nome_profissional):
    """Adiciona um novo profissional com um horário de trabalho padrão."""
    try:
        horario_padrao = {
            dia: {"ativo": (dia not in ["sab", "dom"]), "inicio": "09:00", "fim": "18:00"}
            for dia in ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]
        }
        profissionais_ref = db.collection('profissionais')
        profissionais_ref.add({
            'clinic_id': clinic_id, 
            'nome': nome_profissional,
            'horario_trabalho': horario_padrao
        })
        return True
    except Exception as e:
        print(f"Erro ao adicionar profissional: {e}")
        return False

def listar_profissionais(clinic_id):
    """Lista todos os profissionais de uma clínica específica."""
    try:
        profissionais_ref = db.collection('profissionais')
        query = profissionais_ref.where('clinic_id', '==', clinic_id)
        docs = query.stream()
        profissionais = []
        for doc in docs:
            prof_data = doc.to_dict()
            prof_data['id'] = doc.id
            profissionais.append(prof_data)
        return profissionais
    except Exception as e:
        print(f"Erro ao listar profissionais: {e}")
        return []

def remover_profissional(clinic_id, profissional_id):
    """Remove um profissional de uma clínica."""
    try:
        prof_ref = db.collection('profissionais').document(profissional_id)
        prof_doc = prof_ref.get()
        if prof_doc.exists and prof_doc.to_dict().get('clinic_id') == clinic_id:
            prof_ref.delete()
            st.rerun() 
            return True
        return False
    except Exception as e:
        print(f"Erro ao remover profissional: {e}")
        return False

def atualizar_horario_profissional(clinic_id, profissional_id, horarios):
    """Atualiza a configuração de horário de um profissional."""
    try:
        prof_ref = db.collection('profissionais').document(profissional_id)
        # Garante que a operação só ocorra se o profissional for da clínica correta
        prof_doc = prof_ref.get()
        if prof_doc.exists and prof_doc.to_dict().get('clinic_id') == clinic_id:
            prof_ref.update({'horario_trabalho': horarios})
            return True
        return False
    except Exception as e:
        print(f"Erro ao atualizar horário: {e}")
        return False

# --- FUNÇÕES DE GESTÃO DE FERIADOS ---
def adicionar_feriado(clinic_id, data_feriado, descricao):
    """Adiciona uma data de feriado/folga para uma clínica."""
    try:
        # Converte a data para timestamp para salvar no Firestore
        data_ts = datetime.combine(data_feriado, datetime.min.time())
        db.collection('feriados').add({
            'clinic_id': clinic_id,
            'data': data_ts,
            'descricao': descricao
        })
        return True
    except Exception as e:
        print(f"Erro ao adicionar feriado: {e}")
        return False

def listar_feriados(clinic_id):
    """Lista todos os feriados de uma clínica, ordenados por data."""
    try:
        query = db.collection('feriados').where('clinic_id', '==', clinic_id).order_by('data')
        docs = query.stream()
        feriados = []
        for doc in docs:
            feriado_data = doc.to_dict()
            feriado_data['id'] = doc.id
            # Converte o timestamp de volta para um objeto date para exibição
            if 'data' in feriado_data and isinstance(feriado_data['data'], datetime):
                feriado_data['data'] = feriado_data['data'].date()
            feriados.append(feriado_data)
        return feriados
    except Exception as e:
        print(f"Erro ao listar feriados: {e}")
        return []

def remover_feriado(clinic_id, feriado_id):
    """Remove um feriado."""
    try:
        feriado_ref = db.collection('feriados').document(feriado_id)
        feriado_doc = feriado_ref.get()
        if feriado_doc.exists and feriado_doc.to_dict().get('clinic_id') == clinic_id:
            feriado_ref.delete()
            st.rerun()
            return True
        return False
    except Exception as e:
        print(f"Erro ao remover feriado: {e}")
        return False


# --- FUNÇÕES DE AGENDAMENTO (permanecem as mesmas) ---
def salvar_agendamento(clinic_id: str, dados: dict, pin_code: str):
    horario_utc = dados['horario'].astimezone(timezone.utc)
    data_para_salvar = {
        'clinic_id': clinic_id, 'pin_code': str(pin_code),
        'profissional_nome': dados['profissional_nome'], 'cliente': dados['cliente'],
        'telefone': dados['telefone'], 'horario': horario_utc, 'status': "Confirmado",
    }
    try:
        db.collection("agendamentos").add(data_para_salvar)
        return True
    except Exception as e:
        return f"Erro de DB: {e}"

def processar_retorno_firestore(doc):
    data = doc.to_dict()
    data['id'] = doc.id
    if 'horario' in data and isinstance(data['horario'], datetime):
        horario_utc = data['horario'].replace(tzinfo=timezone.utc)
        data['horario'] = horario_utc.astimezone(TZ_SAO_PAULO)
    return data

def buscar_agendamento_por_pin(pin_code: str):
    try:
        query = db.collection("agendamentos").where(filter=FieldFilter('pin_code', '==', str(pin_code))).limit(1)
        docs = query.get()
        return processar_retorno_firestore(docs[0]) if docs else None
    except: return None

def buscar_todos_agendamentos(clinic_id: str):
    try:
        query = db.collection("agendamentos").where(filter=FieldFilter('clinic_id', '==', clinic_id))
        docs = query.stream()
        data = [processar_retorno_firestore(doc) for doc in docs]
        return pd.DataFrame(data) if data else pd.DataFrame()
    except: return pd.DataFrame()

def atualizar_status_agendamento(id_agendamento: str, novo_status: str):
    try:
        db.collection("agendamentos").document(id_agendamento).update({'status': novo_status})
        return True
    except: return False

def atualizar_horario_agendamento(id_agendamento: str, novo_horario_local: datetime):
    try:
        novo_horario_utc = novo_horario_local.astimezone(timezone.utc)
        db.collection("agendamentos").document(id_agendamento).update({'horario': novo_horario_utc})
        return True
    except: return False

