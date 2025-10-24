# database.py (VERSÃO COM GESTÃO DE TURMAS E PACOTES)
# ATUALIZADO:
# 1. [SOLUÇÃO DEFINITIVA] `salvar_agendamento` agora armazena o `cliente_id`.
# 2. [SOLUÇÃO DEFINITIVA] `buscar_agendamentos_futuros_por_cliente` agora busca por `cliente_id`.
# 3. Removido `order_by` da query de agendamentos futuros.
# 4. [DIAGNÓSTICO] Adicionados logs detalhados em `buscar_agendamentos_futuros_por_cliente`.

import streamlit as st
import pandas as pd
from datetime import datetime, time, date, timedelta
import json
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from zoneinfo import ZoneInfo
import sys # Importado para logs

# --- Configuração ---
TZ_SAO_PAULO = ZoneInfo('America/Sao_Paulo')

# --- Inicialização da Conexão ---
@st.cache_resource
def get_firestore_client():
    try:
        json_credenciais = st.secrets["firestore"]["json_key_string"]
        credenciais_dict = json.loads(json_credenciais)
        # Adiciona log para confirmar a conexão
        print("LOG: Conectando ao Firestore...", file=sys.stderr)
        client = firestore.Client.from_service_account_info(credenciais_dict)
        print("LOG: Conectado ao Firestore com sucesso.", file=sys.stderr)
        return client
    except Exception as e:
        st.error(f"Erro ao conectar ao Google Firestore: {e}")
        print(f"ERRO FATAL: Falha ao conectar ao Firestore: {e}", file=sys.stderr) # Log do erro
        return None

db = get_firestore_client()
if db is None:
    print("LOG: Cliente Firestore não inicializado. Aplicação parada.", file=sys.stderr)
    st.stop()

# --- Funções de Gestão de Clínicas (Super Admin) ---
def listar_clinicas():
    """Lista todas as clínicas cadastradas para o painel admin."""
    try:
        docs = db.collection('clinicas').order_by('nome_fantasia').stream()
        clinicas = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            clinicas.append(data)
        return clinicas
    except Exception as e:
        print(f"ERRO AO LISTAR CLÍNICAS: {e}", file=sys.stderr)
        return []

def adicionar_clinica(nome_fantasia: str, username: str, password: str):
    """Adiciona uma nova clínica à coleção principal."""
    try:
        query = db.collection('clinicas').where(filter=FieldFilter('username', '==', username)).limit(1)
        if any(query.stream()):
            return False, "Este nome de usuário já está em uso."

        db.collection('clinicas').add({
            'nome_fantasia': nome_fantasia,
            'username': username,
            'password': password, # Idealmente, use hash para senhas
            'ativo': True
        })
        return True, "Clínica adicionada com sucesso."
    except Exception as e:
        print(f"ERRO AO ADICIONAR CLÍNICA: {e}", file=sys.stderr)
        return False, str(e)

def toggle_status_clinica(clinic_id: str, status_atual: bool):
    """Ativa ou desativa uma clínica (soft delete)."""
    try:
        clinic_ref = db.collection('clinicas').document(clinic_id)
        clinic_ref.update({'ativo': not status_atual})
        return True
    except Exception as e:
        print(f"ERRO AO ALTERAR STATUS DA CLÍNICA: {e}", file=sys.stderr)
        return False

# --- Funções de Autenticação ---
def buscar_clinica_por_login(username, password):
    """Busca uma clínica ativa pelo username e password."""
    try:
        clinicas_ref = db.collection('clinicas')
        # Atenção: Armazenar senhas em texto plano não é seguro.
        query = clinicas_ref.where(filter=FieldFilter('username', '==', username)) \
                           .where(filter=FieldFilter('password', '==', password)) \
                           .where(filter=FieldFilter('ativo', '==', True)).limit(1)
        docs = query.stream()
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None
    except Exception as e:
        print(f"ERRO AO BUSCAR CLÍNICA: {e}", file=sys.stderr)
        return None

