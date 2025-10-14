# database.py 
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
        # AQUI é onde ele LÊ o que você COLOU na tela Secrets
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        
        # Cria e retorna o cliente Supabase
        return create_client(url, key)
    except KeyError:
        st.error("Erro de Configuração: As chaves 'url' ou 'key' do Supabase não foram encontradas no st.secrets. Verifique o formato TOML.")
        st.stop() 
    except Exception as e:
        st.error(f"Erro de Conexão com Supabase. Verifique a URL/KEY. Erro: {e}")
        st.stop()
        
# Variável de conexão Supabase
supabase: Client = init_supabase()
TABELA_AGENDAMENTOS = "agendamentos"


# --- Funções de Operação no Banco de Dados ---

def salvar_agendamento(dados: dict, token: str):
    """Cria um novo agendamento no DB Supabase."""
    
    data_para_salvar = {
        'token_unico': token,
        'profissional': dados['profissional'],
        'cliente': dados['cliente'],
        'telefone': dados['telefone'],
        'horario': dados['horario'].isoformat(), # Converte datetime para string ISO
        'status': "Confirmado",
        'is_pacote_sessao': False 
    }
    
    if supabase:
        # Insere dados na tabela 'agendamentos'
        response = supabase.table(TABELA_AGENDAMENTOS).insert(data_para_salvar).execute()
        # O Streamlit Cloud pode mostrar um erro se a tabela não tiver sido criada corretamente!
        if response.data:
            return response.data
    return None

def buscar_agendamento_por_token(token: str):
    """Busca um agendamento específico usando o token de segurança."""
    if supabase:
        response = supabase.table(TABELA_AGENDAMENTOS).select("*").eq("token_unico", token).execute()
        
        if response.data:
            # Converte a string de horário de volta para datetime
            data = response.data[0]
            data['horario'] = datetime.fromisoformat(data['horario'].replace('Z', '+00:00')) # Trata o formato ISO 8601
            return data
    return None

def buscar_todos_agendamentos():
    """Busca todos os agendamentos no DB."""
    if supabase:
        # ORDER BY para obter dados organizados
        response = supabase.table(TABELA_AGENDAMENTOS).select("*").order("horario").execute()
        if response.data:
            df = pd.DataFrame(response.data)
            df['horario'] = pd.to_datetime(df['horario'])
            return df
    return pd.DataFrame()

def atualizar_status_agendamento(id_agendamento: int, novo_status: str):
    """Atualiza o status de um agendamento específico."""
    if supabase:
        # O ID deve ser o ID da linha no Supabase
        response = supabase.table(TABELA_AGENDAMENTOS).update({"status": novo_status}).eq("id", id_agendamento).execute()
        return response.data
    return None
