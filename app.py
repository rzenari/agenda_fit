import streamlit as st
from datetime import datetime, time
import pandas as pd
import random

# Importa as lógicas e o NOVO DB Supabase de forma segura com parênteses
from database import (
    salvar_agendamento, 
    buscar_agendamento_por_token, 
    buscar_todos_agendamentos
)
from logica_negocio import (
    gerar_token_unico, 
    horario_esta_disponivel, 
    processar_cancelamento_seguro, 
    get_relatorio_no_show, 
    buscar_agendamentos_hoje
)


# --- Configuração ---
st.set_page_config(layout="wide", page_title="Agenda Fit - Agendamento Inteligente")
PROFISSIONAIS = ["Dr. João (Físio)", "Dra. Maria (Pilates)", "Dr. Pedro (Nutrição)"]

# Inicialização do DB (Chamando a função segura via cache_resource)
@st.cache_resource
def setup_database():
    """Chama a função de inicialização do DB."""
    # A função init_supabase está dentro do database.py e é chamada aqui
    from database import init_supabase 
    return init_supabase()

db_client = setup_database()
if db_client is None:
    st.stop() # Para o aplicativo se a conexão com o Supabase falhar


# --- ROTEAMENTO E PARÂMETROS ---
token_param = st.query_params.get("token", [None])[0]


# --- FUNÇÕES DE RENDERIZAÇÃO ---

def render_agendamento_seguro():
    """Renderiza a tela de cancelamento/remarcação via token (Módulo I - Cliente)."""
    st.title("🔒 Gestão do seu Agendamento")
    
    token = st.query_params.get("token", [None])[0]
    
    if not token:
        st.error("Token de acesso não fornecido. Acesse pelo link exclusivo enviado.")
        return

    # Busca o agendamento no DB Supabase
    agendamento = buscar_agendamento_por_token(token)
    
    if agendamento and agendamento['status'] == "Confirmado":
        st.info(f"Seu agendamento com {agendamento['profissional']} está CONFIRMADO para:")
        st.subheader(f"{agendamento['horario'].strftime('%d/%m/%Y')} às {agendamento['horario'].strftime('%H:%M')}")
        st.caption(f"Cliente: {agendamento['cliente']} | Status Atual: {agendamento['status']}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("❌ CANCELAR AGENDAMENTO", use_container_width=True, type="primary"):
                if processar_cancelamento_seguro(token):
                    st.success("Agendamento cancelado com sucesso. O horário foi liberado para outro cliente.")
                    st.toast("Consulta cancelada!")
                    st.rerun() 
                else:
                    st.error("Erro ao cancelar. Tente novamente ou contate o profissional.")

        with col2:
             st.button("🔄 REMARCAR (Em Breve)", use_container_width=True, disabled=True)
             
    elif agendamento:
        st.warning(f"Este agendamento já está: {agendamento['status']}. Não é possível alterar online.")
    else:
        st.error("Token de agendamento inválido ou expirado. Por favor, contate o profissional.")


def render_backoffice_admin():
    """Renderiza a tela de gestão do profissional (Módulo II - Admin)."""
    
    # --- Login simples para MVP ---
    st.sidebar.header("Login (Admin)")
    senha = st.sidebar.text_input("Senha", type="password")
    if senha != "1234":
        st.warning("Acesso restrito ao profissional. Senha de teste: 1234")
        return

    st.sidebar.success("Login como Administrador")

    # --- Navegação do Admin ---
    tab1, tab2, tab3 = st.tabs(["Agenda Hoje/Manual", "Relatórios e Faltas", "Configuração (Pacotes)"])

    # --- TAB 1: Agendamento Manual e Agenda do Dia ---
    with tab1:
        st.header("📝 Agendamento Rápido e Manual")
        
        with st.form("admin_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                cliente = st.text_input("Nome do Cliente:", key="c_nome")
                telefone = st.text_input("Telefone (para link gestão):", key="c_tel")
            with col2:
                profissional = st.selectbox("Profissional:", PROFISSIONAIS, key="c_prof")
                data_consulta = st.date_input("Data:", datetime.today(), key="c_data")
            with col3:
                hora_consulta = st.time_input("Hora:", time(9, 0), step=1800, key="c_hora")
                submitted = st.form_submit_button("AGENDAR NOVA SESSÃO", type="primary")

            if submitted and cliente:
                dt_consulta = datetime.combine(data_consulta, hora_consulta)
                
                # Checagem de disponibilidade
                if horario_esta_disponivel(profissional, dt_consulta):
                    token = gerar_token_unico()
                    dados = {'profissional': profissional, 'cliente': cliente, 'telefone': telefone, 'horario': dt_consulta}
                    
                    if salvar_agendamento(dados, token):
                        st.success(f"Consulta agendada para {cliente}.")
                        
                        # Gerando o link de gestão para o profissional enviar
                        link_base = f"https://agendafit.streamlit.app" # Substituir pelo seu link real
                        link_gestao = f"{link_base}?token={token}"
                        
                        st.markdown(f"**LINK DE GESTÃO PARA O CLIENTE:** `{link_gestao}`")
                        st.rerun() # Recarrega a tela para atualizar a agenda
                    else:
                        st.error("Erro ao salvar no banco de dados. Verifique a conexão do Supabase.")
                else:
                    st.error("Horário já ocupado! Tente outro.")
        
        st.subheader("Agenda de Hoje")
        agenda_hoje = buscar_agendamentos_hoje()
        
        if not agenda_hoje.empty:
            df_agenda = agenda_hoje[['horario', 'cliente', 'profissional', 'status']].copy()
            df_agenda['Hora'] = df_agenda['horario'].dt.strftime('%H:%M')
            st.dataframe(df_agenda[['Hora', 'cliente', 'profissional', 'status']], use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma consulta confirmada para hoje.")

    # --- TAB 2: Relatórios e Faltas ---
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
            col2.metric("Total de Sessões Ocorridas/Faltadas", total_atendimentos)

            st.dataframe(df_relatorio.rename(columns={
                'total_atendimentos': 'Total Sessões', 
                'total_faltas': 'Faltas', 
                'total_cancelados': 'Cancelados',
                'total_finalizados': 'Finalizados',
                'Taxa No-Show (%)': 'Taxa Falta (%)'
            }), use_container_width=True, hide_index=True)

            st.bar_chart(df_relatorio.set_index('profissional')['Taxa No-Show (%)'])
        else:
            st.info("Ainda não há dados suficientes de sessões para gerar relatórios.")

    # --- TAB 3: Configuração e Pacotes ---
    with tab3:
        st.header("⚙️ Gestão de Pacotes e Otimização")
        st.warning("Funcionalidades avançadas em desenvolvimento. Necessita de uma tabela 'pacotes' no Supabase.")
        st.markdown("""
        **Otimizador de Pacotes:**
        1.  Gerenciar quantos créditos o cliente tem (Ex: 10/12 sessões).
        2.  Disparar alertas automáticos (Notificações) para renovação na 9ª sessão.
        """)


# --- RENDERIZAÇÃO PRINCIPAL ---

if token_param:
    render_agendamento_seguro()
else:
    render_backoffice_admin()
