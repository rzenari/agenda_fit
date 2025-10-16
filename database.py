# database.py (VERSÃO FINAL COM CORREÇÃO DE FUSO HORÁRIO)

import streamlit as st
import pandas as pd
from datetime import datetime, time, date, timedelta
import json
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
import pytz # Importa a biblioteca de fuso horário

# Define o fuso horário padrão para São Paulo
TZ_SAO_PAULO = pytz.timezone('America/Sao_Paulo')

# --- Inicialização da Conexão ---
@st.cache_resource
def get_firestore_client():
    try:
        json_credenciais = st.secrets["firestore"]["json_key_string"]
        credenciais_dict = json.loads(json_credenciais)
        return firestore.Client.from_service_account_info(credenciais_dict)
    except Exception as e:
        st.error(f"Erro ao conectar ao Google Firestore. Detalhe: {e}")
        st.stop()

db = get_firestore_client()
COLECAO_AGENDAMENTOS = "agendamentos"


# --- Funções de Operação no Banco de Dados (NoSQL) ---

def salvar_agendamento(dados: dict, pin_code: str):
    """Cria um novo documento no Firestore, garantindo que o PIN seja string e o horário seja UTC."""
    
    # Converte o horário localizado para UTC para salvar no banco
    horario_local = dados['horario']
    horario_utc = horario_local.astimezone(pytz.utc)

    data_para_salvar = {
        'pin_code': str(pin_code),
        'profissional': dados['profissional'],
        'cliente': dados['cliente'],
        'telefone': dados['telefone'],
        'horario': horario_utc,  # SALVA EM UTC
        'status': "Confirmado",
        'is_pacote_sessao': False 
    }
    try:
        db.collection(COLECAO_AGENDAMENTOS).add(data_para_salvar)
        return True
    except Exception as e:
        return f"Erro de DB: {e}"

def processar_retorno_firestore(doc):
    """Função auxiliar para converter o timestamp UTC do Firestore para o horário local de SP."""
    data = doc.to_dict()
    data['id'] = doc.id 
    if 'horario' in data and hasattr(data['horario'], 'to_datetime'):
        horario_utc = data['horario'].to_datetime().replace(tzinfo=pytz.utc)
        # Converte para o fuso de São Paulo para exibição
        data['horario'] = horario_utc.astimezone(TZ_SAO_PAULO)
    return data

def buscar_agendamento_por_pin(pin_code: str):
    """Busca um agendamento pelo PIN (string) e converte o horário para o fuso local."""
    try:
        query = db.collection(COLECAO_AGENDAMENTOS).where(filter=FieldFilter('pin_code', '==', str(pin_code))).limit(1)
        docs = query.get()
        
        if docs:
            return processar_retorno_firestore(docs[0])
        else:
            return None
            
    except Exception as e:
        print(f"ERRO CRÍTICO NA BUSCA POR PIN: {e}")
        return None

def buscar_todos_agendamentos():
    try:
        docs = db.collection(COLECAO_AGENDAMENTOS).stream()
        data = [processar_retorno_firestore(doc) for doc in docs]
        if not data: return pd.DataFrame()
        return pd.DataFrame(data).sort_values(by='horario')
    except Exception as e:
        print(f"ERRO NA BUSCA TOTAL: {e}")
        return pd.DataFrame()

def buscar_agendamentos_por_intervalo(start_dt_utc: datetime, end_dt_utc: datetime):
    """Busca agendamentos por um intervalo de data/hora em UTC."""
    try:
        query = db.collection(COLECAO_AGENDAMENTOS) \
            .where(filter=FieldFilter('horario', '>=', start_dt_utc)) \
            .where(filter=FieldFilter('horario', '<', end_dt_utc)) \
            .order_by('horario')
        docs = query.stream()
        data = [processar_retorno_firestore(doc) for doc in docs]
        return pd.DataFrame(data)
    except Exception as e:
        print(f"ERRO NA BUSCA POR INTERVALO: {e}")
        return pd.DataFrame()

def atualizar_status_agendamento(id_agendamento: str, novo_status: str):
    try:
        doc_ref = db.collection(COLECAO_AGENDAMENTOS).document(id_agendamento)
        doc_ref.update({'status': novo_status})
        return True
    except Exception as e:
        print(f"ERRO AO ATUALIZAR STATUS: {e}")
        return False
        
def buscar_agendamento_por_id(id_agendamento: str):
    try:
        doc = db.collection(COLECAO_AGENDAMENTOS).document(id_agendamento).get()
        if doc.exists:
            return processar_retorno_firestore(doc)
    except Exception as e:
        print(f"ERRO NA BUSCA POR ID: {e}")
    return None

