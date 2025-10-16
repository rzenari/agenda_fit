# app.py (VERSÃO FINAL SEM DEBUG NA TELA)

import streamlit as st
from datetime import datetime, time, date, timedelta
import pandas as pd
import random

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

# Inicialização do DB (Chama o client Firestore)
db_client = get_firestore_client()
if db_client is None:
    st.stop() 


# --- ROTEAMENTO E PARÂMETROS ---
pin_param = st.query_params.get("pin", [None])[0]
if pin_param:
    pin_param = str(pin_param)


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

    dt_consulta = datetime.combine(data_consulta, hora_consulta)
    
    if horario_esta_disponivel(profissional, dt_consulta):
        pin_code = gerar_token_unico() 
        dados = {'profissional': profissional, 'cliente': cliente, 'telefone': telefone, 'horario': dt_consulta}
        
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
            
            st.session_state.c_nome_input = ""
            st.session_state.c_tel_input = ""
            st.session_state.c_data_input = datetime.today().date()
            st.session_state.c_hora_input = time(9, 0)
            
        else:
            st.session_state.last_agendamento_info = {
                'cliente': cliente,
                'status': str(resultado)
            }
    else:
        st.session_state.last_agendamento_info = {'status': "Horário já ocupado! Tente outro.", 'cliente': cliente}

    st.rerun()


# --- FUNÇÃO DE AÇÃO GLOBAL ---
def handle_admin_action(id_agendamento: str, acao):
    if acao_admin_agendamento(id_agendamento, acao):
        st.success(f"Ação '{acao.upper()}' registrada para o agendamento ID {id_agendamento}!")
        st.rerun()
    else:
        st.error("Falha ao registrar a ação no sistema.")


# --- FUNÇÕES DE RENDERIZAÇÃO ---

