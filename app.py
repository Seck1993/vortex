import os
import random
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
from sqlalchemy import func, text
from models import db, Jogador, ConfigAtividade, ImportacaoXML, Pontuacao, PersonagemSecundario
from xml_engine import analisar_xml_guilda

app = Flask(__name__)

# Configuração de Banco de Dados
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///vortex.db')
if app.config['SQLALCHEMY_DATABASE_URI'].startswith("postgres://"):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'tmp/' 
app.config['SECRET_KEY'] = 'chave_super_secreta_vortex' 

db.init_app(app)

# ================= MODELOS ORIGINAIS =================
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

# ================= NOVOS MODELOS DE EVENTO (BANNER) =================
class EventoSorteio(db.Model):
    __tablename__ = 'evento_sorteio'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), default="SORTEIO HOJE AS 20:00")
    ativo = db.Column(db.Boolean, default=True)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    itens = db.relationship('EventoItem', backref='evento', cascade="all, delete-orphan", lazy=True)

class EventoItem(db.Model):
    __tablename__ = 'evento_item'
    id = db.Column(db.Integer, primary_key=True)
    evento_id = db.Column(db.Integer, db.ForeignKey('evento_sorteio.id'))
    nome_item = db.Column(db.String(100), nullable=False)
    max_pontos = db.Column(db.Float, default=100.0)
    sorteado = db.Column(db.Boolean, default=False)
    vencedor_nome = db.Column(db.String(100), nullable=True)
    apostas = db.relationship('ApostaSorteio', backref='item', cascade="all, delete-orphan", lazy=True)

class ApostaSorteio(db.Model):
    __tablename__ = 'aposta_sorteio'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('evento_item.id'))
    jogador_id = db.Column(db.Integer, db.ForeignKey('jogadores.id'))
    pontos = db.Column(db.Float, default=0.0)
    jogador = db.relationship('Jogador')

# ================= ROTAS E LÓGICA =================
@app.route('/')
def index():
    configuracoes = ConfigAtividade.query.filter(ConfigAtividade.nome_xml != 'REGUA_MEGA').order_by(ConfigAtividade.id.asc()).all()
    config_mega = ConfigAtividade.query.filter_by(nome_xml='REGUA_MEGA').first()
    cp_mega = config_mega.pontos_padrao if config_mega else 100000

    pontos_brutos = db.session.query(Pontuacao.jogador_id, Pontuacao.atividade, func.sum(Pontuacao.pontos)).group_by(Pontuacao.jogador_id, Pontuacao.atividade).all()

    mapa_pontos = {}
    for pid, atv, pts in pontos_brutos:
        if pid not in mapa_pontos:
            mapa_pontos[pid] = {'total_bruto': 0, 'total_final': 0, 'atividades': {}, 'blackskull': 0, 'ajustes': 0, 'penalidades': 0}
        
        if atv == 'BlackSkull':
            mapa_pontos[pid]['blackskull'] += pts
            mapa_pontos[pid]['total_bruto'] += pts
            mapa_pontos[pid]['total_final'] += pts
        elif atv in ['Edição via Painel', 'Ajuste Manual']:
            mapa_pontos[pid]['ajustes'] += pts
            mapa_pontos[pid]['total_bruto'] += pts
            mapa_pontos[pid]['total_final'] += pts
        else:
            mapa_pontos[pid]['atividades'][atv] = mapa_pontos[pid]['atividades'].get(atv, 0) + pts
            mapa_pontos[pid]['total_bruto'] += pts
            mapa_pontos[pid]['total_final'] += pts

    penalidades = db.session.query(SorteioHistorico.jogador_id, func.sum(SorteioHistorico.penalidade)).group_by(SorteioHistorico.jogador_id).all()
    for pid, pen in penalidades:
        if pid not in mapa_pontos:
            mapa_pontos[pid] = {'total_bruto': 0, 'total_final': 0, 'atividades': {}, 'blackskull': 0, 'ajustes': 0, 'penalidades': 0}
        mapa_pontos[pid]['penalidades'] += pen
        mapa_pontos[pid]['total_final'] -= pen

    jogadores = Jogador.query.filter(db.or_(Jogador.status == 'Ativo', Jogador.status == None, Jogador.status == '')).all()
    
    pontuacao_seck = 0
    for j in jogadores:
        if j.nome.upper().strip() == 'SECK':
            pontuacao_seck = mapa_pontos.get(j.id, {}).get('total_bruto', 0)
            break

    ranking = []
    soma_total_pontos = 0
    
    for j in jogadores:
        p_data = mapa_pontos.get(j.id, {'total_bruto': 0, 'total_final': 0, 'atividades': {}, 'blackskull': 0, 'ajustes': 0, 'penalidades': 0})
        total_bruto = p_data['total_bruto']
        total_final = p_data['total_final']
        
        if pontuacao_seck > 0:
            if total_bruto >= pontuacao_seck:
                participacao, pontos_base, pontos_diamante = 100.0, pontuacao_seck, total_bruto - pontuacao_seck
            else:
                participacao, pontos_base, pontos_diamante = round((total_bruto / pontuacao_seck) * 100, 2), total_bruto, 0
        else:
            participacao, pontos_base, pontos_diamante = 0, total_bruto, 0

        ranking.append({
            'jogador': j, 'alts_str': ', '.join([a.nome_alt for a in j.alts]), 'pontos': total_final,
            'pontos_base': pontos_base, 'pontos_diamante': pontos_diamante, 'participacao': participacao,
            'penalidades': p_data['penalidades']
        })
        soma_total_pontos += total_final

    ranking.sort(key=lambda x: (x['pontos'], x['jogador'].poder_combate, x['jogador'].level), reverse=True)

    historico_sorteios = SorteioHistorico.query.order_by(SorteioHistorico.data_sorteio.desc()).all()
    historico_meme = SorteioMemeHistorico.query.order_by(SorteioMemeHistorico.data_sorteio.desc()).all()
    importacoes = ImportacaoXML.query.order_by(ImportacaoXML.data_importacao.desc()).all()
    
    user_role = session.get('role', 'guest')

    # Dados do Evento Ativo
    evento_ativo = EventoSorteio.query.filter_by(ativo=True).order_by(EventoSorteio.id.desc()).first()
    
    # Preparar estrutura do evento para o frontend
    evento_data = None
    if evento_ativo:
        itens_data = []
        for item in evento_ativo.itens:
            apostas = [{'jogador_nome': a.jogador.nome, 'pontos': a.pontos, 'id': a.id} for a in item.apostas]
            itens_data.append({
                'id': item.id,
                'nome_item': item.nome_item,
                'max_pontos': item.max_pontos,
                'sorteado': item.sorteado,
                'vencedor_nome': item.vencedor_nome,
                'apostas': apostas,
                'total_apostado': sum(a['pontos'] for a in apostas)
            })
        evento_data = {
            'id': evento_ativo.id,
            'titulo': evento_ativo.titulo,
            'itens': itens_data
        }

    return render_template(
        'dashboard.html', ranking=ranking, historico_sorteios=historico_sorteios, historico_meme=historico_meme, 
        configuracoes=configuracoes, importacoes=importacoes, user_role=user_role, cp_mega=cp_mega, 
        evento=evento_data
    )