# --- Funções de Gestão de Profissionais ---
def listar_profissionais(clinic_id: str):
    """Lista todos os profissionais de uma clínica específica."""
    try:
        profissionais_ref = db.collection('clinicas').document(clinic_id).collection('profissionais')
        docs = profissionais_ref.order_by('nome').stream()
        profissionais = []
        for doc in docs:
            prof = doc.to_dict()
            prof['id'] = doc.id
            profissionais.append(prof)
        return profissionais
    except Exception as e:
        print(f"ERRO AO LISTAR PROFISSIONAIS: {e}", file=sys.stderr)
        return []

def adicionar_profissional(clinic_id: str, nome: str):
    """Adiciona um novo profissional a uma clínica."""
    try:
        profissionais_ref = db.collection('clinicas').document(clinic_id).collection('profissionais')
        profissionais_ref.add({'nome': nome, 'horario_trabalho': {}})
        return True
    except Exception as e:
        print(f"ERRO AO ADICIONAR PROFISSIONAL: {e}", file=sys.stderr)
        return False

def remover_profissional(clinic_id: str, profissional_id: str):
    """Remove um profissional de uma clínica."""
    try:
        db.collection('clinicas').document(clinic_id).collection('profissionais').document(profissional_id).delete()
        return True
    except Exception as e:
        print(f"ERRO AO REMOVER PROFISSIONAL: {e}", file=sys.stderr)
        return False

def atualizar_horario_profissional(clinic_id: str, prof_id: str, horarios: dict):
    """Atualiza a configuração de horário de um profissional."""
    try:
        prof_ref = db.collection('clinicas').document(clinic_id).collection('profissionais').document(prof_id)
        prof_ref.update({'horario_trabalho': horarios})
        return True
    except Exception as e:
        print(f"ERRO AO ATUALIZAR HORÁRIO: {e}", file=sys.stderr)
        return False

# --- Funções de Gestão de Agendamentos ---

def salvar_agendamento(clinic_id: str, dados: dict, pin_code: str):
    """Cria um novo agendamento para uma clínica."""
    try:
        agendamentos_ref = db.collection('agendamentos')
        cliente_id_val = dados.get('cliente_id')
        print(f"LOG: Salvando agendamento. Cliente ID recebido: {cliente_id_val}", file=sys.stderr) # Log ID
        data_para_salvar = {
            'clinic_id': clinic_id,
            'pin_code': pin_code,
            'profissional_nome': dados['profissional_nome'],
            'cliente': dados['cliente'],
            'cliente_id': cliente_id_val, # Garante que está pegando o valor correto
            'telefone': dados['telefone'],
            'horario': dados['horario'],
            'servico_nome': dados['servico_nome'],
            'duracao_min': dados['duracao_min'],
            'status': "Confirmado",
            'turma_id': dados.get('turma_id'),
            'pacote_cliente_id': dados.get('pacote_cliente_id')
        }
        print(f"LOG: Dados a serem salvos no agendamento: {data_para_salvar}", file=sys.stderr) # Log Dados
        agendamentos_ref.add(data_para_salvar)
        print("LOG: Agendamento salvo com sucesso.", file=sys.stderr) # Log Sucesso
        return True
    except Exception as e:
        print(f"ERRO AO SALVAR AGENDAMENTO: {e}", file=sys.stderr) # Log Erro
        return str(e)

def buscar_agendamento_por_pin(pin_code: str):
    """Busca um agendamento pelo PIN."""
    try:
        query = db.collection('agendamentos').where(filter=FieldFilter('pin_code', '==', pin_code)).limit(1)
        docs = query.stream()
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            if 'horario' in data and isinstance(data['horario'], datetime):
                data['horario'] = data['horario'].astimezone(TZ_SAO_PAULO)
            return data
        return None
    except Exception as e:
        print(f"ERRO NA BUSCA POR PIN: {e}", file=sys.stderr)
        return None

