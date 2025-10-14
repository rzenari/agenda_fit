# database.py (VERSÃO FINAL com PIN Code)

import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import pandas as pd
import uuid

# --- Inicialização da Conexão ---
@st.cache_resource
def init_supabase() -> Client:
    # [Inicialização do Supabase omitida, permanece a mesma]
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        
        return create_client(url, key)
    except KeyError:
        st.error("Erro de Configuração: As chaves 'url' ou 'key' do Supabase não foram encontradas no st.secrets.")
        st.stop() 
    except Exception as e:
        st.error(f"Erro de Conexão com Supabase. Verifique a URL/KEY. Erro: {e}")
        st.stop()
        
supabase: Client = init_supabase()
TABELA_AGENDAMENTOS = "agendamentos"


# --- Funções de Operação no Banco de Dados ---

def salvar_agendamento(dados: dict, pin_code: str):
    """Cria um novo agendamento no DB Supabase usando o PIN."""
    
    horario_iso = dados['horario'].isoformat()
    
    data_para_salvar = {
        'token_unico': pin_code, # Usaremos a coluna token_unico para armazenar o PIN
        'profissional': dados['profissional'],
        'cliente': dados['cliente'],
        'telefone': dados['telefone'],
        'horario': horario_iso,
        'status': "Confirmado",
        'is_pacote_sessao': False 
    }
    
    if supabase:
        response = supabase.table(TABELA_AGENDAMENTOS).insert(data_para_salvar).execute()
        if response.data:
            return response.data
    return None

def buscar_agendamento_por_pin(pin_code: str):
    """
    Busca um agendamento específico usando o PIN.
    O PIN é mais simples e menos propenso a erros de tipagem.
    """
    if supabase:
        response = supabase.table(TABELA_AGENDAMENTOS).select("*").eq("token_unico", pin_code).limit(1).execute()
        
        if response.data:
            data = response.data[0]
            # Conversão robusta de data
            timestamp = pd.to_datetime(data['horario'])
            data['horario'] = timestamp.to_pydatetime().replace(tzinfo=None)
            
            return data
    return None

def buscar_todos_agendamentos():
    # [Função buscar_todos_agendamentos omitida, permanece a mesma]
    if supabase:
        response = supabase.table(TABELA_AGENDAMENTOS).select("*").order("horario").execute()
        if response.data:
            df = pd.DataFrame(response.data)
            df['horario'] = pd.to_datetime(df['horario'])
            df['horario'] = df['horario'].apply(lambda x: x.replace(tzinfo=None) if pd.notna(x) else x)
            return df
    return pd.DataFrame()

def atualizar_status_agendamento(id_agendamento: int, novo_status: str):
    """Atualiza o status de um agendamento específico (Usado pelo Admin)."""
    if supabase:
        response = supabase.table(TABELA_AGENDAMENTOS).update({"status": novo_status}).eq("id", id_agendamento).execute()
        return response.data
    return None

def buscar_agendamento_por_id(id_agendamento: int):
    """Busca um agendamento pelo ID (Usado pelo Admin para ações rápidas)."""
    if supabase:
        response = supabase.table(TABELA_AGENDAMENTOS).select("*").eq("id", id_agendamento).limit(1).execute()
        if response.data:
            return response.data[0]
    return None
