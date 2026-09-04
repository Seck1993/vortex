import os
import time
import json
import random
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
from werkzeug.utils import secure_filename
from sqlalchemy import func, text
from models import db, Jogador, ConfigAtividade, ImportacaoXML, Pontuacao, PersonagemSecundario
from xml_engine import analisar_xml_guilda

app = Flask(__name__)

# Configuração que aceita o PostgreSQL do Render ou o SQLite local
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///vortex.db')
if app.config['SQLALCHEMY_DATABASE_URI'].startswith("postgres://"):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'tmp/' 
app.config['SECRET_KEY'] = 'chave_super_secreta_vortex' 

db.init_app(app)


def asset_version(filename):
    """Retorna a data de modificação do arquivo estático como string, usada
    como query param de cache-busting (?v=...) nos links/scripts do template."""
    caminho = os.path.join(app.static_folder, filename)
    try:
        return str(int(os.path.getmtime(caminho)))
    except OSError:
        return "1"


app.jinja_env.globals['asset_version'] = asset_version


def caminho_upload_seguro(arquivo, prefixo_padrao):
    """Monta o caminho de gravação de um upload dentro de UPLOAD_FOLDER.

    Usa secure_filename para impedir que um nome como '../app.py' escape da
    pasta de uploads e sobrescreva arquivos do projeto."""
    nome_seguro = secure_filename(arquivo.filename or '')
    if not nome_seguro:
        nome_seguro = f"{prefixo_padrao}_{int(time.time() * 1000)}"
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    return os.path.join(app.config['UPLOAD_FOLDER'], nome_seguro)


def calcular_pontuacao_base_semanal(pontos_semanais):
    """Calcula a 'moda' (valor mais frequente; empate resolvido pelo maior valor)
    de uma coleção de totais de pontos semanais por jogador. Usada como teto de
    100% de participação. Extraída para uso único em index() e apostar_item(),
    que antes duplicavam esta lógica de negócio central."""
    frequencias = {}
    for pts in pontos_semanais:
        if pts > 0:
            frequencias[pts] = frequencias.get(pts, 0) + 1
    if not frequencias:
        return 0
    return max(frequencias.keys(), key=lambda k: (frequencias[k], k))


def erro_interno(e):
    """Loga o stack trace no servidor e devolve uma mensagem genérica ao cliente,
    evitando vazar detalhes internos (stack trace / mensagens do SQLAlchemy)."""
    app.logger.exception("Erro interno em rota da API")
    return jsonify({"erro": "Erro interno no servidor. Tente novamente ou contate o administrador."}), 500


class SorteioHistorico(db.Model):
    __tablename__ = 'sorteios'
    id = db.Column(db.Integer, primary_key=True)
    jogador_id = db.Column(db.Integer, db.ForeignKey('jogadores.id'), nullable=False)
    data_sorteio = db.Column(db.DateTime, default=datetime.utcnow)
    observacao = db.Column(db.String(255), default="")
    penalidade = db.Column(db.Integer, default=0)
    
    jogador = db.relationship('Jogador', backref=db.backref('sorteios', lazy=True))

class SorteioMemeHistorico(db.Model):
    __tablename__ = 'sorteios_meme'
    id = db.Column(db.Integer, primary_key=True)
    jogador_id = db.Column(db.Integer, db.ForeignKey('jogadores.id'), nullable=False)
    item_sorteado = db.Column(db.String(100), default="")
    data_sorteio = db.Column(db.DateTime, default=datetime.utcnow)
    observacao = db.Column(db.String(255), default="")
    
    jogador = db.relationship('Jogador', backref=db.backref('sorteios_meme', lazy=True))

# ================= MODELOS DE EVENTO (BANNER E APOSTAS) =================
class EventoSorteio(db.Model):
    __tablename__ = 'evento_sorteio'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), default="SORTEIO HOJE AS 20:00")
    ativo = db.Column(db.Boolean, default=True)
    prazo_encerramento = db.Column(db.String(50), nullable=True) 
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    itens = db.relationship('EventoItem', backref='evento', cascade="all, delete-orphan", lazy=True)

class EventoItem(db.Model):
    __tablename__ = 'evento_item'
    id = db.Column(db.Integer, primary_key=True)
    evento_id = db.Column(db.Integer, db.ForeignKey('evento_sorteio.id'))
    nome_item = db.Column(db.String(100), nullable=False)
    max_pontos = db.Column(db.Float, default=100.0)
    restricao = db.Column(db.String(20), default="Todos") # NOVA REGRA DE FAIXA (Todos, Titã, Mega)
    sorteado = db.Column(db.Boolean, default=False)
    vencedor_nome = db.Column(db.String(100), nullable=True)
    em_andamento = db.Column(db.Boolean, default=False) 
    dados_roleta_json = db.Column(db.Text, nullable=True) 
    apostas = db.relationship('ApostaSorteio', backref='item', cascade="all, delete-orphan", lazy=True)

class ApostaSorteio(db.Model):
    __tablename__ = 'aposta_sorteio'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('evento_item.id'))
    jogador_id = db.Column(db.Integer, db.ForeignKey('jogadores.id'))
    pontos = db.Column(db.Float, default=0.0)
    jogador = db.relationship('Jogador')


class StaffMembro(db.Model):
    """Cadastro de pessoas que podem representar a fatia fixa de 15% (Staff)
    nos sorteios de item. Independente do cadastro de Jogadores."""
    __tablename__ = 'staff_membros'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)


