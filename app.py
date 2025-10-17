# app.py (VERSÃO MULTI-CLINICA COM GESTÃO DE HORÁRIOS E FERIADOS MELHORADA)

import streamlit as st
from datetime import datetime, time, date, timedelta
import pandas as pd
from zoneinfo import ZoneInfo

# IMPORTAÇÕES CORRIGIDAS PARA O NOVO MODELO
from database import (
    get_firestore_client,
    buscar_clinica_por_login,
    listar_profissionais,
    adicionar_profissional,
    remover_profissional,
    salvar_agendamento,
    buscar_agendamento_por_pin,
    atualizar_horario_profissional,
    adicionar_feriado,
    listar_feriados,
    remover_feriado
)
from logica_negocio import (
    gerar_token_unico,
    horario_esta_disponivel,
    processar_cancelamento_seguro,
    get_relatorio_no_show,
    acao_admin_agendamento,
    buscar_agendamentos_por_data,
    processar_remarcacao,
    importar_feriados_nacionais
)

# --- Configuração ---
st.set_page_config(layout="wide", page_title="Agenda Fit - Agendamento Inteligente")
TZ_SAO_PAULO = ZoneInfo('America/Sao_Paulo')
DIAS_SEMANA = {"seg": "Segunda", "ter": "Terça", "qua": "Quarta", "qui": "Quinta", "sex": "Sexta", "sab": "Sábado", "dom": "Domingo"}

# Inicialização do DB
db_client = get_firestore_client()
if db_client is None:
    st.stop()

# --- INICIALIZAÇÃO DO SESSION STATE ---
if 'remarcando' not in st.session_state: st.session_state.remarcando = False
if 'agendamentos_selecionados' not in st.session_state: st.session_state.agendamentos_selecionados = {}
if 'remarcacao_status' not in st.session_state: st.session_state.remarcacao_status = None
if "clinic_id" not in st.session_state: st.session_state.clinic_id = None
if "clinic_name" not in st.session_state: st.session_state.clinic_name = None
if 'data_filtro_agenda' not in st.session_state: st.session_state.data_filtro_agenda = datetime.now(TZ_SAO_PAULO).date()
if 'last_agendamento_info' not in st.session_state: st.session_state.last_agendamento_info = None
if 'editando_horario_id' not in st.session_state: st.session_state.editando_horario_id = None 
if 'active_tab' not in st.session_state: st.session_state.active_tab = "Agenda e Agendamento" # Para manter a aba ativa


# --- FUNÇÕES DE LÓGICA DA UI (HANDLERS) ---
def handle_login():
    """Tenta autenticar a clínica."""
    username = st.session_state.login_username
    password = st.session_state.login_password
    clinica = buscar_clinica_por_login(username, password)
    if clinica:
        st.session_state.clinic_id = clinica['id']
        st.session_state.clinic_name = clinica.get('nome_fantasia', username)
        st.rerun()
    else:
        st.error("Usuário ou senha inválidos.")

def handle_logout():
    """Limpa a sessão e desloga a clínica."""
    keys_to_clear = ['clinic_id', 'clinic_name', 'editando_horario_id', 'active_tab']
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

def handle_add_profissional():
    """Adiciona um novo profissional para a clínica logada."""
    st.session_state.active_tab = "Gerenciar Profissionais"
    nome_profissional = st.session_state.nome_novo_profissional
    if nome_profissional:
        if adicionar_profissional(st.session_state.clinic_id, nome_profissional):
            st.success(f"Profissional '{nome_profissional}' adicionado com sucesso!")
            st.session_state.nome_novo_profissional = ""
        else:
            st.error("Erro ao adicionar profissional.")
    else:
        st.warning("O nome do profissional não pode estar em branco.")

