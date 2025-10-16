# database.py (VERSÃO FINAL COM DIAGNÓSTICO DE CREDENCIAIS)

import streamlit as st
import pandas as pd
from datetime import datetime, time, date
import json 
from google.cloud import firestore

# --- Inicialização da Conexão ---
@st.cache_resource
def get_firestore_client():
    """
    Inicializa o cliente Firestore lendo a Service Account como uma string JSON inteira.
    Faz diagnóstico se a autenticação falhar.
    """
    try:
        # 1. Leitura da string JSON completa
        json_credenciais = st.secrets["firestore"]["json_key_string"]
        credenciais_dict = json.loads(json_credenciais)

        # 2. DEBUG CRÍTICO: Imprime no console se o project_id está sendo lido
        print(f"DEBUG: Project ID lido: {credenciais_dict.get('project_id', 'FALHA AO LER PROJECT ID')}")
        
        # 3. Usa o dicionário decodificado para autenticar
        return firestore.Client.from_service_account_info(credenciais_dict)
    except KeyError:
        st.error("Erro Crítico: O campo 'json_key_string' está faltando na seção [firestore] dos Secrets.")
        st.stop()
    except json.JSONDecodeError as e:
        st.error(f"Erro de formato JSON. Detalhe: {e}. Verifique as aspas/quebras de linha da Private Key nos Secrets.")
        st.stop()
    except Exception as e:
        # AQUI ESTÁ O TRATAMENTO DO ERRO DE AUTENTICAÇÃO DO GOOGLE
        st.error(f"Erro ao conectar ao Google Firestore. Motivo: Falha de autenticação. (Detalhe: {e})")
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
