# app.py (VERSÃO COM GESTÃO DE TURMAS, SUPER ADMIN, PACOTES E GESTÃO DE AG. CLIENTE)
# ATUALIZADO:
# 1. [SOLUÇÃO DEFINITIVA] `handle_agendamento_submission` agora passa `cliente_id` para `salvar_agendamento`.
# 2. [SOLUÇÃO DEFINITIVA] Aba "Gerenciar Clientes" agora busca agendamentos futuros por `cliente_id`.

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
    salvar_agendamento, # Modificado para aceitar cliente_id
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
    # Funções de Turmas
    adicionar_turma,
    listar_turmas,
    remover_turma as db_remover_turma,
    atualizar_turma,
    # Funções para o Super Admin
    listar_clinicas,
    adicionar_clinica,
    toggle_status_clinica,
    # Funções de Pacotes (DATABASE)
    listar_pacotes_modelos,
    adicionar_pacote_modelo,
    remover_pacote_modelo as db_remover_pacote_modelo,
    listar_pacotes_do_cliente,
    deduzir_credito_pacote_cliente,
    # Função de agendamentos futuros modificada para usar cliente_id
    buscar_agendamentos_futuros_por_cliente
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
    # Função para Turmas
    gerar_turmas_disponiveis,
    get_dados_dashboard,
    gerar_visao_semanal,
    gerar_visao_comparativa,
    # Funções de Pacotes (LÓGICA)
    buscar_pacotes_validos_cliente,
    associar_pacote_cliente
)

# --- Configuração ---
st.set_page_config(layout="wide", page_title="Agenda Fit - Agendamento Inteligente")
TZ_SAO_PAULO = ZoneInfo('America/Sao_Paulo')
DIAS_SEMANA = {"seg": "Segunda", "ter": "Terça", "qua": "Quarta", "qui": "Quinta",
                "sex": "Sexta", "sab": "Sábado", "dom": "Domingo"}
DIAS_SEMANA_MAP_REV = {v: k for k, v in DIAS_SEMANA.items()}
DIAS_SEMANA_LISTA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

# Inicialização do DB
db_client = get_firestore_client()
if db_client is None:
    st.stop()

# --- INICIALIZAÇÃO DO SESSION STATE ---
if 'remarcando' not in st.session_state:
    st.session_state.remarcando = False
if 'agendamentos_selecionados' not in st.session_state:
    st.session_state.agendamentos_selecionados = {}
if 'remarcacao_status' not in st.session_state:
    st.session_state.remarcacao_status = None
if "clinic_id" not in st.session_state:
    st.session_state.clinic_id = None
if "clinic_name" not in st.session_state:
    st.session_state.clinic_name = None
if 'form_data_selecionada' not in st.session_state:
    st.session_state.form_data_selecionada = datetime.now(TZ_SAO_PAULO).date()
if 'filter_data_selecionada' not in st.session_state:
    st.session_state.filter_data_selecionada = datetime.now(TZ_SAO_PAULO).date()
if 'last_agendamento_info' not in st.session_state:
    st.session_state.last_agendamento_info = None
if 'editando_horario_id' not in st.session_state:
    st.session_state.editando_horario_id = None
if 'active_tab' not in st.session_state:
    st.session_state.active_tab = "🗓️ Agenda e Agendamento"
if 'agenda_cliente_select' not in st.session_state:
    st.session_state.agenda_cliente_select = "Novo Cliente"
if 'c_tel_input' not in st.session_state:
    st.session_state.c_tel_input = ""
if 'confirmando_agendamento' not in st.session_state:
    st.session_state.confirmando_agendamento = False
if 'detalhes_agendamento' not in st.session_state:
    st.session_state.detalhes_agendamento = {}
if 'is_super_admin' not in st.session_state:
    st.session_state.is_super_admin = False

# States para Pacotes
if 'agenda_cliente_id_selecionado' not in st.session_state:
    st.session_state.agenda_cliente_id_selecionado = None
if 'pacotes_validos_cliente' not in st.session_state:
    st.session_state.pacotes_validos_cliente = []
if 'pacote_status_placeholder' not in st.session_state:
    st.session_state.pacote_status_placeholder = None

# States para Remarcação na tela de Cliente
if 'remarcando_cliente_ag_id' not in st.session_state:
    st.session_state.remarcando_cliente_ag_id = None
if 'remarcacao_cliente_status' not in st.session_state:
    st.session_state.remarcacao_cliente_status = {}
if 'remarcacao_cliente_form_data' not in st.session_state:
    st.session_state.remarcacao_cliente_form_data = {}
if 'remarcacao_cliente_form_hora' not in st.session_state:
    st.session_state.remarcacao_cliente_form_hora = {}


# --- FUNÇÕES DE LÓGICA DA UI (HANDLERS) ---

def sync_dates_from_filter():
    pass

def handle_login():
    """Tenta autenticar a clínica ou o super admin."""
    username = st.session_state.login_username.strip()
    password = st.session_state.login_password.strip()

    super_admin_user = st.secrets.get("super_admin", {}).get("username")
    super_admin_pass = st.secrets.get("super_admin", {}).get("password")

    if super_admin_user:
        super_admin_user = super_admin_user.strip()
    if super_admin_pass:
        super_admin_pass = super_admin_pass.strip()

    if username == super_admin_user and password == super_admin_pass and super_admin_user is not None:
        st.session_state.is_super_admin = True
        st.session_state.clinic_id = None
        st.rerun()
        return

    clinica = buscar_clinica_por_login(username, password)
    if clinica:
        st.session_state.clinic_id = clinica['id']
        st.session_state.clinic_name = clinica.get('nome_fantasia', username)
        st.session_state.is_super_admin = False
        st.rerun()
    else:
        st.error("Usuário ou senha inválidos.")

def handle_logout():
    """Limpa a sessão e desloga o usuário."""
    keys_to_clear = ['clinic_id', 'clinic_name', 'editando_horario_id',
                     'active_tab', 'agenda_cliente_select', 'c_tel_input', 'confirmando_agendamento',
                     'detalhes_agendamento', 'form_data_selecionada', 'filter_data_selecionada',
                     'is_super_admin', 'agenda_cliente_id_selecionado', 'pacotes_validos_cliente',
                     'pacote_status_placeholder', 'remarcando_cliente_ag_id', 'remarcacao_cliente_status',
                     'remarcacao_cliente_form_data', 'remarcacao_cliente_form_hora']
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
    """Callback para atualizar telefone e ID do cliente e verificar pacotes."""
    cliente_selecionado = st.session_state.agenda_cliente_select
    if cliente_selecionado != "Novo Cliente":
        clientes = listar_clientes(st.session_state.clinic_id)
        cliente_data = next((c for c in clientes if c['nome'] == cliente_selecionado), None)
        if cliente_data:
            st.session_state.c_tel_input = cliente_data.get('telefone', '')
            st.session_state.agenda_cliente_id_selecionado = cliente_data.get('id')
        else:
            st.session_state.c_tel_input = ''
            st.session_state.agenda_cliente_id_selecionado = None
    else:
        st.session_state.c_tel_input = ''
        st.session_state.agenda_cliente_id_selecionado = None

    handle_verificar_pacotes()

def handle_verificar_pacotes():
    """Verifica pacotes válidos quando cliente ou serviço mudam."""
    cliente_id = st.session_state.get('agenda_cliente_id_selecionado')

    servico_nome = st.session_state.get('c_servico_input')
    servicos_clinica = listar_servicos(st.session_state.clinic_id)
    servico_obj = next((s for s in servicos_clinica if s['nome'] == servico_nome), None)
    servico_id = servico_obj['id'] if servico_obj else None

    placeholder = st.session_state.pacote_status_placeholder
    if not placeholder:
        try:
             st.session_state.pacote_status_placeholder = st.empty()
             placeholder = st.session_state.pacote_status_placeholder
        except Exception as e:
            print(f"Erro ao recriar placeholder: {e}")
            return

    if cliente_id and servico_id:
        pacotes_validos = buscar_pacotes_validos_cliente(
            st.session_state.clinic_id,
            cliente_id,
            servico_id
        )
        st.session_state.pacotes_validos_cliente = pacotes_validos
        if pacotes_validos:
            pacote = pacotes_validos[0]
            expiracao = pacote['data_expiracao'].strftime('%d/%m/%Y')
            msg = f"ℹ️ Cliente possui Pacote '{pacote['nome_pacote']}' com {pacote['creditos_restantes']}/{pacote['creditos_total']} créditos (válido até {expiracao})."
            placeholder.info(msg)
        else:
            placeholder.empty()
    else:
        st.session_state.pacotes_validos_cliente = []
        placeholder.empty()