def handle_agendamento_submission():
    """Lida com a criação de um novo agendamento pelo admin da clínica."""
    st.session_state.active_tab = "Agenda e Agendamento"
    clinic_id = st.session_state.clinic_id
    cliente = st.session_state.c_nome_input
    profissional = st.session_state.c_prof_input
    data_consulta = st.session_state.c_data_input
    hora_consulta = st.session_state.c_hora_input

    if not cliente or not profissional:
        st.session_state.last_agendamento_info = {'cliente': cliente, 'status': "Cliente e Profissional são obrigatórios."}
        st.rerun()
        return

    dt_consulta_naive = datetime.combine(data_consulta, hora_consulta)
    dt_consulta_local = dt_consulta_naive.replace(tzinfo=TZ_SAO_PAULO)
    
    disponivel, msg_disponibilidade = horario_esta_disponivel(clinic_id, profissional, dt_consulta_local)

    if disponivel:
        pin_code = gerar_token_unico()
        dados = {
            'profissional_nome': profissional,
            'cliente': cliente,
            'telefone': st.session_state.c_tel_input,
            'horario': dt_consulta_local
        }
        resultado = salvar_agendamento(clinic_id, dados, pin_code)

        if resultado is True:
            link_gestao = f"https://agendafit.streamlit.app?pin={pin_code}"
            st.session_state.last_agendamento_info = {'cliente': cliente, 'link_gestao': link_gestao, 'status': True}
            st.session_state.data_filtro_agenda = data_consulta
            st.session_state.c_nome_input, st.session_state.c_tel_input = "", ""
        else:
            st.session_state.last_agendamento_info = {'cliente': cliente, 'status': str(resultado)}
    else:
        st.session_state.last_agendamento_info = {'cliente': cliente, 'status': msg_disponibilidade}
    st.rerun()

def handle_salvar_horarios_profissional(prof_id):
    """Salva a configuração de horários de um profissional."""
    st.session_state.active_tab = "Configurações da Clínica"
    if not prof_id:
        st.error("Nenhum profissional selecionado.")
        return
    
    horarios = {}
    for dia_key, dia_nome in DIAS_SEMANA.items():
        horarios[dia_key] = {
            "ativo": st.session_state[f"ativo_{dia_key}_{prof_id}"],
            "inicio": st.session_state[f"inicio_{dia_key}_{prof_id}"].strftime("%H:%M"),
            "fim": st.session_state[f"fim_{dia_key}_{prof_id}"].strftime("%H:%M")
        }
    
    if atualizar_horario_profissional(st.session_state.clinic_id, prof_id, horarios):
        st.success("Horários de trabalho atualizados com sucesso!")
        st.session_state.editando_horario_id = None # Sai do modo de edição
    else:
        st.error("Falha ao atualizar horários.")

def handle_adicionar_feriado():
    """Adiciona um novo feriado ou folga para a clínica."""
    st.session_state.active_tab = "Configurações da Clínica"
    data = st.session_state.nova_data_feriado
    descricao = st.session_state.descricao_feriado
    if data and descricao:
        if adicionar_feriado(st.session_state.clinic_id, data, descricao):
            st.success(f"Feriado '{descricao}' em {data.strftime('%d/%m/%Y')} adicionado.")
        else:
            st.error("Erro ao adicionar feriado.")
    else:
        st.warning("Data e Descrição são obrigatórias.")

def handle_importar_feriados():
    """Importa feriados nacionais para a clínica."""
    st.session_state.active_tab = "Configurações da Clínica"
    ano = st.session_state.ano_importacao
    count = importar_feriados_nacionais(st.session_state.clinic_id, ano)
    if count > 0:
        st.success(f"{count} feriados nacionais de {ano} importados com sucesso!")
    else:
        st.warning(f"Não foi possível importar feriados para {ano}. Verifique se já não foram importados.")

def handle_remarcar_confirmacao(pin, agendamento_id, profissional_nome):
    nova_data = st.session_state.nova_data_remarcacao
    nova_hora = st.session_state.nova_hora_remarcacao
    novo_horario_naive = datetime.combine(nova_data, nova_hora)
    novo_horario_local = novo_horario_naive.replace(tzinfo=TZ_SAO_PAULO)
    sucesso, mensagem = processar_remarcacao(pin, agendamento_id, profissional_nome, novo_horario_local)
    st.session_state.remarcacao_status = {'sucesso': sucesso, 'mensagem': mensagem}
    if sucesso:
        st.session_state.remarcando = False
    st.rerun()

