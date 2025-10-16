# database.py (VERSÃO MULTI-CLINICA)

import streamlit as st
import pandas as pd
from datetime import datetime, timezone
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
    """Adiciona um novo profissional a uma clínica específica."""
    try:
        profissionais_ref = db.collection('profissionais')
        profissionais_ref.add({'clinic_id': clinic_id, 'nome': nome_profissional})
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


# --- FUNÇÕES DE AGENDAMENTO (Adaptadas para Multi-Clínica) ---

def salvar_agendamento(clinic_id: str, dados: dict, pin_code: str):
    """Salva um novo agendamento, associando-o a uma clínica."""
    horario_utc = dados['horario'].astimezone(timezone.utc)
    data_para_salvar = {
        'clinic_id': clinic_id,
        'pin_code': str(pin_code),
        'profissional_nome': dados['profissional_nome'],
        'cliente': dados['cliente'],
        'telefone': dados['telefone'],
        'horario': horario_utc,
        'status': "Confirmado",
    }
    try:
        db.collection("agendamentos").add(data_para_salvar)
        return True
    except Exception as e:
        return f"Erro de DB: {e}"

def processar_retorno_firestore(doc):
    """Converte um documento do Firestore, ajustando o fuso horário."""
    data = doc.to_dict()
    data['id'] = doc.id
    if 'horario' in data and isinstance(data['horario'], datetime):
        horario_utc = data['horario'].replace(tzinfo=timezone.utc)
        data['horario'] = horario_utc.astimezone(TZ_SAO_PAULO)
    return data

def buscar_agendamento_por_pin(pin_code: str):
    """Busca um agendamento pelo PIN (funciona para todas as clínicas)."""
    try:
        query = db.collection("agendamentos").where(filter=FieldFilter('pin_code', '==', str(pin_code))).limit(1)
        docs = query.get()
        return processar_retorno_firestore(docs[0]) if docs else None
    except Exception as e:
        return None

def buscar_agendamentos_por_intervalo(clinic_id: str, start_dt_utc: datetime, end_dt_utc: datetime):
    """Busca agendamentos de uma clínica em um intervalo."""
    try:
        query = db.collection("agendamentos") \
            .where(filter=FieldFilter('clinic_id', '==', clinic_id)) \
            .where(filter=FieldFilter('horario', '>=', start_dt_utc)) \
            .where(filter=FieldFilter('horario', '<', end_dt_utc)) \
            .order_by('horario')
        docs = query.stream()
        return [processar_retorno_firestore(doc) for doc in docs]
    except Exception as e:
        print(f"ERRO NA BUSCA POR INTERVALO: {e}")
        return []

def buscar_todos_agendamentos(clinic_id: str):
    """Busca todos os agendamentos de uma clínica."""
    try:
        query = db.collection("agendamentos").where(filter=FieldFilter('clinic_id', '==', clinic_id))
        docs = query.stream()
        data = [processar_retorno_firestore(doc) for doc in docs]
        return pd.DataFrame(data) if data else pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

def atualizar_status_agendamento(id_agendamento: str, novo_status: str):
    try:
        db.collection("agendamentos").document(id_agendamento).update({'status': novo_status})
        return True
    except Exception:
        return False

def atualizar_horario_agendamento(id_agendamento: str, novo_horario_local: datetime):
    try:
        novo_horario_utc = novo_horario_local.astimezone(timezone.utc)
        db.collection("agendamentos").document(id_agendamento).update({'horario': novo_horario_utc})
        return True
    except Exception:
        return False

