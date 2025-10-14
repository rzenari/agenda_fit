# database.py (VERSÃO FINAL E MAIS ESTÁVEL)

import streamlit as st
import pandas as pd
from datetime import datetime
import uuid
import pendulum
# IMPORTANTE: A importação do SQLAlchemy não é mais necessária aqui, mas é no requirements.txt

from streamlit.connections import SQLConnection

# --- Inicialização da Conexão PostgreSQL (Supabase) ---
# Usamos st.connection com o nome 'postgresql' que deve estar configurado no secrets.toml
@st.cache_resource
def get_connection() -> SQLConnection:
    """Obtém a conexão SQL com o banco de dados Supabase (PostgreSQL)."""
    try:
        # st.connection busca as credenciais do secrets.toml e constrói a conexão
        conn = st.connection("postgresql", type="sql")
        return conn
    except Exception as e:
        # Esta é a mensagem de erro que você estava vendo, que agora será resolvida com a instalação do SQLAlchemy
        st.error(f"Erro ao conectar ao banco de dados (st.connection). Verifique a string de conexão no secrets.toml. Detalhe: {e}")
        st.stop()

# Variável de conexão
conn = get_connection()
TABELA_AGENDAMENTOS = "agendamentos"


# --- Funções de Operação no Banco de Dados ---
# [O restante do database.py permanece o mesmo, pois as funções são chamadas por conn.query]

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
    except Exception as e:
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


def buscar_todos_agendamentos():
    """Busca todos os agendamentos no DB e retorna um DataFrame."""
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
    """Atualiza o status de um agendamento específico."""
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
    """Busca um agendamento pelo ID (usado pelo Admin para ações rápidas)."""
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
