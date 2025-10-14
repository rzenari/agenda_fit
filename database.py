# database.py (VERSÃO FINAL COM REMOÇÃO DE POSTGREST)

import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit.connections import SQLConnection
# LINHA ABAIXO REMOVIDA: from postgrest import APIError 
# O código deve usar o bloco try...except genérico do Python


# --- Inicialização da Conexão PostgreSQL (Supabase) ---
@st.cache_resource
def get_connection() -> SQLConnection:
    """Obtém a conexão SQL, construindo a URI a partir dos secrets do Supabase."""
    try:
        # 1. Lendo os secrets (restante do código omitido)
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        
        # 2. Montando a URI (restante do código omitido)
        db_password = st.secrets["supabase"]["password"]
        host_db = url.replace("https://", "").split("/")[0]
        db_uri = f"postgresql://postgres:{db_password}@{host_db}:5432/postgres"

        # 3. Conecta usando a URI construída
        conn = st.connection("sql_postgres", type="sql", url=db_uri) 
        return conn
    except KeyError:
        st.error("Erro Crítico: Verifique se 'url' e 'password' estão na seção [supabase] nos seus Secrets.")
        st.stop()
    except Exception as e:
        # O tratamento de erro genérico continua
        st.error(f"Erro ao conectar ao DB. Detalhe: {e}")
        st.stop()

# Variável de conexão
conn = get_connection()
TABELA_AGENDAMENTOS = "agendamentos"


# --- Funções de Operação no Banco de Dados ---

def salvar_agendamento(dados: dict, pin_code: str):
    """Cria um novo agendamento usando query SQL pura."""
    
    pin_code_str = str(pin_code)
    horario_iso = dados['horario'].isoformat()
    
    query = f"""
    INSERT INTO {TABELA_AGENDAMENTOS} (token_unico, profissional, cliente, telefone, horario, status, is_pacote_sessao)
    VALUES ('{pin_code_str}', '{dados['profissional']}', '{dados['cliente']}', '{dados['telefone']}', '{horario_iso}', 'Confirmado', FALSE);
    """
    
    try:
        conn.query(query, ttl=0, write=True)
        return True
    except Exception as e: # Exceção genérica é suficiente
        print(f"ERRO AO SALVAR: {e}")
        return False


def buscar_agendamento_por_pin(pin_code: str):
    """
    Busca um agendamento específico usando o PIN com query SQL pura.
    """
    pin_code_str = str(pin_code)
    query = f"""
    SELECT * FROM {TABELA_AGENDAMENTOS} WHERE token_unico = '{pin_code_str}' LIMIT 1;
    """
    
    try:
        df = conn.query(query, ttl=0)
        
        if not df.empty:
            data = df.iloc[0].to_dict()
            
            if data['horario']:
                data['horario'] = data['horario'].replace(tzinfo=None)
            
            return data
    except Exception as e:
        print(f"ERRO NA BUSCA POR PIN: {e}")
    return None

# [O restante do database.py com as outras funções permanece o mesmo]
# ...
def buscar_todos_agendamentos():
    # [código omitido]
    query = f"SELECT * FROM {TABELA_AGENDAMENTOS} ORDER BY horario;"
    try:
        df = conn.query(query, ttl=0)
        if 'horario' in df.columns:
            df['horario'] = df['horario'].apply(lambda x: x.replace(tzinfo=None) if x else x)
            return df
    except Exception as e:
        print(f"ERRO NA BUSCA TOTAL: {e}")
    return pd.DataFrame()


def atualizar_status_agendamento(id_agendamento: int, novo_status: str):
    # [código omitido]
    query = f"""
    UPDATE {TABELA_AGENDAMENTOS} SET status = '{novo_status}' 
    WHERE id = {id_agendamento};
    """
    try:
        conn.query(query, ttl=0, write=True)
        return True
    except Exception as e:
        print(f"ERRO AO ATUALIZAR STATUS: {e}")
        return False
        
def buscar_agendamento_por_id(id_agendamento: int):
    # [código omitido]
    query = f"""
    SELECT * FROM {TABELA_AGENDAMENTOS} WHERE id = {id_agendamento} LIMIT 1;
    """
    try:
        df = conn.query(query, ttl=0)
        if not df.empty:
            data = df.iloc[0].to_dict()
            if data['horario']:
                data['horario'] = data['horario'].replace(tzinfo=None)
            return data
    except Exception as e:
        print(f"ERRO NA BUSCA POR ID: {e}")
    return None
