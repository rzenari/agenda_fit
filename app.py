# app.py (VERSÃO COM PAINEL DE SUPER ADMINISTRADOR)

import streamlit as st
from datetime import datetime, time, date, timedelta
import pandas as pd
from zoneinfo import ZoneInfo
import plotly.graph_objects as go
import numpy as np

# IMPORTAÇÕES CORRIGIDAS E ADICIONADAS PARA O NOVO MODELO
from database import (
    get_firestore_client,
    buscar_clinica_por_login,
    listar_profissionais,
    adicionar_profissional,
    remover_profissional as db_remover_profissional,
    salvar_agendamento,
    buscar_agendamento_por_pin,
    atualizar_horario_profissional,
    adicionar_feriado,
    listar_feriados,
    remover_feriado as db_remover_feriado,
    listar_clientes,
    adicionar_cliente,
    remover_cliente as db_remover_cliente,
    listar_servicos,
    adicionar_servico,
    remover_servico as db_remover_servico,
    # Funções para o Super Admin
    listar_clinicas,
    adicionar_clinica,
    toggle_status_clinica
)
from logica_negocio import (
    gerar_token_unico,
    verificar_disponibilidade_com_duracao,
    processar_cancelamento_seguro,
    acao_admin_agendamento,
    buscar_agendamentos_por_data,
    processar_remarcacao,
    importar_feriados_nacionais,
    gerar_horarios_disponiveis,
    get_dados_dashboard,
    gerar_visao_semanal,
    gerar_visao_comparativa
)

# --- Configuração ---
st.set_page_config(layout="wide", page_title="Agenda Fit - Agendamento Inteligente")
TZ_SAO_PAULO = ZoneInfo('America/Sao_Paulo')
DIAS_SEMANA = {"seg": "Segunda", "ter": "Terça", "qua": "Quarta", "qui": "Quinta", "sex": "Sexta", "sab": "Sábado", "dom": "Domingo"}
DIAS_SEMANA_LISTA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


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
if 'form_data_selecionada' not in st.session_state: st.session_state.form_data_selecionada = datetime.now(TZ_SAO_PAULO).date()
if 'filter_data_selecionada' not in st.session_state: st.session_state.filter_data_selecionada = datetime.now(TZ_SAO_PAULO).date()
if 'last_agendamento_info' not in st.session_state: st.session_state.last_agendamento_info = None
if 'editando_horario_id' not in st.session_state: st.session_state.editando_horario_id = None
if 'active_tab' not in st.session_state: st.session_state.active_tab = "🗓️ Agenda e Agendamento"
if 'agenda_cliente_select' not in st.session_state: st.session_state.agenda_cliente_select = "Novo Cliente"
if 'c_tel_input' not in st.session_state: st.session_state.c_tel_input = ""
if 'confirmando_agendamento' not in st.session_state: st.session_state.confirmando_agendamento = False
if 'detalhes_agendamento' not in st.session_state: st.session_state.detalhes_agendamento = {}
# Novo estado para Super Admin
if 'is_super_admin' not in st.session_state: st.session_state.is_super_admin = False


# --- FUNÇÕES DE LÓGICA DA UI (HANDLERS) ---

def sync_dates_from_filter():
    """Callback para sincronizar a data do formulário quando a data do filtro muda."""
    st.session_state.form_data_selecionada = st.session_state.filter_data_selecionada

def handle_login():
    """Tenta autenticar a clínica ou o super admin."""
    # CORREÇÃO: Usar .strip() para remover espaços em branco do input do usuário
    username = st.session_state.login_username.strip()
    password = st.session_state.login_password.strip()

    # 1. Verificar se é o Super Admin (usando st.secrets)
    super_admin_user = st.secrets.get("super_admin", {}).get("username")
    super_admin_pass = st.secrets.get("super_admin", {}).get("password")

    # CORREÇÃO: Usar .strip() nos segredos também, garantindo que não sejam nulos antes
    if super_admin_user:
        super_admin_user = super_admin_user.strip()
    if super_admin_pass:
        super_admin_pass = super_admin_pass.strip()
        
    if username == super_admin_user and password == super_admin_pass and super_admin_user is not None:
        st.session_state.is_super_admin = True
        st.session_state.clinic_id = None # Limpa qualquer ID de clínica
        st.rerun()
        return

    # 2. Se não for admin, busca a clínica
    clinica = buscar_clinica_por_login(username, password)
    if clinica:
        st.session_state.clinic_id = clinica['id']
        st.session_state.clinic_name = clinica.get('nome_fantasia', username)
        st.session_state.is_super_admin = False # Garante que não é admin
        st.rerun()
    else:
        st.error("Usuário ou senha inválidos.")

