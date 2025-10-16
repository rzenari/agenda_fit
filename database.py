# database.py (VERSÃO FINAL COM SINTAXE MODERNA E DEBUG)

import streamlit as st
import pandas as pd
from datetime import datetime, time, date, timedelta
import json
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter # Importação para a sintaxe moderna

# --- Inicialização da Conexão ---
@st.cache_resource
def get_firestore_client():
    """
    Inicializa o cliente Firestore lendo a Service Account dos Secrets do Streamlit.
    """
    try:
        json_credenciais = st.secrets["firestore"]["json_key_string"]
        credenciais_dict = json.loads(json_credenciais)
        return firestore.Client.from_service_account_info(credenciais_dict)
    except Exception as e:
        st.error(f"Erro ao conectar ao Google Firestore. Falha na credencial ou permissão. Detalhe: {e}")
        st.stop()

db = get_firestore_client()
COLECAO_AGENDAMENTOS = "agendamentos"


# --- Funções de Operação no Banco de Dados (NoSQL) ---

def salvar_agendamento(dados: dict, pin_code: str):
    """Cria um novo documento (agendamento) no Firestore e retorna True ou a string de erro."""
    data_para_salvar = {
        'pin_code': str(pin_code),
        'profissional': dados['profissional'],
        'cliente': dados['cliente'],
        'telefone': dados['telefone'],
        'horario': dados['horario'],  
        'status': "Confirmado",
        'is_pacote_sessao': False 
    }
    try:
        db.collection(COLECAO_AGENDAMENTOS).add(data_para_salvar)
        return True
    except Exception as e:
        return f"Erro de DB: {e}"

def buscar_agendamento_por_pin(pin_code: str):
    """Busca um agendamento pelo PIN usando o método .get() e sintaxe FieldFilter."""
    
    # Este print aparecerá no terminal/logs onde o Streamlit está rodando
    print(f"--- [DEBUG DB] Iniciando busca por PIN: {pin_code} (tipo: {type(pin_code)}) ---")

    try:
        # CORREÇÃO: Usando a sintaxe 'filter' para eliminar warnings e ser mais explícito
        query = db.collection(COLECAO_AGENDAMENTOS).where(filter=FieldFilter('pin_code', '==', str(pin_code))).limit(1)
        docs = query.get()
        
        if not docs:
            print(f"--- [DEBUG DB] Nenhum documento encontrado para o PIN: {pin_code} ---")
            return None
        
        print(f"--- [DEBUG DB] Documento encontrado! ID: {docs[0].id} ---")
        
        doc = docs[0]
        data = doc.to_dict()
        data['id'] = doc.id 
        
        if 'horario' in data and hasattr(data['horario'], 'to_datetime'):
            data['horario'] = data['horario'].to_datetime().replace(tzinfo=None)
        
        return data
            
    except Exception as e:
        print(f"--- [DEBUG DB] ERRO DURANTE A EXECUÇÃO DA QUERY: {e} ---")
        return None

def buscar_todos_agendamentos():
    """Busca todos os agendamentos e retorna um DataFrame."""
    try:
        docs = db.collection(COLECAO_AGENDAMENTOS).stream()
        data = []
        for doc in docs:
            item = doc.to_dict()
            item['id'] = doc.id
            if 'horario' in item and hasattr(item['horario'], 'to_datetime'):
                item['horario'] = item['horario'].to_datetime().replace(tzinfo=None)
            data.append(item)
            
        if not data:
            return pd.DataFrame()
        return pd.DataFrame(data).sort_values(by='horario')
    except Exception as e:
        print(f"ERRO NA BUSCA TOTAL: {e}")
        return pd.DataFrame()


def buscar_agendamentos_por_intervalo(start_dt: datetime, end_dt: datetime):
    """Busca agendamentos por um intervalo de data/hora no Firestore."""
    try:
        # CORREÇÃO: Usando a sintaxe 'filter' também aqui
        query = db.collection(COLECAO_AGENDAMENTOS) \
            .where(filter=FieldFilter('horario', '>=', start_dt)) \
            .where(filter=FieldFilter('horario', '<', end_dt)) \
            .order_by('horario')
        
        docs = query.stream()
        
        data = []
        for doc in docs:
            item = doc.to_dict()
            item['id'] = doc.id
            if 'horario' in item and hasattr(item['horario'], 'to_datetime'):
                item['horario'] = item['horario'].to_datetime().replace(tzinfo=None)
            data.append(item)
            
        return pd.DataFrame(data)
    except Exception as e:
        print(f"ERRO NA BUSCA POR INTERVALO: {e}")
        return pd.DataFrame()


def atualizar_status_agendamento(id_agendamento: str, novo_status: str):
    """Atualiza o status de um agendamento específico."""
    try:
        doc_ref = db.collection(COLECAO_AGENDAMENTOS).document(id_agendamento)
        doc_ref.update({'status': novo_status})
        return True
    except Exception as e:
        print(f"ERRO AO ATUALIZAR STATUS: {e}")
        return False
        
def buscar_agendamento_por_id(id_agendamento: str):
    """Busca um agendamento pelo ID do documento do Firestore."""
    try:
        doc = db.collection(COLECAO_AGENDAMENTOS).document(id_agendamento).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            if 'horario' in data and hasattr(data['horario'], 'to_datetime'):
                data['horario'] = data['horario'].to_datetime().replace(tzinfo=None)
            return data
    except Exception as e:
        print(f"ERRO NA BUSCA POR ID: {e}")
    return None