def buscar_agendamentos_por_intervalo(clinic_id: str, start_date: date, end_date: date):
    """Busca todos os agendamentos de uma clínica em um intervalo de datas."""
    try:
        start_dt = datetime.combine(start_date, time.min, tzinfo=TZ_SAO_PAULO)
        end_dt = datetime.combine(end_date, time.max, tzinfo=TZ_SAO_PAULO)

        query = db.collection('agendamentos').where(filter=FieldFilter('clinic_id', '==', clinic_id))
        # REMOVIDO FILTRO DE HORARIO DA QUERY - FILTRADO EM PYTHON ABAIXO
        # Isso evita a necessidade de um índice composto clinic_id + horario
        docs = query.stream()

        data = []
        count_docs_total = 0
        count_docs_filtrados = 0
        for doc in docs:
            count_docs_total += 1
            item = doc.to_dict()
            item['id'] = doc.id
            if 'horario' in item and isinstance(item['horario'], datetime):
                item['horario'] = item['horario'].astimezone(TZ_SAO_PAULO)
                # Filtro de data aplicado aqui
                if start_dt <= item['horario'] <= end_dt:
                    data.append(item)
                    count_docs_filtrados += 1
            elif 'horario' not in item or not isinstance(item['horario'], datetime):
                 print(f"WARN: Agendamento ID {doc.id} sem 'horario' válido.", file=sys.stderr)


        print(f"LOG: buscar_agendamentos_por_intervalo ({clinic_id}, {start_date} a {end_date}): {count_docs_total} docs lidos, {count_docs_filtrados} no intervalo.", file=sys.stderr)
        return pd.DataFrame(data)
    except Exception as e:
        print(f"ERRO NA BUSCA DE AGENDAMENTOS POR INTERVALO: {e}", file=sys.stderr)
        return pd.DataFrame()


def buscar_agendamentos_por_data_e_profissional(clinic_id: str, profissional_nome: str, data_selecionada: date):
    """Busca agendamentos para um profissional específico em uma data específica."""
    try:
        start_dt = datetime.combine(data_selecionada, time.min, tzinfo=TZ_SAO_PAULO)
        end_dt = datetime.combine(data_selecionada, time.max, tzinfo=TZ_SAO_PAULO)

        query = db.collection('agendamentos').where(filter=FieldFilter('clinic_id', '==', clinic_id)) \
                                             .where(filter=FieldFilter('profissional_nome', '==', profissional_nome))
        # REMOVIDO FILTRO DE HORARIO DA QUERY - FILTRADO EM PYTHON ABAIXO

        docs = query.stream()
        data = []
        count_docs_total = 0
        count_docs_filtrados = 0
        for doc in docs:
            count_docs_total += 1
            item = doc.to_dict()
            item['id'] = doc.id
            if 'horario' in item and isinstance(item['horario'], datetime):
                item['horario'] = item['horario'].astimezone(TZ_SAO_PAULO)
                # Filtro de data aplicado aqui
                if start_dt <= item['horario'] <= end_dt:
                    data.append(item)
                    count_docs_filtrados += 1

        print(f"LOG: buscar_agendamentos_por_data_e_profissional ({clinic_id}, {profissional_nome}, {data_selecionada}): {count_docs_total} docs lidos, {count_docs_filtrados} na data.", file=sys.stderr)
        return pd.DataFrame(data)
    except Exception as e:
        print(f"ERRO NA BUSCA POR DATA E PROFISSIONAL: {e}", file=sys.stderr)
        return pd.DataFrame()


def atualizar_status_agendamento(id_agendamento: str, novo_status: str):
    """Atualiza o status de um agendamento específico."""
    try:
        doc_ref = db.collection('agendamentos').document(id_agendamento)
        doc_ref.update({'status': novo_status})
        return True
    except Exception as e:
        print(f"ERRO AO ATUALIZAR STATUS ({id_agendamento} para {novo_status}): {e}", file=sys.stderr)
        return False

def atualizar_horario_agendamento(id_agendamento: str, novo_horario: datetime):
    """Atualiza o horário de um agendamento (usado na remarcação)."""
    try:
        doc_ref = db.collection('agendamentos').document(id_agendamento)
        novo_horario_utc = novo_horario.astimezone(ZoneInfo('UTC'))
        doc_ref.update({'horario': novo_horario_utc})
        return True
    except Exception as e:
        print(f"ERRO AO ATUALIZAR HORÁRIO ({id_agendamento} para {novo_horario}): {e}", file=sys.stderr)
        return False

