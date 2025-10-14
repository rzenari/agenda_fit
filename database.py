# database.py (CORRIGIDO PARA O NOME DA SEÇÃO SECRETS)

# ... (imports omitidas)

from streamlit.connections import SQLConnection

# --- Inicialização da Conexão PostgreSQL (Supabase) ---
@st.cache_resource
def get_connection() -> SQLConnection:
    """Obtém a conexão SQL, AGORA USANDO O NOME DA SEÇÃO SECRETS."""
    try:
        # ATUALIZAÇÃO CRÍTICA: Chamamos a conexão pelo novo nome genérico 'conexao_supabase'
        conn = st.connection("conexao_supabase", type="sql") 
        return conn
    except Exception as e:
        # Esta é a mensagem de erro que você estava vendo, que agora deve ser resolvida com o nome correto
        st.error(f"Erro ao conectar ao banco de dados (st.connection). Verifique a string de conexão no secrets.toml. Detalhe: {e}")
        st.stop()

# Variável de conexão
conn = get_connection()
TABELA_AGENDAMENTOS = "agendamentos"


# [O restante do código do database.py permanece o mesmo, pois as funções internas não mudaram.]

# ... (Funções salvar_agendamento, buscar_agendamento_por_pin, etc.)

def salvar_agendamento(dados: dict, pin_code: str):
    # [código omitido, permanece o mesmo]
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
    # [código omitido, permanece o mesmo]
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
    # [código omitido, permanece o mesmo]
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
    # [código omitido, permanece o mesmo]
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
    # [código omitido, permanece o mesmo]
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