def handle_logout():
    """Limpa a sessão e desloga o usuário."""
    keys_to_clear = ['clinic_id', 'clinic_name', 'editando_horario_id', 'active_tab', 'agenda_cliente_select', 'c_tel_input', 'confirmando_agendamento', 'detalhes_agendamento', 'form_data_selecionada', 'filter_data_selecionada', 'is_super_admin']
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

def handle_add_clinica():
    """Lida com a adição de uma nova clínica pelo Super Admin."""
    nome = st.session_state.sa_nome_clinica
    user = st.session_state.sa_user_clinica
    pwd = st.session_state.sa_pwd_clinica

    if nome and user and pwd:
        sucesso, msg = adicionar_clinica(nome, user, pwd)
        if sucesso:
            st.success(msg)
            st.rerun()
        else:
            st.error(f"Erro: {msg}")
    else:
        st.warning("Todos os campos são obrigatórios.")

def handle_toggle_status_clinica(clinic_id, status_atual):
    """Ativa ou desativa uma clínica."""
    if toggle_status_clinica(clinic_id, status_atual):
        st.success("Status da clínica alterado com sucesso.")
        st.rerun()
    else:
        st.error("Erro ao alterar o status da clínica.")
# ... (restante das funções handle_... existentes, sem alterações) ...
def handle_add_profissional():
    """Adiciona um novo profissional para a clínica logada."""
    nome_profissional = st.session_state.nome_novo_profissional
    if nome_profissional:
        if adicionar_profissional(st.session_state.clinic_id, nome_profissional):
            st.success(f"Profissional '{nome_profissional}' adicionado com sucesso!")
            st.rerun()
        else:
            st.error("Erro ao adicionar profissional.")
    else:
        st.warning("O nome do profissional não pode estar em branco.")

def handle_selecao_cliente():
    """Callback para atualizar o telefone quando um cliente é selecionado."""
    cliente_selecionado = st.session_state.agenda_cliente_select
    if cliente_selecionado != "Novo Cliente":
        clientes = listar_clientes(st.session_state.clinic_id)
        cliente_data = next((c for c in clientes if c['nome'] == cliente_selecionado), None)
        if cliente_data:
            st.session_state.c_tel_input = cliente_data.get('telefone', '')
        else:
            st.session_state.c_tel_input = ''
    else:
        st.session_state.c_tel_input = ''

def handle_pre_agendamento():
    """Coleta os dados do formulário e abre o diálogo de confirmação."""
    cliente_selecionado = st.session_state.agenda_cliente_select
    if cliente_selecionado == "Novo Cliente":
        cliente = st.session_state.get('c_nome_novo_cliente_input', '')
        telefone = st.session_state.get('c_tel_input', '')
    else:
        cliente = cliente_selecionado
        telefone = st.session_state.get('c_tel_input', '')
    
    hora_consulta = st.session_state.get('c_hora_input')
    if not cliente or not telefone or not isinstance(hora_consulta, time):
        st.warning("Por favor, preencha o nome do cliente, telefone e selecione um horário válido.")
        return

    st.session_state.detalhes_agendamento = {
        'cliente': cliente,
        'telefone': telefone,
        'profissional': st.session_state.c_prof_input,
        'servico': st.session_state.c_servico_input,
        'data': st.session_state.form_data_selecionada, # Usar estado do formulário
        'hora': hora_consulta,
        'cliente_era_novo': cliente_selecionado == "Novo Cliente"
    }
    # Sincroniza a data do filtro com a data do formulário
    st.session_state.filter_data_selecionada = st.session_state.form_data_selecionada
    st.session_state.confirmando_agendamento = True
    st.rerun()

