# database.py (VERSÃO COM GESTÃO DE TURMAS E PACOTES)
# ATUALIZADO:
# 1. Adicionada função `atualizar_turma`.
# 2. Adicionadas funções para Pacotes (Modelos e Pacotes do Cliente).
# 3. Adicionada lógica de `pacote_cliente_id` ao `salvar_agendamento`.
# 4. Adicionada função `deduzir_credito_pacote_cliente` com firestore.Increment.
# 5. Ajustada a query de `buscar_agendamentos_futuros_por_cliente` para buscar a partir do início do dia (00:00).
# 6. [CORREÇÃO] Removido o `order_by('horario')` da query `buscar_agendamentos_futuros_por_cliente` para simplificar a necessidade de índices.

import streamlit as st
import pandas as pd
from datetime import datetime, time, date, timedelta
import json
from google.cloud import firestore  # Importação principal
from google.cloud.firestore_v1.base_query import FieldFilter
from zoneinfo import ZoneInfo

# --- Configuração ---
TZ_SAO_PAULO = ZoneInfo('America/Sao_Paulo')

# --- Inicialização da Conexão ---
@st.cache_resource
def get_firestore_client():
    try:
        json_credenciais = st.secrets["firestore"]["json_key_string"]
        credenciais_dict = json.loads(json_credenciais)
        return firestore.Client.from_service_account_info(credenciais_dict)
    except Exception as e:
        st.error(f"Erro ao conectar ao Google Firestore: {e}")
        return None

db = get_firestore_client()
if db is None:
    st.stop()

# --- Funções de Gestão de Clínicas (Super Admin) ---
# (Funções listar_clinicas, adicionar_clinica, toggle_status_clinica... mantidas como estavam)
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
        print(f"ERRO AO LISTAR CLÍNICAS: {e}")
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
            'password': password,
            'ativo': True
        })
        return True, "Clínica adicionada com sucesso."
    except Exception as e:
        print(f"ERRO AO ADICIONAR CLÍNICA: {e}")
        return False, str(e)

def toggle_status_clinica(clinic_id: str, status_atual: bool):
    """Ativa ou desativa uma clínica (soft delete)."""
    try:
        clinic_ref = db.collection('clinicas').document(clinic_id)
        clinic_ref.update({'ativo': not status_atual})
        return True
    except Exception as e:
        print(f"ERRO AO ALTERAR STATUS DA CLÍNICA: {e}")
        return False

# --- Funções de Autenticação ---
def buscar_clinica_por_login(username, password):
    """Busca uma clínica ativa pelo username e password."""
    try:
        clinicas_ref = db.collection('clinicas')
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
        print(f"ERRO AO BUSCAR CLÍNICA: {e}")
        return None

# --- Funções de Gestão de Profissionais ---
# (Funções listar_profissionais, adicionar_profissional, remover_profissional, atualizar_horario_profissional... mantidas como estavam)
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
        print(f"ERRO AO LISTAR PROFISSIONAIS: {e}")
        return []

def adicionar_profissional(clinic_id: str, nome: str):
    """Adiciona um novo profissional a uma clínica."""
    try:
        profissionais_ref = db.collection('clinicas').document(clinic_id).collection('profissionais')
        profissionais_ref.add({'nome': nome, 'horario_trabalho': {}})
        return True
    except Exception as e:
        print(f"ERRO AO ADICIONAR PROFISSIONAL: {e}")
        return False

def remover_profissional(clinic_id: str, profissional_id: str):
    """Remove um profissional de uma clínica."""
    try:
        db.collection('clinicas').document(clinic_id).collection('profissionais').document(profissional_id).delete()
        return True
    except Exception as e:
        print(f"ERRO AO REMOVER PROFISSIONAL: {e}")
        return False

def atualizar_horario_profissional(clinic_id: str, prof_id: str, horarios: dict):
    """Atualiza a configuração de horário de um profissional."""
    try:
        prof_ref = db.collection('clinicas').document(clinic_id).collection('profissionais').document(prof_id)
        prof_ref.update({'horario_trabalho': horarios})
        return True
    except Exception as e:
        print(f"ERRO AO ATUALIZAR HORÁRIO: {e}")
        return False

# --- Funções de Gestão de Agendamentos ---
def salvar_agendamento(clinic_id: str, dados: dict, pin_code: str):
    """Cria um novo agendamento para uma clínica."""
    try:
        agendamentos_ref = db.collection('agendamentos')
        data_para_salvar = {
            'clinic_id': clinic_id,
            'pin_code': pin_code,
            'profissional_nome': dados['profissional_nome'],
            'cliente': dados['cliente'],
            'telefone': dados['telefone'],
            'horario': dados['horario'],
            'servico_nome': dados['servico_nome'],
            'duracao_min': dados['duracao_min'],
            'status': "Confirmado",
            'turma_id': dados.get('turma_id'), # Adiciona o campo opcional
            'pacote_cliente_id': dados.get('pacote_cliente_id') # <-- NOVO CAMPO
        }
        agendamentos_ref.add(data_para_salvar)
        return True
    except Exception as e:
        return str(e)

