# database.py (Versão Limpa após a Mudança de Tipo no Supabase)
import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import pandas as pd
import uuid

# [Inicialização do Supabase omitida, permanece a mesma]
@st.cache_resource
def init_supabase() -> Client:
    # ... (código de conexão com st.secrets)
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Erro de Conexão com Supabase. Verifique a URL/KEY. Erro: {e}")
        st.stop()
        
supabase: Client = init_supabase()
TABELA_AGENDAMENTOS = "agendamentos"


# --- Funções de Operação no Banco de Dados ---

# ... [salvar_agendamento e atualizar_status_agendamento permanecem iguais]

def buscar_agendamento_por_token(token: str):
    """Busca um agendamento específico usando o token de segurança."""
    if supabase:
        response = supabase.table(TABELA_AGENDAMENTOS).select("*").eq("token_unico", token).limit(1).execute()
        
        if response.data:
            data = response.data[0]
            
            # Converte a string de horário diretamente, sem manipulação de timezone
            data['horario'] = pd.to_datetime(data['horario']).to_pydatetime()
            
            return data
    return None

def buscar_todos_agendamentos():
    """Busca todos os agendamentos no DB e retorna um DataFrame."""
    if supabase:
        response = supabase.table(TABELA_AGENDAMENTOS).select("*").order("horario").execute()
        if response.data:
            df = pd.DataFrame(response.data)
            # Converte a coluna 'horario' sem manipulação complexa
            df['horario'] = pd.to_datetime(df['horario'])
            return df
    return pd.DataFrame()
