# database.py (VERSÃO COM CORREÇÃO DE ÍNDICE E KEYERROR)

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
COLECAO_AGENDAMENTOS = "agendamentos"

def salvar_agendamento(dados: dict, pin_code: str):
    """Salva um novo agendamento, convertendo o horário local para UTC."""
    horario_utc = dados['horario'].astimezone(timezone.utc)
    data_para_salvar = {
        'pin_code': str(pin_code),
        'profissional': dados['profissional'],
        'cliente': dados['cliente'],
        'telefone': dados['telefone'],
        'horario': horario_utc,
        'status': "Confirmado",
    }
    try:
        db.collection(COLECAO_AGENDAMENTOS).add(data_para_salvar)
        return True
    except Exception as e:
        return f"Erro de DB: {e}"

def processar_retorno_firestore(doc):
    """Converte um documento do Firestore para um dicionário, ajustando o fuso horário."""
    data = doc.to_dict()
    data['id'] = doc.id
    if 'horario' in data and isinstance(data['horario'], datetime):
        horario_utc = data['horario'].replace(tzinfo=timezone.utc)
        data['horario'] = horario_utc.astimezone(TZ_SAO_PAULO)
    return data

def buscar_agendamento_por_pin(pin_code: str):
    """Busca um agendamento específico pelo seu PIN."""
    if not pin_code: return None
    try:
        query = db.collection(COLECAO_AGENDAMENTOS).where(filter=FieldFilter('pin_code', '==', str(pin_code))).limit(1)
        docs = query.get()
        return processar_retorno_firestore(docs[0]) if docs else None
    except Exception as e:
        print(f"ERRO NA BUSCA POR PIN: {e}")
        return None

def buscar_agendamentos_por_intervalo(start_dt_utc: datetime, end_dt_utc: datetime):
    """
    Busca agendamentos em um intervalo de tempo.
    Removemos o filtro de 'status' para evitar a necessidade de um índice composto no Firestore.
    """
    try:
        query = db.collection(COLECAO_AGENDAMENTOS) \
            .where(filter=FieldFilter('horario', '>=', start_dt_utc)) \
            .where(filter=FieldFilter('horario', '<', end_dt_utc)) \
            .order_by('horario')
        docs = query.stream()
        return [processar_retorno_firestore(doc) for doc in docs]
    except Exception as e:
        print(f"ERRO NA BUSCA POR INTERVALO: {e}")
        return []

def atualizar_status_agendamento(id_agendamento: str, novo_status: str):
    """Atualiza o campo 'status' de um agendamento."""
    try:
        db.collection(COLECAO_AGENDAMENTOS).document(id_agendamento).update({'status': novo_status})
        return True
    except Exception as e:
        return False

def atualizar_horario_agendamento(id_agendamento: str, novo_horario_local: datetime):
    """Atualiza o horário de um agendamento, convertendo o horário local para UTC."""
    try:
        novo_horario_utc = novo_horario_local.astimezone(timezone.utc)
        doc_ref = db.collection(COLECAO_AGENDAMENTOS).document(id_agendamento)
        doc_ref.update({'horario': novo_horario_utc})
        return True
    except Exception as e:
        print(f"ERRO AO ATUALIZAR HORÁRIO: {e}")
        return False

def buscar_todos_agendamentos():
    """Busca todos os agendamentos da coleção (usado para checar disponibilidade)."""
    try:
        docs = db.collection(COLECAO_AGENDAMENTOS).stream()
        data = [processar_retorno_firestore(doc) for doc in docs]
        return pd.DataFrame(data) if data else pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

