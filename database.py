# database.py (VERSÃO FINAL DE COMPATIBILIDADE)

import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit.connections import SQLConnection
from postgrest import APIError # Importa APIError para tratamento de exceções

# --- Inicialização da Conexão PostgreSQL (Supabase) ---
@st.cache_resource
def get_connection() -> SQLConnection:
    """Obtém a conexão SQL, construindo a URI a partir dos secrets do Supabase."""
    try:
        # 1. Lendo os secrets no formato que você tem
        supabase_url = st.secrets["supabase"]["url"]
        db_password = st.secrets["supabase"]["password"] # <-- LÊ O NOVO CAMPO PASSWORD
        
        # 2. Processando a URL para obter o host (ex: db.projeto.supabase.co)
        # O host é a URL sem o prefixo HTTPS
        host_db = supabase_url.replace("https://", "").split("/")[0]

        # 3. Montando a URI de conexão PostgreSQL nativa
        # Assume user/database 'postgres' e porta 5432 (padrão Supabase)
        db_uri = f"postgresql://postgres:{db_password}@{host_db}:5432/postgres"

        # 4. Conecta usando a URI construída
        conn = st.connection("sql_postgres", type="sql", url=db_uri) 
        return conn
    except KeyError:
        st.error("Erro Crítico: Verifique se 'url' e 'password' estão na seção [supabase] nos seus Secrets.")
        st.stop()
    except Exception as e:
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
            
            # Limpa o timezone para compatibilidade com o app.py
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