# (Funções buscar_agendamento_por_pin, buscar_agendamentos_por_intervalo, buscar_agendamentos_por_data_e_profissional, atualizar_status_agendamento, atualizar_horario_agendamento... mantidas como estavam)
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
        print(f"ERRO NA BUSCA POR PIN: {e}")
        return None

def buscar_agendamentos_por_intervalo(clinic_id: str, start_date: date, end_date: date):
    """Busca todos os agendamentos de uma clínica em um intervalo de datas."""
    try:
        start_dt = datetime.combine(start_date, time.min, tzinfo=TZ_SAO_PAULO)
        end_dt = datetime.combine(end_date, time.max, tzinfo=TZ_SAO_PAULO)
        
        query = db.collection('agendamentos').where(filter=FieldFilter('clinic_id', '==', clinic_id))
        docs = query.stream()
        
        data = []
        for doc in docs:
            item = doc.to_dict()
            item['id'] = doc.id
            if 'horario' in item and isinstance(item['horario'], datetime):
                item['horario'] = item['horario'].astimezone(TZ_SAO_PAULO)
                if start_dt <= item['horario'] <= end_dt:
                    data.append(item)
        
        return pd.DataFrame(data)
    except Exception as e:
        print(f"ERRO NA BUSCA DE AGENDAMENTOS POR INTERVALO: {e}")
        return pd.DataFrame()

def buscar_agendamentos_por_data_e_profissional(clinic_id: str, profissional_nome: str, data_selecionada: date):
    """Busca agendamentos para um profissional específico em uma data específica."""
    try:
        start_dt = datetime.combine(data_selecionada, time.min, tzinfo=TZ_SAO_PAULO)
        end_dt = datetime.combine(data_selecionada, time.max, tzinfo=TZ_SAO_PAULO)

        query = db.collection('agendamentos').where(filter=FieldFilter('clinic_id', '==', clinic_id)) \
                                             .where(filter=FieldFilter('profissional_nome', '==', profissional_nome))

        docs = query.stream()
        data = []
        for doc in docs:
            item = doc.to_dict()
            item['id'] = doc.id
            if 'horario' in item and isinstance(item['horario'], datetime):
                item['horario'] = item['horario'].astimezone(TZ_SAO_PAULO)
                if start_dt <= item['horario'] <= end_dt:
                    data.append(item)
        return pd.DataFrame(data)
    except Exception as e:
        print(f"ERRO NA BUSCA POR DATA E PROFISSIONAL: {e}")
        return pd.DataFrame()

def atualizar_status_agendamento(id_agendamento: str, novo_status: str):
    """Atualiza o status de um agendamento específico."""
    try:
        doc_ref = db.collection('agendamentos').document(id_agendamento)
        doc_ref.update({'status': novo_status})
        return True
    except Exception as e:
        print(f"ERRO AO ATUALIZAR STATUS: {e}")
        return False

def atualizar_horario_agendamento(id_agendamento: str, novo_horario: datetime):
    """Atualiza o horário de um agendamento (usado na remarcação)."""
    try:
        doc_ref = db.collection('agendamentos').document(id_agendamento)
        novo_horario_utc = novo_horario.astimezone(ZoneInfo('UTC'))
        doc_ref.update({'horario': novo_horario_utc})
        return True
    except Exception as e:
        print(f"ERRO AO ATUALIZAR HORÁRIO: {e}")
        return False
        
# <-- INÍCIO DA FUNÇÃO MODIFICADA -->
def buscar_agendamentos_futuros_por_cliente(clinic_id: str, nome_cliente: str):
    """Busca agendamentos futuros (Confirmados) para um cliente específico."""
    try:
        hoje_sp = datetime.now(TZ_SAO_PAULO).date()
        inicio_do_dia_hoje = datetime.combine(hoje_sp, time.min, tzinfo=TZ_SAO_PAULO)
        
        query = db.collection('agendamentos') \
                  .where(filter=FieldFilter('clinic_id', '==', clinic_id)) \
                  .where(filter=FieldFilter('cliente', '==', nome_cliente)) \
                  .where(filter=FieldFilter('status', '==', 'Confirmado')) \
                  .where(filter=FieldFilter('horario', '>=', inicio_do_dia_hoje))
                  # Removido o .order_by('horario') para simplificar índice

        docs = query.stream()
        agendamentos = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            if 'horario' in data and isinstance(data['horario'], datetime):
                 data['horario'] = data['horario'].astimezone(TZ_SAO_PAULO)
            agendamentos.append(data)
            
        # Ordena em Python se necessário (Firestore geralmente retorna ordenado pelo campo do filtro de range)
        agendamentos.sort(key=lambda x: x['horario'])
        
        return agendamentos
    except Exception as e:
        print(f"ERRO AO BUSCAR AGENDAMENTOS FUTUROS DO CLIENTE: {e}")
        # Em caso de erro (ex: índice faltando), retorna lista vazia
        # Você pode verificar os logs do Streamlit/GCP para detalhes do erro
        return []