# <-- FUNÇÃO COM LOGS ADICIONADOS -->
def buscar_agendamentos_futuros_por_cliente(clinic_id: str, cliente_id: str):
    """Busca agendamentos futuros (Confirmados) para um cliente específico usando seu ID."""
    # Log 1: Parâmetros recebidos
    print(f"LOG: Iniciando buscar_agendamentos_futuros_por_cliente. clinic_id='{clinic_id}', cliente_id='{cliente_id}'", file=sys.stderr)

    if not cliente_id:
        print("LOG: cliente_id está vazio ou None. Retornando lista vazia.", file=sys.stderr)
        return []

    try:
        hoje_sp = datetime.now(TZ_SAO_PAULO).date()
        inicio_do_dia_hoje = datetime.combine(hoje_sp, time.min, tzinfo=TZ_SAO_PAULO)
        print(f"LOG: Data/hora de início para busca: {inicio_do_dia_hoje}", file=sys.stderr) # Log 2: Data de início

        # Log 3: Detalhes da Query
        print(f"LOG: Executando query: collection='agendamentos', where clinic_id=='{clinic_id}', cliente_id=='{cliente_id}', status=='Confirmado', horario>='{inicio_do_dia_hoje}'", file=sys.stderr)
        query = db.collection('agendamentos') \
                  .where(filter=FieldFilter('clinic_id', '==', clinic_id)) \
                  .where(filter=FieldFilter('cliente_id', '==', cliente_id)) \
                  .where(filter=FieldFilter('status', '==', 'Confirmado')) \
                  .where(filter=FieldFilter('horario', '>=', inicio_do_dia_hoje))

        docs = query.stream()
        agendamentos = []
        count_docs_encontrados = 0
        for doc in docs:
            count_docs_encontrados += 1
            data = doc.to_dict()
            data['id'] = doc.id
            if 'horario' in data and isinstance(data['horario'], datetime):
                 data['horario'] = data['horario'].astimezone(TZ_SAO_PAULO)
                 agendamentos.append(data)
            else:
                 print(f"WARN: Agendamento ID {doc.id} encontrado mas sem 'horario' válido. Ignorado.", file=sys.stderr)


        # Log 4: Resultado da Query
        print(f"LOG: Query retornou {count_docs_encontrados} documentos.", file=sys.stderr)

        # Ordena em Python
        agendamentos.sort(key=lambda x: x.get('horario', datetime.min.replace(tzinfo=TZ_SAO_PAULO))) # Adiciona fallback para horário

        # Log 5: Resultado Final
        print(f"LOG: Retornando {len(agendamentos)} agendamentos futuros para cliente_id='{cliente_id}'.", file=sys.stderr)
        return agendamentos

    except Exception as e:
        # Log 6: Erro
        print(f"ERRO AO BUSCAR AGENDAMENTOS FUTUROS DO CLIENTE (por ID='{cliente_id}'): {e}", file=sys.stderr)
        # Considerar logar o traceback completo se o erro persistir
        # import traceback
        # print(traceback.format_exc(), file=sys.stderr)
        return []
# <-- FIM DA FUNÇÃO COM LOGS -->

# --- Funções de Gestão de Feriados ---
def adicionar_feriado(clinic_id: str, data_feriado: date, descricao: str):
    """Adiciona um feriado ou folga para uma clínica."""
    try:
        feriados_ref = db.collection('clinicas').document(clinic_id).collection('feriados')
        # Salva como Timestamp (meia-noite UTC para consistência, embora só a data importe)
        data_dt_utc = datetime.combine(data_feriado, time.min, tzinfo=ZoneInfo('UTC'))
        feriados_ref.add({'data': data_dt_utc, 'descricao': descricao, 'clinic_id': clinic_id})
        return True
    except Exception as e:
        print(f"ERRO AO ADICIONAR FERIADO: {e}", file=sys.stderr)
        return False

def listar_feriados(clinic_id: str):
    """Lista todos os feriados de uma clínica, ordenados por data."""
    try:
        feriados_ref = db.collection('clinicas').document(clinic_id).collection('feriados')
        docs = feriados_ref.order_by('data').stream()
        feriados = []
        for doc in docs:
            feriado = doc.to_dict()
            feriado['id'] = doc.id
            # Converte Timestamp do Firestore para objeto date local
            if 'data' in feriado and isinstance(feriado['data'], datetime):
                # Assume que foi salvo como UTC meia-noite, converte para SP e pega a data
                feriado['data'] = feriado['data'].astimezone(TZ_SAO_PAULO).date()
            feriados.append(feriado)
        return feriados
    except Exception as e:
        print(f"Erro ao listar feriados: {e}", file=sys.stderr)
        return []


