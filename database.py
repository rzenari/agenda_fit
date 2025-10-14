# database.py (VERSÃO FINAL com ISO EXPLÍCITO)

import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit.connections import SQLConnection

# [Inicialização e Conexão Omitidas, permanecem as mesmas]
@st.cache_resource
def get_connection() -> SQLConnection:
    try:
        # [Código de inicialização]
        supabase_url = st.secrets["supabase"]["url"]
        db_password = st.secrets["supabase"]["password"] 
        db_port = st.secrets["supabase"].get("port_db", 5432)
        host_db = supabase_url.replace("https://", "").split("/")[0]
        db_uri = f"postgresql://postgres:{db_password}@{host_db}:{db_port}/postgres"

        conn = st.connection("sql_postgres", type="sql", url=db_uri) 
        return conn
    except Exception as e:
        st.error(f"Erro ao conectar ao DB. Detalhe: {e}")
        st.stop()

conn = get_connection()
TABELA_AGENDAMENTOS = "public.agendamentos"


# --- Funções de Operação no Banco de Dados ---

def salvar_agendamento(dados: dict, pin_code: str):
    """Cria um novo agendamento usando query SQL pura."""
    
    pin_code_str = str(pin_code)
    # AQUI ESTÁ A CORREÇÃO CRÍTICA: FORÇAR O DATETIME PARA STRING ISO NO FORMATO SQL
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
        'horario': horario_sql, # <--- ENVIADO COMO STRING CLARA
        'status': 'Confirmado',
        'is_pacote_sessao': False 
    }
    
    try:
        conn.query(query, params=params, ttl=0, write=True)
        return True
    except Exception as e:
        print(f"ERRO AO SALVAR: {e}")
        return False

# [As outras funções de busca e atualização permanecem as mesmas]
# ...