# <-- FIM DA FUNÇÃO MODIFICADA -->
        
# --- Funções de Gestão de Feriados ---
# (Funções adicionar_feriado, listar_feriados, remover_feriado... mantidas como estavam)
def adicionar_feriado(clinic_id: str, data_feriado: date, descricao: str):
    """Adiciona um feriado ou folga para uma clínica."""
    try:
        feriados_ref = db.collection('clinicas').document(clinic_id).collection('feriados')
        data_dt = datetime.combine(data_feriado, time.min)
        feriados_ref.add({'data': data_dt, 'descricao': descricao, 'clinic_id': clinic_id})
        return True
    except Exception as e:
        print(f"ERRO AO ADICIONAR FERIADO: {e}")
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
            if 'data' in feriado and isinstance(feriado['data'], datetime):
                feriado['data'] = feriado['data'].date()
            feriados.append(feriado)
        return feriados
    except Exception as e:
        print(f"Erro ao listar feriados: {e}")
        return []

def remover_feriado(clinic_id: str, feriado_id: str):
    """Remove um feriado de uma clínica."""
    try:
        db.collection('clinicas').document(clinic_id).collection('feriados').document(feriado_id).delete()
        return True
    except Exception as e:
        print(f"ERRO AO REMOVER FERIADO: {e}")
        return False

# --- Funções de Gestão de Clientes ---
# (Funções listar_clientes, adicionar_cliente, remover_cliente... mantidas como estavam)
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
        print(f"ERRO AO LISTAR CLIENTES: {e}")
        return []

def adicionar_cliente(clinic_id: str, nome: str, telefone: str, observacoes: str):
    """Adiciona um novo cliente a uma clínica."""
    try:
        clientes_ref = db.collection('clinicas').document(clinic_id).collection('clientes')
        clientes_ref.add({'nome': nome, 'telefone': telefone, 'observacoes': observacoes})
        return True
    except Exception as e:
        print(f"ERRO AO ADICIONAR CLIENTE: {e}")
        return False

def remover_cliente(clinic_id: str, cliente_id: str):
    """Remove um cliente de uma clínica."""
    try:
        db.collection('clinicas').document(clinic_id).collection('clientes').document(cliente_id).delete()
        return True
    except Exception as e:
        print(f"ERRO AO REMOVER CLIENTE: {e}")
        return False

# --- Funções de Gestão de Serviços ---
# (Funções listar_servicos, adicionar_servico, remover_servico... mantidas como estavam)
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
        print(f"ERRO AO LISTAR SERVIÇOS: {e}")
        return []

def adicionar_servico(clinic_id: str, nome: str, duracao_min: int, tipo: str):
    """Adiciona um novo serviço a uma clínica."""
    try:
        servicos_ref = db.collection('clinicas').document(clinic_id).collection('servicos')
        servicos_ref.add({'nome': nome, 'duracao_min': duracao_min, 'tipo': tipo})
        return True
    except Exception as e:
        print(f"ERRO AO ADICIONAR SERVIÇO: {e}")
        return False

def remover_servico(clinic_id: str, servico_id: str):
    """Remove um serviço de uma clínica."""
    try:
        db.collection('clinicas').document(clinic_id).collection('servicos').document(servico_id).delete()
        return True
    except Exception as e:
        print(f"ERRO AO REMOVER SERVIÇO: {e}")
        return False

# --- Funções - Gestão de Turmas ---
# (Funções adicionar_turma, listar_turmas, remover_turma, atualizar_turma, contar_agendamentos_turma_dia... mantidas como estavam)
def adicionar_turma(clinic_id: str, dados_turma: dict):
    """Adiciona uma nova turma recorrente para a clínica."""
    try:
        turmas_ref = db.collection('clinicas').document(clinic_id).collection('turmas')
        turmas_ref.add(dados_turma)
        return True
    except Exception as e:
        print(f"ERRO AO ADICIONAR TURMA: {e}")
        return False

