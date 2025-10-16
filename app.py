# app.py (VERSÃO COM LEITURA DE PIN CORRIGIDA)

import streamlit as st
from datetime import datetime, time, date, timedelta
import pandas as pd
import random
from zoneinfo import ZoneInfo # BIBLIOTECA MODERNA DE FUSO HORÁRIO

# IMPORTAÇÕES CORRETAS
from database import (
    get_firestore_client, salvar_agendamento, buscar_agendamento_por_pin,
    buscar_todos_agendamentos, buscar_agendamento_por_id
)
from logica_negocio import (
    gerar_token_unico, horario_esta_disponivel, processar_cancelamento_seguro,
    get_relatorio_no_show, acao_admin_agendamento, buscar_agendamentos_hoje
)


# --- Configuração ---
st.set_page_config(layout="wide", page_title="Agenda Fit - Agendamento Inteligente")
PROFISSIONAIS = ["Dr. João (Físio)", "Dra. Maria (Pilates)", "Dr. Pedro (Nutrição)"]
TZ_SAO_PAULO = ZoneInfo('America/Sao_Paulo')

# Inicialização do DB (Chama o client Firestore)
db_client = get_firestore_client()
if db_client is None:
    st.stop()


# --- ROTEAMENTO E PARÂMETROS ---
# A leitura do PIN agora é feita dentro da função de renderização para maior robustez
pin_param = st.query_params.get("pin")


# Inicialização do Session State para persistir a mensagem
if 'last_agendamento_info' not in st.session_state:
    st.session_state.last_agendamento_info = None


# --- FUNÇÃO DE SALVAMENTO (Callback) ---
def handle_agendamento_submission():
    """Lógica de submissão do formulário, chamada no on_click."""

    cliente = st.session_state.c_nome_input
    telefone = st.session_state.c_tel_input
    profissional = st.session_state.c_prof_input
    data_consulta = st.session_state.c_data_input
    hora_consulta = st.session_state.c_hora_input

    st.session_state.last_agendamento_info = None

    if not cliente:
        st.session_state.last_agendamento_info = {'status': "Nome do cliente é obrigatório.", 'cliente': ''}
        st.rerun()
        return

    # Combina data/hora e atribui o fuso horário de São Paulo
    dt_consulta_naive = datetime.combine(data_consulta, hora_consulta)
    dt_consulta_local = dt_consulta_naive.replace(tzinfo=TZ_SAO_PAULO)

    if horario_esta_disponivel(profissional, dt_consulta_local):
        pin_code = gerar_token_unico()
        dados = {'profissional': profissional, 'cliente': cliente, 'telefone': telefone, 'horario': dt_consulta_local}

        resultado = salvar_agendamento(dados, pin_code)

        if resultado is True:
            link_base = "https://agendafit.streamlit.app"
            link_gestao = f"{link_base}?pin={pin_code}"

            st.session_state.last_agendamento_info = {
                'cliente': cliente,
                'pin_code': pin_code,
                'link_gestao': link_gestao,
                'status': True
            }

            # Limpa o formulário para o próximo agendamento
            st.session_state.c_nome_input = ""
            st.session_state.c_tel_input = ""
            st.session_state.c_data_input = datetime.now(TZ_SAO_PAULO).date()
            st.session_state.c_hora_input = time(9, 0)

        else:
            st.session_state.last_agendamento_info = {'status': str(resultado)}
    else:
        st.session_state.last_agendamento_info = {'status': "Horário já ocupado! Tente outro."}

    st.rerun()


# --- FUNÇÃO DE AÇÃO GLOBAL ---
def handle_admin_action(id_agendamento: str, acao):
    if acao_admin_agendamento(id_agendamento, acao):
        st.success(f"Ação '{acao.upper()}' registrada com sucesso!")
        st.rerun()
    else:
        st.error("Falha ao registrar a ação no sistema.")


# --- FUNÇÕES DE RENDERIZAÇÃO ---