@app.route('/')
def index():
    configuracoes = ConfigAtividade.query.filter(ConfigAtividade.nome_xml.notin_(['REGUA_MEGA', 'REGUA_TITA', 'SEMANA_ATIVA'])).order_by(ConfigAtividade.id.asc()).all()
    tipos_eventos = {c.nome_xml: c.tipo_evento for c in configuracoes}

    # Controle da Semana Ativa
    config_semana = ConfigAtividade.query.filter_by(nome_xml='SEMANA_ATIVA').first()
    semana_ativa_numero = config_semana.pontos_padrao if config_semana else 1
    semana_ativa_str = f"Semana {semana_ativa_numero}"

    # Puxa os valores das réguas
    config_mega = ConfigAtividade.query.filter_by(nome_xml='REGUA_MEGA').first()
    cp_mega = config_mega.pontos_padrao if config_mega else 100000

    config_tita = ConfigAtividade.query.filter_by(nome_xml='REGUA_TITA').first()
    cp_tita = config_tita.pontos_padrao if config_tita else 50000

    pontos_brutos = db.session.query(
        Pontuacao.jogador_id, 
        Pontuacao.atividade, 
        Pontuacao.semana,
        func.sum(Pontuacao.pontos)
    ).group_by(Pontuacao.jogador_id, Pontuacao.atividade, Pontuacao.semana).all()

    mapa_pontos = {}
    for pid, atv, sem, pts in pontos_brutos:
        if pid not in mapa_pontos:
            mapa_pontos[pid] = {'total_bruto': 0, 'total_final': 0, 'total_semanal': 0, 'atividades': {}, 'blackskull': 0, 'ajustes': 0, 'penalidades': 0}
        
        mapa_pontos[pid]['total_bruto'] += pts
        mapa_pontos[pid]['total_final'] += pts

        if sem == semana_ativa_str:
            mapa_pontos[pid]['total_semanal'] += pts

        if atv == 'BlackSkull':
            mapa_pontos[pid]['blackskull'] += pts
        elif atv in ['Edição via Painel', 'Ajuste Manual', 'Ajuste Geral']:
            mapa_pontos[pid]['ajustes'] += pts
        else:
            mapa_pontos[pid]['atividades'][atv] = mapa_pontos[pid]['atividades'].get(atv, 0) + pts

    penalidades = db.session.query(SorteioHistorico.jogador_id, func.sum(SorteioHistorico.penalidade)).group_by(SorteioHistorico.jogador_id).all()
    for pid, pen in penalidades:
        if pid not in mapa_pontos:
            mapa_pontos[pid] = {'total_bruto': 0, 'total_final': 0, 'total_semanal': 0, 'atividades': {}, 'blackskull': 0, 'ajustes': 0, 'penalidades': 0}
        mapa_pontos[pid]['penalidades'] += pen
        mapa_pontos[pid]['total_final'] -= pen

    jogadores = Jogador.query.filter(
        db.or_(Jogador.status == 'Ativo', Jogador.status == None, Jogador.status == '')
    ).all()
    
    # === CÁLCULO DA "MODA" (TETO DE 100%) ===
    pontuacao_base_semanal = calcular_pontuacao_base_semanal(
        mapa_pontos.get(j.id, {}).get('total_semanal', 0) for j in jogadores
    )

    ranking = []
    soma_total_pontos = 0
    
    for j in jogadores:
        p_data = mapa_pontos.get(j.id, {'total_bruto': 0, 'total_final': 0, 'total_semanal': 0, 'atividades': {}, 'blackskull': 0, 'ajustes': 0, 'penalidades': 0})
        
        total_semanal_jogador = p_data['total_semanal']
        total_final = p_data['total_final']
        
        if pontuacao_base_semanal > 0:
            if total_semanal_jogador >= pontuacao_base_semanal:
                participacao = 100.0
                pontos_diamante = total_semanal_jogador - pontuacao_base_semanal
            else:
                participacao = round((total_semanal_jogador / pontuacao_base_semanal) * 100, 2)
                pontos_diamante = 0
        else:
            participacao = 0.0
            pontos_diamante = 0

        alts_list = [a.nome_alt for a in j.alts]
        ranking.append({
            'jogador': j,
            'alts_str': ', '.join(alts_list),
            'pontos': total_final, 
            'pontos_diamante': pontos_diamante,
            'participacao': participacao, 
            'atividades': p_data['atividades'],
            'blackskull': p_data['blackskull'],
            'ajustes': p_data['ajustes'],
            'penalidades': p_data['penalidades']
        })
        soma_total_pontos += total_final

    ranking.sort(key=lambda x: x['jogador'].nome.lower())
    ranking.sort(key=lambda x: (x['pontos'], x['jogador'].poder_combate, x['jogador'].level), reverse=True)

    historico_sorteios = SorteioHistorico.query.order_by(SorteioHistorico.data_sorteio.desc()).all()
    historico_meme = SorteioMemeHistorico.query.order_by(SorteioMemeHistorico.data_sorteio.desc()).all()
    importacoes = ImportacaoXML.query.filter_by(semana=semana_ativa_str).order_by(ImportacaoXML.data_importacao.desc()).all()
    
    total_jogadores = len(jogadores)
    user_role = session.get('role', 'guest')

    staff_membros = StaffMembro.query.order_by(StaffMembro.nome.asc()).all()

    # Lista completa (inclusive inativos) para a aba de gerenciamento de membros
    todos_jogadores = Jogador.query.order_by(Jogador.nome.asc()).all()

    # Dados do Evento Ativo (Banner)
    evento_ativo = EventoSorteio.query.filter_by(ativo=True).order_by(EventoSorteio.id.desc()).first()
    
    evento_data = None
    if evento_ativo:
        itens_data = []
        for item in evento_ativo.itens:
            apostas = [{'jogador_nome': a.jogador.nome, 'pontos': a.pontos, 'id': a.id} for a in item.apostas]
            itens_data.append({
                'id': item.id,
                'nome_item': item.nome_item,
                'max_pontos': item.max_pontos,
                'restricao': item.restricao, # Passa a restrição para a Tela
                'sorteado': item.sorteado,
                'vencedor_nome': item.vencedor_nome,
                'apostas': apostas,
                'total_apostado': sum(a['pontos'] for a in apostas)
            })
        evento_data = {
            'id': evento_ativo.id,
            'titulo': evento_ativo.titulo,
            'prazo_encerramento': evento_ativo.prazo_encerramento or "",
            'itens': itens_data
        }

    return render_template(
        'dashboard.html', 
        ranking=ranking, 
        historico_sorteios=historico_sorteios,
        historico_meme=historico_meme, 
        configuracoes=configuracoes,
        importacoes=importacoes,
        total_jogadores=total_jogadores,
        soma_total_pontos=soma_total_pontos,
        user_role=user_role,
        cp_mega=cp_mega,
        cp_tita=cp_tita,
        semana_ativa_numero=semana_ativa_numero,
        evento=evento_data,
        staff_membros=staff_membros,
        todos_jogadores=todos_jogadores
    )

