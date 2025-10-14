import streamlit as st
from datetime import datetime, time
import pandas as pd
import random

# IMPORTAÇÕES SEGURAS E CORRETAS:
from database import init_supabase, salvar_agendamento, buscar_agendamento_por_pin, buscar_todos_agendamentos, buscar_agendamento_por_id, atualizar_status_agendamento
from logica_negocio import gerar_token_unico, horario_esta_disponivel, processar_cancelamento_seguro, get_relatorio_no_show, acao_admin_agendamento, buscar_agendamentos_hoje


# --- Configuração ---
st.set_page_config(layout="wide", page_title="Agenda Fit - Agendamento Inteligente")
PROFISSIONAIS = ["Dr. João (Físio)", "Dra. Maria (Pilates)", "Dr. Pedro (Nutrição)"]

# Inicialização do DB (Chamando a função segura via cache_resource)
@st.cache_resource
def setup_database():
    """Chama a função de inicialização do DB."""
    from database import init_supabase 
    return init_supabase()

db_client = setup_database()
if db_client is None:
    st.stop() 


# --- ROTEAMENTO E PARÂMETROS ---
pin_param = st.query_params.get("pin", [None])[0]


# Inicialização do Session State para persistir a mensagem
if 'last_agendamento_info' not in st.session_state:
    st.session_state.last_agendamento_info = None


# --- FUNÇÃO DE AÇÃO GLOBAL (CORRIGIDA) ---
# Esta função foi movida para o escopo global para ser usada pelos botões on_click.
def handle_admin_action(id_agendamento, acao):
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

    # Busca o agendamento no DB Supabase
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
    
    # --- Login simples para MVP ---
    st.sidebar.header("Login (Admin)")
    senha = st.sidebar.text_input("Senha", type="password")
    if senha != "1234":
        st.warning("Acesso restrito ao profissional. Senha de teste: 1234")
        st.session_state.last_agendamento_info = None 
        return

    st.sidebar.success("Login como Administrador")

    # --- Navegação do Admin ---
    tab1, tab2, tab3 = st.tabs(["Agenda Hoje/Manual", "Relatórios e Faltas", "Configuração (Pacotes)"])

    # --- TAB 1: Agendamento Manual e Agenda do Dia ---
    with tab1:
        st.header("📝 Agendamento Rápido e Manual")
        
        if st.session_state.last_agendamento_info:
            info = st.session_state.last_agendamento_info
            
            st.success(f"Consulta agendada para {info['cliente']} com sucesso!")
            st.markdown(f"**LINK DE GESTÃO PARA O CLIENTE:** `[PIN: {info['pin_code']}] {info['link_gestao']}`")
        
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
                st.session_state.last_agendamento_info = None 
                
                dt_consulta = datetime.combine(data_consulta, hora_consulta)
                
                if horario_esta_disponivel(profissional, dt_consulta):
                    pin_code = gerar_token_unico() 
                    dados = {'profissional': profissional, 'cliente': cliente, 'telefone': telefone, 'horario': dt_consulta}
                    
                    if salvar_agendamento(dados, pin_code):
                        
                        link_base = f"https://agendafit.streamlit.app" 
                        link_gestao = f"{link_base}?pin={pin_code}" 
                        
                        st.session_state.last_agendamento_info = {
                            'cliente': cliente,
                            'pin_code': pin_code,
                            'link_gestao': link_gestao
                        }
                        
                        st.rerun() 
                    else:
                        st.error("Erro ao salvar no banco de dados. Verifique a conexão do Supabase.")
                else:
                    st.error("Horário já ocupado! Tente outro.")
        
        st.subheader("Agenda de Hoje")
        agenda_hoje = buscar_agendamentos_hoje()
        
        if not agenda_hoje.empty:
            df_agenda = agenda_hoje[['horario', 'cliente', 'profissional', 'status', 'id']].copy()
            df_agenda['Hora'] = df_agenda['horario'].dt.strftime('%H:%M')

            # --- GESTÃO DA AGENDA: BOTÕES DE AÇÃO ---
            st.dataframe(
                df_agenda[['Hora', 'cliente', 'profissional', 'status', 'id']],
                column_config={
                    "id": st.column_config.Column(width="small", label="ID"),
                    "Ações": st.column_config.Column("Ações", width="large")
                },
                on_select="ignore", 
                use_container_width=True, 
                hide_index=True,
            )
            
            # Renderiza os botões de ação abaixo do DataFrame
            for index, row in df_agenda.iterrows():
                col_id, col_finalizar, col_no_show, col_cancelar = st.columns([0.5, 1, 1, 1])
                
                col_id.markdown(f"**ID:** {row['id']}")

                # Botão para marcar como FINALIZADO
                col_finalizar.button("✅ Sessão Concluída", 
                                     key=f"finish_{row['id']}", 
                                     on_click=handle_admin_action, 
                                     args=(row['id'], "finalizar"),
                                     type="primary")
                
                # Botão para marcar como NO-SHOW (Falta)
                col_no_show.button("🚫 Marcar Falta", 
                                  key=f"noshow_{row['id']}", 
                                  on_click=handle_admin_action, 
                                  args=(row['id'], "no-show"))

                # Botão para Cancelar
                col_cancelar.button("❌ Cancelar", 
                                    key=f"cancel_{row['id']}", 
                                    on_click=handle_admin_action, 
                                    args=(row['id'], "cancelar"))

                st.markdown("---", unsafe_allow_html=True) 

        else:
            st.info("Nenhuma consulta confirmada para hoje.")


    # --- TAB 2: Relatórios e Faltas (omissões por brevidade) ---
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

    # --- TAB 3: Configuração e Pacotes (omissões por brevidade) ---
    with tab3:
        st.header("⚙️ Gestão de Pacotes e Otimização")
        st.warning("Funcionalidades avançadas em desenvolvimento. Necessita de uma tabela 'pacotes' no Supabase.")
        st.markdown("""
        **Otimizador de Pacotes:**
        1.  Gerenciar quantos créditos o cliente tem (Ex: 10/12 sessões).
        2.  Disparar alertas automáticos (Notificações) para renovação na 9ª sessão.
        """)


# --- RENDERIZAÇÃO PRINCIPAL ---

if pin_param:
    render_agendamento_seguro()
else:
    render_backoffice_admin()
