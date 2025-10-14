# database.py (VERSÃO FINAL E FUNCIONAL PARA FIRESTORE)

import streamlit as st
import pandas as pd
from datetime import datetime
import json 
from google.cloud import firestore

# --- Inicialização da Conexão (Sem problemas de porta/firewall) ---
@st.cache_resource
def get_firestore_client():
    """
    Inicializa o cliente Firestore lendo os campos individuais dos Secrets
    e remontando o JSON da Service Account.
    """
    try:
        secrets = st.secrets["firestore"]
        
        # 1. Remontagem do dicionário de credenciais
        credenciais_dict = {
            "type": secrets["type"],
            "project_id": secrets["project_id"],
            "private_key_id": secrets["private_key_id"],
            "client_email": secrets["client_email"],
            "token_uri": secrets["token_uri"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_id": "NAO_NECESSARIO_PARA_AUTH", 
            # 2. A CORREÇÃO CRÍTICA: Converter \\n (string) em \n (quebra de linha real)
            "private_key": secrets["private_key"].replace('\\n', '\n'),
        }

        # 3. Usa o dicionário remontado para autenticar
        return firestore.Client.from_service_account_info(credenciais_dict)
    except KeyError as e:
        st.error(f"Erro Crítico: Falta o campo {e} nos Secrets. Verifique se todos os campos estão configurados.")
        st.stop()
    except Exception as e:
        st.error(f"Erro ao conectar ao Google Firestore. Detalhe: {e}. Verifique as permissões da Service Account.")
        st.stop()

db = get_firestore_client()
COLECAO_AGENDAMENTOS = "agendamentos"


# --- Funções de Operação no Banco de Dados ---
# [O restante do código (salvar, buscar, etc.) permanece o mesmo]

def salvar_agendamento(dados: dict, pin_code: str):
    # ... (código de salvamento omitido)
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
        print(f"ERRO AO SALVAR NO FIRESTORE: {e}")
        return False

def buscar_agendamento_por_pin(pin_code: str):
    # ... (código de busca omitido)
    try:
        docs = db.collection(COLECAO_AGENDAMENTOS).where('pin_code', '==', str(pin_code)).limit(1).stream()
        
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id 
            
            if 'horario' in data:
                 data['horario'] = data['horario'].to_datetime().replace(tzinfo=None)
            
            return data
            
        return None
    except Exception as e:
        print(f"ERRO NA BUSCA POR PIN: {e}")
        return None

def buscar_todos_agendamentos():
    # ... (código de busca total omitido)
    try:
        docs = db.collection(COLECAO_AGENDAMENTOS).stream()
        data = []
        for doc in docs:
            item = doc.to_dict()
            item['id'] = doc.id
            if 'horario' in item:
                item['horario'] = item['horario'].to_datetime().replace(tzinfo=None)
            data.append(item)
            
        return pd.DataFrame(data).sort_values(by='horario')
    except Exception as e:
        print(f"ERRO NA BUSCA TOTAL: {e}")
        return pd.DataFrame()


def atualizar_status_agendamento(id_agendamento: str, novo_status: str):
    # ... (código de atualização omitido)
    try:
        doc_ref = db.collection(COLECAO_AGENDAMENTOS).document(id_agendamento)
        doc_ref.update({'status': novo_status})
        return True
    except Exception as e:
        print(f"ERRO AO ATUALIZAR STATUS: {e}")
        return False
        
def buscar_agendamento_por_id(id_agendamento: str):
    # ... (código de busca por id omitido)
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
