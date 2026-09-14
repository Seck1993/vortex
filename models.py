from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Jogador(db.Model):
    __tablename__ = 'jogadores'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    level = db.Column(db.Integer, default=1, nullable=False)
    poder_combate = db.Column(db.Integer, default=0, nullable=False)
    status = db.Column(db.String(20), default='Ativo') 
    data_entrada = db.Column(db.DateTime, default=datetime.utcnow)
    
    classe = db.Column(db.String(50), nullable=True)
    skill_4 = db.Column(db.Boolean, default=False)
    skill_5 = db.Column(db.Boolean, default=False)
    skill_6 = db.Column(db.Boolean, default=False)
    skill_7 = db.Column(db.Boolean, default=False)
    constante_3 = db.Column(db.Boolean, default=False)
    constante_4 = db.Column(db.Boolean, default=False)
    trindade = db.Column(db.Boolean, default=False)
    mestre_tecnica = db.Column(db.Boolean, default=False)

    pontos = db.relationship('Pontuacao', backref='jogador', lazy=True, cascade="all, delete-orphan")

class PersonagemSecundario(db.Model):
    __tablename__ = 'personagens_secundarios'
    id = db.Column(db.Integer, primary_key=True)
    jogador_id = db.Column(db.Integer, db.ForeignKey('jogadores.id'), nullable=False)
    nome_alt = db.Column(db.String(100), unique=True, nullable=False)
    
    jogador = db.relationship('Jogador', backref=db.backref('alts', lazy=True, cascade="all, delete-orphan"))

class ConfigAtividade(db.Model):
    __tablename__ = 'config_atividades'
    id = db.Column(db.Integer, primary_key=True)
    nome_xml = db.Column(db.String(100), unique=True, nullable=False)
    pontos_padrao = db.Column(db.Integer, default=1, nullable=False)
    is_ativa = db.Column(db.Boolean, default=True)
    tipo_evento = db.Column(db.String(20), default='diario')

class ImportacaoXML(db.Model):
    __tablename__ = 'importacoes'
    id = db.Column(db.Integer, primary_key=True)
    semana = db.Column(db.String(50), nullable=False, default="Acumulativo")
    hash_arquivo = db.Column(db.String(128), nullable=False, unique=True)
    data_importacao = db.Column(db.DateTime, default=datetime.utcnow)
    admin_responsavel = db.Column(db.String(100), nullable=True)
    nome_personalizado = db.Column(db.String(100), default="") 
    tipo_arquivo = db.Column(db.String(20), default="xml") 

class Pontuacao(db.Model):
    __tablename__ = 'pontuacoes'
    id = db.Column(db.Integer, primary_key=True)
    jogador_id = db.Column(db.Integer, db.ForeignKey('jogadores.id'), nullable=False, index=True)
    semana = db.Column(db.String(50), nullable=False, default="Acumulativo", index=True)
    atividade = db.Column(db.String(100), nullable=False, index=True)
    pontos = db.Column(db.Integer, nullable=False)
    
    importacao_id = db.Column(db.Integer, db.ForeignKey('importacoes.id'), nullable=True)
    motivo_ajuste = db.Column(db.String(255), nullable=True)
    
    data_registro = db.Column(db.DateTime, default=datetime.utcnow)

class GrupoBoss(db.Model):
    __tablename__ = 'grupo_boss'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    tipo_respawn = db.Column(db.String(20), default="intervalo")
    intervalo_horas = db.Column(db.Integer, default=42)
    hora_diaria = db.Column(db.String(100), nullable=True)
    dias_semana = db.Column(db.String(50), nullable=True)
    horario_ancora = db.Column(db.DateTime, nullable=True)
    
    bosses = db.relationship('Boss', backref='grupo_rel', lazy=True)

class Boss(db.Model):
    __tablename__ = 'bosses'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    local = db.Column(db.String(100), default="")
    is_nosso = db.Column(db.Boolean, default=False)
    
    # Relação com a Linha de tempo unificada
    grupo_id = db.Column(db.Integer, db.ForeignKey('grupo_boss.id'), nullable=True)

    # Campos antigos mantidos apenas por segurança para migração
    grupo = db.Column(db.String(50), default="Sem Grupo")
    tipo_respawn = db.Column(db.String(20), default="intervalo")
    intervalo_horas = db.Column(db.Integer, default=42)
    hora_diaria = db.Column(db.String(100), nullable=True)
    dias_semana = db.Column(db.String(50), nullable=True)
    horario_ancora = db.Column(db.DateTime, nullable=True)
