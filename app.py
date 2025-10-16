# app.py (VERSÃO COM REMARCAÇÃO E CANCELAMENTO EM MASSA)

import streamlit as st
from datetime import datetime, time, date, timedelta
import pandas as pd
import random
from zoneinfo import ZoneInfo

# IMPORTAÇÕES CORRETAS
from database import (
    get_firestore_client, salvar_agendamento, buscar_agendamento_por_pin,
    buscar_todos_agendamentos, atualizar_horario_agendamento
)
from logica_negocio import (
    gerar_token_unico, horario_esta_disponivel, processar_cancelamento_seguro,
    get_relatorio_no_show, acao_admin_agendamento, buscar_agendamentos_hoje,
    processar_remarcacao
)


# --- Configuração ---
st.set_page_config(layout="wide", page_title="Agenda Fit - Agendamento Inteligente")
PROFISSIONAIS = ["Dr. João (Físio)", "Dra. Maria (Pilates)", "Dr. Pedro (Nutrição)"]
TZ_SAO_PAULO = ZoneInfo('America/Sao_Paulo')

# Inicialização do DB
db_client = get_firestore_client()
if db_client is None:
    st.stop()


# --- INICIALIZAÇÃO DO SESSION STATE ---
if 'last_agendamento_info' not in st.session_state:
    st.session_state.last_agendamento_info = None
if 'remarcando' not in st.session_state:
    st.session_state.remarcando = False
if 'agendamentos_selecionados' not in st.session_state:
    st.session_state.agendamentos_selecionados = {}


# --- FUNÇÕES DE CALLBACK ---
def handle_agendamento_submission():
    cliente = st.session_state.c_nome_input
    profissional = st.session_state.c_prof_input
    data_consulta = st.session_state.c_data_input
    hora_consulta = st.session_state.c_hora_input

    if not cliente:
        st.warning("Nome do cliente é obrigatório.")
        return

    dt_consulta_naive = datetime.combine(data_consulta, hora_consulta)
    dt_consulta_local = dt_consulta_naive.replace(tzinfo=TZ_SAO_PAULO)

    if horario_esta_disponivel(profissional, dt_consulta_local):
        pin_code = gerar_token_unico()
        dados = {'profissional': profissional, 'cliente': cliente, 'telefone': st.session_state.c_tel_input, 'horario': dt_consulta_local}
        resultado = salvar_agendamento(dados, pin_code)

        if resultado is True:
            link_gestao = f"https://agendafit.streamlit.app?pin={pin_code}"
            st.session_state.last_agendamento_info = {'cliente': cliente, 'link_gestao': link_gestao, 'status': True}
            # Limpa campos
            st.session_state.c_nome_input, st.session_state.c_tel_input = "", ""
        else:
            st.session_state.last_agendamento_info = {'status': str(resultado)}
    else:
        st.session_state.last_agendamento_info = {'status': "Horário já ocupado! Tente outro."}
    st.rerun()

def handle_remarcar_confirmacao(pin, agendamento_id):
    nova_data = st.session_state.nova_data_remarcacao
    nova_hora = st.session_state.nova_hora_remarcacao
    novo_horario_naive = datetime.combine(nova_data, nova_hora)
    novo_horario_local = novo_horario_naive.replace(tzinfo=TZ_SAO_PAULO)

    sucesso, mensagem = processar_remarcacao(pin, agendamento_id, novo_horario_local)

    if sucesso:
        st.success(mensagem)
        st.session_state.remarcando = False
    else:
        st.error(mensagem)
    st.rerun()

def handle_cancelar_selecionados():
    ids_para_cancelar = [ag_id for ag_id, selecionado in st.session_state.agendamentos_selecionados.items() if selecionado]
    if not ids_para_cancelar:
        st.warning("Nenhum agendamento selecionado.")
        return

    sucessos = 0
    for ag_id in ids_para_cancelar:
        if acao_admin_agendamento(ag_id, "cancelar"):
            sucessos += 1
    
    st.success(f"{sucessos} de {len(ids_para_cancelar)} agendamentos cancelados com sucesso.")
    st.session_state.agendamentos_selecionados = {} # Limpa a seleção
    st.rerun()


