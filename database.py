# database.py (VERSÃO FINAL COM st.connection("firestore"))

import streamlit as st
import pandas as pd
from datetime import datetime, time, date
from streamlit.connections import BaseConnection # Importação do BaseConnection (st.connection)
from google.cloud.firestore import Client # Para tipagem do cliente interno

# Definição do nome da Coleção
COLECAO_AGENDAMENTOS = "agendamentos"


# --- Inicialização da Conexão (Forma NATIVA Streamlit) ---
@st.cache_resource
def get_db_connection():
    """Obtém a conexão Firestore via st.connection, que lê o JSON dos secrets."""
    try:
        # AQUI é onde o Streamlit lida com a autenticação JSON
        # O nome 'firestore' deve corresponder à chave [connections.firestore] no secrets
        conn = st.connection("firestore", type="firestore")
        return conn.client # Retorna o objeto Cliente do Firestore autenticado
    except Exception as e:
        # Erro de conexão, geralmente causado por JSON mal formatado ou falta de permissão
        st.error(f"Erro ao conectar ao Firestore. Verifique o JSON nos Secrets. Detalhe: {e}")
        st.stop()

db: Client = get_db_connection()


# --- Funções de Operação no Banco de Dados (NoSQL) ---

def salvar_agendamento(dados: dict, pin_code: str):
    """Cria um novo documento (agendamento) no Firestore."""
    
    data_para_salvar = {
        'pin_code': str(pin_code),
        'profissional': dados['profissional'],
        'cliente': dados['cliente'],
        'telefone': dados['telefone'],
        'horario': dados['horario'],  # Firestore armazena nativamente o datetime
        'status': "Confirmado",
        'is_pacote_sessao': False 
    }
    
    try:
        # db é o objeto Cliente do Firestore
        db.collection(COLECAO_AGENDAMENTOS).add(data_para_salvar)
        return True
    except Exception as e:
        print(f"ERRO AO SALVAR NO FIRESTORE: {e}")
        return False

def buscar_agendamento_por_pin(pin_code: str):
    """Busca um agendamento pelo PIN (Query NoSQL)."""
    try:
        # Busca por um documento onde 'pin_code' é igual ao valor
        docs = db.collection(COLECAO_AGENDAMENTOS).where('pin_code', '==', str(pin_code)).limit(1).stream()
        
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id 
            
            # Converte a hora (TimeStamp) para datetime Python Naive
            if 'horario' in data:
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
            # Converte a hora (TimeStamp) para datetime Python Naive
            if 'horario' in item:
                item['horario'] = item['horario'].to_datetime().replace(tzinfo=None)
            data.append(item)
            
        return pd.DataFrame(data).sort_values(by='horario')
    except Exception as e:
        print(f"ERRO NA BUSCA TOTAL: {e}")
        return pd.DataFrame()


def atualizar_status_agendamento(id_agendamento: str, novo_status: str):
    """Atualiza o status de um agendamento específico (usa ID de documento)."""
    try:
        # Usa o ID (string) do documento para fazer o update
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