def handle_pre_agendamento():
    """Coleta os dados do formulário e abre o diálogo de confirmação."""
    cliente_selecionado = st.session_state.agenda_cliente_select
    if cliente_selecionado == "Novo Cliente":
        cliente = st.session_state.get('c_nome_novo_cliente_input', '')
        telefone = st.session_state.get('c_tel_input', '')
        cliente_id = None # Novo cliente não tem ID ainda
    else:
        cliente = cliente_selecionado
        telefone = st.session_state.get('c_tel_input', '')
        cliente_id = st.session_state.get('agenda_cliente_id_selecionado') # Cliente existente tem ID

    servico_nome = st.session_state.c_servico_input
    servicos_clinica = listar_servicos(st.session_state.clinic_id)
    servico_obj = next((s for s in servicos_clinica if s['nome'] == servico_nome), None)

    if not servico_obj:
        st.error("Serviço não encontrado.")
        return

    is_turma = servico_obj.get('tipo', 'Individual') == 'Em Grupo'

    hora_consulta_raw = st.session_state.get('c_hora_input')

    if not cliente or not telefone or not hora_consulta_raw:
        st.warning("Por favor, preencha o nome do cliente, telefone e selecione um horário/turma válido.")
        return

    turma_id = None
    if is_turma:
        if isinstance(hora_consulta_raw, tuple) and len(hora_consulta_raw) == 2:
            turma_id, hora_consulta = hora_consulta_raw
        else:
            st.warning("Seleção de turma inválida.")
            return
    else:
        if isinstance(hora_consulta_raw, time):
            hora_consulta = hora_consulta_raw
        else:
            st.warning("Seleção de horário inválida.")
            return

    pacote_para_debitar_id = None
    pacote_info_msg = None
    if st.session_state.pacotes_validos_cliente:
        pacote = st.session_state.pacotes_validos_cliente[0]
        pacote_para_debitar_id = pacote['id']
        pacote_info_msg = f"Será debitado 1 crédito do pacote '{pacote['nome_pacote']}'."

    st.session_state.detalhes_agendamento = {
        'cliente': cliente,
        'telefone': telefone,
        'profissional': st.session_state.c_prof_input,
        'servico': servico_nome,
        'data': st.session_state.form_data_selecionada,
        'hora': hora_consulta,
        'cliente_era_novo': cliente_selecionado == "Novo Cliente",
        'turma_id': turma_id,
        'cliente_id': cliente_id, # <-- Passa o ID obtido
        'servico_id': servico_obj['id'],
        'pacote_cliente_id': pacote_para_debitar_id,
        'pacote_info_msg': pacote_info_msg
    }
    st.session_state.filter_data_selecionada = st.session_state.form_data_selecionada
    st.session_state.confirmando_agendamento = True
    st.rerun()

# <-- FUNÇÃO MODIFICADA -->
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

    disponivel = True
    msg_disponibilidade = ""
    if not detalhes['turma_id']:
        disponivel, msg_disponibilidade = verificar_disponibilidade_com_duracao(clinic_id, detalhes['profissional'], dt_consulta_local, duracao_servico)

    if disponivel:
        pin_code = gerar_token_unico()
        cliente_id_para_salvar = detalhes.get('cliente_id') # ID do cliente (pode ser None se for novo)

        # Se for cliente novo, cria primeiro para obter o ID
        if detalhes['cliente_era_novo']:
            # Modificar adicionar_cliente para retornar o ID seria o ideal
            # Solução alternativa: criar e depois buscar pelo telefone (menos robusto)
            adicionado = adicionar_cliente(clinic_id, detalhes['cliente'], detalhes['telefone'], "")
            if adicionado:
                # Tenta buscar o cliente recém-adicionado pelo telefone para pegar o ID
                clientes_atualizados = listar_clientes(clinic_id)
                cliente_novo_obj = next((c for c in clientes_atualizados if c.get('telefone') == detalhes['telefone'] and c.get('nome') == detalhes['cliente']), None)
                if cliente_novo_obj:
                    cliente_id_para_salvar = cliente_novo_obj['id']
                    print(f"Novo cliente '{detalhes['cliente']}' criado com ID: {cliente_id_para_salvar}")
                else:
                    print(f"ERRO: Não foi possível encontrar o ID do novo cliente '{detalhes['cliente']}' após adicioná-lo.")
                    st.warning("Não foi possível obter o ID do novo cliente. A associação com pacotes ou a busca futura por ID podem falhar.")
            else:
                 print(f"ERRO: Falha ao adicionar novo cliente '{detalhes['cliente']}'.")
                 st.error("Falha ao adicionar novo cliente.")
                 # Decide se quer prosseguir sem o ID ou parar
                 # Prosseguir sem ID significa que a busca futura falhará
                 cliente_id_para_salvar = None # Garante que é None se falhou


        dados = {
            'profissional_nome': detalhes['profissional'],
            'cliente': detalhes['cliente'],
            'cliente_id': cliente_id_para_salvar, # <-- Passa o ID obtido
            'telefone': detalhes['telefone'],
            'horario': dt_consulta_local,
            'servico_nome': detalhes['servico'],
            'duracao_min': duracao_servico,
            'turma_id': detalhes.get('turma_id'),
            'pacote_cliente_id': detalhes.get('pacote_cliente_id')
        }
        resultado = salvar_agendamento(clinic_id, dados, pin_code)

        if resultado is True:
            # Tenta deduzir o crédito se um pacote e um ID de cliente estiverem disponíveis
            if detalhes.get('pacote_cliente_id') and cliente_id_para_salvar:
                try:
                    deduzido = deduzir_credito_pacote_cliente(
                        clinic_id,
                        cliente_id_para_salvar, # Usa o ID obtido (novo ou existente)
                        detalhes['pacote_cliente_id']
                    )
                    if deduzido:
                        print(f"Crédito deduzido do pacote {detalhes['pacote_cliente_id']} para cliente {cliente_id_para_salvar}")
                    else:
                         print(f"Falha ao deduzir crédito do pacote {detalhes['pacote_cliente_id']} para cliente {cliente_id_para_salvar}")
                         st.warning("Agendamento salvo, mas falha ao deduzir o crédito do pacote.")
                except Exception as e:
                    print(f"ERRO AO DEDUZIR CRÉDITO (mas agendamento salvo): {e}")
                    st.warning(f"Agendamento salvo, mas ocorreu um erro ao deduzir o crédito: {e}")
            elif detalhes.get('pacote_cliente_id') and not cliente_id_para_salvar:
                 print("AVISO: Pacote selecionado, mas ID do cliente não disponível para dedução (pode ser novo cliente não encontrado).")
                 st.warning("Agendamento salvo, mas o crédito do pacote não pôde ser deduzido automaticamente.")


            link_gestao = f"https://agendafit.streamlit.app?pin={pin_code}"
            st.session_state.last_agendamento_info = {'cliente': detalhes['cliente'], 'link_gestao': link_gestao, 'pin_code': pin_code, 'status': True}
            st.session_state.form_data_selecionada = detalhes['data']
            st.session_state.filter_data_selecionada = detalhes['data']
        else:
            st.session_state.last_agendamento_info = {'cliente': detalhes['cliente'], 'status': str(resultado)}
    else:
        st.session_state.last_agendamento_info = {'cliente': detalhes['cliente'], 'status': msg_disponibilidade}

    # Reset state
    st.session_state.agenda_cliente_select = "Novo Cliente"
    st.session_state.c_tel_input = ""
    st.session_state.confirmando_agendamento = False
    st.session_state.detalhes_agendamento = {}
    st.session_state.pacotes_validos_cliente = []
    if st.session_state.pacote_status_placeholder:
        try: st.session_state.pacote_status_placeholder.empty()
        except: pass
    st.session_state.agenda_cliente_id_selecionado = None
    st.rerun()