# --- RENDERIZAÇÃO DAS PÁGINAS ---
def render_agendamento_seguro():
    st.title("🔒 Gestão do seu Agendamento")
    pin = st.query_params.get("pin")

    if not pin:
        st.error("Link inválido ou PIN não fornecido.")
        return

    agendamento = buscar_agendamento_por_pin(pin)

    if not agendamento:
        st.error("PIN de agendamento inválido ou expirado.")
        return

    if agendamento['status'] != "Confirmado":
        st.warning(f"Este agendamento já se encontra com o status: **{agendamento['status']}**.")
        return
    
    st.info(f"Seu agendamento com **{agendamento['profissional']}** está CONFIRMADO para:")
    st.subheader(f"{agendamento['horario'].strftime('%d/%m/%Y')} às {agendamento['horario'].strftime('%H:%M')}")
    st.caption(f"Cliente: {agendamento['cliente']}")
    st.markdown("---")

    if st.session_state.remarcando:
        with st.form("form_remarcacao"):
            st.subheader("Selecione o novo horário")
            col1, col2 = st.columns(2)
            col1.date_input("Nova data", key="nova_data_remarcacao", min_value=date.today())
            col2.time_input("Nova hora", key="nova_hora_remarcacao", step=timedelta(minutes=30))
            
            st.form_submit_button("✅ Confirmar Remarcação", on_click=handle_remarcar_confirmacao, args=(pin, agendamento['id']), use_container_width=True)
        if st.button("Cancelar Remarcação", use_container_width=True):
            st.session_state.remarcando = False
            st.rerun()
    else:
        col1, col2 = st.columns(2)
        if col1.button("❌ CANCELAR AGENDAMENTO", use_container_width=True, type="primary"):
            if processar_cancelamento_seguro(pin):
                st.success("Agendamento cancelado com sucesso.")
                st.balloons()
            else:
                st.error("Erro ao cancelar.")
        
        if col2.button("🔄 REMARCAR HORÁRIO", use_container_width=True):
            st.session_state.remarcando = True
            st.rerun()

def render_backoffice_admin():
    st.sidebar.header("Login (Admin)")
    if st.sidebar.text_input("Senha", type="password") != "1234":
        st.warning("Acesso restrito.")
        return
    st.sidebar.success("Login como Administrador")

    tab1, tab2 = st.tabs(["Agenda e Agendamento", "Relatórios"])
    with tab1:
        st.header("📝 Agendamento Rápido e Manual")
        if st.session_state.get('last_agendamento_info'):
            info = st.session_state.last_agendamento_info
            if info.get('status'):
                st.success(f"Agendado para {info['cliente']} com sucesso!")
                st.markdown(f"**LINK DE GESTÃO:** `{info['link_gestao']}`")
            else:
                st.error(f"Erro: {info['status']}")
            st.session_state.last_agendamento_info = None

        with st.form("admin_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.text_input("Nome do Cliente:", key="c_nome_input")
                st.text_input("Telefone:", key="c_tel_input")
            with col2:
                st.selectbox("Profissional:", PROFISSIONAIS, key="c_prof_input")
                st.date_input("Data:", key="c_data_input", min_value=date.today())
            with col3:
                st.time_input("Hora:", key="c_hora_input", step=timedelta(minutes=30))
                st.form_submit_button("AGENDAR NOVA SESSÃO", type="primary", on_click=handle_agendamento_submission)

        st.subheader("🗓️ Agenda de Hoje")
        agenda_hoje = buscar_agendamentos_hoje()

        if not agenda_hoje.empty:
            for index, row in agenda_hoje.iterrows():
                ag_id = row['id']
                if ag_id not in st.session_state.agendamentos_selecionados:
                    st.session_state.agendamentos_selecionados[ag_id] = False
                
                cols = st.columns([0.1, 0.8, 0.5, 0.5, 0.5])
                selecionado = cols[0].checkbox("", key=f"select_{ag_id}", value=st.session_state.agendamentos_selecionados[ag_id])
                st.session_state.agendamentos_selecionados[ag_id] = selecionado
                
                cols[1].write(f"**{row['cliente']}** ({row['horario'].strftime('%H:%M')})")
                cols[2].button("✅", key=f"finish_{ag_id}", on_click=handle_admin_action, args=(ag_id, "finalizar"), help="Sessão Concluída")
                cols[3].button("🚫", key=f"noshow_{ag_id}", on_click=handle_admin_action, args=(ag_id, "no-show"), help="Marcar Falta")
                cols[4].button("❌", key=f"cancel_{ag_id}", on_click=handle_admin_action, args=(ag_id, "cancelar"), help="Cancelar Agendamento")
            
            st.markdown("---")
            if any(st.session_state.agendamentos_selecionados.values()):
                st.button("❌ Cancelar Selecionados", type="primary", on_click=handle_cancelar_selecionados)
        else:
            st.info("Nenhuma consulta confirmada para hoje.")
    with tab2:
        st.header("📈 Relatórios de Faltas (No-Show)")
        df_relatorio = get_relatorio_no_show()
        if not df_relatorio.empty:
            st.dataframe(df_relatorio)
        else:
            st.info("Ainda não há dados para gerar relatórios.")


# --- ROTEAMENTO PRINCIPAL ---
pin_param = st.query_params.get("pin")
if pin_param:
    render_agendamento_seguro()
else:
    render_backoffice_admin()

