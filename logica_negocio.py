# logica_negocio.py (VERSÃO CORRIGIDA)

import uuid
from datetime import datetime, date, time, timedelta
import pandas as pd
import random

# Importações de funções de DB
from database import (
    buscar_todos_agendamentos,
    atualizar_status_agendamento,
    buscar_agendamento_por_pin,
    buscar_agendamento_por_id,
    buscar_agendamentos_por_intervalo # Importar a função correta
)

def gerar_token_unico():
    """Gera um código PIN numérico de 6 dígitos."""
    return str(random.randint(100000, 999999))

def horario_esta_disponivel(profissional: str, data_hora: datetime) -> bool:
    """Verifica se um horário está disponível, consultando todos os agendamentos."""
    df = buscar_todos_agendamentos()
    if df.empty:
        return True

    # Garante que a comparação seja feita com datetimes "naive" (sem fuso horário)
    data_hora_naive = data_hora.replace(tzinfo=None)

    # Procura por um agendamento conflitante (mesmo profissional, mesmo horário e já confirmado)
    conflito = df[
        (df['profissional'] == profissional) &
        (df['horario'] == data_hora_naive) &
        (df['status'] == "Confirmado") # Apenas status 'Confirmado' bloqueia o horário
    ]

    # Se o dataframe 'conflito' estiver vazio, significa que não há conflitos.
    return conflito.empty

def processar_cancelamento_seguro(pin_code: str) -> bool:
    """Processa o cancelamento de um agendamento a partir de um PIN."""
    agendamento = buscar_agendamento_por_pin(pin_code)

    if agendamento and agendamento['status'] == "Confirmado":
        return atualizar_status_agendamento(agendamento['id'], "Cancelado pelo Cliente")

    return False

def acao_admin_agendamento(agendamento_id: str, acao: str) -> bool:
    """Executa uma ação administrativa em um agendamento (cancelar, finalizar, no-show)."""
    status_map = {
        "cancelar": "Cancelado (Admin)",
        "finalizar": "Finalizado",
        "no-show": "No-Show",
    }
    novo_status = status_map.get(acao)

    if novo_status:
        return atualizar_status_agendamento(agendamento_id, novo_status)

    return False

def get_relatorio_no_show() -> pd.DataFrame:
    """Gera um relatório de faltas (No-Show) por profissional."""
    df = buscar_todos_agendamentos()

    if df.empty:
        return pd.DataFrame()

    # Garante que a coluna de horário seja do tipo datetime
    df['horario'] = pd.to_datetime(df['horario'])
    
    # Filtra apenas agendamentos que já deveriam ter ocorrido
    df = df[df['horario'].dt.date <= date.today()]

    df_grouped = df.groupby('profissional').agg(
        total_atendimentos=('status', 'size'),
        total_faltas=('status', lambda x: (x == 'No-Show').sum()),
        total_cancelados=('status', lambda x: (x.str.contains('Cancelado', case=False, na=False)).sum()),
        total_finalizados=('status', lambda x: (x == 'Finalizado').sum())
    ).reset_index()

    # Evita divisão por zero
    if not df_grouped.empty:
        df_grouped['Taxa No-Show (%)'] = (
            (df_grouped['total_faltas'] / df_grouped['total_atendimentos'].replace(0, 1)) * 100
        )
        return df_grouped.sort_values(by='Taxa No-Show (%)', ascending=False)
    
    return pd.DataFrame()


# --- CORREÇÃO PRINCIPAL APLICADA AQUI ---
def buscar_agendamentos_hoje():
    """
    Busca agendamentos para a data de hoje de forma eficiente.
    Esta é a implementação correta que filtra os dados diretamente no banco de dados,
    resolvendo o problema de a agenda não aparecer no site.
    """
    # 1. Define o intervalo de data para "hoje"
    hoje = date.today()
    start_of_day = datetime.combine(hoje, time.min)  # Hoje à 00:00:00
    end_of_day = start_of_day + timedelta(days=1)     # Amanhã à 00:00:00

    # 2. Usa a função de busca por intervalo para fazer a query no Firestore
    df_hoje = buscar_agendamentos_por_intervalo(start_of_day, end_of_day)

    # 3. Se o DataFrame do dia estiver vazio, retorna um DataFrame vazio
    if df_hoje.empty:
        return pd.DataFrame()

    # 4. Filtra o DataFrame para mostrar apenas agendamentos com status "Confirmado"
    #    Isso evita que consultas canceladas ou finalizadas apareçam na agenda.
    df_confirmados = df_hoje[df_hoje['status'] == 'Confirmado'].copy()

    # 5. Ordena os resultados por horário
    return df_confirmados.sort_values(by='horario')