def remover_feriado(clinic_id: str, feriado_id: str):
    """Remove um feriado de uma clínica."""
    try:
        db.collection('clinicas').document(clinic_id).collection('feriados').document(feriado_id).delete()
        return True
    except Exception as e:
        print(f"ERRO AO REMOVER FERIADO: {e}", file=sys.stderr)
        return False

# --- Funções de Gestão de Clientes ---
def listar_clientes(clinic_id: str):
    """Lista todos os clientes de uma clínica."""
    try:
        clientes_ref = db.collection('clinicas').document(clinic_id).collection('clientes')
        docs = clientes_ref.order_by('nome').stream()
        clientes = []
        for doc in docs:
            cliente = doc.to_dict()
            cliente['id'] = doc.id
            clientes.append(cliente)
        return clientes
    except Exception as e:
        print(f"ERRO AO LISTAR CLIENTES: {e}", file=sys.stderr)
        return []

def adicionar_cliente(clinic_id: str, nome: str, telefone: str, observacoes: str):
    """Adiciona um novo cliente a uma clínica e retorna o ID."""
    try:
        clientes_ref = db.collection('clinicas').document(clinic_id).collection('clientes')
        # Verifica se já existe um cliente com o mesmo nome ou telefone (opcional, mas bom)
        query_nome = clientes_ref.where(filter=FieldFilter('nome', '==', nome)).limit(1).stream()
        query_tel = clientes_ref.where(filter=FieldFilter('telefone', '==', telefone)).limit(1).stream()
        if any(query_nome) or any(query_tel):
             print(f"WARN: Tentativa de adicionar cliente duplicado (Nome ou Tel): {nome} / {telefone}", file=sys.stderr)
             # Você pode retornar False ou o ID do existente se encontrar
             # Por ora, vamos permitir, mas logamos
             pass # Permite adicionar mesmo assim

        doc_ref = clientes_ref.add({'nome': nome, 'telefone': telefone, 'observacoes': observacoes})
        # doc_ref é uma tupla (timestamp, document_reference)
        # O ID está em doc_ref[1].id
        novo_id = doc_ref[1].id
        print(f"LOG: Cliente '{nome}' adicionado com ID: {novo_id}", file=sys.stderr)
        return True, novo_id # Retorna sucesso e o ID
    except Exception as e:
        print(f"ERRO AO ADICIONAR CLIENTE '{nome}': {e}", file=sys.stderr)
        return False, None # Retorna falha e None para ID


def remover_cliente(clinic_id: str, cliente_id: str):
    """Remove um cliente de uma clínica."""
    try:
        # Adicionar lógica para remover/anonimizar agendamentos associados?
        db.collection('clinicas').document(clinic_id).collection('clientes').document(cliente_id).delete()
        return True
    except Exception as e:
        print(f"ERRO AO REMOVER CLIENTE ID '{cliente_id}': {e}", file=sys.stderr)
        return False

# --- Funções de Gestão de Serviços ---
def listar_servicos(clinic_id: str):
    """Lista todos os serviços de uma clínica."""
    try:
        servicos_ref = db.collection('clinicas').document(clinic_id).collection('servicos')
        docs = servicos_ref.order_by('nome').stream()
        servicos = []
        for doc in docs:
            servico = doc.to_dict()
            servico['id'] = doc.id
            servicos.append(servico)
        return servicos
    except Exception as e:
        print(f"ERRO AO LISTAR SERVIÇOS: {e}", file=sys.stderr)
        return []

def adicionar_servico(clinic_id: str, nome: str, duracao_min: int, tipo: str):
    """Adiciona um novo serviço a uma clínica."""
    try:
        servicos_ref = db.collection('clinicas').document(clinic_id).collection('servicos')
        servicos_ref.add({'nome': nome, 'duracao_min': duracao_min, 'tipo': tipo})
        return True
    except Exception as e:
        print(f"ERRO AO ADICIONAR SERVIÇO: {e}", file=sys.stderr)
        return False

def remover_servico(clinic_id: str, servico_id: str):
    """Remove um serviço de uma clínica."""
    try:
        # Adicionar verificação se o serviço está em uso por pacotes ou turmas?
        db.collection('clinicas').document(clinic_id).collection('servicos').document(servico_id).delete()
        return True
    except Exception as e:
        print(f"ERRO AO REMOVER SERVIÇO: {e}", file=sys.stderr)
        return False

