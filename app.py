import os
import random
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
from sqlalchemy import func, text
from models import db, Jogador, ConfigAtividade, ImportacaoXML, Pontuacao, PersonagemSecundario
from xml_engine import analisar_xml_guilda

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///vortex.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'tmp/' 
app.config['SECRET_KEY'] = 'chave_super_secreta_vortex' 

db.init_app(app)

class SorteioHistorico(db.Model):
    __tablename__ = 'sorteios'
    id = db.Column(db.Integer, primary_key=True)
    jogador_id = db.Column(db.Integer, db.ForeignKey('jogadores.id'), nullable=False)
    data_sorteio = db.Column(db.DateTime, default=datetime.utcnow)
    observacao = db.Column(db.String(255), default="")
    penalidade = db.Column(db.Integer, default=0)
    
    jogador = db.relationship('Jogador', backref=db.backref('sorteios', lazy=True))

# --- NOVO MODELO: Sorteio Meme ---
class SorteioMemeHistorico(db.Model):
    __tablename__ = 'sorteios_meme'
    id = db.Column(db.Integer, primary_key=True)
    jogador_id = db.Column(db.Integer, db.ForeignKey('jogadores.id'), nullable=False)
    item_sorteado = db.Column(db.String(100), default="")
    data_sorteio = db.Column(db.DateTime, default=datetime.utcnow)
    observacao = db.Column(db.String(255), default="")
    
    jogador = db.relationship('Jogador', backref=db.backref('sorteios_meme', lazy=True))
# ---------------------------------

@app.route('/')
def index():
    pontos_brutos = db.session.query(
        Pontuacao.jogador_id, 
        Pontuacao.atividade, 
        func.sum(Pontuacao.pontos)
    ).group_by(Pontuacao.jogador_id, Pontuacao.atividade).all()

    mapa_pontos = {}
    for pid, atv, pts in pontos_brutos:
        if pid not in mapa_pontos:
            mapa_pontos[pid] = {'total': 0, 'atividades': {}, 'blackskull': 0, 'ajustes': 0}
        
        if atv == 'BlackSkull':
            mapa_pontos[pid]['blackskull'] += pts
            mapa_pontos[pid]['total'] += pts
        elif atv in ['Edição via Painel', 'Ajuste Manual']:
            mapa_pontos[pid]['ajustes'] += pts
            mapa_pontos[pid]['total'] += pts
        else:
            mapa_pontos[pid]['atividades'][atv] = mapa_pontos[pid]['atividades'].get(atv, 0) + pts
            mapa_pontos[pid]['total'] += pts

    penalidades = db.session.query(SorteioHistorico.jogador_id, func.sum(SorteioHistorico.penalidade)).group_by(SorteioHistorico.jogador_id).all()
    for pid, pen in penalidades:
        if pid not in mapa_pontos:
            mapa_pontos[pid] = {'total': 0, 'atividades': {}, 'blackskull': 0, 'ajustes': 0}
        mapa_pontos[pid]['ajustes'] -= pen
        mapa_pontos[pid]['total'] -= pen

    jogadores = Jogador.query.all()
    ranking = []
    for j in jogadores:
        p_data = mapa_pontos.get(j.id, {'total': 0, 'atividades': {}, 'blackskull': 0, 'ajustes': 0})
        alts_list = [a.nome_alt for a in j.alts]
        ranking.append({
            'jogador': j,
            'alts_str': ', '.join(alts_list),
            'pontos': p_data['total'],
            'atividades': p_data['atividades'],
            'blackskull': p_data['blackskull'],
            'ajustes': p_data['ajustes']
        })

    ranking.sort(key=lambda x: x['jogador'].nome.lower())
    ranking.sort(key=lambda x: (x['pontos'], x['jogador'].level, x['jogador'].poder_combate), reverse=True)

    historico_sorteios = SorteioHistorico.query.order_by(SorteioHistorico.data_sorteio.desc()).all()
    
    # Busca do novo histórico
    historico_meme = SorteioMemeHistorico.query.order_by(SorteioMemeHistorico.data_sorteio.desc()).all()
    
    configuracoes = ConfigAtividade.query.order_by(ConfigAtividade.id.asc()).all()
    importacoes = ImportacaoXML.query.order_by(ImportacaoXML.data_importacao.desc()).all()
    
    total_jogadores = len(jogadores)
    soma_total_pontos = db.session.query(func.sum(Pontuacao.pontos)).scalar() or 0

    return render_template(
        'dashboard.html', 
        ranking=ranking, 
        historico_sorteios=historico_sorteios,
        historico_meme=historico_meme, # Enviando para o template
        configuracoes=configuracoes,
        importacoes=importacoes,
        total_jogadores=total_jogadores,
        soma_total_pontos=soma_total_pontos
    )