@app.route('/api/login', methods=['POST'])
def login():
    senha = request.get_json().get('senha')
    if senha == 'vortex2026':  
        session['logged_in'], session['role'] = True, 'admin'
        return jsonify({"mensagem": "Autenticado Administrador"}), 200
    elif senha == 'membro2026':
        session['logged_in'], session['role'] = True, 'membro'
        return jsonify({"mensagem": "Autenticado Membro"}), 200
    return jsonify({"erro": "Senha incorreta"}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('logged_in', None)
    session.pop('role', None)
    return jsonify({"mensagem": "Logout"}), 200

def admin_required(): return session.get('logged_in') and session.get('role') == 'admin'
def login_required(): return session.get('logged_in')

# --- ROTAS DO NOVO SISTEMA DE EVENTOS (BANNER E APOSTAS) ---

@app.route('/api/criar-evento', methods=['POST'])
def api_criar_evento():
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    dados = request.get_json()
    
    # Desativa eventos anteriores
    EventoSorteio.query.filter_by(ativo=True).update({'ativo': False})
    
    novo_evento = EventoSorteio(titulo=dados.get('titulo', 'NOVO SORTEIO'))
    db.session.add(novo_evento)
    db.session.flush()

    for item in dados.get('itens', []):
        db.session.add(EventoItem(evento_id=novo_evento.id, nome_item=item['nome'], max_pontos=float(item['max_pontos'])))
    
    db.session.commit()
    return jsonify({"mensagem": "Evento de sorteio publicado!"}), 200

@app.route('/api/encerrar-evento', methods=['POST'])
def api_encerrar_evento():
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    EventoSorteio.query.filter_by(ativo=True).update({'ativo': False})
    db.session.commit()
    return jsonify({"mensagem": "Evento encerrado e banner removido."}), 200

@app.route('/api/apostar-item', methods=['POST'])
def api_apostar_item():
    if not login_required(): return jsonify({"erro": "Faça login para apostar"}), 401
    dados = request.get_json()
    item_id = dados.get('item_id')
    jogador_id = dados.get('jogador_id')
    pontos = float(dados.get('pontos', 0))

    if pontos <= 0: return jsonify({"erro": "Pontos inválidos"}), 400

    item = db.session.get(EventoItem, item_id)
    if not item or item.sorteado: return jsonify({"erro": "Item inválido ou já sorteado"}), 400

    # Verifica se já existe aposta do player neste item, se sim, atualiza, senão, cria
    aposta = ApostaSorteio.query.filter_by(item_id=item_id, jogador_id=jogador_id).first()
    if aposta:
        aposta.pontos = pontos
    else:
        db.session.add(ApostaSorteio(item_id=item_id, jogador_id=jogador_id, pontos=pontos))
    
    db.session.commit()
    return jsonify({"mensagem": "Aposta registrada com sucesso! Ponto só será descontado se você vencer."}), 200

@app.route('/api/remover-aposta/<int:id>', methods=['DELETE'])
def api_remover_aposta(id):
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    aposta = db.session.get(ApostaSorteio, id)
    if aposta:
        db.session.delete(aposta)
        db.session.commit()
    return jsonify({"mensagem": "Aposta removida."}), 200

@app.route('/api/realizar-sorteio-item', methods=['POST'])
def api_realizar_sorteio_item():
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    item_id = request.get_json().get('item_id')
    
    item = db.session.get(EventoItem, item_id)
    if not item or item.sorteado: return jsonify({"erro": "Item já sorteado."}), 400

    apostas = ApostaSorteio.query.filter_by(item_id=item_id).all()
    if not apostas: return jsonify({"erro": "Nenhum participante apostou neste item ainda."}), 400

    fatias = {}
    candidatos = []
    pesos = []
    soma_porcentagens = 0.0

    for ap in apostas:
        porcentagem = (ap.pontos / item.max_pontos) * 100.0
        fatias[ap.jogador.nome] = porcentagem
        soma_porcentagens += porcentagem
        candidatos.append({"id": ap.jogador.id, "nome": ap.jogador.nome, "pontos_apostados": ap.pontos, "is_staff": False})
        pesos.append(porcentagem)

    # O que sobrar vai pra Staff
    porcentagem_staff = 100.0 - soma_porcentagens
    if porcentagem_staff > 0:
        fatias['Staff (Administração)'] = porcentagem_staff
        candidatos.append({"id": None, "nome": 'Staff (Administração)', "pontos_apostados": 0, "is_staff": True})
        pesos.append(porcentagem_staff)

    # Sorteio Quântico
    vencedor = random.choices(candidatos, weights=pesos, k=1)[0]
    
    # Atualiza o Item
    item.sorteado = True
    item.vencedor_nome = vencedor['nome']
    
    # REGRA: Somente debita pontos se for um Jogador que venceu (Apenas quem ganha perde os pontos)
    if not vencedor['is_staff']:
        novo_sorteio = SorteioHistorico(
            jogador_id=vencedor['id'], 
            observacao=f"Venceu: {item.nome_item}",
            penalidade=int(vencedor['pontos_apostados']) # Deduz apenas os pontos apostados pelo vencedor
        )
        db.session.add(novo_sorteio)

    db.session.commit()

    return jsonify({
        "vencedor_nome": vencedor['nome'],
        "vencedor_id": vencedor['id'],
        "fatias": fatias
    }), 200

# ================= AS DEMAIS ROTAS CONTINUAM INTACTAS =================
# (Mantenha as rotas /api/importar, /api/editar-jogadores, /api/realizar-sorteio-meme, etc. exatamente como você já tinha nas versões anteriores)

with app.app_context():
    db.create_all()
    # Adicionando checagem de colunas para garantir que o SQLite ou Postgres se atualizem sozinhos
    colunas_jogadores = {
        'status': "VARCHAR(20) DEFAULT 'Ativo'", 'classe': "VARCHAR(50) DEFAULT ''",
        'skill_4': 'BOOLEAN DEFAULT FALSE', 'skill_5': 'BOOLEAN DEFAULT FALSE',
        'skill_6': 'BOOLEAN DEFAULT FALSE', 'skill_7': 'BOOLEAN DEFAULT FALSE',
        'constante_3': 'BOOLEAN DEFAULT FALSE', 'constante_4': 'BOOLEAN DEFAULT FALSE',
        'trindade': 'BOOLEAN DEFAULT FALSE', 'mestre_tecnica': 'BOOLEAN DEFAULT FALSE'
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

if __name__ == '__main__':
    app.run(debug=True, port=5000)