def handle_agendamento_submission():
    """Lida com a criação de um novo agendamento após a confirmação."""
    detalhes = st.session_state.detalhes_agendamento
    if not detalhes:
        return

    clinic_id = st.session_state.clinic_id
    servicos_clinica = listar_servicos(clinic_id)
    servico_data = next((s for s in servicos_clinica if s['nome'] == detalhes['servico']), None)
    duracao_servico = servico_data['duracao_min'] if servico_data else 30

    dt_consulta_naive = datetime.combine(detalhes['data'], detalhes['hora'])
    dt_consulta_local = dt_consulta_naive.replace(tzinfo=TZ_SAO_PAULO)
    
    disponivel, msg_disponibilidade = verificar_disponibilidade_com_duracao(clinic_id, detalhes['profissional'], dt_consulta_local, duracao_servico)

    if disponivel:
        pin_code = gerar_token_unico()
        dados = {
            'profissional_nome': detalhes['profissional'],
            'cliente': detalhes['cliente'],
            'telefone': detalhes['telefone'],
            'horario': dt_consulta_local,
            'servico_nome': detalhes['servico'],
            'duracao_min': duracao_servico
        }
        resultado = salvar_agendamento(clinic_id, dados, pin_code)

        if resultado is True:
            if detalhes['cliente_era_novo']:
                adicionar_cliente(clinic_id, detalhes['cliente'], detalhes['telefone'], "")

            link_gestao = f"https://agendafit.streamlit.app?pin={pin_code}"
            st.session_state.last_agendamento_info = {'cliente': detalhes['cliente'], 'link_gestao': link_gestao, 'pin_code': pin_code, 'status': True}
            # Sincroniza ambas as datas para a data do agendamento
            st.session_state.form_data_selecionada = detalhes['data']
            st.session_state.filter_data_selecionada = detalhes['data']
        else:
            st.session_state.last_agendamento_info = {'cliente': detalhes['cliente'], 'status': str(resultado)}
    else:
        st.session_state.last_agendamento_info = {'cliente': detalhes['cliente'], 'status': msg_disponibilidade}
    
    # Limpa o estado após o agendamento
    st.session_state.agenda_cliente_select = "Novo Cliente"
    st.session_state.c_tel_input = ""
    st.session_state.confirmando_agendamento = False
    st.session_state.detalhes_agendamento = {}
    st.rerun()

def handle_salvar_horarios_profissional(prof_id):
    """Salva a configuração de horários de um profissional."""
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
        st.session_state.editando_horario_id = None 
    else:
        st.error("Falha ao atualizar horários.")

def handle_adicionar_feriado():
    data = st.session_state.nova_data_feriado
    descricao = st.session_state.descricao_feriado
    if data and descricao:
        if adicionar_feriado(st.session_state.clinic_id, data, descricao):
            st.success(f"Feriado '{descricao}' em {data.strftime('%d/%m/%Y')} adicionado.")
            st.rerun()
        else:
            st.error("Erro ao adicionar feriado.")
    else:
        st.warning("Data e Descrição são obrigatórias.")

def handle_importar_feriados():
    ano = st.session_state.ano_importacao
    count = importar_feriados_nacionais(st.session_state.clinic_id, ano)
    if count > 0:
        st.success(f"{count} feriados nacionais de {ano} importados com sucesso!")
    else:
        st.warning(f"Não foi possível importar feriados para {ano}. Verifique se já não foram importados.")

def handle_remarcar_confirmacao(pin, agendamento_id, profissional_nome):
    nova_data = st.session_state.nova_data_remarcacao
    nova_hora = st.session_state.nova_hora_remarcacao
    
    if not isinstance(nova_hora, time):
        st.session_state.remarcacao_status = {'sucesso': False, 'mensagem': "Nenhum horário válido selecionado."}
        return

    novo_horario_naive = datetime.combine(nova_data, nova_hora)
    novo_horario_local = novo_horario_naive.replace(tzinfo=TZ_SAO_PAULO)
    sucesso, mensagem = processar_remarcacao(pin, agendamento_id, profissional_nome, novo_horario_local)
    st.session_state.remarcacao_status = {'sucesso': sucesso, 'mensagem': mensagem}
    if sucesso:
        st.session_state.remarcando = False

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
    st.session_state.agendamentos_selecionados.clear()
    st.rerun()

def handle_admin_action(id_agendamento: str, acao: str):
    if acao_admin_agendamento(id_agendamento, acao):
        st.success(f"Ação '{acao.upper()}' registrada com sucesso!")
        st.rerun()
    else:
        st.error("Falha ao registrar a ação no sistema.")

def entrar_modo_edicao(prof_id):
    st.session_state.editando_horario_id = prof_id

def handle_add_cliente():
    nome = st.session_state.nome_novo_cliente
    telefone = st.session_state.tel_novo_cliente
    obs = st.session_state.obs_novo_cliente
    if nome and telefone:
        if adicionar_cliente(st.session_state.clinic_id, nome, telefone, obs):
            st.success(f"Cliente '{nome}' adicionado com sucesso!")
            st.rerun()
        else:
            st.error("Erro ao adicionar cliente.")
    else:
        st.warning("Nome e Telefone são obrigatórios.")

def handle_add_servico():
    nome = st.session_state.nome_novo_servico
    duracao = st.session_state.duracao_novo_servico
    if nome and duracao > 0:
        if adicionar_servico(st.session_state.clinic_id, nome, duracao):
            st.success(f"Serviço '{nome}' adicionado com sucesso!")
            st.rerun()
        else:
            st.error("Erro ao adicionar serviço.")
    else:
        st.warning("Nome do serviço e duração maior que zero são obrigatórios.")

