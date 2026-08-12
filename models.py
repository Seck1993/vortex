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
    jogador_id = db.Column(db.Integer, db.ForeignKey('jogadores.id'), nullable=False)
    semana = db.Column(db.String(50), nullable=False, default="Acumulativo")
    atividade = db.Column(db.String(100), nullable=False)
    pontos = db.Column(db.Integer, nullable=False)
    
    importacao_id = db.Column(db.Integer, db.ForeignKey('importacoes.id'), nullable=True)
    motivo_ajuste = db.Column(db.String(255), nullable=True)
    
    data_registro = db.Column(db.DateTime, default=datetime.utcnow)