def render_agendamento_seguro():
    """Renderiza a tela de cancelamento/remarcação via PIN (Módulo I - Cliente)."""
    st.title("🔒 Gestão do seu Agendamento")
    
    pin = st.query_params.get("pin", [None])[0]

    if not pin:
        st.error("Link inválido. Acesse pelo link exclusivo enviado.")
        return

    agendamento = buscar_agendamento_por_pin(pin)
    
    if agendamento and agendamento['status'] == "Confirmado":
        st.info(f"Seu agendamento com {agendamento['profissional']} está CONFIRMADO para:")
        st.subheader(f"{agendamento['horario'].strftime('%d/%m/%Y')} às {agendamento['horario'].strftime('%H:%M')}")
        st.caption(f"Cliente: {agendamento['cliente']} | Status Atual: {agendamento['status']}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("❌ CANCELAR AGENDAMENTO", use_container_width=True, type="primary"):
                if processar_cancelamento_seguro(pin):
                    st.success("Agendamento cancelado com sucesso. O horário foi liberado para outro cliente.")
                    st.toast("Consulta cancelada!")
                    # Limpa o parâmetro da URL para evitar re-cancelamento no refresh
                    st.query_params.clear()
                    st.rerun() 
                else:
                    st.error("Erro ao cancelar. Tente novamente ou contate o profissional.")

        with col2:
                st.button("🔄 REMARCAR (Em Breve)", use_container_width=True, disabled=True)
            
    elif agendamento:
        st.warning(f"Este agendamento já está: {agendamento['status']}. Não é possível alterar online.")
    else:
        st.error("PIN de agendamento inválido ou expirado. Por favor, contate o profissional.")


def render_backoffice_admin():
    """Renderiza a tela de gestão do profissional (Módulo II - Admin)."""
    
    st.sidebar.header("Login (Admin)")
    senha = st.sidebar.text_input("Senha", type="password", key="admin_password")
    
    if senha != "1234":
        st.warning("Acesso restrito ao profissional. Senha de teste: 1234")
        st.session_state.last_agendamento_info = None 
        return

    st.sidebar.success("Login como Administrador")

    tab1, tab2, tab3 = st.tabs(["Agenda Hoje/Manual", "Relatórios e Faltas", "Configuração (Pacotes)"])

    with tab1:
        st.header("📝 Agendamento Rápido e Manual")
        
        if st.session_state.last_agendamento_info:
            info = st.session_state.last_agendamento_info
            
            if info.get('status') is True:
                st.success(f"Consulta agendada para {info['cliente']} com sucesso!")
                st.markdown(f"**LINK DE GESTÃO PARA O CLIENTE:** `{info['link_gestao']}`")
            elif info.get('status') is not None:
                st.error(f"Problema no Agendamento para {info.get('cliente', 'cliente não informado')}. Motivo: {info['status']}")
            
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
                st.time_input("Hora:", step=timedelta(minutes=30), key="c_hora_input")
                st.form_submit_button("AGENDAR NOVA SESSÃO", type="primary", on_click=handle_agendamento_submission)

        st.subheader("Agenda de Hoje")
        agenda_hoje = buscar_agendamentos_hoje()
        
        if not agenda_hoje.empty:
            df_agenda = agenda_hoje[['horario', 'cliente', 'profissional', 'status', 'id']].copy()
            df_agenda['Data'] = df_agenda['horario'].dt.strftime('%d/%m/%Y')
            df_agenda['Hora'] = df_agenda['horario'].dt.strftime('%H:%M')

            st.dataframe(df_agenda[['Data', 'Hora', 'cliente', 'profissional', 'status']], use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.write("**Ações Administrativas:**")

            for _, row in df_agenda.iterrows():
                cols = st.columns([0.4, 1.5, 1, 1, 1])
                cols[0].caption(f"ID: {row['id']}") 
                cols[1].write(f"**{row['cliente']}**")
                cols[2].button("✅ Concluída", key=f"finish_{row['id']}", on_click=handle_admin_action, args=(row['id'], "finalizar"), type="primary", use_container_width=True)
                cols[3].button("🚫 Falta", key=f"noshow_{row['id']}", on_click=handle_admin_action, args=(row['id'], "no-show"), use_container_width=True)
                cols[4].button("❌ Cancelar", key=f"cancel_{row['id']}", on_click=handle_admin_action, args=(row['id'], "cancelar"), use_container_width=True)
                st.markdown("---", unsafe_allow_html=True) 

        else:
            st.info("Nenhuma consulta confirmada para hoje.")

    with tab2:
        st.header("📈 Relatórios: Redução de Faltas (No-Show)")
        df_relatorio = get_relatorio_no_show()
        if not df_relatorio.empty:
            st.subheader("Taxa de No-Show Média vs. Profissional")
            total_atendimentos = df_relatorio['total_atendimentos'].sum()
            total_faltas = df_relatorio['total_faltas'].sum()
            taxa_media = (total_faltas / total_atendimentos) * 100 if total_atendimentos > 0 else 0
            col1, col2 = st.columns(2)
            col1.metric("Taxa Média de No-Show", f"{taxa_media:.2f}%")
            col2.metric("Total de Sessões Ocorridas/Faltadas", int(total_atendimentos))
            st.dataframe(df_relatorio.rename(columns={'total_atendimentos': 'Total Sessões', 'total_faltas': 'Faltas', 'total_cancelados': 'Cancelados', 'total_finalizados': 'Finalizados', 'Taxa No-Show (%)': 'Taxa Falta (%)'}), use_container_width=True, hide_index=True)
            st.bar_chart(df_relatorio.set_index('profissional')['Taxa No-Show (%)'])
        else:
            st.info("Ainda não há dados suficientes de sessões para gerar relatórios.")

    with tab3:
        st.header("⚙️ Gestão de Pacotes e Otimização")
        st.warning("Funcionalidades avançadas em desenvolvimento.")

# --- RENDERIZAÇÃO PRINCIPAL ---
if pin_param:
    render_agendamento_seguro()
else:
    render_backoffice_admin()