# <-- FIM DA FUNÇÃO MODIFICADA -->

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
    """Handler para a página de gestão (PIN)"""
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
    """Handler genérico para ações de admin (cancelar, finalizar, no-show)"""
    if acao_admin_agendamento(id_agendamento, acao):
        st.success(f"Ação '{acao.upper()}' registrada com sucesso!")
        if st.session_state.remarcando_cliente_ag_id == id_agendamento:
             handle_cancelar_remarcacao_cliente(id_agendamento)
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
    tipo = st.session_state.tipo_novo_servico
    if nome and duracao > 0:
        if adicionar_servico(st.session_state.clinic_id, nome, duracao, tipo):
            st.success(f"Serviço '{nome}' adicionado com sucesso!")
            st.rerun()
        else:
            st.error("Erro ao adicionar serviço.")
    else:
        st.warning("Nome do serviço e duração maior que zero são obrigatórios.")

def handle_add_turma():
    clinic_id = st.session_state.clinic_id
    nome = st.session_state.get("turma_nome")
    servico_id = st.session_state.get("turma_servico")
    profissional_id = st.session_state.get("turma_profissional")
    capacidade = st.session_state.get("turma_capacidade")
    dias_semana_nomes = st.session_state.get("turma_dias_semana")
    horario = st.session_state.get("turma_horario")

    if not all([nome, servico_id, profissional_id, capacidade, dias_semana_nomes, horario]):
        st.warning("Todos os campos são obrigatórios para criar a turma.")
        return

    dias_semana_keys = [DIAS_SEMANA_MAP_REV[dia] for dia in dias_semana_nomes]

    dados_turma = {
        "nome": nome,
        "servico_id": servico_id,
        "profissional_id": profissional_id,
        "capacidade_maxima": capacidade,
        "dias_semana": dias_semana_keys,
        "horario": horario.strftime("%H:%M")
    }

    if adicionar_turma(clinic_id, dados_turma):
        st.success(f"Turma '{nome}' criada com sucesso!")
        st.rerun()
    else:
        st.error("Ocorreu um erro ao criar a turma.")

def handle_update_turma(turma_id: str):
    """Salva as alterações de uma turma existente."""
    clinic_id = st.session_state.clinic_id

    nome = st.session_state.get(f"edit_turma_nome_{turma_id}")
    servico_id = st.session_state.get(f"edit_turma_servico_{turma_id}")
    profissional_id = st.session_state.get(f"edit_turma_profissional_{turma_id}")
    capacidade = st.session_state.get(f"edit_turma_capacidade_{turma_id}")
    dias_semana_nomes = st.session_state.get(f"edit_turma_dias_semana_{turma_id}")
    horario = st.session_state.get(f"edit_turma_horario_{turma_id}")

    if not all([turma_id, nome, servico_id, profissional_id, capacidade, dias_semana_nomes, horario]):
        st.warning("Todos os campos são obrigatórios para editar a turma.")
        return

    dias_semana_keys = [DIAS_SEMANA_MAP_REV[dia] for dia in dias_semana_nomes]

    dados_turma = {
        "nome": nome,
        "servico_id": servico_id,
        "profissional_id": profissional_id,
        "capacidade_maxima": capacidade,
        "dias_semana": dias_semana_keys,
        "horario": horario.strftime("%H:%M")
    }

    if atualizar_turma(clinic_id, turma_id, dados_turma):
        st.success(f"Turma '{nome}' atualizada com sucesso!")
        st.session_state.turma_edit_select = ""
        st.rerun()
    else:
        st.error("Ocorreu um erro ao atualizar a turma.")

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

def handle_remove_turma(clinic_id: str, turma_id: str):
    if db_remover_turma(clinic_id, turma_id):
        st.success("Turma removida com sucesso!")
        st.rerun()
    else:
        st.error("Erro ao remover turma.")

# Handlers para Pacotes

def handle_add_pacote_modelo():
    clinic_id = st.session_state.clinic_id
    nome = st.session_state.get("pacote_nome")
    creditos = st.session_state.get("pacote_creditos")
    validade = st.session_state.get("pacote_validade")
    servicos_validos = st.session_state.get("pacote_servicos_ids")
    preco = st.session_state.get("pacote_preco", 0.0)

    if not all([nome, creditos, validade, servicos_validos]):
        st.warning("Nome, Créditos, Validade e ao menos um Serviço Válido são obrigatórios.")
        return

    dados_pacote = {
        "nome": nome,
        "creditos_sessoes": creditos,
        "validade_dias": validade,
        "servicos_validos": servicos_validos,
        "preco": preco
    }

    if adicionar_pacote_modelo(clinic_id, dados_pacote):
        st.success(f"Modelo de Pacote '{nome}' criado com sucesso!")
        st.rerun()
    else:
        st.error("Erro ao criar modelo de pacote.")

def handle_remove_pacote_modelo(clinic_id: str, pacote_id: str):
    if db_remover_pacote_modelo(clinic_id, pacote_id):
        st.success("Modelo de pacote removido com sucesso!")
        st.rerun()
    else:
        st.error("Erro ao remover modelo de pacote.")

def handle_associar_pacote_cliente(cliente_id: str):
    clinic_id = st.session_state.clinic_id
    pacote_modelo_id = st.session_state.get(f"pacote_assoc_select_{cliente_id}")

    if not pacote_modelo_id:
        st.warning("Selecione um pacote para associar.")
        return

    sucesso, msg = associar_pacote_cliente(clinic_id, cliente_id, pacote_modelo_id)
    if sucesso:
        st.success(msg)
        st.rerun()
    else:
        st.error(msg)

# Handlers para Remarcação na tela de Cliente
def handle_iniciar_remarcacao_cliente(agendamento: dict):
    """Define o estado para mostrar o formulário de remarcação na tela do cliente."""
    ag_id = agendamento['id']
    st.session_state.remarcando_cliente_ag_id = ag_id
    st.session_state.remarcacao_cliente_status[ag_id] = {}

    data_atual = agendamento.get('horario', datetime.now(TZ_SAO_PAULO)).date()
    if data_atual < date.today():
        data_atual = date.today()
    st.session_state.remarcacao_cliente_form_data[ag_id] = data_atual

def handle_cancelar_remarcacao_cliente(ag_id: str):
    """Esconde o formulário de remarcação."""
    st.session_state.remarcando_cliente_ag_id = None
    st.session_state.remarcacao_cliente_status[ag_id] = {}

def handle_confirmar_remarcacao_cliente(agendamento: dict):
    """Processa a remarcação a partir da tela do cliente."""
    ag_id = agendamento['id']
    nova_data = st.session_state.remarcacao_cliente_form_data.get(ag_id)
    nova_hora = st.session_state.remarcacao_cliente_form_hora.get(ag_id)

    if not isinstance(nova_hora, time) or not nova_data:
        st.session_state.remarcacao_cliente_status[ag_id] = {'sucesso': False, 'mensagem': "Selecione uma data e um horário válidos."}
        st.rerun()
        return

    novo_horario_naive = datetime.combine(nova_data, nova_hora)
    novo_horario_local = novo_horario_naive.replace(tzinfo=TZ_SAO_PAULO)

    clinic_id = agendamento['clinic_id']
    profissional_nome = agendamento['profissional_nome']
    duracao = agendamento.get('duracao_min', 30)

    disponivel, msg = verificar_disponibilidade_com_duracao(
        clinic_id,
        profissional_nome,
        novo_horario_local,
        duracao,
        agendamento_id_excluir=ag_id
    )

    if not disponivel:
        st.session_state.remarcacao_cliente_status[ag_id] = {'sucesso': False, 'mensagem': msg}
    else:
        from database import atualizar_horario_agendamento
        if atualizar_horario_agendamento(ag_id, novo_horario_local):
            st.session_state.remarcacao_cliente_status[ag_id] = {'sucesso': True, 'mensagem': "Remarcado com sucesso!"}
            st.session_state.remarcando_cliente_ag_id = None
        else:
            st.session_state.remarcacao_cliente_status[ag_id] = {'sucesso': False, 'mensagem': "Erro ao salvar no banco de dados."}

    st.rerun()

