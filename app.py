import streamlit as st
from datetime import datetime, time, timedelta
import pandas as pd
import random

# Importa as suas lógicas e DB
from database import get_session, salvar_agendamento, buscar_agendamentos_hoje, Agendamento
from logica_negocio import gerar_token_unico, horario_esta_disponivel, processar_cancelamento_seguro, get_relatorio_no_show

# Inicializa o DB
iniciar_db = st.cache_resource(lambda: get_session())() # Cache do DB
# A chamada de iniciar_db() no cache_resource garante que o arquivo agenda.db seja criado.


# --- Configuração ---
st.set_page_config(layout="wide", page_title="Agenda Fit - Agendamento Inteligente")
PROFISSIONAIS = ["Dr. João (Físio)", "Dra. Maria (Pilates)", "Dr. Pedro (Nutrição)"]


# --- Lógica de Roteamento Simples ---
page = st.query_params.get("page", "admin")
token_param = st.query_params.get("token", None)

# --- FUNÇÕES DE RENDERIZAÇÃO ---

def render_agendamento_seguro():
    """Renderiza a tela de cancelamento/remarcação via token (Módulo I - Cliente)."""
    st.title("🔒 Gestão do seu Agendamento")
    
    # Usa a sessão do DB
    session = get_session() 
    agendamento = buscar_agendamento_por_token(session, token_param)
    
    if agendamento and agendamento.status == "Confirmado":
        st.info(f"Seu agendamento com {agendamento.profissional} está CONFIRMADO para:")
        st.subheader(f"{agendamento.horario.strftime('%d/%m/%Y')} às {agendamento.horario.strftime('%H:%M')}")
        st.caption(f"Status Atual: {agendamento.status}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("❌ CANCELAR AGENDAMENTO", use_container_width=True, type="primary"):
                # Chama a lógica de segurança do logica_negocio.py
                if processar_cancelamento_seguro(token_param):
                    st.success("Agendamento cancelado com sucesso. O horário foi liberado para outro cliente.")
                    st.balloons()
                else:
                    st.error("Erro ao cancelar. Tente novamente ou contate o profissional.")

        with col2:
             # A remarcação exige mais lógica de UI, por isso fica desabilitada no MVP
             st.button("🔄 REMARCAR (Em Breve)", use_container_width=True, disabled=True)
             
    elif agendamento and agendamento.status != "Confirmado":
        st.warning(f"Este agendamento já está: {agendamento.status}.")
    else:
        st.error("Link inválido ou agendamento não encontrado.")
        
    session.close()


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
                hora_consulta = st.time_input("Hora:", time(9, 0), step=1800, key="c_hora") # Intervalo de 30min
                submitted = st.form_submit_button("AGENDAR NOVA SESSÃO", type="primary")

            if submitted and cliente:
                dt_consulta = datetime.combine(data_consulta, hora_consulta)
                session = get_session()
                
                if horario_esta_disponivel(session, profissional, dt_consulta):
                    token = gerar_token_unico()
                    dados = {'profissional': profissional, 'cliente': cliente, 'telefone': telefone, 'horario': dt_consulta}
                    salvar_agendamento(session, dados, token)
                    st.success(f"Consulta agendada para {cliente}. Token: {token}")
                    st.info(f"Link de Gestão: {st.experimental_get_query_params().get('url', [''])[0]}?token={token}")
                else:
                    st.error("Horário já ocupado ou conflito na agenda. Tente outro.")
                session.close()

        st.subheader("Agenda de Hoje")
        session = get_session()
        agenda_hoje = buscar_agendamentos_hoje(session)
        session.close()
        
        if agenda_hoje:
            df_agenda = pd.DataFrame([
                {'Hora': item.horario.strftime('%H:%M'), 
                 'Cliente': item.cliente, 
                 'Profissional': item.profissional, 
                 'Status': item.status} 
                for item in agenda_hoje
            ])
            st.dataframe(df_agenda, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma consulta confirmada para hoje.")

    # --- TAB 2: Relatórios e Faltas (O Poder do Python/Pandas) ---
    with tab2:
        st.header("📈 Relatórios: Redução de Faltas (No-Show)")
        
        # Chama a função de alto valor do logica_negocio.py
        df_relatorio = get_relatorio_no_show()
        
        if not df_relatorio.empty:
            st.subheader("Taxa de No-Show por Profissional")
            # Exibição do KPI (Métrica principal)
            col1, col2 = st.columns(2)
            col1.metric("Taxa Média de No-Show", f"{df_relatorio['total_no_show'].sum() / df_relatorio['total_atendimentos'].sum():.2%}")
            col2.metric("Total de Faltas Registradas", df_relatorio['total_no_show'].sum())

            # Exibição do ranking por profissional
            st.dataframe(df_relatorio.rename(columns={
                'total_atendimentos': 'Total Sessões', 
                'total_no_show': 'Faltas', 
                'Taxa No-Show (%)': 'Taxa de Falta (%)'
            }), use_container_width=True, hide_index=True)

            # Otimização: Gráfico para visualizar a dor
            st.bar_chart(df_relatorio.set_index('profissional')['Taxa No-Show (%)'])
        else:
            st.info("Ainda não há dados suficientes para gerar relatórios.")


    # --- TAB 3: Configuração e Pacotes (Futuro) ---
    with tab3:
        st.header("⚙️ Gestão de Pacotes (MVP Simples)")
        st.info("Neste MVP, estamos focando no agendamento. O próximo passo será a gestão completa de créditos de sessões.")
        st.markdown("""
        **Próximos Passos (Funções a Adicionar):**
        1.  Formulário para registrar a compra de um **Pacote (10 sessões)**.
        2.  Lógica Python para consumir 1 crédito a cada sessão 'Finalizada'.
        3.  Alerta (via lógica Python) quando o cliente estiver na **última sessão** para renovação.
        """)

# --- RENDERIZAÇÃO PRINCIPAL ---

# 1. Se o parâmetro 'token' existir na URL, renderiza a tela segura do cliente.
if token_param:
    render_agendamento_seguro()

# 2. Se o parâmetro for 'admin' (ou padrão), renderiza o backoffice.
else:
    render_backoffice_admin()