def listar_turmas(clinic_id: str, profissionais_list: list = None, servicos_list: list = None):
    """Lista todas as turmas de uma clínica, opcionalmente populando nomes."""
    try:
        turmas_ref = db.collection('clinicas').document(clinic_id).collection('turmas')
        docs = turmas_ref.order_by('horario').stream()
        turmas = []
        for doc in docs:
            turma = doc.to_dict()
            turma['id'] = doc.id
            
            # Popula nomes se as listas forem fornecidas
            if profissionais_list:
                prof_id = turma.get('profissional_id')
                prof_info = next((p for p in profissionais_list if p['id'] == prof_id), None)
                turma['profissional_nome'] = prof_info['nome'] if prof_info else 'N/A'
            
            if servicos_list:
                serv_id = turma.get('servico_id')
                serv_info = next((s for s in servicos_list if s['id'] == serv_id), None)
                turma['servico_nome'] = serv_info['nome'] if serv_info else 'N/A'
            
            turmas.append(turma)
        return turmas
    except Exception as e:
        print(f"ERRO AO LISTAR TURMAS: {e}")
        return []

def remover_turma(clinic_id: str, turma_id: str):
    """Remove uma turma da clínica."""
    try:
        db.collection('clinicas').document(clinic_id).collection('turmas').document(turma_id).delete()
        return True
    except Exception as e:
        print(f"ERRO AO REMOVER TURMA: {e}")
        return False

def atualizar_turma(clinic_id: str, turma_id: str, dados_turma: dict):
    """Atualiza os dados de uma turma existente."""
    try:
        turma_ref = db.collection('clinicas').document(clinic_id).collection('turmas').document(turma_id)
        turma_ref.update(dados_turma)
        return True
    except Exception as e:
        print(f"ERRO AO ATUALIZAR TURMA: {e}")
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
        
        count = sum(1 for _ in query.stream())
        return count
    except Exception as e:
        print(f"ERRO AO CONTAR AGENDAMENTOS DA TURMA: {e}")
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
        print(f"ERRO AO LISTAR MODELOS DE PACOTES: {e}")
        return []

def adicionar_pacote_modelo(clinic_id: str, dados_pacote: dict):
    """Adiciona um novo modelo de pacote."""
    try:
        pacotes_ref = db.collection('clinicas').document(clinic_id).collection('pacotes')
        pacotes_ref.add(dados_pacote)
        return True
    except Exception as e:
        print(f"ERRO AO ADICIONAR MODELO DE PACOTE: {e}")
        return False

def remover_pacote_modelo(clinic_id: str, pacote_id: str):
    """Remove um modelo de pacote."""
    try:
        db.collection('clinicas').document(clinic_id).collection('pacotes').document(pacote_id).delete()
        return True
    except Exception as e:
        print(f"ERRO AO REMOVER MODELO DE PACOTE: {e}")
        return False

# 2. Funções para Pacotes dos Clientes (Instâncias individuais)

def listar_pacotes_do_cliente(clinic_id: str, cliente_id: str):
    """Lista todos os pacotes adquiridos por um cliente específico."""
    try:
        pacotes_ref = db.collection('clinicas').document(clinic_id) \
                        .collection('clientes').document(cliente_id) \
                        .collection('pacotes_clientes')
        
        docs = pacotes_ref.order_by('data_expiracao', direction=firestore.Query.DESCENDING).stream()
        pacotes = []
        for doc in docs:
            pacote = doc.to_dict()
            pacote['id'] = doc.id
            # Converte timestamps do Firestore para objetos date/datetime de Python
            if 'data_inicio' in pacote and isinstance(pacote['data_inicio'], datetime):
                pacote['data_inicio'] = pacote['data_inicio'].astimezone(TZ_SAO_PAULO)
            if 'data_expiracao' in pacote and isinstance(pacote['data_expiracao'], datetime):
                pacote['data_expiracao'] = pacote['data_expiracao'].astimezone(TZ_SAO_PAULO)
            pacotes.append(pacote)
        return pacotes
    except Exception as e:
        print(f"ERRO AO LISTAR PACOTES DO CLIENTE: {e}")
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
        print(f"ERRO AO ASSOCIAR PACOTE AO CLIENTE: {e}")
        return False

def deduzir_credito_pacote_cliente(clinic_id: str, cliente_id: str, pacote_cliente_id: str):
    """Deduz 1 crédito de um pacote específico do cliente usando Increment."""
    try:
        pacote_ref = db.collection('clinicas').document(clinic_id) \
                       .collection('clientes').document(cliente_id) \
                       .collection('pacotes_clientes').document(pacote_cliente_id)
        
        # Usa firestore.Increment para uma dedução atômica
        pacote_ref.update({
            'creditos_restantes': firestore.Increment(-1)
        })
        return True
    except Exception as e:
        print(f"ERRO AO DEDUZIR CRÉDITO DO PACOTE: {e}")
        return False
