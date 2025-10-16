# database.py (VERSÃO FINAL com Busca por Intervalo Firestore)

import streamlit as st
import pandas as pd
from datetime import datetime, time, date, timedelta
import json 
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter # Importação para filtros de data

# --- Inicialização da Conexão ---
@st.cache_resource
def get_firestore_client():
    """
    Inicializa o cliente Firestore lendo a Service Account.
    """
    try:
        # Tenta carregar as credenciais como string JSON (formato esperado)
        json_credenciais = st.secrets["firestore"]["json_key_string"]
        credenciais_dict = json.loads(json_credenciais)

        return firestore.Client.from_service_account_info(credenciais_dict)
    except Exception as e:
        # O erro "Invalid grant: account not found" indica falha na credencial.
        # Por favor, verifique se a string JSON_KEY_STRING nas secrets está correta.
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
        return True # Sucesso
    except Exception as e:
        return str(e) # Retorna a mensagem de erro


def buscar_agendamento_por_pin(pin_code: str):
    """Busca um agendamento pelo PIN (Query NoSQL)."""
    try:
        docs = db.collection(COLECAO_AGENDAMENTOS).where('pin_code', '==', str(pin_code)).limit(1).stream()
        
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id 
            
            if 'horario' in data:
                 # Converte o timestamp para datetime Python Naive (sem fuso)
                 data['horario'] = data['horario'].to_datetime().replace(tzinfo=None)
            
            return data
            
        return None
    except Exception as e:
        print(f"ERRO NA BUSCA POR PIN: {e}")
        return None

def buscar_todos_agendamentos():
    """Busca todos os agendamentos e retorna um DataFrame."""
    try:
        docs = db.collection(COLECAO_AGENDAMENTOS).stream()
        data = []
        for doc in docs:
            item = doc.to_dict()
            item['id'] = doc.id
            if 'horario' in item:
                # Converte o timestamp para datetime Python Naive (sem fuso)
                item['horario'] = item['horario'].to_datetime().replace(tzinfo=None)
            data.append(item)
            
        return pd.DataFrame(data).sort_values(by='horario')
    except Exception as e:
        print(f"ERRO NA BUSCA TOTAL: {e}")
        return pd.DataFrame()


def buscar_agendamentos_por_intervalo(start_dt: datetime, end_dt: datetime):
    """
    Busca agendamentos por um intervalo de data/hora no Firestore.
    Implementa o filtro de data no nível do banco de dados (mais robusto).
    """
    try:
        docs = db.collection(COLECAO_AGENDAMENTOS).where(
            filter=FieldFilter('horario', '>=', start_dt)
        ).where(
            filter=FieldFilter('horario', '<', end_dt)
        ).order_by('horario').stream()
        
        data = []
        for doc in docs:
            item = doc.to_dict()
            item['id'] = doc.id
            if 'horario' in item:
                # Converte o timestamp para datetime Python Naive (sem fuso)
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
            if 'horario' in data:
                 data['horario'] = data['horario'].to_datetime().replace(tzinfo=None)
            return data
    except Exception as e:
        print(f"ERRO NA BUSCA POR ID: {e}")
    return None