def handle_remove_profissional(clinic_id: str, prof_id: str):
    if db_remover_profissional(clinic_id, prof_id):
        st.success("Profissional removido com sucesso!")
        st.rerun()
    else:
        st.error("Erro ao remover profissional.")

def handle_remove_cliente(clinic_id: str, cliente_id: str):
    if db_remover_cliente(clinic_id, cliente_id):
        st.success("Cliente removido com sucesso!")
        st.rerun()
    else:
        st.error("Erro ao remover cliente.")

def handle_remove_servico(clinic_id: str, servico_id: str):
    if db_remover_servico(clinic_id, servico_id):
        st.success("Serviço removido com sucesso!")
        st.rerun()
    else:
        st.error("Erro ao remover serviço.")

def handle_remove_feriado(clinic_id: str, feriado_id: str):
    if db_remover_feriado(clinic_id, feriado_id):
        st.rerun()
    else:
        st.error("Erro ao remover feriado.")

# --- RENDERIZAÇÃO DAS PÁGINAS ---

def render_login_page():
    st.title("Bem-vindo ao Agenda Fit!")
    st.write("Faça login para gerenciar sua clínica ou acesse o painel de administrador.")
    with st.form("login_form"):
        st.text_input("Usuário", key="login_username")
        st.text_input("Senha", type="password", key="login_password")
        st.form_submit_button("Entrar", on_click=handle_login)

def render_agendamento_seguro():
    # ... (código da página de gestão de agendamento do cliente, sem alterações) ...
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
        st.subheader("Selecione o novo horário")
        nova_data = st.date_input("Nova data", key="nova_data_remarcacao", min_value=date.today())
        
        duracao_agendamento = agendamento.get('duracao_min', 30)
        st.info(f"Selecione um novo horário para o serviço de {duracao_agendamento} minutos.")

        horarios_disponiveis = gerar_horarios_disponiveis(
            agendamento['clinic_id'],
            agendamento['profissional_nome'],
            nova_data,
            duracao_agendamento,
            agendamento_id_excluir=agendamento['id']
        )

        with st.form("form_remarcacao"):
            if horarios_disponiveis:
                st.selectbox("Nova hora:", options=horarios_disponiveis, key="nova_hora_remarcacao", format_func=lambda t: t.strftime('%H:%M'))
                pode_remarcar = True
            else:
                st.selectbox("Nova hora:", options=["Nenhum horário disponível"], key="nova_hora_remarcacao", disabled=True)
                pode_remarcar = False
            
            st.form_submit_button("✅ Confirmar Remarcação", on_click=handle_remarcar_confirmacao, args=(pin, agendamento['id'], agendamento['profissional_nome']), disabled=not pode_remarcar)

        if st.button("⬅️ Voltar"):
            st.session_state.remarcando = False
            st.rerun()
    else:
        col1, col2 = st.columns(2)
        if col1.button("❌ CANCELAR AGENDAMENTO", type="primary"):
            if processar_cancelamento_seguro(pin):
                st.success("Agendamento cancelado com sucesso.")
            else:
                st.error("Erro ao cancelar.")
            st.rerun()
        if col2.button("🔄 REMARCAR HORÁRIO"):
            st.session_state.remarcando = True
            st.rerun()

