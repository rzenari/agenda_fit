# database.py (NOVO - USANDO SUPABASE)

import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import pandas as pd
import uuid

# --- Inicialização da Conexão ---
@st.cache_resource
def init_supabase() -> Client:
    """Inicializa e armazena o cliente Supabase usando st.secrets."""
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Erro ao conectar ao Supabase. Verifique seu secrets.toml e a URL/KEY. Erro: {e}")
        return None

# Variável de conexão Supabase
supabase: Client = init_supabase()
TABELA_AGENDAMENTOS = "agendamentos"


# --- Funções de Operação no Banco de Dados ---

def salvar_agendamento(dados: dict, token: str):
    """Cria um novo agendamento no DB Supabase."""
    
    # Prepara os dados no formato PostgreSQL/Supabase
    data_para_salvar = {
        'token_unico': token,
        'profissional': dados['profissional'],
        'cliente': dados['cliente'],
        'telefone': dados['telefone'],
        'horario': dados['horario'].isoformat(), # Converte datetime para string ISO
        'status': "Confirmado",
        'is_pacote_sessao': False # Valor padrão
    }
    
    if supabase:
        response = supabase.table(TABELA_AGENDAMENTOS).insert(data_para_salvar).execute()
        return response.data
    return None

def buscar_agendamento_por_token(token: str):
    """Busca um agendamento específico usando o token de segurança."""
    if supabase:
        response = supabase.table(TABELA_AGENDAMENTOS).select("*").eq("token_unico", token).execute()
        
        if response.data:
            # Converte a string de horário de volta para datetime
            data = response.data[0]
            data['horario'] = datetime.fromisoformat(data['horario'])
            return data
    return None

def buscar_todos_agendamentos():
    """Busca todos os agendamentos no DB."""
    if supabase:
        response = supabase.table(TABELA_AGENDAMENTOS).select("*").execute()
        if response.data:
            # Converte para DataFrame e os horários para datetime
            df = pd.DataFrame(response.data)
            df['horario'] = pd.to_datetime(df['horario'])
            return df
    return pd.DataFrame()

def atualizar_status_agendamento(id_agendamento: int, novo_status: str):
    """Atualiza o status de um agendamento específico."""
    if supabase:
        response = supabase.table(TABELA_AGENDAMENTOS).update({"status": novo_status}).eq("id", id_agendamento).execute()
        return response.data
    return None