# --- Funções - Gestão de Turmas ---
def adicionar_turma(clinic_id: str, dados_turma: dict):
    """Adiciona uma nova turma recorrente para a clínica."""
    try:
        turmas_ref = db.collection('clinicas').document(clinic_id).collection('turmas')
        turmas_ref.add(dados_turma)
        return True
    except Exception as e:
        print(f"ERRO AO ADICIONAR TURMA: {e}", file=sys.stderr)
        return False

def listar_turmas(clinic_id: str, profissionais_list: list = None, servicos_list: list = None):
    """Lista todas as turmas de uma clínica, opcionalmente populando nomes."""
    try:
        turmas_ref = db.collection('clinicas').document(clinic_id).collection('turmas')
        docs = turmas_ref.order_by('horario').stream() # Assume que 'horario' é string HH:MM
        turmas = []
        for doc in docs:
            turma = doc.to_dict()
            turma['id'] = doc.id

            if profissionais_list:
                prof_id = turma.get('profissional_id')
                prof_info = next((p for p in profissionais_list if p['id'] == prof_id), None)
                turma['profissional_nome'] = prof_info['nome'] if prof_info else 'Profissional Removido'

            if servicos_list:
                serv_id = turma.get('servico_id')
                serv_info = next((s for s in servicos_list if s['id'] == serv_id), None)
                turma['servico_nome'] = serv_info['nome'] if serv_info else 'Serviço Removido'

            turmas.append(turma)
        return turmas
    except Exception as e:
        print(f"ERRO AO LISTAR TURMAS: {e}", file=sys.stderr)
        return []


def remover_turma(clinic_id: str, turma_id: str):
    """Remove uma turma da clínica."""
    try:
        # Adicionar lógica para lidar com agendamentos futuros dessa turma?
        db.collection('clinicas').document(clinic_id).collection('turmas').document(turma_id).delete()
        return True
    except Exception as e:
        print(f"ERRO AO REMOVER TURMA: {e}", file=sys.stderr)
        return False

def atualizar_turma(clinic_id: str, turma_id: str, dados_turma: dict):
    """Atualiza os dados de uma turma existente."""
    try:
        turma_ref = db.collection('clinicas').document(clinic_id).collection('turmas').document(turma_id)
        turma_ref.update(dados_turma)
        return True
    except Exception as e:
        print(f"ERRO AO ATUALIZAR TURMA: {e}", file=sys.stderr)
        return False

def contar_agendamentos_turma_dia(clinic_id: str, turma_id: str, data: date):
    """Conta quantos agendamentos confirmados existem para uma turma específica em um dia."""
    try:
        start_dt = datetime.combine(data, time.min, tzinfo=TZ_SAO_PAULO)
        end_dt = datetime.combine(data, time.max, tzinfo=TZ_SAO_PAULO)

        query = db.collection('agendamentos').where(filter=FieldFilter('clinic_id', '==', clinic_id)) \
                                             .where(filter=FieldFilter('turma_id', '==', turma_id)) \
                                             .where(filter=FieldFilter('status', '==', 'Confirmado')) \
                                             .where(filter=FieldFilter('horario', '>=', start_dt)) \
                                             .where(filter=FieldFilter('horario', '<=', end_dt))

        # Firestore não tem count() eficiente em todas as SDKs, iterar é a forma garantida
        count = sum(1 for _ in query.stream())
        return count
    except Exception as e:
        print(f"ERRO AO CONTAR AGENDAMENTOS DA TURMA (ID: {turma_id}, Data: {data}): {e}", file=sys.stderr)
        return 0


# --- NOVAS FUNÇÕES - Gestão de Pacotes ---

# 1. Funções para Modelos de Pacotes (Gerenciados pela Clínica)
def listar_pacotes_modelos(clinic_id: str):
    """Lista todos os modelos de pacotes criados pela clínica."""
    try:
        pacotes_ref = db.collection('clinicas').document(clinic_id).collection('pacotes')
        docs = pacotes_ref.order_by('nome').stream()
        pacotes = []
        for doc in docs:
            pacote = doc.to_dict()
            pacote['id'] = doc.id
            pacotes.append(pacote)
        return pacotes
    except Exception as e:
        print(f"ERRO AO LISTAR MODELOS DE PACOTES: {e}", file=sys.stderr)
        return []