# --- RENDERIZAÇÃO DAS PÁGINAS ---

def render_login_page():
    st.title("Bem-vindo ao Agenda Fit!")
    st.write("Faça login para gerenciar sua clínica ou acesse o painel de administrador.")
    with st.form("login_form"):
        st.text_input("Usuário", key="login_username")
        st.text_input("Senha", type="password", key="login_password")
        st.form_submit_button("Entrar", on_click=handle_login)

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

    if agendamento.get('turma_id'):
        st.info("Agendamentos de turmas não podem ser remarcados ou cancelados individualmente por este link.")
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

def render_gerenciar_pacotes(servicos_clinica):
    st.header("🛍️ Gerenciar Pacotes")

    with st.form("add_pacote_modelo_form", clear_on_submit=True):
        st.subheader("Criar Novo Modelo de Pacote")

        c1, c2 = st.columns(2)
        c1.text_input("Nome do Pacote", key="pacote_nome", placeholder="Ex: Pacote 10 Sessões Pilates")
        c2.number_input("Preço (Opcional, para referência)", key="pacote_preco", min_value=0.0, step=0.01, format="%.2f")

        c3, c4 = st.columns(2)
        c3.number_input("Número de Créditos/Sessões", key="pacote_creditos", min_value=1, step=1)
        c4.number_input("Validade (em dias)", key="pacote_validade", min_value=1, step=1, value=30)

        servicos_map = {s['nome']: s['id'] for s in servicos_clinica}
        if not servicos_map:
            st.error("Nenhum serviço cadastrado. Crie serviços primeiro na aba '📋 Gerenciar Serviços'.")
            st.form_submit_button("Criar Pacote", disabled=True)
        else:
            nomes_servicos_selecionados = st.multiselect(
                "Serviços Válidos para este Pacote",
                options=servicos_map.keys()
            )
            st.session_state.pacote_servicos_ids = [servicos_map[nome] for nome in nomes_servicos_selecionados]
            st.form_submit_button("Criar Pacote", on_click=handle_add_pacote_modelo)

    st.divider()
    st.subheader("Modelos de Pacotes Existentes")
    modelos_pacotes = listar_pacotes_modelos(st.session_state.clinic_id)
    if not modelos_pacotes:
        st.info("Nenhum modelo de pacote criado.")
    else:
        servicos_map_inv = {s['id']: s['nome'] for s in servicos_clinica}
        for pacote in modelos_pacotes:
            col1, col2 = st.columns([0.8, 0.2])
            with col1:
                st.write(f"**{pacote['nome']}**")
                nomes_servicos = [servicos_map_inv.get(sid, 'Serviço Removido') for sid in pacote.get('servicos_validos', [])]
                st.caption(f"{pacote.get('creditos_sessoes', 'N/A')} créditos | Validade: {pacote.get('validade_dias', 'N/A')} dias | Preço: R$ {pacote.get('preco', 0.0):.2f}")
                st.caption(f"Serviços: {', '.join(nomes_servicos)}")
            with col2:
                st.button("Remover", key=f"del_pacote_{pacote['id']}", on_click=handle_remove_pacote_modelo, args=(st.session_state.clinic_id, pacote['id']))