@app.route('/api/login', methods=['POST'])
def login():
    dados = request.get_json()
    if dados.get('senha') == 'vortex2026':  
        session['logged_in'] = True
        return jsonify({"mensagem": "Autenticado com sucesso"}), 200
    return jsonify({"erro": "Senha incorreta"}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('logged_in', None)
    return jsonify({"mensagem": "Logout efetuado"}), 200

def admin_required():
    return session.get('logged_in')

# --- UPLOAD DE XML (PONTOS) ---
@app.route('/api/importar', methods=['POST'])
def importar_xml():
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    
    if 'xml_file' not in request.files:
        return jsonify({"erro": "Arquivo não enviado."}), 400

    arquivo = request.files['xml_file']
    guilda_alvo = request.form.get('guilda_alvo', 'vortex') 
    
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
        
    caminho = os.path.join(app.config['UPLOAD_FOLDER'], arquivo.filename)
    arquivo.save(caminho)

    try:
        configs = ConfigAtividade.query.filter_by(is_ativa=True).all()
        mapa_configs = {c.nome_xml: c.pontos_padrao for c in configs}

        dados_extraidos, hash_arquivo = analisar_xml_guilda(caminho, mapa_configs)

        if ImportacaoXML.query.filter_by(semana="Acumulativo", hash_arquivo=hash_arquivo).first():
            os.remove(caminho)
            return jsonify({"erro": "Este arquivo exato já foi importado!"}), 409

        if guilda_alvo == 'vortex':
            jogadores_validos = {j.nome.lower(): True for j in Jogador.query.all()}
        else:
            jogadores_validos = {a.nome_alt.lower(): True for a in PersonagemSecundario.query.all()}

        preview_dados = []
        eventos_permitidos_bs = ['Raid de Guilda', 'Expedição da Guilda']

        for d in dados_extraidos:
            nome_lower = d['nome'].lower()
            encontrado = nome_lower in jogadores_validos
            
            if guilda_alvo == 'blackskull':
                total_pts_jogador = sum(a['pontos'] for a in d['atividades'] if a['atividade'] in eventos_permitidos_bs)
            else:
                total_pts_jogador = sum(a['pontos'] for a in d['atividades'])
            
            preview_dados.append({
                "nome_xml": d['nome'],
                "encontrado_no_bd": encontrado,
                "pontos_totais": total_pts_jogador,
                "detalhes": d['atividades']
            })

        os.remove(caminho)
        return jsonify({
            "mensagem": "Pré-visualização gerada",
            "hash": hash_arquivo,
            "preview": preview_dados
        }), 200

    except Exception as e:
        if os.path.exists(caminho):
            os.remove(caminho)
        return jsonify({"erro": str(e)}), 500

@app.route('/api/confirmar', methods=['POST'])
def confirmar_importacao():
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    
    dados = request.get_json()
    hash_arquivo = dados.get('hash')
    jogadores_data = dados.get('jogadores')
    cadastrar_novos = dados.get('cadastrar_novos', False)
    guilda_alvo = dados.get('guilda_alvo', 'vortex')
    semana_fixa = "Acumulativo"

    if ImportacaoXML.query.filter_by(semana=semana_fixa, hash_arquivo=hash_arquivo).first():
        return jsonify({"erro": "Esta importação já foi confirmada."}), 409

    configs_semanais = ConfigAtividade.query.filter_by(tipo_evento='semanal').all()
    atividades_semanais_unicas = [c.nome_xml for c in configs_semanais]

    try:
        label_import = "Upload Diário (Vortex)" if guilda_alvo == 'vortex' else "Upload Semanal (BlackSkull)"
        nova_importacao = ImportacaoXML(semana=semana_fixa, hash_arquivo=hash_arquivo, admin_responsavel="admin", nome_personalizado=label_import, tipo_arquivo="xml")
        db.session.add(nova_importacao)
        db.session.flush() 

        if guilda_alvo == 'vortex':
            for j_data in jogadores_data:
                nome_xml = j_data['nome_xml']
                jogador = Jogador.query.filter(func.lower(Jogador.nome) == nome_xml.lower()).first()
                
                if not jogador:
                    if cadastrar_novos:
                        jogador = Jogador(nome=nome_xml)
                        db.session.add(jogador)
                        db.session.flush() 
                    else:
                        continue 

                for atv in j_data['detalhes']:
                    nome_atividade = atv['atividade']
                    
                    if nome_atividade in atividades_semanais_unicas:
                        pass

                    novo_ponto = Pontuacao(
                        jogador_id=jogador.id,
                        semana=semana_fixa,
                        atividade=nome_atividade,
                        pontos=atv['pontos'],
                        importacao_id=nova_importacao.id
                    )
                    db.session.add(novo_ponto)
                    
        else: # LÓGICA BLACKSKULL COM FILTRO
            alts_map = {a.nome_alt.lower(): a.jogador_id for a in PersonagemSecundario.query.all()}
            eventos_permitidos_bs = ['Raid de Guilda', 'Expedição da Guilda']
            
            for j_data in jogadores_data:
                nome_xml = j_data['nome_xml'].lower()
                if nome_xml in alts_map:
                    jogador_id = alts_map[nome_xml]
                    # IGNORA TUDO QUE NÃO SEJA RAID OU EXPEDIÇÃO
                    total_pts = sum(a['pontos'] for a in j_data['detalhes'] if a['atividade'] in eventos_permitidos_bs)
                    
                    if total_pts > 0:
                        novo_ponto = Pontuacao(
                            jogador_id=jogador_id,
                            semana=semana_fixa,
                            atividade="BlackSkull",
                            pontos=total_pts,
                            importacao_id=nova_importacao.id
                        )
                        db.session.add(novo_ponto)

        db.session.commit()
        return jsonify({"mensagem": "Importação de Pontos concluída!"}), 200

    except Exception as e:
        db.session.rollback() 
        return jsonify({"erro": str(e)}), 500

@app.route('/api/importar-excel', methods=['POST'])
def importar_excel():
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    if 'excel_file' not in request.files: return jsonify({"erro": "Arquivo não enviado."}), 400

    arquivo = request.files['excel_file']
    caminho = os.path.join(app.config['UPLOAD_FOLDER'], arquivo.filename)
    arquivo.save(caminho)

    try: import openpyxl
    except ImportError: return jsonify({"erro": "A biblioteca 'openpyxl' não está instalada. Execute 'pip install openpyxl'."}), 500

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
            nome = row[idx_nome]
            if not nome: continue
            
            jogador = Jogador.query.filter(func.lower(Jogador.nome) == str(nome).lower()).first()
            if jogador:
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
        return jsonify({"mensagem": f"{jogadores_atualizados} jogadores atualizados!"}), 200
        
    except Exception as e:
        if os.path.exists(caminho): os.remove(caminho)
        db.session.rollback()
        return jsonify({"erro": str(e)}), 500


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
        return jsonify({"erro": str(e)}), 500

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
        return jsonify({"erro": str(e)}), 500

@app.route('/api/editar-jogadores', methods=['POST'])
def editar_jogadores():
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    dados = request.get_json()
    jogadores_data = dados.get('jogadores', [])
    
    try:
        for item in jogadores_data:
            jogador = db.session.get(Jogador, item['id'])
            if jogador:
                jogador.level = int(item['level'])
                jogador.poder_combate = int(item['poder_combate'])
                
                alts_string = item.get('alts', '')
                PersonagemSecundario.query.filter_by(jogador_id=jogador.id).delete()
                if alts_string:
                    novos_alts = [n.strip() for n in alts_string.split(',') if n.strip()]
                    for n_alt in novos_alts:
                        existente = PersonagemSecundario.query.filter_by(nome_alt=n_alt).first()
                        if not existente:
                            db.session.add(PersonagemSecundario(jogador_id=jogador.id, nome_alt=n_alt))

                novo_total_desejado = int(item['pontos'])
                pts = db.session.query(func.sum(Pontuacao.pontos)).filter_by(jogador_id=jogador.id).scalar() or 0
                pens = db.session.query(func.sum(SorteioHistorico.penalidade)).filter_by(jogador_id=jogador.id).scalar() or 0
                pontos_atuais = pts - pens
                
                diferenca = novo_total_desejado - pontos_atuais
                if diferenca != 0:
                    ajuste = Pontuacao(
                        jogador_id=jogador.id,
                        semana="Ajuste Manual",
                        atividade="Ajuste Manual",
                        pontos=diferenca,
                        motivo_ajuste="Ajuste direto na tabela"
                    )
                    db.session.add(ajuste)
        
        db.session.commit()
        return jsonify({"mensagem": "Modificações e Alts salvos com sucesso!"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": str(e)}), 500

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
        return jsonify({"erro": str(e)}), 500

# Rota mantida original
@app.route('/api/realizar-sorteio', methods=['POST'])
def realizar_sorteio():
    if not admin_required(): return jsonify({"erro": "Acesso negado"}), 401
    dados = request.get_json()
    jogadores_ids = dados.get('jogadores_ids', [])
    if not jogadores_ids: return jsonify({"erro": "Nenhum jogador selecionado."}), 400
    try:
        vencedor_id = random.choice(jogadores_ids)
        vencedor = db.session.get(Jogador, vencedor_id)
        novo_sorteio = SorteioHistorico(jogador_id=vencedor.id)
        db.session.add(novo_sorteio)
        db.session.commit()
        return jsonify({"vencedor_nome": vencedor.nome, "vencedor_id": vencedor.id}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": str(e)}), 500

# --- NOVAS ROTAS: Sorteio Meme ---
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
        return jsonify({"erro": str(e)}), 500

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
        return jsonify({"erro": str(e)}), 500

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
        return jsonify({"erro": str(e)}), 500
# ---------------------------------

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
        return jsonify({"erro": str(e)}), 500

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
        return jsonify({"erro": str(e)}), 500

with app.app_context():
    try:
        db.session.execute(text('SELECT tipo_evento FROM config_atividades LIMIT 1'))
    except Exception:
        db.session.rollback()
        db.session.execute(text('ALTER TABLE config_atividades ADD COLUMN tipo_evento VARCHAR(20) DEFAULT "diario"'))
        db.session.commit()
        eventos_semanais = "'Raid de Guilda', 'Expedição da Guilda', 'Confronto pelo Paraíso', 'Campo de Batalha de Aço', 'Escaramuça', 'Guerra de Mineração', 'Fortaleza Albern'"
        db.session.execute(text(f"UPDATE config_atividades SET tipo_evento = 'semanal' WHERE nome_xml IN ({eventos_semanais})"))
        db.session.commit()

    try:
        db.session.execute(text('SELECT nome_personalizado FROM importacoes LIMIT 1'))
    except Exception:
        db.session.rollback()
        db.session.execute(text('ALTER TABLE importacoes ADD COLUMN nome_personalizado VARCHAR(100) DEFAULT ""'))
        db.session.commit()
        
    try:
        db.session.execute(text('SELECT tipo_arquivo FROM importacoes LIMIT 1'))
    except Exception:
        db.session.rollback()
        db.session.execute(text('ALTER TABLE importacoes ADD COLUMN tipo_arquivo VARCHAR(20) DEFAULT "xml"'))
        db.session.commit()

    db.create_all()
    if not ConfigAtividade.query.first():
        atividades_iniciais = [
            ('Verificado', 'diario'), ('Doar', 'diario'), ('Atividade da Guilda', 'diario'), 
            ('Raid de Guilda', 'semanal'), ('Expedição da Guilda', 'semanal'), 
            ('Confronto pelo Paraíso', 'semanal'), ('Campo de Batalha de Aço', 'semanal'), 
            ('Escaramuça', 'semanal'), ('Guerra de Mineração', 'semanal'), ('Fortaleza Albern', 'semanal')
        ]
        for atv, tipo in atividades_iniciais:
            db.session.add(ConfigAtividade(nome_xml=atv, pontos_padrao=1, tipo_evento=tipo))
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True, port=5000)