def render_backoffice_clinica():
    # ... (código do backoffice da clínica, sem alterações funcionais) ...
    clinic_id = st.session_state.clinic_id
    
    st.sidebar.header(f"Clínica: {st.session_state.clinic_name}")
    if st.sidebar.button("Sair"):
        handle_logout()
    
    profissionais_clinica = listar_profissionais(clinic_id)
    clientes_clinica = listar_clientes(clinic_id)
    servicos_clinica = listar_servicos(clinic_id)

    tab_options = ["🗓️ Agenda e Agendamento", "📈 Dashboard", "👤 Gerenciar Clientes", "📋 Gerenciar Serviços", "👥 Gerenciar Profissionais", "⚙️ Configurações"]
    
    active_tab = st.radio(
        "Navegação", 
        tab_options, 
        key="active_tab", 
        horizontal=True, 
        label_visibility="collapsed"
    )

    if active_tab == "🗓️ Agenda e Agendamento":
        st.header("📝 Agendamento Rápido e Manual")

        # --- LÓGICA DE CONFIRMAÇÃO (SEM st.dialog) ---
        if st.session_state.get('confirmando_agendamento', False):
            st.subheader("Revisar e Confirmar Agendamento")
            detalhes = st.session_state.detalhes_agendamento
            st.write(f"**Cliente:** {detalhes['cliente']}")
            st.write(f"**Telefone:** {detalhes['telefone']}")
            st.write(f"**Profissional:** {detalhes['profissional']}")
            st.write(f"**Serviço:** {detalhes['servico']}")
            st.write(f"**Data:** {detalhes['data'].strftime('%d/%m/%Y')}")
            st.write(f"**Horário:** {detalhes['hora'].strftime('%H:%M')}")
            
            c1, c2 = st.columns(2)
            if c1.button("✅ Confirmar Agendamento", type="primary"):
                handle_agendamento_submission()
            if c2.button("❌ Voltar"):
                st.session_state.confirmando_agendamento = False
                st.rerun()
        
        elif not profissionais_clinica or not servicos_clinica:
            st.warning("É necessário ter ao menos um profissional e um serviço cadastrado para realizar agendamentos.")
        else:
            if st.session_state.get('last_agendamento_info'):
                info = st.session_state.last_agendamento_info
                if info.get('status') is True:
                    st.success(f"Agendado para {info.get('cliente')} com sucesso!")
                    st.markdown(f"**LINK DE GESTÃO:** `{info.get('link_gestao')}` (PIN: **{info.get('pin_code')}**)")
                else:
                    st.error(f"Erro ao agendar para {info.get('cliente', 'cliente não informado')}: {info.get('status')}")
                st.session_state.last_agendamento_info = None

            st.subheader("1. Selecione o Cliente")
            opcoes_clientes = ["Novo Cliente"] + [c['nome'] for c in clientes_clinica]
            st.selectbox(
                "Cliente:",
                options=opcoes_clientes,
                key="agenda_cliente_select",
                on_change=handle_selecao_cliente
            )

            st.subheader("2. Preencha os Detalhes do Agendamento")
            
            # CORREÇÃO: Removido o st.form para permitir a atualização dinâmica dos horários.
            # Agora, cada alteração nos widgets abaixo irá re-executar o script e atualizar a lista de horários.
            
            if st.session_state.agenda_cliente_select == "Novo Cliente":
                col_nome, col_tel = st.columns(2)
                col_nome.text_input("Nome do Novo Cliente", key="c_nome_novo_cliente_input")
                col_tel.text_input("Telefone", key="c_tel_input")
            else:
                st.markdown(f"**Agendando para:** {st.session_state.agenda_cliente_select}")
                st.text_input("Telefone (edite se necessário)", key="c_tel_input")
            
            st.divider()

            form_cols = st.columns(3)
            form_cols[0].selectbox("Profissional:", [p['nome'] for p in profissionais_clinica], key="c_prof_input")
            form_cols[1].date_input("Data:", key="form_data_selecionada", min_value=date.today())
            form_cols[2].selectbox("Serviço:", [s['nome'] for s in servicos_clinica], key="c_servico_input")

            servico_selecionado_nome = st.session_state.c_servico_input
            servico_data = next((s for s in servicos_clinica if s['nome'] == servico_selecionado_nome), None)
            duracao_servico = servico_data['duracao_min'] if servico_data else 30

            horarios_disponiveis = gerar_horarios_disponiveis(
                clinic_id, 
                st.session_state.c_prof_input, 
                st.session_state.form_data_selecionada, # Usar estado do formulário
                duracao_servico
            )
            
            if horarios_disponiveis:
                form_cols[1].selectbox("Hora:", options=horarios_disponiveis, key="c_hora_input", format_func=lambda t: t.strftime('%H:%M'))
                pode_agendar = True
            else:
                form_cols[1].selectbox("Hora:", options=["Nenhum horário disponível"], key="c_hora_input", disabled=True)
                pode_agendar = False
            
            # CORREÇÃO: Trocado st.form_submit_button por st.button
            st.button("AGENDAR NOVA SESSÃO", type="primary", disabled=not pode_agendar, on_click=handle_pre_agendamento)

        st.markdown("---")
        st.header("🗓️ Visualização da Agenda")
        
        view_tab1, view_tab2, view_tab3 = st.tabs(["Visão Diária (Lista)", "Visão Semanal (Profissional)", "Visão Comparativa (Diária)"])

        with view_tab1:
            # CORREÇÃO: Usar chave única e callback para sincronizar
            st.date_input("Filtrar por data:", key='filter_data_selecionada', format="DD/MM/YYYY", on_change=sync_dates_from_filter)
            agenda_do_dia = buscar_agendamentos_por_data(clinic_id, st.session_state.filter_data_selecionada)
            
            if not agenda_do_dia.empty:
                header_cols = st.columns([0.1, 0.4, 0.3, 0.3])
                header_cols[1].markdown("**Cliente / Serviço**")
                header_cols[2].markdown("**Profissional / Horário**")
                header_cols[3].markdown("**Ações**")
                st.divider()

                for index, row in agenda_do_dia.iterrows():
                    ag_id = row['id']
                    data_cols = st.columns([0.1, 0.4, 0.3, 0.3])
                    
                    selecionado = data_cols[0].checkbox(" ", key=f"select_{ag_id}", label_visibility="collapsed")
                    st.session_state.agendamentos_selecionados[ag_id] = selecionado
                    
                    data_cols[1].write(f"**{row['cliente']}**<br><small>{row.get('servico_nome', 'N/A')}</small>", unsafe_allow_html=True)
                    data_cols[2].write(f"{row['profissional_nome']} - {row['horario'].strftime('%H:%M')}")
                    
                    with data_cols[3]:
                        action_cols = st.columns(5)
                        detalhes_popover = action_cols[0].popover("ℹ️", help="Ver Detalhes")
                        with detalhes_popover:
                            pin = row.get('pin_code', 'N/A')
                            link = f"https://agendafit.streamlit.app?pin={pin}"
                            st.markdown(f"**Serviço:** {row.get('servico_nome', 'N/A')}")
                            st.markdown(f"**Telefone:** {row.get('telefone', 'N/A')}")
                            st.markdown(f"**PIN:** `{pin}`")
                            st.markdown(f"**Link:** `{link}`")
                        wpp_popover = action_cols[1].popover("💬", help="Gerar Mensagem WhatsApp")
                        with wpp_popover:
                            pin = row.get('pin_code', 'N/A')
                            link_gestao = f"https://agendafit.streamlit.app?pin={pin}"
                            mensagem = (
                                f"Olá, {row['cliente']}! Tudo bem?\n\n"
                                f"Este é um lembrete do seu agendamento na {st.session_state.clinic_name} com o(a) profissional {row['profissional_nome']} "
                                f"no dia {row['horario'].strftime('%d/%m/%Y')} às {row['horario'].strftime('%H:%M')}.\n\n"
                                f"Para confirmar, remarcar ou cancelar, por favor, use este link: {link_gestao}"
                            )
                            st.text_area("Mensagem:", value=mensagem, height=200, key=f"wpp_msg_{ag_id}")
                            st.write("Copie a mensagem acima e envie para o cliente.")

                        action_cols[2].button("✅", key=f"finish_{ag_id}", on_click=handle_admin_action, args=(ag_id, "finalizar"), help="Sessão Concluída")
                        action_cols[3].button("🚫", key=f"noshow_{ag_id}", on_click=handle_admin_action, args=(ag_id, "no-show"), help="Marcar Falta")
                        action_cols[4].button("❌", key=f"cancel_{ag_id}", on_click=handle_admin_action, args=(ag_id, "cancelar"), help="Cancelar Agendamento")

                if any(st.session_state.agendamentos_selecionados.values()):
                    st.button("❌ Cancelar Selecionados", type="primary", on_click=handle_cancelar_selecionados)
            else:
                st.info(f"Nenhuma consulta confirmada para {st.session_state.filter_data_selecionada.strftime('%d/%m/%Y')}.")

        with view_tab2:
            st.subheader("Agenda Semanal por Profissional")
            if not profissionais_clinica:
                st.warning("Cadastre um profissional para ver a agenda semanal.")
            else:
                prof_selecionado = st.selectbox("Selecione o Profissional", options=[p['nome'] for p in profissionais_clinica], key="semanal_prof_select")
                today = date.today()
                start_of_week = today - timedelta(days=today.weekday())
                
                df_semanal = gerar_visao_semanal(clinic_id, prof_selecionado, start_of_week)

                if df_semanal.empty:
                    st.info(f"Nenhum agendamento para {prof_selecionado} nesta semana.")
                else:
                    st.dataframe(df_semanal, use_container_width=True)

        with view_tab3:
            st.subheader("Agenda Comparativa do Dia")
            data_comparativa = st.date_input("Selecione a Data", key="comparativa_data_select")
            if not profissionais_clinica:
                st.warning("Cadastre profissionais para comparar as agendas.")
            else:
                df_comparativo = gerar_visao_comparativa(clinic_id, data_comparativa, [p['nome'] for p in profissionais_clinica])
                st.dataframe(df_comparativo.style.set_properties(**{'text-align': 'center'}), use_container_width=True)


    elif active_tab == "📈 Dashboard":
        # ... (código do dashboard, sem alterações) ...
        st.header("📈 Dashboard de Desempenho")
        
        hoje = datetime.now(TZ_SAO_PAULO).date()
        col1, col2 = st.columns(2)
        start_date = col1.date_input("Data de Início", hoje - timedelta(days=30))
        end_date = col2.date_input("Data de Fim", hoje)

        if start_date > end_date:
            st.error("A data de início não pode ser posterior à data de fim.")
        else:
            df_dashboard = get_dados_dashboard(clinic_id, start_date, end_date)

            if df_dashboard.empty:
                st.info("Não há dados de agendamento no período selecionado para gerar relatórios.")
            else:
                col_graf1, col_graf2 = st.columns(2)
                
                with col_graf1:
                    st.subheader("Agendamentos por Status")
                    status_counts = df_dashboard['status'].value_counts()
                    fig_pie = go.Figure(data=[go.Pie(labels=status_counts.index, values=status_counts.values, hole=.3)])
                    fig_pie.update_layout(showlegend=True, margin=dict(t=0, b=0, l=0, r=0))
                    st.plotly_chart(fig_pie, use_container_width=True)

                with col_graf2:
                    st.subheader("Atendimentos por Profissional")
                    prof_counts = df_dashboard['profissional_nome'].value_counts()
                    fig_bar = go.Figure(data=[go.Bar(x=prof_counts.index, y=prof_counts.values)])
                    fig_bar.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0), xaxis_title=None, yaxis_title="Nº de Atendimentos")
                    st.plotly_chart(fig_bar, use_container_width=True)

                st.subheader("Evolução de Atendimentos no Período")
                df_dashboard['data'] = df_dashboard['horario'].dt.date
                atendimentos_por_dia = df_dashboard.groupby('data').size().reset_index(name='contagem')
                atendimentos_por_dia = atendimentos_por_dia.sort_values('data')
                fig_line = go.Figure(data=go.Scatter(x=atendimentos_por_dia['data'], y=atendimentos_por_dia['contagem'], mode='lines+markers'))
                fig_line.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0), xaxis_title="Data", yaxis_title="Nº de Atendimentos")
                st.plotly_chart(fig_line, use_container_width=True)

                st.subheader("Mapa de Calor: Horários de Pico")
                df_confirmados = df_dashboard[df_dashboard['status'].isin(['Finalizado', 'Confirmado'])].copy()
                if not df_confirmados.empty:
                    df_confirmados['dia_semana_num'] = df_confirmados['horario'].dt.weekday
                    df_confirmados['dia_semana_nome'] = df_confirmados['horario'].dt.day_name()
                    df_confirmados['hora'] = df_confirmados['horario'].dt.hour
                    
                    heatmap_data = df_confirmados.pivot_table(index='hora', columns='dia_semana_num', values='id', aggfunc='count').fillna(0)
                    
                    dias_pt = {0: 'Segunda', 1: 'Terça', 2: 'Quarta', 3: 'Quinta', 4: 'Sexta', 5: 'Sábado', 6: 'Domingo'}
                    heatmap_data = heatmap_data.rename(columns=dias_pt)

                    ordem_dias = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
                    for dia in ordem_dias:
                        if dia not in heatmap_data.columns:
                            heatmap_data[dia] = 0
                    heatmap_data = heatmap_data[ordem_dias]

                    fig_heatmap = go.Figure(data=go.Heatmap(
                        z=heatmap_data.values,
                        x=heatmap_data.columns,
                        y=heatmap_data.index,
                        colorscale='Viridis'))
                    fig_heatmap.update_layout(
                        title='Concentração de Agendamentos por Dia e Hora',
                        xaxis_nticks=7,
                        yaxis_title="Hora do Dia")
                    st.plotly_chart(fig_heatmap, use_container_width=True)
                else:
                    st.info("Não há dados de agendamentos confirmados ou finalizados para gerar o mapa de calor.")

    elif active_tab == "👤 Gerenciar Clientes":
        # ... (código da aba de clientes, sem alterações) ...
        st.header("👤 Gerenciar Clientes")
        with st.form("add_cliente_form"):
            st.subheader("Cadastrar Novo Cliente")
            c1, c2 = st.columns(2)
            c1.text_input("Nome do Cliente", key="nome_novo_cliente")
            c2.text_input("Telefone", key="tel_novo_cliente")
            st.text_area("Observações", key="obs_novo_cliente")
            st.form_submit_button("Adicionar Cliente", on_click=handle_add_cliente)
        
        st.markdown("---")
        st.subheader("Clientes Cadastrados")
        if clientes_clinica:
            df_clientes = pd.DataFrame(clientes_clinica)
            st.dataframe(df_clientes[['nome', 'telefone', 'observacoes']], use_container_width=True)
            
            cliente_para_remover_nome = st.selectbox("Selecione um cliente para remover", options=[""] + [c['nome'] for c in clientes_clinica], key="cliente_remover_select")
            if cliente_para_remover_nome:
                cliente_id_remover = next((c['id'] for c in clientes_clinica if c['nome'] == cliente_para_remover_nome), None)
                if cliente_id_remover:
                    st.button(f"Remover {cliente_para_remover_nome}", type="primary", key=f"del_cliente_{cliente_id_remover}", on_click=handle_remove_cliente, args=(clinic_id, cliente_id_remover))
        else:
            st.info("Nenhum cliente cadastrado.")

    elif active_tab == "📋 Gerenciar Serviços":
        # ... (código da aba de serviços, sem alterações) ...
        st.header("📋 Gerenciar Serviços")
        with st.form("add_servico_form"):
            st.subheader("Cadastrar Novo Serviço")
            s1, s2 = st.columns(2)
            s1.text_input("Nome do Serviço", key="nome_novo_servico", placeholder="Ex: Sessão de Fisioterapia")
            s2.number_input("Duração Padrão (minutos)", min_value=15, step=15, key="duracao_novo_servico", value=30)
            st.form_submit_button("Adicionar Serviço", on_click=handle_add_servico)
            st.caption("A duração definida aqui impactará diretamente os horários disponíveis na agenda.")

        st.markdown("---")
        st.subheader("Serviços Cadastrados")
        if servicos_clinica:
            for servico in servicos_clinica:
                sc1, sc2, sc3 = st.columns([0.5, 0.3, 0.2])
                sc1.write(servico['nome'])
                sc2.write(f"{servico['duracao_min']} minutos")
                sc3.button("Remover", key=f"del_serv_{servico['id']}", on_click=handle_remove_servico, args=(clinic_id, servico['id']))
        else:
            st.info("Nenhum serviço cadastrado.")

    elif active_tab == "👥 Gerenciar Profissionais":
        # ... (código da aba de profissionais, sem alterações) ...
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
                col2.button("Remover", key=f"del_{prof['id']}", on_click=handle_remove_profissional, args=(clinic_id, prof['id']))
        else:
            st.info("Nenhum profissional cadastrado.")

    elif active_tab == "⚙️ Configurações":
        # ... (código da aba de configurações, sem alterações) ...
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
                        submit_cols[0].form_submit_button("✅ Salvar Alterações", on_click=handle_salvar_horarios_profissional, args=(prof_id,))
                        if submit_cols[1].form_submit_button("❌ Cancelar"):
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
                    
                    st.button("✏️ Editar Horários", key=f"edit_{prof_id}", on_click=entrar_modo_edicao, args=(prof_id,))

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
            if st.button("Importar Feriados do Ano"):
                handle_importar_feriados()

        feriados = listar_feriados(clinic_id)
        if feriados:
            st.write("Datas bloqueadas cadastradas:")
            for feriado in feriados:
                c1, c2, c3 = st.columns([0.4, 0.4, 0.2])
                c1.write(feriado['data'].strftime('%d/%m/%Y'))
                c2.write(feriado['descricao'])
                c3.button("Remover", key=f"del_feriado_{feriado['id']}", on_click=handle_remove_feriado, args=(clinic_id, feriado['id']))

