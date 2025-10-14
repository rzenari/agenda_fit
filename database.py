# database.py (VERSÃO FINAL COM PARÂMETROS SEGUROS)

import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit.connections import SQLConnection
from psycopg2.errors import UniqueViolation # Adicionando import para tratamento de erro específico

# [Inicialização da Conexão PostgreSQL e Variáveis Omitidas, permanecem as mesmas]
@st.cache_resource
def get_connection() -> SQLConnection:
    # [Código de inicialização omitido]
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        
        db_password = st.secrets["supabase"]["password"]
        host_db = url.replace("https://", "").split("/")[0]
        db_uri = f"postgresql://postgres:{db_password}@{host_db}:5432/postgres"

        conn = st.connection("sql_postgres", type="sql", url=db_uri) 
        return conn
    except Exception as e:
        st.error(f"Erro ao conectar ao DB. Detalhe: {e}")
        st.stop()

conn = get_connection()
TABELA_AGENDAMENTOS = "public.agendamentos" # Nome da tabela com schema


# --- Funções de Operação no Banco de Dados ---

def salvar_agendamento(dados: dict, pin_code: str):
    """Cria um novo agendamento usando parâmetros seguros."""
    
    query = f"""
    INSERT INTO {TABELA_AGENDAMENTOS} (token_unico, profissional, cliente, telefone, horario, status, is_pacote_sessao)
    VALUES (%(token_unico)s, %(profissional)s, %(cliente)s, %(telefone)s, %(horario)s, %(status)s, %(is_pacote_sessao)s);
    """
    
    params = {
        'token_unico': str(pin_code),
        'profissional': dados['profissional'],
        'cliente': dados['cliente'],
        'telefone': dados['telefone'],
        'horario': dados['horario'], # Envia o datetime; o adaptador cuida do formato SQL
        'status': 'Confirmado',
        'is_pacote_sessao': False 
    }
    
    try:
        # Executa a query com os parâmetros separados (write=True)
        conn.query(query, params=params, ttl=0, write=True)
        return True
    except Exception as e:
        print(f"ERRO AO SALVAR: {e}")
        return False


def buscar_agendamento_por_pin(pin_code: str):
    """Busca um agendamento específico usando parâmetros seguros."""
    
    query = f"""
    SELECT * FROM {TABELA_AGENDAMENTOS} WHERE token_unico = %(pin)s LIMIT 1;
    """
    
    try:
        # Executa a query com o parâmetro PIN
        df = conn.query(query, params={'pin': str(pin_code)}, ttl=0)
        
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
    # Query de SELECT não precisa de parâmetros, mas mantemos o tratamento de data
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