def adicionar_pacote_modelo(clinic_id: str, dados_pacote: dict):
    """Adiciona um novo modelo de pacote."""
    try:
        pacotes_ref = db.collection('clinicas').document(clinic_id).collection('pacotes')
        pacotes_ref.add(dados_pacote)
        return True
    except Exception as e:
        print(f"ERRO AO ADICIONAR MODELO DE PACOTE: {e}", file=sys.stderr)
        return False

def remover_pacote_modelo(clinic_id: str, pacote_id: str):
    """Remove um modelo de pacote."""
    try:
        # Adicionar verificação se este modelo está em uso por algum pacote de cliente?
        db.collection('clinicas').document(clinic_id).collection('pacotes').document(pacote_id).delete()
        return True
    except Exception as e:
        print(f"ERRO AO REMOVER MODELO DE PACOTE (ID: {pacote_id}): {e}", file=sys.stderr)
        return False


# 2. Funções para Pacotes dos Clientes (Instâncias individuais)
def listar_pacotes_do_cliente(clinic_id: str, cliente_id: str):
    """Lista todos os pacotes adquiridos por um cliente específico."""
    try:
        pacotes_ref = db.collection('clinicas').document(clinic_id) \
                        .collection('clientes').document(cliente_id) \
                        .collection('pacotes_clientes')

        # Ordena pela data de expiração mais recente primeiro
        docs = pacotes_ref.order_by('data_expiracao', direction=firestore.Query.DESCENDING).stream()
        pacotes = []
        for doc in docs:
            pacote = doc.to_dict()
            pacote['id'] = doc.id
            # Converte timestamps Firestore para datetimes Python com timezone
            if 'data_inicio' in pacote and isinstance(pacote['data_inicio'], datetime):
                pacote['data_inicio'] = pacote['data_inicio'].astimezone(TZ_SAO_PAULO)
            if 'data_expiracao' in pacote and isinstance(pacote['data_expiracao'], datetime):
                pacote['data_expiracao'] = pacote['data_expiracao'].astimezone(TZ_SAO_PAULO)
            pacotes.append(pacote)
        return pacotes
    except Exception as e:
        print(f"ERRO AO LISTAR PACOTES DO CLIENTE (ID: {cliente_id}): {e}", file=sys.stderr)
        return []

def associar_pacote_ao_cliente(clinic_id: str, cliente_id: str, dados_pacote_cliente: dict):
    """Associa/vende um pacote a um cliente."""
    try:
        pacotes_ref = db.collection('clinicas').document(clinic_id) \
                        .collection('clientes').document(cliente_id) \
                        .collection('pacotes_clientes')
        pacotes_ref.add(dados_pacote_cliente)
        return True
    except Exception as e:
        print(f"ERRO AO ASSOCIAR PACOTE AO CLIENTE (Cliente ID: {cliente_id}): {e}", file=sys.stderr)
        return False

def deduzir_credito_pacote_cliente(clinic_id: str, cliente_id: str, pacote_cliente_id: str):
    """Deduz 1 crédito de um pacote específico do cliente usando Increment."""
    if not cliente_id or not pacote_cliente_id:
         print(f"ERRO: Tentativa de deduzir crédito com IDs inválidos. Cliente: '{cliente_id}', Pacote: '{pacote_cliente_id}'", file=sys.stderr)
         return False
    try:
        pacote_ref = db.collection('clinicas').document(clinic_id) \
                       .collection('clientes').document(cliente_id) \
                       .collection('pacotes_clientes').document(pacote_cliente_id)

        # Usa firestore.Increment para uma dedução atômica e segura
        pacote_ref.update({
            'creditos_restantes': firestore.Increment(-1)
        })
        print(f"LOG: Crédito deduzido com sucesso do Pacote Cliente ID: {pacote_cliente_id}", file=sys.stderr)
        return True
    except Exception as e:
        print(f"ERRO AO DEDUZIR CRÉDITO DO PACOTE (Cliente ID: {cliente_id}, Pacote Cliente ID: {pacote_cliente_id}): {e}", file=sys.stderr)
        return False