def render_super_admin_panel():
    """Renderiza a página de gerenciamento do Super Administrador."""
    st.title("🔑 Painel do Super Administrador")
    st.sidebar.header("Modo Admin")
    if st.sidebar.button("Sair do Modo Admin"):
        handle_logout()

    st.subheader("Cadastrar Nova Clínica")
    with st.form("add_clinic_form", clear_on_submit=True):
        st.text_input("Nome Fantasia da Clínica", key="sa_nome_clinica")
        col1, col2 = st.columns(2)
        col1.text_input("Usuário (para login da clínica)", key="sa_user_clinica")
        col2.text_input("Senha (provisória)", key="sa_pwd_clinica", type="password")
        st.form_submit_button("Adicionar Clínica", on_click=handle_add_clinica)

    st.markdown("---")
    st.subheader("Clínicas Cadastradas")
    
    clinicas = listar_clinicas()
    if not clinicas:
        st.info("Nenhuma clínica cadastrada.")
    else:
        for clinica in clinicas:
            col1, col2, col3 = st.columns([0.5, 0.2, 0.3])
            with col1:
                st.write(f"**{clinica.get('nome_fantasia', 'Nome não definido')}**")
                st.caption(f"Usuário: {clinica.get('username')}")
            with col2:
                status = clinica.get('ativo', False)
                st.write("Status: " + ("✅ Ativa" if status else "❌ Inativa"))
            with col3:
                button_text = "Desativar" if status else "Ativar"
                st.button(button_text, key=f"toggle_{clinica['id']}", on_click=handle_toggle_status_clinica, args=(clinica['id'], status))

# --- ROTEAMENTO PRINCIPAL ---
pin_param = st.query_params.get("pin")

if pin_param:
    render_agendamento_seguro()
elif st.session_state.get('is_super_admin'):
    render_super_admin_panel()
elif 'clinic_id' in st.session_state and st.session_state.clinic_id:
    render_backoffice_clinica()
else:
    render_login_page()