def handle_cancelar_selecionados():
    st.session_state.active_tab = "Agenda e Agendamento"
    ids_para_cancelar = [ag_id for ag_id, selecionado in st.session_state.agendamentos_selecionados.items() if selecionado]
    if not ids_para_cancelar:
        st.warning("Nenhum agendamento selecionado.")
        return
    sucessos = 0
    for ag_id in ids_para_cancelar:
        if acao_admin_agendamento(ag_id, "cancelar"):
            sucessos += 1
    st.success(f"{sucessos} de {len(ids_para_cancelar)} agendamentos cancelados com sucesso.")
    st.session_state.agendamentos_selecionados.clear()
    st.rerun()

def handle_admin_action(id_agendamento: str, acao: str):
    st.session_state.active_tab = "Agenda e Agendamento"
    if acao_admin_agendamento(id_agendamento, acao):
        st.success(f"Ação '{acao.upper()}' registrada com sucesso!")
        st.rerun()
    else:
        st.error("Falha ao registrar a ação no sistema.")


# --- RENDERIZAÇÃO DAS PÁGINAS ---

def render_login_page():
    st.title("Bem-vindo ao Agenda Fit!")
    st.write("Faça login para gerenciar sua clínica.")
    with st.form("login_form"):
        st.text_input("Usuário", key="login_username")
        st.text_input("Senha", type="password", key="login_password")
        st.form_submit_button("Entrar", on_click=handle_login, use_container_width=True)

def render_agendamento_seguro():
    st.title("🔒 Gestão do seu Agendamento")
    if st.session_state.remarcacao_status:
        status = st.session_state.remarcacao_status
        if status['sucesso']:
            st.success(status['mensagem'])
        else:
            st.error(status['mensagem'])
        st.session_state.remarcacao_status = None
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
    st.info(f"Seu agendamento com **{agendamento['profissional_nome']}** está CONFIRMADO para:")
    st.subheader(f"{agendamento['horario'].strftime('%d/%m/%Y')} às {agendamento['horario'].strftime('%H:%M')}")
    st.caption(f"Cliente: {agendamento['cliente']}")
    st.markdown("---")
    if st.session_state.remarcando:
        with st.form("form_remarcacao"):
            st.subheader("Selecione o novo horário")
            col1, col2 = st.columns(2)
            col1.date_input("Nova data", key="nova_data_remarcacao", min_value=date.today())
            col2.time_input("Nova hora", key="nova_hora_remarcacao", step=timedelta(minutes=30))
            st.form_submit_button("✅ Confirmar Remarcação", on_click=handle_remarcar_confirmacao, args=(pin, agendamento['id'], agendamento['profissional_nome']), use_container_width=True)
        if st.button("⬅️ Voltar", use_container_width=True):
            st.session_state.remarcando = False
            st.rerun()
    else:
        col1, col2 = st.columns(2)
        if col1.button("❌ CANCELAR AGENDAMENTO", use_container_width=True, type="primary"):
            if processar_cancelamento_seguro(pin):
                st.success("Agendamento cancelado com sucesso.")
            else:
                st.error("Erro ao cancelar.")
        if col2.button("🔄 REMARCAR HORÁRIO", use_container_width=True):
            st.session_state.remarcando = True
            st.rerun()