def render_backoffice_clinica():
    clinic_id = st.session_state.clinic_id

    try:
        if st.session_state.form_data_selecionada < date.today():
            st.session_state.form_data_selecionada = date.today()
    except TypeError:
        st.session_state.form_data_selecionada = date.today()

    st.sidebar.header(f"Clínica: {st.session_state.clinic_name}")
    if st.sidebar.button("Sair"):
        handle_logout()

    profissionais_clinica = listar_profissionais(clinic_id)
    clientes_clinica = listar_clientes(clinic_id)
    servicos_clinica = listar_servicos(clinic_id)
    turmas_clinica = listar_turmas(clinic_id, profissionais_clinica, servicos_clinica)

    tab_options = ["🗓️ Agenda e Agendamento", "📅 Gerenciar Turmas", "🛍️ Gerenciar Pacotes", "📈 Dashboard", "👤 Gerenciar Clientes", "📋 Gerenciar Serviços", "👥 Gerenciar Profissionais", "⚙️ Configurações"]

    active_tab = st.radio(
        "Navegação",
        tab_options,
        key="active_tab",
        horizontal=True,
        label_visibility="collapsed"
    )

    if active_tab == "🗓️ Agenda e Agendamento":
        st.header("📝 Agendamento Rápido e Manual")

        if st.session_state.get('confirmando_agendamento', False):
            st.subheader("Revisar e Confirmar Agendamento")
            detalhes = st.session_state.detalhes_agendamento
            st.write(f"**Cliente:** {detalhes['cliente']}")
            st.write(f"**Telefone:** {detalhes['telefone']}")
            st.write(f"**Profissional:** {detalhes['profissional']}")
            st.write(f"**Serviço:** {detalhes['servico']}")
            st.write(f"**Data:** {detalhes['data'].strftime('%d/%m/%Y')}")
            st.write(f"**Horário:** {detalhes['hora'].strftime('%H:%M')}")
            if detalhes.get('turma_id'):
                st.write(f"**Modalidade:** Em Grupo / Turma")

            if detalhes.get('pacote_info_msg'):
                st.info(detalhes['pacote_info_msg'])

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
            st.selectbox("Cliente:", options=opcoes_clientes, key="agenda_cliente_select", on_change=handle_selecao_cliente)

            if 'pacote_status_placeholder' not in st.session_state or st.session_state.pacote_status_placeholder is None:
                st.session_state.pacote_status_placeholder = st.empty()
            handle_verificar_pacotes()


            st.subheader("2. Preencha os Detalhes do Agendamento")

            if st.session_state.agenda_cliente_select == "Novo Cliente":
                col_nome, col_tel = st.columns(2)
                col_nome.text_input("Nome do Novo Cliente", key="c_nome_novo_cliente_input")
                col_tel.text_input("Telefone", key="c_tel_input")
            else:
                st.markdown(f"**Agendando para:** {st.session_state.agenda_cliente_select}")
                st.text_input("Telefone (edite se necessário)", key="c_tel_input")

            st.divider()

            form_cols = st.columns(3)
            form_cols[1].date_input("Data:", key="form_data_selecionada", min_value=date.today())
            servico_selecionado_nome = form_cols[2].selectbox("Serviço:", [s['nome'] for s in servicos_clinica], key="c_servico_input", on_change=handle_verificar_pacotes)

            servico_data = next((s for s in servicos_clinica if s['nome'] == servico_selecionado_nome), None)

            if servico_data:
                tipo_servico = servico_data.get('tipo', 'Individual')
                duracao_servico = servico_data['duracao_min']

                if tipo_servico == 'Em Grupo':
                    turmas_disponiveis = gerar_turmas_disponiveis(
                        clinic_id,
                        st.session_state.form_data_selecionada,
                        turmas_clinica,
                    )

                    opcoes_turmas = {f"{t['horario_str']} - {t['nome']} ({t['profissional_nome']}) - {t['vagas_ocupadas']}/{t['capacidade_maxima']} vagas": (t['id'], t['horario_obj']) for t in turmas_disponiveis if t['vagas_disponiveis'] > 0}

                    profissional_nome_turma = "-- (Selecione uma turma) --"
                    pode_agendar = False

                    if opcoes_turmas:
                        selecao = form_cols[1].selectbox("Turma:", options=opcoes_turmas.keys(), key="c_hora_input_raw")
                        st.session_state.c_hora_input = opcoes_turmas[selecao]
                        turma_id_selecionado = opcoes_turmas[selecao][0]
                        turma_selecionada_obj = next((t for t in turmas_clinica if t['id'] == turma_id_selecionado), None)
                        if turma_selecionada_obj:
                            profissional_nome_turma = turma_selecionada_obj.get('profissional_nome', 'N/A')
                        pode_agendar = True
                    else:
                        if turmas_disponiveis:
                            form_cols[1].selectbox("Turma:", options=["Nenhuma turma com vagas disponíveis"], key="c_hora_input", disabled=True)
                        else:
                            form_cols[1].selectbox("Turma:", options=["Nenhuma turma disponível para este dia"], key="c_hora_input", disabled=True)
                        pode_agendar = False

                    form_cols[0].text_input("Profissional:", value=profissional_nome_turma, disabled=True)
                    st.session_state.c_prof_input = profissional_nome_turma

                else: # Individual
                    form_cols[0].selectbox("Profissional:", [p['nome'] for p in profissionais_clinica], key="c_prof_input")
                    horarios_disponiveis = gerar_horarios_disponiveis(
                        clinic_id,
                        st.session_state.c_prof_input,
                        st.session_state.form_data_selecionada,
                        duracao_servico
                    )
                    if horarios_disponiveis:
                        form_cols[1].selectbox("Hora:", options=horarios_disponiveis, key="c_hora_input", format_func=lambda t: t.strftime('%H:%M'))
                        pode_agendar = True
                    else:
                        form_cols[1].selectbox("Hora:", options=["Nenhum horário disponível"], key="c_hora_input", disabled=True)
                        pode_agendar = False

                st.button("AGENDAR NOVA SESSÃO", type="primary", disabled=not pode_agendar, on_click=handle_pre_agendamento)

        st.markdown("---")
        st.header("🗓️ Visualização da Agenda")

        view_tab1, view_tab2, view_tab3 = st.tabs(["Visão Diária (Lista)", "Visão Semanal (Profissional)", "Visão Comparativa (Diária)"])

        with view_tab1:
            st.date_input("Filtrar por data:", key='filter_data_selecionada', format="DD/MM/YYYY")

            agenda_do_dia = buscar_agendamentos_por_data(clinic_id, st.session_state.filter_data_selecionada)

            if not agenda_do_dia.empty:
                turmas_na_agenda = {}
                agendamentos_individuais = []

                for _, row in agenda_do_dia.iterrows():
                    if pd.notna(row.get('turma_id')):
                        turma_id = row['turma_id']
                        horario_key = row['horario'].strftime('%H:%M')
                        key = (turma_id, horario_key)

                        if key not in turmas_na_agenda:
                            turma_info = next((t for t in turmas_clinica if t['id'] == turma_id), None)
                            turmas_na_agenda[key] = {
                                'nome_turma': turma_info['nome'] if turma_info else 'Turma Removida',
                                'profissional_nome': turma_info['profissional_nome'] if turma_info else 'N/A',
                                'horario': row['horario'],
                                'capacidade': turma_info['capacidade_maxima'] if turma_info else 'N/A',
                                'clientes': []
                            }
                        turmas_na_agenda[key]['clientes'].append(row)
                    else:
                        agendamentos_individuais.append(row)

                if turmas_na_agenda:
                    st.subheader("Aulas em Grupo")
                    for (turma_id, _), turma_data in sorted(turmas_na_agenda.items(), key=lambda item: item[1]['horario']):
                        expander_title = f"{turma_data['horario'].strftime('%H:%M')} - {turma_data['nome_turma']} ({turma_data['profissional_nome']}) - {len(turma_data['clientes'])}/{turma_data['capacidade']} vagas"
                        with st.expander(expander_title):
                            for cliente_row in turma_data['clientes']:
                                st.write(f" - {cliente_row['cliente']} ({cliente_row.get('servico_nome', 'N/A')}) (Tel: {cliente_row.get('telefone', 'N/A')})")
                    st.divider()

                if agendamentos_individuais:
                    st.subheader("Atendimentos Individuais")
                    for row in sorted(agendamentos_individuais, key=lambda r: r['horario']):
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
                                if pd.notna(row.get('pacote_cliente_id')):
                                    nome_pacote_usado = "ID Pacote: ..." + row['pacote_cliente_id'][-5:]
                                    st.markdown(f"**Usou Pacote:** Sim ({nome_pacote_usado})")


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

                        if row.get('pacote_cliente_id'):
                            st.caption("💳 Agendamento via Pacote")

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

    elif active_tab == "📅 Gerenciar Turmas":
        st.header("📅 Gerenciar Turmas")

        with st.form("add_turma_form", clear_on_submit=True):
            st.subheader("Criar Nova Turma")

            servicos_map = {s['nome']: s['id'] for s in servicos_clinica if s.get('tipo') == 'Em Grupo'}
            profissionais_map = {p['nome']: p['id'] for p in profissionais_clinica}

            if not servicos_map:
                st.warning("Para criar uma turma, primeiro cadastre um serviço do tipo 'Em Grupo' na aba 'Gerenciar Serviços'.")
            elif not profissionais_map:
                 st.warning("Para criar uma turma, primeiro cadastre um profissional na aba 'Gerenciar Profissionais'.")
            else:
                c1, c2 = st.columns(2)
                c1.text_input("Nome da Turma", key="turma_nome", placeholder="Ex: Pilates Avançado")
                c2.number_input("Capacidade Máxima", min_value=1, step=1, key="turma_capacidade")

                c3, c4 = st.columns(2)
                servico_nome_selecionado = c3.selectbox("Serviço Associado", options=servicos_map.keys())
                st.session_state.turma_servico = servicos_map.get(servico_nome_selecionado)

                prof_nome_selecionado = c4.selectbox("Profissional Responsável", options=profissionais_map.keys())
                st.session_state.turma_profissional = profissionais_map.get(prof_nome_selecionado)

                st.multiselect("Recorrência (Dias da Semana)", options=DIAS_SEMANA_LISTA, key="turma_dias_semana")
                st.time_input("Horário de Início", key="turma_horario", step=timedelta(minutes=15), value=time(18,0))

                st.form_submit_button("Criar Turma", on_click=handle_add_turma)

        st.divider()
        st.subheader("Editar Turma Existente")

        if not turmas_clinica:
            st.info("Nenhuma turma cadastrada para editar.")
        else:
            servicos_map = {s['nome']: s['id'] for s in servicos_clinica if s.get('tipo') == 'Em Grupo'}
            profissionais_map = {p['nome']: p['id'] for p in profissionais_clinica}

            turmas_map_edit = {t['nome']: t['id'] for t in turmas_clinica}
            turma_nome_selecionada_edit = st.selectbox("Selecione a turma para editar", options=[""] + list(turmas_map_edit.keys()), key="turma_edit_select")

            if turma_nome_selecionada_edit:
                turma_id_para_editar = turmas_map_edit[turma_nome_selecionada_edit]
                turma_obj = next((t for t in turmas_clinica if t['id'] == turma_id_para_editar), None)

                if turma_obj and servicos_map and profissionais_map:
                    with st.form(f"edit_turma_form_{turma_id_para_editar}", clear_on_submit=False):
                        st.write(f"Editando: **{turma_obj['nome']}**")

                        default_servico_nome = next((nome for nome, id_s in servicos_map.items() if id_s == turma_obj.get('servico_id')), None)
                        default_prof_nome = next((nome for nome, id_p in profissionais_map.items() if id_p == turma_obj.get('profissional_id')), None)
                        default_dias = [DIAS_SEMANA[key] for key in turma_obj.get('dias_semana', []) if key in DIAS_SEMANA]
                        try:
                            default_horario = datetime.strptime(turma_obj.get('horario', '18:00'), "%H:%M").time()
                        except ValueError:
                            default_horario = time(18, 0)

                        index_servico = list(servicos_map.keys()).index(default_servico_nome) if default_servico_nome in servicos_map else 0
                        index_prof = list(profissionais_map.keys()).index(default_prof_nome) if default_prof_nome in profissionais_map else 0

                        c1_edit, c2_edit = st.columns(2)
                        c1_edit.text_input("Nome da Turma", key=f"edit_turma_nome_{turma_id_para_editar}", value=turma_obj.get('nome'))
                        c2_edit.number_input("Capacidade Máxima", min_value=1, step=1, key=f"edit_turma_capacidade_{turma_id_para_editar}", value=turma_obj.get('capacidade_maxima', 1))

                        c3_edit, c4_edit = st.columns(2)

                        servico_nome_selecionado_edit = c3_edit.selectbox("Serviço Associado",
                                                                         options=servicos_map.keys(),
                                                                         key=f"edit_turma_servico_nome_{turma_id_para_editar}",
                                                                         index=index_servico)
                        st.session_state[f"edit_turma_servico_{turma_id_para_editar}"] = servicos_map.get(servico_nome_selecionado_edit)

                        prof_nome_selecionado_edit = c4_edit.selectbox("Profissional Responsável",
                                                                     options=profissionais_map.keys(),
                                                                     key=f"edit_turma_prof_nome_{turma_id_para_editar}",
                                                                     index=index_prof)
                        st.session_state[f"edit_turma_profissional_{turma_id_para_editar}"] = profissionais_map.get(prof_nome_selecionado_edit)

                        st.multiselect("Recorrência (Dias da Semana)", options=DIAS_SEMANA_LISTA, key=f"edit_turma_dias_semana_{turma_id_para_editar}", default=default_dias)
                        st.time_input("Horário de Início", key=f"edit_turma_horario_{turma_id_para_editar}", step=timedelta(minutes=15), value=default_horario)

                        st.form_submit_button("Salvar Alterações", on_click=handle_update_turma, args=(turma_id_para_editar,))
                elif not servicos_map:
                    st.warning("Não é possível editar turmas pois não há serviços 'Em Grupo' cadastrados.")
                elif not profissionais_map:
                    st.warning("Não é possível editar turmas pois não há profissionais cadastrados.")

        st.divider()
        st.subheader("Grade de Aulas Semanal")
        if not turmas_clinica:
            st.info("Nenhuma turma cadastrada.")
        else:
            grade = {dia: [] for dia in DIAS_SEMANA_LISTA}
            horarios = sorted(list(set(t['horario'] for t in turmas_clinica if 'horario' in t)))

            grade_df_data = {}
            for horario in horarios:
                linha = {}
                for dia_nome in DIAS_SEMANA_LISTA:
                    dia_key = DIAS_SEMANA_MAP_REV[dia_nome]
                    turmas_no_horario = [
                        f"{t['nome']} ({t.get('profissional_nome', 'N/A')})"
                        for t in turmas_clinica if t.get('horario') == horario and dia_key in t.get('dias_semana', [])
                    ]
                    linha[dia_nome] = ", ".join(turmas_no_horario) if turmas_no_horario else ""
                if any(linha.values()):
                    grade_df_data[horario] = linha

            if grade_df_data:
                grade_df = pd.DataFrame.from_dict(grade_df_data, orient='index')
                grade_df = grade_df.sort_index()
                st.dataframe(grade_df, use_container_width=True)
            else:
                 st.info("Nenhuma turma encontrada para exibir na grade.")

        st.divider()
        st.subheader("Remover Turma")
        if turmas_clinica:
            turma_para_remover_nome = st.selectbox("Selecione uma turma para remover", options=[""] + [t['nome'] for t in turmas_clinica], key="turma_remover_select")
            if turma_para_remover_nome:
                turma_id_remover = next((t['id'] for t in turmas_clinica if t['nome'] == turma_para_remover_nome), None)
                if turma_id_remover:
                    st.button(f"Remover {turma_para_remover_nome}", type="primary", key=f"del_turma_{turma_id_remover}", on_click=handle_remove_turma, args=(clinic_id, turma_id_remover))

    elif active_tab == "🛍️ Gerenciar Pacotes":
        render_gerenciar_pacotes(servicos_clinica)

    elif active_tab == "📈 Dashboard":
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
                    if 'profissional_nome' in df_dashboard.columns:
                        prof_counts = df_dashboard['profissional_nome'].value_counts()
                        fig_bar = go.Figure(data=[go.Bar(x=prof_counts.index, y=prof_counts.values)])
                        fig_bar.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0), xaxis_title=None, yaxis_title="Nº de Atendimentos")
                        st.plotly_chart(fig_bar, use_container_width=True)
                    else:
                        st.warning("Coluna 'profissional_nome' não encontrada nos dados.")

                st.subheader("Evolução de Atendimentos no Período")
                if 'horario' in df_dashboard.columns and pd.api.types.is_datetime64_any_dtype(df_dashboard['horario']):
                    df_dashboard['data'] = df_dashboard['horario'].dt.date
                    atendimentos_por_dia = df_dashboard.groupby('data').size().reset_index(name='contagem')
                    atendimentos_por_dia = atendimentos_por_dia.sort_values('data')
                    fig_line = go.Figure(data=go.Scatter(x=atendimentos_por_dia['data'], y=atendimentos_por_dia['contagem'], mode='lines+markers'))
                    fig_line.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0), xaxis_title="Data", yaxis_title="Nº de Atendimentos")
                    st.plotly_chart(fig_line, use_container_width=True)
                else:
                    st.warning("Coluna 'horario' não encontrada ou não é do tipo data/hora.")

                st.subheader("Mapa de Calor: Horários de Pico")
                df_confirmados = df_dashboard[df_dashboard['status'].isin(['Finalizado', 'Confirmado'])].copy()

                if not df_confirmados.empty and 'horario' in df_confirmados.columns and pd.api.types.is_datetime64_any_dtype(df_confirmados['horario']):
                    df_confirmados['dia_semana_num'] = df_confirmados['horario'].dt.weekday
                    df_confirmados['hora'] = df_confirmados['horario'].dt.hour

                    if 'id' in df_confirmados.columns:
                        heatmap_data = df_confirmados.pivot_table(index='hora', columns='dia_semana_num', values='id', aggfunc='count').fillna(0)

                        dias_pt = {0: 'Segunda', 1: 'Terça', 2: 'Quarta', 3: 'Quinta', 4: 'Sexta', 5: 'Sábado', 6: 'Domingo'}
                        heatmap_data = heatmap_data.rename(columns=dias_pt)

                        ordem_dias = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
                        for dia in ordem_dias:
                            if dia not in heatmap_data.columns:
                                heatmap_data[dia] = 0
                        heatmap_data = heatmap_data[ordem_dias]

                        fig_heatmap = go.Figure(data=go.Heatmap(z=heatmap_data.values, x=heatmap_data.columns, y=heatmap_data.index, colorscale='Viridis'))
                        fig_heatmap.update_layout(title='Concentração de Agendamentos por Dia e Hora', xaxis_nticks=7, yaxis_title="Hora do Dia")
                        st.plotly_chart(fig_heatmap, use_container_width=True)
                    else:
                        st.warning("Coluna 'id' não encontrada para gerar o mapa de calor.")
                elif df_confirmados.empty:
                    st.info("Não há dados de agendamentos confirmados ou finalizados para gerar o mapa de calor.")
                else:
                     st.warning("Coluna 'horario' ausente ou inválida para gerar o mapa de calor.")


    # <-- ABA MODIFICADA -->
    elif active_tab == "👤 Gerenciar Clientes":
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

        modelos_pacotes = listar_pacotes_modelos(clinic_id)
        modelos_pacotes_map = {p['nome']: p['id'] for p in modelos_pacotes}

        turmas_map = {t['id']: t['nome'] for t in turmas_clinica}

        if clientes_clinica:
            for cliente in clientes_clinica:
                cliente_id = cliente.get('id') # Pega o ID do cliente
                if not cliente_id:
                    st.warning(f"Cliente '{cliente.get('nome','N/A')}' sem ID, pulando.")
                    continue

                with st.expander(f"{cliente['nome']} - {cliente.get('telefone', 'Sem telefone')}"):
                    st.write(f"**Observações:** {cliente.get('observacoes', 'N/A')}")
                    st.button("Remover Cliente", type="primary", key=f"del_cliente_{cliente_id}", on_click=handle_remove_cliente, args=(clinic_id, cliente_id))

                    st.divider()
                    st.subheader("Pacotes do Cliente")

                    pacotes_do_cliente = listar_pacotes_do_cliente(clinic_id, cliente_id)
                    if not pacotes_do_cliente:
                        st.info("Cliente não possui pacotes.")
                    else:
                        hoje_tz = datetime.now(TZ_SAO_PAULO)
                        data_pacotes = []
                        for p in pacotes_do_cliente:
                            status = "Ativo"
                            if isinstance(p.get('data_expiracao'), datetime) and p['data_expiracao'] < hoje_tz:
                                status = "Expirado"
                            elif p.get('creditos_restantes', 0) <= 0:
                                status = "Esgotado"

                            data_pacotes.append({
                                "Pacote": p.get('nome_pacote_modelo', 'N/A'),
                                "Créditos": f"{p.get('creditos_restantes','N/A')} / {p.get('creditos_total','N/A')}",
                                "Expira em": p['data_expiracao'].strftime('%d/%m/%Y') if isinstance(p.get('data_expiracao'), datetime) else 'N/A',
                                "Status": status
                            })
                        st.dataframe(pd.DataFrame(data_pacotes), use_container_width=True, hide_index=True)

                    st.subheader("Associar Novo Pacote")
                    if not modelos_pacotes_map:
                        st.warning("Nenhum modelo de pacote criado. Crie um na aba '🛍️ Gerenciar Pacotes'.")
                    else:
                        cols_assoc = st.columns([0.7, 0.3])

                        pacote_nome_selecionado = cols_assoc[0].selectbox(
                            "Selecione o Pacote Modelo:",
                            options=[""] + list(modelos_pacotes_map.keys()),
                            key=f"pacote_assoc_select_nome_{cliente_id}",
                            label_visibility="collapsed"
                        )
                        st.session_state[f"pacote_assoc_select_{cliente_id}"] = modelos_pacotes_map.get(pacote_nome_selecionado)

                        cols_assoc[1].button(
                            "Associar Pacote",
                            key=f"btn_assoc_{cliente_id}",
                            on_click=handle_associar_pacote_cliente,
                            args=(cliente_id,)
                        )

                    st.divider()
                    st.subheader("Agendamentos Futuros")

                    # <-- CHAMADA MODIFICADA: Usa cliente_id -->
                    agendamentos_futuros = buscar_agendamentos_futuros_por_cliente(clinic_id, cliente_id)
                    # <-- FIM DA CHAMADA MODIFICADA -->

                    print(f"[DIAGNÓSTICO APP] Cliente ID: '{cliente_id}', Agendamentos Futuros Encontrados: {len(agendamentos_futuros)}")

                    if not agendamentos_futuros:
                        st.info("Cliente não possui agendamentos futuros confirmados.")
                    else:
                        for ag in agendamentos_futuros:
                            ag_id = ag.get('id', f'MISSING_ID_{cliente_id}_{ag.get("horario")}') # Chave mais robusta se ID faltar
                            horario_ag = ag.get('horario')

                            if ag.get('turma_id'):
                                tipo_ag = f"Turma: {turmas_map.get(ag['turma_id'], 'N/A')}"
                                pode_remarcar = False
                            else:
                                tipo_ag = f"Serviço: {ag.get('servico_nome', 'N/A')}"
                                pode_remarcar = True

                            info_cols, button_cols = st.columns([0.6, 0.4])

                            with info_cols:
                                horario_str = horario_ag.strftime('%d/%m/%Y às %H:%M') if isinstance(horario_ag, datetime) else "Horário Inválido"
                                st.write(f"**{horario_str}**")
                                st.write(f"<small>{ag.get('profissional_nome','N/A')} ({tipo_ag})</small>", unsafe_allow_html=True)
                                if ag.get('pacote_cliente_id'):
                                    st.caption("💳 Agendamento via Pacote")

                            with button_cols:
                                num_cols = 6 if pode_remarcar else 5
                                action_cols = st.columns(num_cols)

                                # Popover Detalhes (ℹ️)
                                detalhes_popover = action_cols[0].popover("ℹ️", help="Ver Detalhes", key=f"cl_info_{ag_id}")
                                with detalhes_popover:
                                    pin = ag.get('pin_code', 'N/A')
                                    link = f"https://agendafit.streamlit.app?pin={pin}" if pin != 'N/A' else 'N/A'
                                    st.markdown(f"**Serviço:** {ag.get('servico_nome', 'N/A')}")
                                    st.markdown(f"**Telefone:** {ag.get('telefone', 'N/A')}")
                                    st.markdown(f"**PIN:** `{pin}`")
                                    st.markdown(f"**Link:** `{link}`")
                                    if pd.notna(ag.get('pacote_cliente_id')):
                                        st.markdown(f"**Usou Pacote:** Sim")

                                # Popover WPP (💬)
                                wpp_popover = action_cols[1].popover("💬", help="Gerar Mensagem WhatsApp", key=f"cl_wpp_{ag_id}")
                                with wpp_popover:
                                    pin = ag.get('pin_code', 'N/A')
                                    link_gestao = f"https://agendafit.streamlit.app?pin={pin}" if pin != 'N/A' else 'N/A'
                                    horario_str_msg = horario_ag.strftime('%d/%m/%Y às %H:%M') if isinstance(horario_ag, datetime) else "Data/Hora Inválida"
                                    mensagem = (
                                        f"Olá, {ag.get('cliente','Cliente')}! Tudo bem?\n\n"
                                        f"Este é um lembrete do seu agendamento na {st.session_state.clinic_name} com o(a) profissional {ag.get('profissional_nome','N/A')} "
                                        f"no dia {horario_str_msg}.\n\n"
                                        f"Para confirmar, remarcar ou cancelar, por favor, use este link: {link_gestao}"
                                    )
                                    st.text_area("Mensagem:", value=mensagem, height=200, key=f"cl_wpp_msg_{ag_id}")
                                    st.write("Copie a mensagem acima e envie para o cliente.")

                                # Botão Finalizar (✅)
                                action_cols[2].button("✅", key=f"cl_finish_{ag_id}", on_click=handle_admin_action, args=(ag_id, "finalizar"), help="Sessão Concluída")
                                # Botão No-Show (🚫)
                                action_cols[3].button("🚫", key=f"cl_noshow_{ag_id}", on_click=handle_admin_action, args=(ag_id, "no-show"), help="Marcar Falta")
                                # Botão Cancelar (❌)
                                action_cols[4].button("❌", key=f"cl_cancel_{ag_id}", on_click=handle_admin_action, args=(ag_id, "cancelar"), help="Cancelar Agendamento")
                                # Botão Remarcar (🔄) - Condicional
                                if pode_remarcar:
                                    action_cols[5].button(
                                        "🔄",
                                        key=f"cl_remarcar_{ag_id}",
                                        on_click=handle_iniciar_remarcacao_cliente,
                                        args=(ag,),
                                        help="Remarcar Horário"
                                    )

                            # Formulário de Remarcação
                            if st.session_state.remarcando_cliente_ag_id == ag_id:
                                with st.form(key=f"form_remarcacao_cliente_{ag_id}"):
                                    horario_str_rem = horario_ag.strftime('%d/%m/%Y %H:%M') if isinstance(horario_ag, datetime) else "Data/Hora Inválida"
                                    st.write(f"Remarcando agendamento de {horario_str_rem}")

                                    if ag_id not in st.session_state.remarcacao_cliente_form_data:
                                        data_atual_rem = horario_ag.date() if isinstance(horario_ag, datetime) else date.today()
                                        if data_atual_rem < date.today(): data_atual_rem = date.today()
                                        st.session_state.remarcacao_cliente_form_data[ag_id] = data_atual_rem

                                    def update_rem_date(ag_id_cb): st.session_state.remarcacao_cliente_form_data[ag_id_cb] = st.session_state[f"rem_data_{ag_id_cb}"]

                                    nova_data = st.date_input(
                                        "Nova Data",
                                        key=f"rem_data_{ag_id}",
                                        value=st.session_state.remarcacao_cliente_form_data[ag_id],
                                        min_value=date.today(),
                                        on_change=update_rem_date,
                                        args=(ag_id,)
                                    )

                                    horarios_disp = gerar_horarios_disponiveis(
                                        clinic_id,
                                        ag.get('profissional_nome','N/A'),
                                        nova_data,
                                        ag.get('duracao_min', 30),
                                        agendamento_id_excluir=ag_id
                                    )

                                    def update_rem_hora(ag_id_cb): st.session_state.remarcacao_cliente_form_hora[ag_id_cb] = st.session_state[f"rem_hora_{ag_id_cb}"]

                                    if horarios_disp:
                                        default_hora_index = 0
                                        if ag_id in st.session_state.remarcacao_cliente_form_hora and st.session_state.remarcacao_cliente_form_hora[ag_id] in horarios_disp:
                                            try: default_hora_index = horarios_disp.index(st.session_state.remarcacao_cliente_form_hora[ag_id])
                                            except ValueError: default_hora_index = 0

                                        st.selectbox(
                                            "Nova Hora", options=horarios_disp, key=f"rem_hora_{ag_id}",
                                            index=default_hora_index, format_func=lambda t: t.strftime('%H:%M'),
                                            on_change=update_rem_hora, args=(ag_id,)
                                        )
                                        if ag_id not in st.session_state.remarcacao_cliente_form_hora or st.session_state.remarcacao_cliente_form_hora[ag_id] not in horarios_disp :
                                             st.session_state.remarcacao_cliente_form_hora[ag_id] = horarios_disp[default_hora_index]
                                        pode_confirmar = True
                                    else:
                                        st.selectbox("Nova Hora", options=["Nenhum horário disponível"], disabled=True, key=f"rem_hora_{ag_id}")
                                        st.session_state.remarcacao_cliente_form_hora[ag_id] = None
                                        pode_confirmar = False

                                    form_cols = st.columns(2)
                                    form_cols[0].form_submit_button(
                                        "✅ Confirmar", on_click=handle_confirmar_remarcacao_cliente, args=(ag,), disabled=not pode_confirmar
                                    )
                                    form_cols[1].form_submit_button(
                                        "Voltar", on_click=handle_cancelar_remarcacao_cliente, args=(ag_id,)
                                    )

                                status_msg = st.session_state.remarcacao_cliente_status.get(ag_id, {})
                                if status_msg:
                                    if status_msg.get('sucesso'): st.success(status_msg.get('mensagem'))
                                    else: st.error(status_msg.get('mensagem'))
                            st.divider()
        else:
            st.info("Nenhum cliente cadastrado.")
    # <-- FIM DA ABA MODIFICADA -->


    elif active_tab == "📋 Gerenciar Serviços":
        st.header("📋 Gerenciar Serviços")
        with st.form("add_servico_form"):
            st.subheader("Cadastrar Novo Serviço")
            s1, s2, s3 = st.columns(3)
            s1.text_input("Nome do Serviço", key="nome_novo_servico", placeholder="Ex: Sessão de Fisioterapia")
            s2.number_input("Duração Padrão (minutos)", min_value=15, step=15, key="duracao_novo_servico", value=30)
            s3.selectbox("Tipo de Atendimento", options=["Individual", "Em Grupo"], key="tipo_novo_servico")

            st.form_submit_button("Adicionar Serviço", on_click=handle_add_servico)
            st.caption("A duração e o tipo definidos aqui impactarão diretamente as opções na agenda.")

        st.markdown("---")
        st.subheader("Serviços Cadastrados")
        if servicos_clinica:
            for servico in servicos_clinica:
                sc1, sc2, sc3, sc4 = st.columns([0.4, 0.2, 0.2, 0.2])
                sc1.write(servico['nome'])
                sc2.write(f"{servico['duracao_min']} min")
                sc3.write(f"*{servico.get('tipo', 'Individual')}*")
                sc4.button("Remover", key=f"del_serv_{servico['id']}", on_click=handle_remove_servico, args=(clinic_id, servico['id']))
        else:
            st.info("Nenhum serviço cadastrado.")

    elif active_tab == "👥 Gerenciar Profissionais":
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
                horarios_salvos = prof_data.get('horario_trabalho', {}) if prof_data else {}


                if st.session_state.editando_horario_id == prof_id:
                    with st.form(key=f"form_horarios_{prof_id}"):
                        st.write(f"**Editando horários para: {prof_selecionado_nome}**")
                        for dia_key, dia_nome in DIAS_SEMANA.items():
                            horario_dia = horarios_salvos.get(dia_key, {"ativo": False, "inicio": "09:00", "fim": "18:00"})
                            cols = st.columns([0.2, 0.4, 0.4])
                            cols[0].checkbox(dia_nome, key=f"ativo_{dia_key}_{prof_id}", value=horario_dia['ativo'])
                            try:
                                inicio_time = datetime.strptime(horario_dia.get('inicio', "09:00"), "%H:%M").time()
                                fim_time = datetime.strptime(horario_dia.get('fim', "18:00"), "%H:%M").time()
                            except ValueError:
                                inicio_time = time(9, 0)
                                fim_time = time(18, 0)

                            cols[1].time_input("Início", key=f"inicio_{dia_key}_{prof_id}", value=inicio_time, step=timedelta(minutes=30), label_visibility="collapsed")
                            cols[2].time_input("Fim", key=f"fim_{dia_key}_{prof_id}", value=fim_time, step=timedelta(minutes=30), label_visibility="collapsed")

                        submit_cols = st.columns(2)
                        submit_cols[0].form_submit_button("✅ Salvar Alterações", on_click=handle_salvar_horarios_profissional, args=(prof_id,))
                        if submit_cols[1].form_submit_button("❌ Cancelar"):
                            st.session_state.editando_horario_id = None
                            st.rerun()
                else:
                    st.write(f"**Horários salvos para: {prof_selecionado_nome}**")
                    for dia_key, dia_nome in DIAS_SEMANA.items():
                        horario_dia = horarios_salvos.get(dia_key, {"ativo": False, "inicio": "09:00", "fim": "18:00"})
                        if horario_dia.get('ativo'):
                            st.text(f"{dia_nome}: {horario_dia.get('inicio','N/A')} - {horario_dia.get('fim','N/A')}")
                        else:
                            st.text(f"{dia_nome}: Não trabalha")

                    st.button("✏️ Editar Horários", key=f"edit_{prof_id}", on_click=entrar_modo_edicao, args=(prof_id,))

        st.markdown("---")
        st.subheader("Feriados e Folgas")
        col1, col2 = st.columns(2)
        with col1:
            with st.form("add_feriado_form"):
                st.date_input("Data do Feriado/Folga", key="nova_data_feriado", value=date.today())
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
                 data_str = feriado['data'].strftime('%d/%m/%Y') if isinstance(feriado.get('data'), date) else "Data Inválida"
                 c1, c2, c3 = st.columns([0.4, 0.4, 0.2])
                 c1.write(data_str)
                 c2.write(feriado.get('descricao', 'N/A'))
                 c3.button("Remover", key=f"del_feriado_{feriado.get('id','N/A')}", on_click=handle_remove_feriado, args=(clinic_id, feriado.get('id','N/A')))


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

