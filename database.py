# database.py (VERSÃO FINAL COM ST.CONNECTION)

import streamlit as st
import pandas as pd
from datetime import datetime, date
import uuid
import pendulum
from streamlit.connections import SQLConnection

# --- Inicialização da Conexão PostgreSQL (Supabase) ---
# Usamos st.connection com o nome 'postgresql' que deve estar configurado no secrets.toml
@st.cache_resource
def get_connection() -> SQLConnection:
    """Obtém a conexão SQL com o banco de dados Supabase (PostgreSQL)."""
    try:
        conn = st.connection("postgresql", type="sql")
        return conn
    except Exception as e:
        st.error(f"Erro ao conectar ao banco de dados (st.connection). Verifique a string de conexão no secrets.toml. Detalhe: {e}")
        st.stop()

# Variável de conexão
conn = get_connection()
TABELA_AGENDAMENTOS = "agendamentos"


# --- Funções de Operação no Banco de Dados ---

def salvar_agendamento(dados: dict, pin_code: str):
    """Cria um novo agendamento usando query SQL pura."""
    
    # 1. Garante que os dados estão limpos e prontos para a query
    pin_code_str = str(pin_code)
    horario_iso = dados['horario'].isoformat()
    
    # 2. Query SQL de inserção
    query = f"""
    INSERT INTO {TABELA_AGENDAMENTOS} (token_unico, profissional, cliente, telefone, horario, status, is_pacote_sessao)
    VALUES ('{pin_code_str}', '{dados['profissional']}', '{dados['cliente']}', '{dados['telefone']}', '{horario_iso}', 'Confirmado', FALSE);
    """
    
    try:
        # Executa a query sem retorno (write=True)
        conn.query(query, ttl=0, write=True)
        return True
    except Exception as e:
        print(f"ERRO AO SALVAR: {e}")
        return False


def buscar_agendamento_por_pin(pin_code: str):
    """
    Busca um agendamento específico usando o PIN com query SQL pura.
    SOLUÇÃO DO PROBLEMA: O SQL é mais confiável que a API do cliente.
    """
    pin_code_str = str(pin_code)
    query = f"""
    SELECT * FROM {TABELA_AGENDAMENTOS} WHERE token_unico = '{pin_code_str}' LIMIT 1;
    """
    
    try:
        # Executa a query e retorna o resultado
        df = conn.query(query, ttl=0)
        
        if not df.empty:
            data = df.iloc[0].to_dict()
            
            # Conversão da data (limpeza do timezone)
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
        df = conn.query(query, ttl=0) # ttl=0 garante que não usa cache
        
        # Limpa o timezone para compatibilidade com o resto do código Python
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