@app.route('/api/login', methods=['POST'])
def login():
    dados = request.get_json()
    senha_enviada = dados.get('senha')

    if senha_enviada == 'ana2026':
        session['logged_in'] = True
        session['role'] = 'admin'
        return jsonify({"mensagem": "Autenticado como Administrador"}), 200
    elif senha_enviada == 'membro2026':
        session['logged_in'] = True
        session['role'] = 'membro'
        return jsonify({"mensagem": "Autenticado como Membro"}), 200

    return jsonify({"erro": "Senha incorreta"}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('logged_in', None)
    session.pop('role', None)
    return jsonify({"mensagem": "Logout efetuado"}), 200

def admin_required():
    return session.get('logged_in') and session.get('role') == 'admin'

def login_required():
    return session.get('logged_in')

# ================= ROTA DE VIRADA DE SEMANA =================
@app.route('/api/nova-semana', methods=['POST'])
def nova_semana():
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    
    config_semana = ConfigAtividade.query.filter_by(nome_xml='SEMANA_ATIVA').first()
    if not config_semana:
        config_semana = ConfigAtividade(nome_xml='SEMANA_ATIVA', pontos_padrao=1, tipo_evento='sistema', is_ativa=False)
        db.session.add(config_semana)
    else:
        config_semana.pontos_padrao += 1
        
    db.session.commit()
    return jsonify({"mensagem": f"Semana {config_semana.pontos_padrao} iniciada com sucesso!"}), 200

# ================= ROTAS DO BANNER E APOSTAS =================

@app.route('/api/publicar-banner', methods=['POST'])
def publicar_banner():
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    dados = request.get_json()
    
    eventos_ativos = EventoSorteio.query.filter_by(ativo=True).all()
    for evt in eventos_ativos:
        evt.ativo = False
        for item in evt.itens:
            if not item.sorteado:
                ApostaSorteio.query.filter_by(item_id=item.id).delete()
    
    prazo_str = str(dados.get('prazo', '')).strip()
    
    novo_evento = EventoSorteio(
        titulo=dados.get('titulo', 'SORTEIO HOJE AS 20:00'),
        prazo_encerramento=prazo_str
    )
    db.session.add(novo_evento)
    db.session.flush()

    for item in dados.get('itens', []):
        db.session.add(EventoItem(
            evento_id=novo_evento.id, 
            nome_item=item['nome'], 
            max_pontos=float(item['max_pontos']),
            restricao=item.get('restricao', 'Todos') # Recebe a Restrição
        ))
    
    db.session.commit()
    return jsonify({"mensagem": "Evento de sorteio publicado!"}), 200

@app.route('/api/encerrar-banner', methods=['POST'])
def encerrar_banner():
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    
    eventos_ativos = EventoSorteio.query.filter_by(ativo=True).all()
    for evt in eventos_ativos:
        evt.ativo = False
        for item in evt.itens:
            if not item.sorteado:
                ApostaSorteio.query.filter_by(item_id=item.id).delete()
                
    db.session.commit()
    return jsonify({"mensagem": "Evento encerrado. Pontos estornados aos jogadores!"}), 200

@app.route('/api/apostar-item', methods=['POST'])
def apostar_item():
    if not login_required(): return jsonify({"erro": "Faça login para apostar"}), 401
    dados = request.get_json()
    item_id = dados.get('item_id')
    jogador_id = dados.get('jogador_id')
    pontos = float(dados.get('pontos', 0))

    if pontos <= 0: return jsonify({"erro": "Pontos inválidos"}), 400

    evento = EventoSorteio.query.filter_by(ativo=True).first()
    if evento and evento.prazo_encerramento:
        try:
            prazo_ms = int(float(evento.prazo_encerramento))
            if int(time.time() * 1000) > prazo_ms:
                return jsonify({"erro": "O prazo limite para apostas foi encerrado!"}), 400
        except Exception:
            pass

    item = db.session.get(EventoItem, item_id)
    if not item or item.sorteado or item.em_andamento: return jsonify({"erro": "Item inválido ou já finalizado/em sorteio."}), 400

    jogador_alvo = db.session.get(Jogador, jogador_id)
    if not jogador_alvo: return jsonify({"erro": "Jogador não encontrado."}), 404

    # === CHECAGEM DE RESTRIÇÃO DE FAIXA (MEGA / TITÃ) ===
    config_mega = ConfigAtividade.query.filter_by(nome_xml='REGUA_MEGA').first()
    cp_mega = config_mega.pontos_padrao if config_mega else 100000

    config_tita = ConfigAtividade.query.filter_by(nome_xml='REGUA_TITA').first()
    cp_tita = config_tita.pontos_padrao if config_tita else 50000

    if item.restricao == 'Mega' and jogador_alvo.poder_combate < cp_mega:
        return jsonify({"erro": f"Acesso negado! Este item é exclusivo para a faixa MEGA (CP Mínimo exigido: {cp_mega:,})."}), 400

    if item.restricao == 'Titã' and jogador_alvo.poder_combate < cp_tita:
        return jsonify({"erro": f"Acesso negado! Este item é exclusivo para as faixas Titã e Mega (CP Mínimo exigido: {cp_tita:,})."}), 400

    # VALIDAÇÃO DE REGRA DE NEGÓCIO: MÍNIMO 90% DE PARTICIPAÇÃO NA SEMANA ATUAL
    config_semana = ConfigAtividade.query.filter_by(nome_xml='SEMANA_ATIVA').first()
    semana_ativa_str = f"Semana {config_semana.pontos_padrao}" if config_semana else "Semana 1"

    pontos_semanais_todos = db.session.query(
        Pontuacao.jogador_id, func.sum(Pontuacao.pontos)
    ).filter_by(semana=semana_ativa_str).group_by(Pontuacao.jogador_id).all()

    pontuacao_base_semanal = calcular_pontuacao_base_semanal(pts for _, pts in pontos_semanais_todos)
    pts_jogador_semana = db.session.query(func.sum(Pontuacao.pontos)).filter_by(jogador_id=jogador_id, semana=semana_ativa_str).scalar() or 0

    participacao_jogador = (pts_jogador_semana / pontuacao_base_semanal) * 100.0 if pontuacao_base_semanal > 0 else 0.0

    if participacao_jogador < 90.0:
        return jsonify({
            "erro": f"Acesso bloqueado! Sua participação na semana atual é {participacao_jogador:.1f}%. (Mínimo exigido: 90%)."
        }), 400

    # VALIDAÇÃO DO SALDO DE PONTOS REAIS
    pts_brutos_jogador = db.session.query(func.sum(Pontuacao.pontos)).filter_by(jogador_id=jogador_id).scalar() or 0
    pens = db.session.query(func.sum(SorteioHistorico.penalidade)).filter_by(jogador_id=jogador_id).scalar() or 0
    
    apostas_ativas = db.session.query(func.sum(ApostaSorteio.pontos)).join(EventoItem).join(EventoSorteio).filter(
        ApostaSorteio.jogador_id == jogador_id,
        EventoItem.sorteado == False,
        EventoSorteio.ativo == True
    ).scalar() or 0

    aposta_existente = ApostaSorteio.query.filter_by(item_id=item_id, jogador_id=jogador_id).first()
    aposta_atual = aposta_existente.pontos if aposta_existente else 0

    pontos_disponiveis = (pts_brutos_jogador - pens) - apostas_ativas + aposta_atual

    if pontos > pontos_disponiveis:
        return jsonify({"erro": f"Saldo insuficiente! Você possui apenas {pontos_disponiveis:.0f} pts reais livres para apostar."}), 400

    if aposta_existente:
        aposta_existente.pontos = pontos
    else:
        db.session.add(ApostaSorteio(item_id=item_id, jogador_id=jogador_id, pontos=pontos))
    
    db.session.commit()
    return jsonify({"mensagem": "Aposta registrada com sucesso!"}), 200

@app.route('/api/remover-aposta/<int:id>', methods=['DELETE'])
def remover_aposta(id):
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    aposta = db.session.get(ApostaSorteio, id)
    if aposta:
        db.session.delete(aposta)
        db.session.commit()
    return jsonify({"mensagem": "Aposta removida."}), 200


# ================= CADASTRO DE STAFF (para a fatia fixa da roleta) =================

@app.route('/api/criar-staff', methods=['POST'])
def criar_staff():
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    nome = str(request.get_json().get('nome', '')).strip()[:100]
    if not nome:
        return jsonify({"erro": "Informe um nome."}), 400

    if StaffMembro.query.filter(func.lower(StaffMembro.nome) == nome.lower()).first():
        return jsonify({"erro": "Já existe uma pessoa da Staff com esse nome."}), 409

    db.session.add(StaffMembro(nome=nome))
    db.session.commit()
    return jsonify({"mensagem": "Pessoa adicionada à Staff!"}), 200

@app.route('/api/editar-staff', methods=['POST'])
def editar_staff():
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    staff_data = request.get_json().get('staff', [])
    try:
        for item in staff_data:
            membro = db.session.get(StaffMembro, item['id'])
            nome = str(item.get('nome', '')).strip()[:100]
            if membro and nome:
                membro.nome = nome
        db.session.commit()
        return jsonify({"mensagem": "Nomes da Staff atualizados!"}), 200
    except Exception as e:
        db.session.rollback()
        return erro_interno(e)

@app.route('/api/deletar-staff/<int:id>', methods=['DELETE'])
def deletar_staff(id):
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    membro = db.session.get(StaffMembro, id)
    if membro:
        db.session.delete(membro)
        db.session.commit()
        return jsonify({"mensagem": "Removido da Staff."}), 200
    return jsonify({"erro": "Não encontrado."}), 404


@app.route('/api/simular-sorteio-item', methods=['POST'])
def simular_sorteio_item():
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    dados = request.get_json()
    item_id = dados.get('item_id')
    nome_staff = str(dados.get('nome_staff', '')).strip()[:100]
    if not nome_staff:
        return jsonify({"erro": "Informe o nome de quem está representando a Staff neste sorteio."}), 400

    item = db.session.get(EventoItem, item_id)
    if not item or item.sorteado: return jsonify({"erro": "Item já sorteado."}), 400

    apostas = ApostaSorteio.query.filter_by(item_id=item_id).all()
    if not apostas: return jsonify({"erro": "Nenhum participante apostou neste item ainda."}), 400

    fatias = {}
    candidatos = []
    pesos = []

    total_pontos = sum(ap.pontos for ap in apostas)

    # A fatia da Staff é sempre 15% fixos; o nome exibido é definido pelo admin
    # na hora do sorteio (não vem do login nem de um rótulo genérico fixo).
    fatias[nome_staff] = 15.0
    candidatos.append({"id": None, "nome": nome_staff, "pontos_apostados": 0, "is_staff": True})
    pesos.append(15.0)

    for ap in apostas:
        porcentagem = (ap.pontos / total_pontos) * 85.0 if total_pontos > 0 else 0
        fatias[ap.jogador.nome] = porcentagem
        candidatos.append({"id": ap.jogador.id, "nome": ap.jogador.nome, "pontos_apostados": ap.pontos, "is_staff": False})
        pesos.append(porcentagem)

    vencedor = random.choices(candidatos, weights=pesos, k=1)[0]

    dados_roleta = {
        "item_id": item.id,
        "nome_item": item.nome_item,
        "vencedor_nome": vencedor['nome'],
        "vencedor_id": vencedor['id'],
        "pontos_apostados": vencedor['pontos_apostados'],
        "is_staff": vencedor['is_staff'],
        "fatias": fatias,
        "timestamp_inicio": int(time.time() * 1000)
    }

    item.em_andamento = True
    item.dados_roleta_json = json.dumps(dados_roleta)
    db.session.commit()
    
    return jsonify(dados_roleta), 200

@app.route('/api/status-sorteio-ao-vivo', methods=['GET'])
def status_sorteio_ao_vivo():
    if not login_required(): return jsonify({"ativo": False}), 401
    
    item_em_sorteio = EventoItem.query.filter_by(em_andamento=True).first()
    if item_em_sorteio and item_em_sorteio.dados_roleta_json:
        dados = json.loads(item_em_sorteio.dados_roleta_json)
        return jsonify({"ativo": True, "dados": dados}), 200
        
    return jsonify({"ativo": False}), 200


@app.route('/api/confirmar-sorteio-item', methods=['POST'])
def confirmar_sorteio_item():
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    dados = request.get_json()
    item_id = dados.get('item_id')
    vencedor_id = dados.get('vencedor_id')
    vencedor_nome = dados.get('vencedor_nome')
    is_staff = dados.get('is_staff')
    pontos_apostados = dados.get('pontos_apostados', 0)

    item = db.session.get(EventoItem, item_id)
    if not item or item.sorteado: return jsonify({"erro": "Erro: Item já finalizado."}), 400

    item.sorteado = True
    item.em_andamento = False
    item.vencedor_nome = vencedor_nome
    
    if not is_staff and vencedor_id:
        novo_sorteio = SorteioHistorico(
            jogador_id=vencedor_id, 
            observacao=f"Venceu: {item.nome_item}",
            penalidade=int(pontos_apostados)
        )
        db.session.add(novo_sorteio)

    db.session.commit()
    return jsonify({"mensagem": "Sorteio finalizado e dados salvos!"}), 200

# ================= AS DEMAIS ROTAS =================

@app.route('/api/salvar-regua', methods=['POST'])
def salvar_regua():
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    dados = request.get_json()
    novo_cp_mega = dados.get('cp_mega')
    novo_cp_tita = dados.get('cp_tita')

    try:
        config_mega = ConfigAtividade.query.filter_by(nome_xml='REGUA_MEGA').first()
        if not config_mega:
            db.session.add(ConfigAtividade(nome_xml='REGUA_MEGA', pontos_padrao=int(novo_cp_mega), tipo_evento='sistema', is_ativa=False))
        else:
            config_mega.pontos_padrao = int(novo_cp_mega)

        config_tita = ConfigAtividade.query.filter_by(nome_xml='REGUA_TITA').first()
        if not config_tita:
            db.session.add(ConfigAtividade(nome_xml='REGUA_TITA', pontos_padrao=int(novo_cp_tita), tipo_evento='sistema', is_ativa=False))
        else:
            config_tita.pontos_padrao = int(novo_cp_tita)

        db.session.commit()
        return jsonify({"mensagem": "Réguas atualizadas globalmente!"}), 200
    except Exception as e:
        db.session.rollback()
        return erro_interno(e)

@app.route('/api/importar', methods=['POST'])
def importar_xml():
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    
    if 'xml_file' not in request.files:
        return jsonify({"erro": "Arquivo não enviado."}), 400

    arquivo = request.files['xml_file']
    guilda_alvo = request.form.get('guilda_alvo', 'vortex')

    caminho = caminho_upload_seguro(arquivo, 'importacao')
    arquivo.save(caminho)

    try:
        todas_atividades_db = [c.nome_xml for c in ConfigAtividade.query.filter(ConfigAtividade.nome_xml.notin_(['REGUA_MEGA', 'REGUA_TITA', 'SEMANA_ATIVA'])).order_by(ConfigAtividade.id.asc()).all()]
        configs = ConfigAtividade.query.filter(ConfigAtividade.is_ativa==True, ConfigAtividade.nome_xml.notin_(['REGUA_MEGA', 'REGUA_TITA', 'SEMANA_ATIVA'])).all()
        mapa_configs = {c.nome_xml: c.pontos_padrao for c in configs}

        dados_extraidos, hash_arquivo = analisar_xml_guilda(caminho, mapa_configs)

        config_semana = ConfigAtividade.query.filter_by(nome_xml='SEMANA_ATIVA').first()
        semana_ativa_str = f"Semana {config_semana.pontos_padrao}" if config_semana else "Semana 1"

        if ImportacaoXML.query.filter_by(semana=semana_ativa_str, hash_arquivo=hash_arquivo).first():
            os.remove(caminho)
            return jsonify({"erro": "Este arquivo exato já foi importado nesta semana!"}), 409

        if guilda_alvo == 'vortex':
            jogadores_validos = {j.nome.lower().strip(): True for j in Jogador.query.all()}
        else:
            jogadores_validos = {a.nome_alt.lower().strip(): True for a in PersonagemSecundario.query.all()}

        preview_dados = []

        for d in dados_extraidos:
            nome_limpo = d['nome'].strip()
            encontrado = nome_limpo.lower() in jogadores_validos
            
            preview_dados.append({
                "nome_xml": nome_limpo,
                "encontrado_no_bd": encontrado,
                "detalhes": d['atividades']
            })

        os.remove(caminho)
        return jsonify({
            "mensagem": "Pré-visualização gerada",
            "hash": hash_arquivo,
            "preview": preview_dados,
            "atividades_encontradas": todas_atividades_db 
        }), 200

    except Exception as e:
        if os.path.exists(caminho):
            os.remove(caminho)
        return erro_interno(e)

@app.route('/api/confirmar', methods=['POST'])
def confirmar_importacao():
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    
    dados = request.get_json()
    hash_arquivo = dados.get('hash')
    jogadores_data = dados.get('jogadores', [])
    cadastrar_novos = dados.get('cadastrar_novos', True)
    guilda_alvo = dados.get('guilda_alvo', 'vortex')
    eventos_selecionados = dados.get('eventos_selecionados', []) 
    
    config_semana = ConfigAtividade.query.filter_by(nome_xml='SEMANA_ATIVA').first()
    semana_fixa = f"Semana {config_semana.pontos_padrao}" if config_semana else "Semana 1"

    if ImportacaoXML.query.filter_by(semana=semana_fixa, hash_arquivo=hash_arquivo).first():
        return jsonify({"erro": "Esta importação já foi confirmada."}), 409

    try:
        label_import = "Upload Diário (Vortex)" if guilda_alvo == 'vortex' else "Upload Semanal (BlackSkull)"
        nova_importacao = ImportacaoXML(semana=semana_fixa, hash_arquivo=hash_arquivo, admin_responsavel="admin", nome_personalizado=label_import, tipo_arquivo="xml")
        db.session.add(nova_importacao)
        db.session.flush() 

        if guilda_alvo == 'vortex':
            nomes_importados = []
            for j_data in jogadores_data:
                nome_xml = j_data['nome_xml'].strip()
                if not nome_xml: continue
                nomes_importados.append(nome_xml.lower())
                
                jogador = Jogador.query.filter(func.lower(Jogador.nome) == nome_xml.lower()).first()
                if not jogador:
                    if cadastrar_novos:
                        jogador = Jogador(nome=nome_xml, status='Ativo')
                        db.session.add(jogador)
                        db.session.flush() 
                    else:
                        continue 
                else:
                    jogador.status = 'Ativo'

                for atv in j_data['detalhes']:
                    nome_atividade = atv['atividade']
                    if nome_atividade not in eventos_selecionados:
                        continue

                    novo_valor_xml = int(atv['pontos'])
                    
                    if novo_valor_xml > 0:
                        novo_ponto = Pontuacao(
                            jogador_id=jogador.id,
                            semana=semana_fixa,
                            atividade=nome_atividade,
                            pontos=novo_valor_xml,
                            importacao_id=nova_importacao.id
                        )
                        db.session.add(novo_ponto)
            
            if len(nomes_importados) > 0:
                todos_jogadores = Jogador.query.all()
                for j in todos_jogadores:
                    if j.nome.lower().strip() not in nomes_importados:
                        j.status = 'Inativo'
                    
        else:
            alts_map = {a.nome_alt.lower().strip(): a.jogador_id for a in PersonagemSecundario.query.all()}
            eventos_permitidos_bs = ['Raid de Guilda', 'Expedição da Guilda']
            for j_data in jogadores_data:
                nome_xml = j_data['nome_xml'].lower().strip()
                if nome_xml in alts_map:
                    jogador_id = alts_map[nome_xml]
                    
                    total_xml_bs = sum(
                        int(a['pontos']) for a in j_data['detalhes'] 
                        if a['atividade'] in eventos_permitidos_bs and a['atividade'] in eventos_selecionados
                    )

                    if total_xml_bs > 0:
                        novo_ponto = Pontuacao(
                            jogador_id=jogador_id,
                            semana=semana_fixa,
                            atividade="BlackSkull",
                            pontos=total_xml_bs,
                            importacao_id=nova_importacao.id
                        )
                        db.session.add(novo_ponto)

        db.session.commit()
        return jsonify({"mensagem": "Importação concluída via soma direta!"}), 200

    except Exception as e:
        db.session.rollback() 
        return erro_interno(e)

@app.route('/api/importar-excel', methods=['POST'])
def importar_excel():
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    if 'excel_file' not in request.files: return jsonify({"erro": "Arquivo não enviado."}), 400

    arquivo = request.files['excel_file']
    caminho = caminho_upload_seguro(arquivo, 'atributos')
    arquivo.save(caminho)

    try: import openpyxl
    except ImportError: return jsonify({"erro": "A biblioteca 'openpyxl' não está instalada."}), 500

    try:
        wb = openpyxl.load_workbook(caminho)
        sheet = wb.active
        headers = [str(cell.value).lower().strip() if cell.value else "" for cell in sheet[1]]
        
        idx_nome = next((i for i, h in enumerate(headers) if 'nome' in h or 'personagem' in h or 'jogador' in h), None)
        idx_level = next((i for i, h in enumerate(headers) if 'level' in h or 'nivel' in h or 'nível' in h or 'lvl' in h), None)
        idx_poder = next((i for i, h in enumerate(headers) if 'poder' in h or 'combate' in h or 'cp' in h), None)
        
        if idx_nome is None: raise ValueError("Coluna de 'Nome' não encontrada.")
            
        jogadores_atualizados = 0
        for row in sheet.iter_rows(min_row=2, values_only=True):
            nome_celula = row[idx_nome]
            if not nome_celula: continue
            
            nome_str = str(nome_celula).strip()
            if not nome_str: continue
            
            jogador = Jogador.query.filter(func.lower(Jogador.nome) == nome_str.lower()).first()
            if not jogador:
                jogador = Jogador(nome=nome_str, status='Ativo')
                db.session.add(jogador)
                db.session.flush()
            else:
                jogador.status = 'Ativo' 

            if idx_level is not None and row[idx_level] is not None:
                jogador.level = int(row[idx_level])
            if idx_poder is not None and row[idx_poder] is not None:
                poder_str = str(row[idx_poder]).replace('.', '').replace(',', '').strip()
                jogador.poder_combate = int(poder_str)
            jogadores_atualizados += 1

        hash_arquivo = "EXCEL_" + str(datetime.utcnow().timestamp())
        nova_importacao = ImportacaoXML(semana="Acumulativo", hash_arquivo=hash_arquivo, admin_responsavel="admin", nome_personalizado="Atualização de Atributos", tipo_arquivo="excel")
        db.session.add(nova_importacao)
        db.session.commit()
        os.remove(caminho)
        return jsonify({"mensagem": f"{jogadores_atualizados} jogadores atualizados/cadastrados!"}), 200
        
    except Exception as e:
        if os.path.exists(caminho): os.remove(caminho)
        db.session.rollback()
        return erro_interno(e)

@app.route('/api/editar-importacao', methods=['POST'])
def editar_importacao():
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    dados = request.get_json()
    importacoes_data = dados.get('importacoes', [])
    try:
        for item in importacoes_data:
            imp = db.session.get(ImportacaoXML, item['id'])
            if imp: imp.nome_personalizado = item['nome']
        db.session.commit()
        return jsonify({"mensagem": "Nomes de upload atualizados com sucesso!"}), 200
    except Exception as e:
        db.session.rollback()
        return erro_interno(e)

@app.route('/api/deletar-importacao/<int:id>', methods=['DELETE'])
def deletar_importacao(id):
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    try:
        imp = db.session.get(ImportacaoXML, id)
        if imp:
            Pontuacao.query.filter_by(importacao_id=imp.id).delete()
            db.session.delete(imp)
            db.session.commit()
            return jsonify({"mensagem": "Rollback concluído! Importação e pontos desfeitos."}), 200
        return jsonify({"erro": "Registro não encontrado."}), 404
    except Exception as e:
        db.session.rollback()
        return erro_interno(e)

@app.route('/api/editar-jogadores', methods=['POST'])
def editar_jogadores():
    if not login_required(): return jsonify({"erro": "Acesso negado"}), 401
    
    dados = request.get_json()
    jogadores_data = dados.get('jogadores', [])
    user_role = session.get('role')
    
    config_semana = ConfigAtividade.query.filter_by(nome_xml='SEMANA_ATIVA').first()
    semana_ativa_str = f"Semana {config_semana.pontos_padrao}" if config_semana else "Semana 1"

    try:
        for item in jogadores_data:
            jogador = db.session.get(Jogador, item['id'])
            if jogador:
                if 'nome' in item and item['nome'] and str(item['nome']).strip() != '':
                    jogador.nome = str(item['nome']).strip()

                if 'level' in item and item['level'] not in [None, '']:
                    jogador.level = int(item['level'])
                if 'poder_combate' in item and item['poder_combate'] not in [None, '']:
                    jogador.poder_combate = int(item['poder_combate'])
                
                if 'classe' in item:
                    jogador.classe = item['classe']
                for s_key in ['skill_4', 'skill_5', 'skill_6', 'skill_7', 'constante_3', 'constante_4', 'trindade', 'mestre_tecnica']:
                    if s_key in item and item[s_key] is not None:
                        setattr(jogador, s_key, bool(item[s_key]))
                
                if user_role == 'admin':
                    if 'alts' in item and item['alts'] is not None:
                        alts_string = item.get('alts', '')
                        PersonagemSecundario.query.filter_by(jogador_id=jogador.id).delete()
                        if alts_string:
                            novos_alts = [n.strip() for n in alts_string.split(',') if n.strip()]
                            for n_alt in novos_alts:
                                PersonagemSecundario.query.filter_by(nome_alt=n_alt).delete()
                                db.session.add(PersonagemSecundario(jogador_id=jogador.id, nome_alt=n_alt))

                    if 'eventos' in item:
                        for atv_nome, novo_valor in item['eventos'].items():
                            novo_valor = int(novo_valor)
                            pts_atuais = db.session.query(func.sum(Pontuacao.pontos)).filter_by(jogador_id=jogador.id, atividade=atv_nome).scalar() or 0
                            
                            diferenca = novo_valor - pts_atuais
                            if diferenca != 0:
                                ajuste = Pontuacao(
                                    jogador_id=jogador.id,
                                    semana=semana_ativa_str,
                                    atividade=atv_nome,
                                    pontos=diferenca,
                                    motivo_ajuste="Edição direta do evento na tabela"
                                )
                                db.session.add(ajuste)

                    if 'pontos' in item and item['pontos'] is not None:
                        novo_total_desejado = int(item['pontos'])
                        pts = db.session.query(func.sum(Pontuacao.pontos)).filter_by(jogador_id=jogador.id).scalar() or 0
                        pens = db.session.query(func.sum(SorteioHistorico.penalidade)).filter_by(jogador_id=jogador.id).scalar() or 0
                        pontos_atuais = pts - pens
                        
                        diferenca_total = novo_total_desejado - pontos_atuais
                        if diferenca_total != 0:
                            ajuste = Pontuacao(
                                jogador_id=jogador.id,
                                semana="Ajuste Geral", 
                                atividade="Ajuste Manual",
                                pontos=diferenca_total,
                                motivo_ajuste="Ajuste direto do total na tabela"
                            )
                            db.session.add(ajuste)
        
        db.session.commit()
        return jsonify({"mensagem": "Modificações salvas com sucesso!"}), 200
    except Exception as e:
        db.session.rollback()
        return erro_interno(e)

# ================= GERENCIAMENTO DE MEMBROS (ADMIN) =================

@app.route('/api/criar-jogador', methods=['POST'])
def criar_jogador():
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    dados = request.get_json()
    nome = str(dados.get('nome', '')).strip()[:100]

    if not nome:
        return jsonify({"erro": "Informe o nome do membro."}), 400

    if Jogador.query.filter(func.lower(Jogador.nome) == nome.lower()).first():
        return jsonify({"erro": "Já existe um membro cadastrado com esse nome."}), 409

    try:
        jogador = Jogador(
            nome=nome,
            level=int(dados.get('level') or 1),
            poder_combate=int(dados.get('poder_combate') or 0),
            status='Ativo'
        )
        db.session.add(jogador)
        db.session.commit()
        return jsonify({"mensagem": f"Membro '{nome}' cadastrado com sucesso!"}), 200
    except Exception as e:
        db.session.rollback()
        return erro_interno(e)

@app.route('/api/deletar-jogador/<int:id>', methods=['DELETE'])
def deletar_jogador(id):
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401

    jogador = db.session.get(Jogador, id)
    if not jogador:
        return jsonify({"erro": "Membro não encontrado."}), 404

    try:
        # Remove o que referencia o jogador e não sai por cascade
        # (Pontuacao e personagens secundários saem automaticamente).
        ApostaSorteio.query.filter_by(jogador_id=jogador.id).delete()
        SorteioHistorico.query.filter_by(jogador_id=jogador.id).delete()
        SorteioMemeHistorico.query.filter_by(jogador_id=jogador.id).delete()
        db.session.delete(jogador)
        db.session.commit()
        return jsonify({"mensagem": "Membro removido junto com todo o seu histórico."}), 200
    except Exception as e:
        db.session.rollback()
        return erro_interno(e)

@app.route('/api/toggle-status-jogador/<int:id>', methods=['POST'])
def toggle_status_jogador(id):
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401

    jogador = db.session.get(Jogador, id)
    if not jogador:
        return jsonify({"erro": "Membro não encontrado."}), 404

    try:
        if jogador.status == 'Ativo' or not jogador.status:
            jogador.status = 'Inativo'
        else:
            jogador.status = 'Ativo'
            
        db.session.commit()
        return jsonify({
            "mensagem": f"Status de {jogador.nome} alterado para {jogador.status}.",
            "novo_status": jogador.status
        }), 200
    except Exception as e:
        db.session.rollback()
        return erro_interno(e)

@app.route('/api/abonar-falta', methods=['POST'])
def abonar_falta():
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    
    dados = request.get_json()
    jogador_id = dados.get('jogador_id')
    pontos = int(dados.get('pontos', 0))
    motivo = dados.get('motivo', 'Abono de Missão (Justificativa)')

    if pontos <= 0:
        return jsonify({"erro": "A quantidade de pontos para abono deve ser maior que zero."}), 400

    jogador = db.session.get(Jogador, jogador_id)
    if not jogador:
        return jsonify({"erro": "Jogador não encontrado."}), 404

    try:
        config_semana = ConfigAtividade.query.filter_by(nome_xml='SEMANA_ATIVA').first()
        semana_ativa_str = f"Semana {config_semana.pontos_padrao}" if config_semana else "Semana 1"

        # Injeta os pontos na semana atual com a tag de Abono
        novo_ponto = Pontuacao(
            jogador_id=jogador.id,
            semana=semana_ativa_str,
            atividade="Abono de Falta",
            pontos=pontos,
            motivo_ajuste=motivo
        )
        db.session.add(novo_ponto)
        db.session.commit()

        return jsonify({"mensagem": f"Abono de {pontos} pontos concedido a {jogador.nome}!"}), 200
    except Exception as e:
        db.session.rollback()
        return erro_interno(e)

@app.route('/api/criar-evento', methods=['POST'])
def criar_evento():
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    dados = request.get_json()
    nome = dados.get('nome')
    tipo = dados.get('tipo')
    pontos = dados.get('pontos')

    try:
        novo_evento = ConfigAtividade(nome_xml=nome, pontos_padrao=int(pontos), tipo_evento=tipo)
        db.session.add(novo_evento)
        db.session.commit()
        return jsonify({"mensagem": "Novo evento criado!"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": "Erro ao criar."}), 500

@app.route('/api/salvar-configuracoes', methods=['POST'])
def salvar_configuracoes():
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    dados = request.get_json()
    configs_data = dados.get('configs', [])
    try:
        for item in configs_data:
            conf = db.session.get(ConfigAtividade, item['id'])
            if conf:
                novo_valor = int(item['pontos'])
                conf.pontos_padrao = novo_valor
                Pontuacao.query.filter_by(atividade=conf.nome_xml).update({'pontos': novo_valor})
        db.session.commit()
        return jsonify({"mensagem": "Matriz atualizada!"}), 200
    except Exception as e:
        db.session.rollback()
        return erro_interno(e)

@app.route('/api/realizar-sorteio-meme', methods=['POST'])
def realizar_sorteio_meme():
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    dados = request.get_json()
    jogadores_ids = dados.get('jogadores_ids', [])
    item_sorteado = dados.get('item', 'Item Misterioso')
    
    if not jogadores_ids: return jsonify({"erro": "Nenhum jogador selecionado."}), 400
    try:
        vencedor_id = random.choice(jogadores_ids)
        vencedor = db.session.get(Jogador, vencedor_id)
        
        novo_sorteio_meme = SorteioMemeHistorico(jogador_id=vencedor.id, item_sorteado=item_sorteado)
        db.session.add(novo_sorteio_meme)
        db.session.commit()
        
        return jsonify({"vencedor_nome": vencedor.nome, "vencedor_id": vencedor.id, "item": item_sorteado}), 200
    except Exception as e:
        db.session.rollback()
        return erro_interno(e)

@app.route('/api/editar-historico-meme', methods=['POST'])
def editar_historico_meme():
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    dados = request.get_json()
    historico_data = dados.get('historico', [])
    try:
        for item in historico_data:
            reg = db.session.get(SorteioMemeHistorico, item['id'])
            if reg:
                reg.observacao = item['observacao']
        db.session.commit()
        return jsonify({"mensagem": "Registros gravados!"}), 200
    except Exception as e:
        db.session.rollback()
        return erro_interno(e)

@app.route('/api/deletar-historico-meme/<int:id>', methods=['DELETE'])
def deletar_historico_meme(id):
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    try:
        reg = db.session.get(SorteioMemeHistorico, id)
        if reg:
            db.session.delete(reg)
            db.session.commit()
            return jsonify({"mensagem": "Registro purgado!"}), 200
        return jsonify({"erro": "Não encontrado."}), 404
    except Exception as e:
        db.session.rollback()
        return erro_interno(e)

@app.route('/api/editar-historico', methods=['POST'])
def editar_historico():
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    dados = request.get_json()
    historico_data = dados.get('historico', [])
    try:
        for item in historico_data:
            reg = db.session.get(SorteioHistorico, item['id'])
            if reg:
                reg.observacao = item['observacao']
                reg.penalidade = int(item['penalidade'])
        db.session.commit()
        return jsonify({"mensagem": "Registros gravados!"}), 200
    except Exception as e:
        db.session.rollback()
        return erro_interno(e)

@app.route('/api/deletar-historico/<int:id>', methods=['DELETE'])
def deletar_historico(id):
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    try:
        reg = db.session.get(SorteioHistorico, id)
        if reg:
            db.session.delete(reg)
            db.session.commit()
            return jsonify({"mensagem": "Registro purgado!"}), 200
        return jsonify({"erro": "Não encontrado."}), 404
    except Exception as e:
        db.session.rollback()
        return erro_interno(e)

def inicializar_banco():
    """Cria as tabelas, aplica migrações leves via ALTER TABLE e semeia dados
    padrão. Extraída para uma função (em vez de código solto em
    `with app.app_context():`) para poder ser chamada de novo pelos testes
    automatizados, que precisam de um banco limpo e semeado a cada teste."""
    db.create_all()

    try:
        db.session.execute(text("ALTER TABLE evento_item ADD COLUMN restricao VARCHAR(20) DEFAULT 'Todos'"))
        db.session.commit()
    except Exception:
        db.session.rollback()

    try:
        if not ConfigAtividade.query.filter_by(nome_xml='SEMANA_ATIVA').first():
            db.session.add(ConfigAtividade(nome_xml='SEMANA_ATIVA', pontos_padrao=1, tipo_evento='sistema', is_ativa=False))
            db.session.commit()
    except Exception:
        db.session.rollback()

    try:
        db.session.execute(text("ALTER TABLE pontuacoes ADD COLUMN semana VARCHAR(50) DEFAULT 'Acumulativo'"))
        db.session.commit()
    except Exception:
        db.session.rollback()

    try:
        db.session.execute(text("ALTER TABLE importacoes ADD COLUMN semana VARCHAR(50) DEFAULT 'Acumulativo'"))
        db.session.commit()
    except Exception:
        db.session.rollback()

    try:
        db.session.execute(text("ALTER TABLE evento_sorteio ADD COLUMN prazo_encerramento VARCHAR(50)"))
        db.session.commit()
    except Exception:
        db.session.rollback()

    try:
        db.session.execute(text("ALTER TABLE evento_item ADD COLUMN em_andamento BOOLEAN DEFAULT FALSE"))
        db.session.commit()
    except Exception:
        db.session.rollback()

    try:
        db.session.execute(text("ALTER TABLE evento_item ADD COLUMN dados_roleta_json TEXT"))
        db.session.commit()
    except Exception:
        db.session.rollback()

    colunas_jogadores = {
        'status': "VARCHAR(20) DEFAULT 'Ativo'",
        'classe': "VARCHAR(50) DEFAULT ''",
        'skill_4': 'BOOLEAN DEFAULT FALSE',
        'skill_5': 'BOOLEAN DEFAULT FALSE',
        'skill_6': 'BOOLEAN DEFAULT FALSE',
        'skill_7': 'BOOLEAN DEFAULT FALSE',
        'constante_3': 'BOOLEAN DEFAULT FALSE',
        'constante_4': 'BOOLEAN DEFAULT FALSE',
        'trindade': 'BOOLEAN DEFAULT FALSE',
        'mestre_tecnica': 'BOOLEAN DEFAULT FALSE'
    }

    for col, tipo in colunas_jogadores.items():
        try:
            db.session.execute(text(f'SELECT {col} FROM jogadores LIMIT 1'))
        except Exception:
            db.session.rollback()
            try:
                db.session.execute(text(f'ALTER TABLE jogadores ADD COLUMN {col} {tipo}'))
                db.session.commit()
            except Exception:
                db.session.rollback()

    try:
        db.session.execute(text("UPDATE jogadores SET status = 'Ativo' WHERE status IS NULL OR status = ''"))
        db.session.commit()
    except Exception:
        db.session.rollback()

    try:
        db.session.execute(text('SELECT tipo_evento FROM config_atividades LIMIT 1'))
    except Exception:
        db.session.rollback()
        try:
            db.session.execute(text("ALTER TABLE config_atividades ADD COLUMN tipo_evento VARCHAR(20) DEFAULT 'diario'"))
            db.session.commit()
            eventos_semanais = "'Raid de Guilda', 'Expedição da Guilda', 'Confronto pelo Paraíso', 'Campo de Batalha de Aço', 'Escaramuça', 'Guerra de Mineração', 'Fortaleza Albern'"
            db.session.execute(text(f"UPDATE config_atividades SET tipo_evento = 'semanal' WHERE nome_xml IN ({eventos_semanais})"))
            db.session.commit()
        except Exception:
            db.session.rollback()

    try:
        db.session.execute(text('SELECT nome_personalizado FROM importacoes LIMIT 1'))
    except Exception:
        db.session.rollback()
        try:
            db.session.execute(text("ALTER TABLE importacoes ADD COLUMN nome_personalizado VARCHAR(100) DEFAULT ''"))
            db.session.commit()
        except Exception:
            db.session.rollback()
        
    try:
        db.session.execute(text('SELECT tipo_arquivo FROM importacoes LIMIT 1'))
    except Exception:
        db.session.rollback()
        try:
            db.session.execute(text("ALTER TABLE importacoes ADD COLUMN tipo_arquivo VARCHAR(20) DEFAULT 'xml'"))
            db.session.commit()
        except Exception:
            db.session.rollback()

    if not ConfigAtividade.query.filter_by(nome_xml='REGUA_MEGA').first():
        db.session.add(ConfigAtividade(nome_xml='REGUA_MEGA', pontos_padrao=100000, tipo_evento='sistema', is_ativa=False))
        db.session.commit()
        
    if not ConfigAtividade.query.filter_by(nome_xml='REGUA_TITA').first():
        db.session.add(ConfigAtividade(nome_xml='REGUA_TITA', pontos_padrao=50000, tipo_evento='sistema', is_ativa=False))
        db.session.commit()

    if not ConfigAtividade.query.filter(ConfigAtividade.nome_xml.notin_(['REGUA_MEGA', 'REGUA_TITA', 'SEMANA_ATIVA'])).first():
        atividades_iniciais = [
            ('Verificado', 'diario'), ('Doar', 'diario'), ('Atividade da Guilda', 'diario'), 
            ('Raid de Guilda', 'semanal'), ('Expedição da Guilda', 'semanal'), 
            ('Confronto pelo Paraíso', 'semanal'), ('Campo de Batalha de Aço', 'semanal'), 
            ('Escaramuça', 'semanal'), ('Guerra de Mineração', 'semanal'), ('Fortaleza Albern', 'semanal')
        ]
        for atv, tipo in atividades_iniciais:
            db.session.add(ConfigAtividade(nome_xml=atv, pontos_padrao=1, tipo_evento=tipo))
        db.session.commit()

    # Índices para as colunas de Pontuacao mais usadas em filtros/GROUP BY.
    # CREATE INDEX IF NOT EXISTS é suportado tanto pelo SQLite quanto pelo PostgreSQL,
    # e é necessário aqui porque db.create_all() não retroaplica índices a tabelas já existentes.
    try:
        db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_pontuacoes_jogador_id ON pontuacoes (jogador_id)"))
        db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_pontuacoes_semana ON pontuacoes (semana)"))
        db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_pontuacoes_atividade ON pontuacoes (atividade)"))
        db.session.commit()
    except Exception:
        db.session.rollback()


with app.app_context():
    inicializar_banco()

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(debug=debug_mode, port=5000)
