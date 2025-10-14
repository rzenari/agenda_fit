import streamlit as st
from datetime import datetime, time
import pandas as pd
import random

# Importa as suas lógicas e DB
# TODAS AS IMPORTAÇÕES ESTÃO AGORA CORRETAS
from database import get_session, salvar_agendamento, buscar_agendamentos_hoje, Agendamento, buscar_agendamento_por_token
from logica_negocio import gerar_token_unico, horario_esta_disponivel, processar_cancelamento_seguro, get_relatorio_no_show


# --- Inicialização ---
# Usamos st.cache_resource para garantir que a conexão com o DB e a criação da tabela
# ocorram apenas uma vez, otimizando o desempenho no Streamlit Cloud.
@st.cache_resource
def setup_database():
    """Chama a função de inicialização do DB."""
    return get_session()

# Chama o setup para garantir que o arquivo agenda.db seja criado/conectado
db_session = setup_database()

# --- Configuração ---
st.set_page_config(layout="wide", page_title="Agenda Fit - Agendamento Inteligente")
PROFISSIONAIS = ["Dr. João (Físio)", "Dra. Maria (Pilates)", "Dr. Pedro (Nutrição)"]


# --- FUNÇÕES DE RENDERIZAÇÃO ---

def render_agendamento_seguro():
    """Renderiza a tela de cancelamento/remarcação via token (Módulo I - Cliente)."""
    st.title("🔒 Gestão do seu Agendamento")
    
    token_param = st.query_params.get("token", [None])[0]
    
    if not token_param:
        st.warning("Token de acesso não fornecido. Acesse pelo link exclusivo enviado.")
        return

    # Busca o agendamento no DB
    agendamento = buscar_agendamento_por_token(db_session, token_param)
    
    if agendamento and agendamento.status == "Confirmado":
        st.info(f"Seu agendamento com {agendamento.profissional} está CONFIRMADO para:")
        st.subheader(f"{agendamento.horario.strftime('%d/%m/%Y')} às {agendamento.horario.strftime('%H:%M')}")
        st.caption(f"Cliente: {agendamento.cliente} | Status Atual: {agendamento.status}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("❌ CANCELAR AGENDAMENTO", use_container_width=True, type="primary"):
                # Chama a lógica de segurança
                if processar_cancelamento_seguro(token_param):
                    st.success("Agendamento cancelado com sucesso. Você está livre!")
                    st.toast("Consulta cancelada!")
                    st.rerun() # Recarrega para mostrar o status atualizado
                else:
                    st.error("Erro ao cancelar. Tente novamente ou contate o profissional.")

        with col2:
             st.button("🔄 REMARCAR (Em Breve)", use_container_width=True, disabled=True)
             
    elif agendamento:
        st.warning(f"Este agendamento já está: {agendamento.status}. Não é possível alterar online.")
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
                telefone = st.text_input("Telefone (Para link gestão):", key="c_tel")
            with col2:
                profissional = st.selectbox("Profissional:", PROFISSIONAIS, key="c_prof")
                data_consulta = st.date_input("Data:", datetime.today(), key="c_data")
            with col3:
                hora_consulta = st.time_input("Hora:", time(9, 0), step=1800, key="c_hora") # Intervalo de 30min
                submitted = st.form_submit_button("AGENDAR NOVA SESSÃO", type="primary")

            if submitted and cliente:
                dt_consulta = datetime.combine(data_consulta, hora_consulta)
                
                if horario_esta_disponivel(db_session, profissional, dt_consulta):
                    token = gerar_token_unico()
                    dados = {'profissional': profissional, 'cliente': cliente, 'telefone': telefone, 'horario': dt_consulta}
                    salvar_agendamento(db_session, dados, token)
                    
                    # Gerando o link de gestão para o profissional enviar
                    link_gestao = f"{st.experimental_get_query_params().get('url', ['https://agendafit.streamlit.app'])[0]}?token={token}"
                    
                    st.success(f"Consulta agendada para {cliente}.")
                    st.markdown(f"**LINK DE GESTÃO PARA O CLIENTE (Token):** `{link_gestao}`")
                else:
                    st.error("Horário já ocupado! Tente outro.")
        
        st.subheader("Agenda de Hoje")
        agenda_hoje = buscar_agendamentos_hoje(db_session)
        
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

    # --- TAB 2: Relatórios e Faltas ---
    with tab2:
        st.header("📈 Relatórios: Redução de Faltas (No-Show)")
        
        df_relatorio = get_relatorio_no_show()
        
        if not df_relatorio.empty and not df_relatorio['total_atendimentos'].empty:
            
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

            # Otimização: Gráfico para visualizar a dor
            st.bar_chart(df_relatorio.set_index('profissional')['Taxa No-Show (%)'])
        else:
            st.info("Ainda não há dados suficientes de sessões para gerar relatórios.")

    # --- TAB 3: Configuração e Pacotes (MVP Simples) ---
    with tab3:
        st.header("⚙️ Gestão de Pacotes e Otimização")
        st.warning("Funcionalidades avançadas em desenvolvimento. Aqui o Python irá automatizar a gestão de créditos.")
        st.markdown("""
        O recurso de **Otimizador de Pacotes** é o principal diferencial deste plano. 
        Ele irá:
        1.  Gerenciar quantos créditos o cliente tem (Ex: 10/12 sessões).
        2.  Disparar alertas automáticos (Notificações) para renovação na 9ª sessão.
        """)

# --- RENDERIZAÇÃO PRINCIPAL ---

# 1. Se o token existir na URL, renderiza a tela segura do cliente.
if token_param:
    render_agendamento_seguro()

# 2. Se o token NÃO existir, renderiza a tela de login/backoffice.
else:
    render_backoffice_admin()