def render_backoffice_clinica():
    clinic_id = st.session_state.clinic_id
    
    st.sidebar.header(f"Clínica: {st.session_state.clinic_name}")
    st.sidebar.button("Sair", on_click=handle_logout)
    
    profissionais_clinica = listar_profissionais(clinic_id)
    nomes_profissionais = [p['nome'] for p in profissionais_clinica]

    # --- NOVO SISTEMA DE ABAS QUE MANTÉM O ESTADO ---
    tab_options = ["Agenda e Agendamento", "Gerenciar Profissionais", "Configurações da Clínica", "Relatórios"]
    
    # A seleção do radio button atualiza o session_state automaticamente
    active_tab = st.radio(
        "Navegação Principal", 
        tab_options, 
        key="active_tab", 
        horizontal=True, 
        label_visibility="collapsed"
    )

    if active_tab == "Agenda e Agendamento":
        st.header("📝 Agendamento Rápido e Manual")
        if not nomes_profissionais:
            st.warning("Nenhum profissional cadastrado. Adicione profissionais na aba 'Gerenciar Profissionais' para poder agendar.")
        else:
            if st.session_state.get('last_agendamento_info'):
                info = st.session_state.last_agendamento_info
                if info.get('status') is True:
                    st.success(f"Agendado para {info.get('cliente')} com sucesso!")
                    st.markdown(f"**LINK DE GESTÃO:** `{info.get('link_gestao')}`")
                else:
                    st.error(f"Erro ao agendar para {info.get('cliente', 'cliente não informado')}: {info.get('status')}")
                st.session_state.last_agendamento_info = None
            with st.form("admin_form"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.text_input("Nome do Cliente:", key="c_nome_input")
                    st.text_input("Telefone:", key="c_tel_input")
                with col2:
                    st.selectbox("Profissional:", nomes_profissionais, key="c_prof_input")
                    st.date_input("Data:", key="c_data_input", min_value=date.today())
                with col3:
                    st.time_input("Hora:", key="c_hora_input", step=timedelta(minutes=30))
                    st.form_submit_button("AGENDAR NOVA SESSÃO", type="primary", on_click=handle_agendamento_submission)
        st.markdown("---")
        st.header("🗓️ Agenda")
        data_selecionada = st.date_input("Filtrar por data:", key='data_filtro_agenda', format="DD/MM/YYYY")
        agenda_do_dia = buscar_agendamentos_por_data(clinic_id, data_selecionada)
        if not agenda_do_dia.empty:
            for index, row in agenda_do_dia.iterrows():
                ag_id = row['id']
                cols = st.columns([0.1, 0.4, 0.3, 0.1, 0.1, 0.1])
                selecionado = cols[0].checkbox(" ", key=f"select_{ag_id}", label_visibility="collapsed")
                st.session_state.agendamentos_selecionados[ag_id] = selecionado
                cols[1].write(f"**{row['cliente']}**")
                cols[2].write(f"{row['profissional_nome']} - {row['horario'].strftime('%H:%M')}")
                cols[3].button("✅", key=f"finish_{ag_id}", on_click=handle_admin_action, args=(ag_id, "finalizar"), help="Sessão Concluída")
                cols[4].button("🚫", key=f"noshow_{ag_id}", on_click=handle_admin_action, args=(ag_id, "no-show"), help="Marcar Falta")
                cols[5].button("❌", key=f"cancel_{ag_id}", on_click=handle_admin_action, args=(ag_id, "cancelar"), help="Cancelar Agendamento")
            if any(st.session_state.agendamentos_selecionados.values()):
                st.button("❌ Cancelar Selecionados", type="primary", on_click=handle_cancelar_selecionados)
        else:
            st.info(f"Nenhuma consulta confirmada para {data_selecionada.strftime('%d/%m/%Y')}.")

    elif active_tab == "Gerenciar Profissionais":
        st.header("👥 Gerenciar Profissionais")
        with st.form("add_prof_form"):
            st.text_input("Nome do Profissional", key="nome_novo_profissional")
            st.form_submit_button("Adicionar", on_click=handle_add_profissional)
        st.markdown("---")
        st.subheader("Profissionais Cadastrados")
        if profissionais_clinica:
            for prof in profissionais_clinica:
                col1, col2 = st.columns([0.8, 0.2])
                col1.write(prof['nome'])
                col2.button("Remover", key=f"del_{prof['id']}", on_click=remover_profissional, args=(clinic_id, prof['id']))
        else:
            st.info("Nenhum profissional cadastrado.")

    elif active_tab == "Configurações da Clínica":
        st.header("⚙️ Configurações da Clínica")
        st.subheader("Horários de Trabalho dos Profissionais")
        if not profissionais_clinica:
            st.info("Cadastre profissionais na aba 'Gerenciar Profissionais' para definir seus horários.")
        else:
            prof_dict = {p['nome']: p['id'] for p in profissionais_clinica}
            prof_selecionado_nome = st.selectbox("Selecione um profissional para configurar", options=prof_dict.keys(), key="selectbox_prof_config")
            
            if prof_selecionado_nome:
                prof_id = prof_dict[prof_selecionado_nome]
                prof_data = next((p for p in profissionais_clinica if p['id'] == prof_id), None)
                horarios_salvos = prof_data.get('horario_trabalho', {})
                if st.session_state.editando_horario_id == prof_id:
                    with st.form(key=f"form_horarios_{prof_id}"):
                        st.write(f"**Editando horários para: {prof_selecionado_nome}**")
                        for dia_key, dia_nome in DIAS_SEMANA.items():
                            horario_dia = horarios_salvos.get(dia_key, {"ativo": False, "inicio": "09:00", "fim": "18:00"})
                            cols = st.columns([0.2, 0.4, 0.4])
                            cols[0].checkbox(dia_nome, key=f"ativo_{dia_key}_{prof_id}", value=horario_dia['ativo'])
                            cols[1].time_input("Início", key=f"inicio_{dia_key}_{prof_id}", value=datetime.strptime(horario_dia['inicio'], "%H:%M").time(), step=timedelta(minutes=30), label_visibility="collapsed")
                            cols[2].time_input("Fim", key=f"fim_{dia_key}_{prof_id}", value=datetime.strptime(horario_dia['fim'], "%H:%M").time(), step=timedelta(minutes=30), label_visibility="collapsed")
                        
                        submit_cols = st.columns(2)
                        submit_cols[0].form_submit_button("✅ Salvar Alterações", on_click=handle_salvar_horarios_profissional, args=(prof_id,), use_container_width=True)
                        if submit_cols[1].form_submit_button("❌ Cancelar", use_container_width=True):
                            st.session_state.editando_horario_id = None
                            st.rerun()
                else:
                    st.write(f"**Horários salvos para: {prof_selecionado_nome}**")
                    for dia_key, dia_nome in DIAS_SEMANA.items():
                        horario_dia = horarios_salvos.get(dia_key, {"ativo": False, "inicio": "09:00", "fim": "18:00"})
                        if horario_dia['ativo']:
                            st.text(f"{dia_nome}: {horario_dia['inicio']} - {horario_dia['fim']}")
                        else:
                            st.text(f"{dia_nome}: Não trabalha")
                    
                    if st.button("✏️ Editar Horários", key=f"edit_{prof_id}"):
                        st.session_state.editando_horario_id = prof_id
                        st.session_state.active_tab = "Configurações da Clínica"
                        st.rerun()
        st.markdown("---")
        st.subheader("Feriados e Folgas")
        col1, col2 = st.columns(2)
        with col1:
            with st.form("add_feriado_form"):
                st.date_input("Data do Feriado/Folga", key="nova_data_feriado")
                st.text_input("Descrição", key="descricao_feriado", placeholder="Ex: Feriado Municipal")
                st.form_submit_button("Adicionar Data Bloqueada", on_click=handle_adicionar_feriado)
        with col2:
            st.write("Importar Feriados Nacionais (Brasil)")
            st.number_input("Ano", min_value=datetime.now().year, max_value=datetime.now().year + 5, key="ano_importacao", label_visibility="collapsed")
            st.button("Importar Feriados do Ano", on_click=handle_importar_feriados)
        feriados = listar_feriados(clinic_id)
        if feriados:
            st.write("Datas bloqueadas cadastradas:")
            for feriado in feriados:
                c1, c2, c3 = st.columns([0.4, 0.4, 0.2])
                c1.write(feriado['data'].strftime('%d/%m/%Y'))
                c2.write(feriado['descricao'])
                c3.button("Remover", key=f"del_feriado_{feriado['id']}", on_click=remover_feriado, args=(clinic_id, feriado['id']))

    elif active_tab == "Relatórios":
        st.header("📈 Relatórios de Faltas (No-Show)")
        df_relatorio = get_relatorio_no_show(clinic_id)
        if not df_relatorio.empty:
            st.dataframe(df_relatorio)
        else:
            st.info("Ainda não há dados para gerar relatórios.")

# --- ROTEAMENTO PRINCIPAL ---
pin_param = st.query_params.get("pin")
if pin_param:
    render_agendamento_seguro()
elif st.session_state.clinic_id:
    render_backoffice_clinica()
else:
    render_login_page()

