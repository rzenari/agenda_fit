# database.py (VERSÃO FINAL E MAIS ESTÁVEL)

import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import pandas as pd
import uuid
import pendulum # Novo import para datas robustas

# --- Inicialização da Conexão ---
@st.cache_resource
def init_supabase() -> Client:
    """Inicializa e armazena o cliente Supabase usando st.secrets."""
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

def salvar_agendamento(dados: dict, token: str):
    """Cria um novo agendamento no DB Supabase."""
    
    # IMPORTANTE: Garante que a data/hora seja formatada como ISO 8601 (o formato que o DB espera)
    horario_iso = dados['horario'].isoformat()
    
    data_para_salvar = {
        'token_unico': token,
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

def buscar_agendamento_por_token(token: str):
    """
    Busca um agendamento específico usando o token de segurança.
    CORREÇÃO CRÍTICA: Converte o dado de volta de forma segura.
    """
    if supabase:
        # A busca por tokens DEVE estar funcionando com a chave correta.
        response = supabase.table(TABELA_AGENDAMENTOS).select("*").eq("token_unico", token).limit(1).execute()
        
        if response.data:
            data = response.data[0]
            
            # --- CORREÇÃO DE DATA/HORA ---
            # 1. Usa Pandas para converter a string do DB
            timestamp = pd.to_datetime(data['horario'])
            
            # 2. Converte para datetime nativo do Python, removendo qualquer informação de fuso horário.
            data['horario'] = timestamp.to_pydatetime().replace(tzinfo=None)
            
            return data
    return None

def buscar_todos_agendamentos():
    """Busca todos os agendamentos no DB e retorna um DataFrame."""
    if supabase:
        response = supabase.table(TABELA_AGENDAMENTOS).select("*").order("horario").execute()
        if response.data:
            df = pd.DataFrame(response.data)
            df['horario'] = pd.to_datetime(df['horario'])
            # CRÍTICO: Remove o timezone de todas as datas para garantir a comparação Naive
            df['horario'] = df['horario'].apply(lambda x: x.replace(tzinfo=None) if pd.notna(x) else x)
            return df
    return pd.DataFrame()

def atualizar_status_agendamento(id_agendamento: int, novo_status: str):
    """Atualiza o status de um agendamento específico."""
    if supabase:
        response = supabase.table(TABELA_AGENDAMENTOS).update({"status": novo_status}).eq("id", id_agendamento).execute()
        return response.data
    return None