def render_agendamento_seguro():
    """Renderiza a tela de cancelamento/remarcação via PIN."""
    st.title("🔒 Gestão do seu Agendamento")

    # MÉTODO DE LEITURA DE PIN MAIS ROBUSTO
    pin_values = st.query_params.get_all("pin")
    pin = pin_values[0] if pin_values else None


    # --- SEÇÃO DE DEBUG ---
    with st.expander("Informações de Debug (Clique para ver)"):
        st.write("Dicionário completo de `query_params`:", st.query_params)
        st.write(f"Lista de valores para a chave 'pin': `{pin_values}`")
        st.write(f"**PIN final lido da URL:** `{pin}` (Tipo: `{type(pin)}`)")
        agendamento_debug = buscar_agendamento_por_pin(pin)
        st.write("**Resultado da busca no Banco de Dados:**")
        st.json(agendamento_debug if agendamento_debug else {"status": "Nenhum agendamento encontrado com este PIN."})
    # --- FIM DA SEÇÃO DE DEBUG ---

    if not pin:
        st.error("Link inválido ou PIN não fornecido na URL.")
        return

    agendamento = buscar_agendamento_por_pin(pin)

    if agendamento and agendamento['status'] == "Confirmado":
        horario_local = agendamento['horario']
        st.info(f"Seu agendamento com {agendamento['profissional']} está CONFIRMADO para:")
        st.subheader(f"{horario_local.strftime('%d/%m/%Y')} às {horario_local.strftime('%H:%M')}")
        st.caption(f"Cliente: {agendamento['cliente']} | Status: {agendamento['status']}")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("❌ CANCELAR AGENDAMENTO", use_container_width=True, type="primary"):
                if processar_cancelamento_seguro(pin):
                    st.success("Agendamento cancelado com sucesso.")
                    st.toast("Consulta cancelada!")
                    st.query_params.clear()
                    st.rerun()
                else:
                    st.error("Erro ao cancelar. Tente novamente.")
        with col2:
            st.button("🔄 REMARCAR (Em Breve)", use_container_width=True, disabled=True)
    elif agendamento:
        st.warning(f"Este agendamento já se encontra com o status: **{agendamento['status']}**.")
    else:
        st.error("PIN de agendamento inválido ou expirado.")


def render_backoffice_admin():
    """Renderiza a tela de gestão do profissional."""
    st.sidebar.header("Login (Admin)")
    senha = st.sidebar.text_input("Senha", type="password", key="admin_password")

    if senha != "1234":
        st.warning("Acesso restrito ao profissional. Senha de teste: 1234")
        return

    st.sidebar.success("Login como Administrador")
    tab1, tab2 = st.tabs(["Agenda e Agendamento", "Relatórios"])

    with tab1:
        st.header("📝 Agendamento Rápido e Manual")
        if st.session_state.get('last_agendamento_info'):
            info = st.session_state.last_agendamento_info
            if info.get('status') is True:
                st.success(f"Agendamento para {info['cliente']} criado com sucesso!")
                st.markdown(f"**LINK DE GESTÃO:** `{info['link_gestao']}`")
            else:
                st.error(f"Erro no agendamento: {info['status']}")
            st.session_state.last_agendamento_info = None

        with st.form("admin_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.text_input("Nome do Cliente:", key="c_nome_input")
                st.text_input("Telefone (para link gestão):", key="c_tel_input")
            with col2:
                st.selectbox("Profissional:", PROFISSIONAIS, key="c_prof_input")
                st.date_input("Data:", key="c_data_input")
            with col3:
                st.time_input("Hora:", key="c_hora_input", step=timedelta(minutes=30))
                st.form_submit_button("AGENDAR NOVA SESSÃO", type="primary", on_click=handle_agendamento_submission)


        st.subheader("🗓️ Agenda de Hoje")
        agenda_hoje = buscar_agendamentos_hoje()

        if not agenda_hoje.empty:
            df_agenda = agenda_hoje[['horario', 'cliente', 'profissional', 'status', 'id']].copy()
            df_agenda['Data'] = df_agenda['horario'].dt.strftime('%d/%m/%Y')
            df_agenda['Hora'] = df_agenda['horario'].dt.strftime('%H:%M')
            st.dataframe(df_agenda[['Data', 'Hora', 'cliente', 'profissional', 'status']], use_container_width=True, hide_index=True)

            st.markdown("---")
            for _, row in df_agenda.iterrows():
                cols = st.columns([0.4, 1.5, 1, 1, 1])
                cols[0].caption(f"ID: {row['id']}")
                cols[1].write(f"**{row['cliente']}** ({row['horario'].strftime('%H:%M')})")
                cols[2].button("✅ Concluída", key=f"finish_{row['id']}", on_click=handle_admin_action, args=(row['id'], "finalizar"), type="primary", use_container_width=True)
                cols[3].button("🚫 Falta", key=f"noshow_{row['id']}", on_click=handle_admin_action, args=(row['id'], "no-show"), use_container_width=True)
                cols[4].button("❌ Cancelar", key=f"cancel_{row['id']}", on_click=handle_admin_action, args=(row['id'], "cancelar"), use_container_width=True)

        else:
            st.info("Nenhuma consulta confirmada para hoje.")

    with tab2:
        st.header("📈 Relatórios: Faltas (No-Show)")
        df_relatorio = get_relatorio_no_show()
        if not df_relatorio.empty:
            st.dataframe(df_relatorio)
        else:
            st.info("Não há dados suficientes para gerar relatórios.")


# --- RENDERIZAÇÃO PRINCIPAL ---
if pin_param:
    render_agendamento_seguro()
else:
    render_backoffice_admin()

