# database.py (VERSÃO FINAL COM ISO EXPLÍCITO)

import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit.connections import SQLConnection
# A biblioteca Pandas é importada implicitamente pelo st.connection

# --- Inicialização da Conexão PostgreSQL (Supabase) ---
@st.cache_resource
def get_connection() -> SQLConnection:
    """Obtém a conexão SQL, construindo a URI a partir dos secrets do Supabase."""
    try:
        # Lendo os secrets (conforme o formato que você configurou)
        supabase_url = st.secrets["supabase"]["url"]
        db_password = st.secrets["supabase"]["password"] 
        db_port = st.secrets["supabase"].get("port_db", 5432)
        host_db = supabase_url.replace("https://", "").split("/")[0]
        
        # Montando a URI de conexão PostgreSQL nativa
        db_uri = f"postgresql://postgres:{db_password}@{host_db}:{db_port}/postgres"

        conn = st.connection("sql_postgres", type="sql", url=db_uri) 
        return conn
    except Exception as e:
        st.error(f"Erro ao conectar ao DB. Detalhe: {e}")
        st.stop()

# Variável de conexão
conn = get_connection()
TABELA_AGENDAMENTOS = "public.agendamentos"


# --- Funções de Operação no Banco de Dados ---

def salvar_agendamento(dados: dict, pin_code: str):
    """Cria um novo agendamento usando query SQL pura."""
    
    pin_code_str = str(pin_code)
    # CORREÇÃO CRÍTICA: FORÇAR O DATETIME PARA STRING ISO NO FORMATO SIMPLES DO SQL
    horario_sql = dados['horario'].strftime('%Y-%m-%d %H:%M:%S') 
    
    query = f"""
    INSERT INTO {TABELA_AGENDAMENTOS} (token_unico, profissional, cliente, telefone, horario, status, is_pacote_sessao)
    VALUES (%(token_unico)s, %(profissional)s, %(cliente)s, %(telefone)s, %(horario)s, %(status)s, %(is_pacote_sessao)s);
    """
    
    params = {
        'token_unico': pin_code_str,
        'profissional': dados['profissional'],
        'cliente': dados['cliente'],
        'telefone': dados['telefone'],
        'horario': horario_sql, # <--- ENVIADO COMO STRING SIMPLES
        'status': 'Confirmado',
        'is_pacote_sessao': False 
    }
    
    try:
        conn.query(query, params=params, ttl=0, write=True)
        return True
    except Exception as e:
        print(f"ERRO AO SALVAR: {e}")
        return False


def buscar_agendamento_por_pin(pin_code: str):
    """
    Busca um agendamento específico usando o PIN com query SQL pura.
    """
    pin_code_str = str(pin_code)
    query = f"""
    SELECT * FROM {TABELA_AGENDAMENTOS} WHERE token_unico = %(pin)s LIMIT 1;
    """
    
    try:
        df = conn.query(query, params={'pin': pin_code_str}, ttl=0)
        
        if not df.empty:
            data = df.iloc[0].to_dict()
            
            # Garante que o horário lido não tem timezone para compatibilidade
            if data['horario']:
                data['horario'] = data['horario'].replace(tzinfo=None)
            
            return data
    except Exception as e:
        print(f"ERRO NA BUSCA POR PIN: {e}")
    return None


def buscar_todos_agendamentos():
    """Busca todos os agendamentos no DB e retorna um DataFrame."""
    query = f"SELECT * FROM {TABELA_AGENDAMENTOS} ORDER BY horario;"
    try:
        df = conn.query(query, ttl=0)
        
        if 'horario' in df.columns:
            # Limpa o timezone para compatibilidade Naive
            df['horario'] = df['horario'].apply(lambda x: x.replace(tzinfo=None) if x else x)
            return df
    except Exception as e:
        print(f"ERRO NA BUSCA TOTAL: {e}")
    return pd.DataFrame()


def atualizar_status_agendamento(id_agendamento: int, novo_status: str):
    """Atualiza o status de um agendamento específico."""
    
    query = f"""
    UPDATE {TABELA_AGENDAMENTOS} SET status = %(status)s 
    WHERE id = %(id_agendamento)s;
    """
    params = {
        'status': novo_status,
        'id_agendamento': id_agendamento
    }
    
    try:
        conn.query(query, params=params, ttl=0, write=True)
        return True
    except Exception as e:
        print(f"ERRO AO ATUALIZAR STATUS: {e}")
        return False
        
def buscar_agendamento_por_id(id_agendamento: int):
    """Busca um agendamento pelo ID (usado pelo Admin para ações rápidas)."""
    query = f"""
    SELECT * FROM {TABELA_AGENDAMENTOS} WHERE id = %(id)s LIMIT 1;
    """
    try:
        df = conn.query(query, params={'id': id_agendamento}, ttl=0)
        if not df.empty:
            data = df.iloc[0].to_dict()
            if data['horario']:
                data['horario'] = data['horario'].replace(tzinfo=None)
            return data
    except Exception as e:
        print(f"ERRO NA BUSCA POR ID: {e}")
    return None
