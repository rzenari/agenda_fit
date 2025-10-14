# database.py (VERSÃO FINAL PARA GOOGLE FIRESTORE)

import streamlit as st
import pandas as pd
from datetime import datetime
import json # Necessário para decodificar a string JSON
from google.cloud import firestore

# --- Inicialização da Conexão (Sem problemas de porta/firewall) ---
@st.cache_resource
def get_firestore_client():
    """
    Inicializa o cliente Firestore lendo a Service Account como uma string JSON inteira.
    Isso contorna o problema de caracteres inválidos do parser TOML.
    """
    try:
        # AQUI É A MUDANÇA: Leitura da string JSON completa
        # A chave DEVE ser chamada 'json_key_string' no Streamlit Secrets
        json_credenciais = st.secrets["firestore"]["json_key_string"]
        
        # O Python decodifica a string LIDA DO SECRETS para um objeto JSON (dicionário)
        credenciais_dict = json.loads(json_credenciais)

        # Usa o dicionário decodificado para autenticar
        return firestore.Client.from_service_account_info(credenciais_dict)
    except KeyError:
        st.error("Erro Crítico: O campo 'json_key_string' está faltando na seção [firestore] dos Secrets.")
        st.stop()
    except json.JSONDecodeError as e:
        st.error(f"Erro de formato JSON. Falha ao decodificar a chave privada. Verifique as quebras de linha na Private Key. Detalhe: {e}")
        st.stop()
    except Exception as e:
        st.error(f"Erro ao conectar ao Google Firestore. Detalhe: {e}")
        st.stop()

db = get_firestore_client()
COLECAO_AGENDAMENTOS = "agendamentos"


# --- Funções de Operação no Banco de Dados (Refatoradas para NoSQL) ---

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
        db.collection(COLECAO_AGENDAMENTOS).add(data_para_salvar)
        return True
    except Exception as e:
        print(f"ERRO AO SALVAR NO FIRESTORE: {e}")
        return False

def buscar_agendamento_por_pin(pin_code: str):
    """Busca um agendamento pelo PIN (Query NoSQL)."""
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
    """Busca todos os agendamentos e retorna um DataFrame."""
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
    """Atualiza o status de um agendamento específico (usa ID de documento)."""
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
