import os
import tempfile

import pytest


@pytest.fixture(scope="session")
def app_module():
    """Importa o módulo app.py UMA vez por sessão de testes, apontando para um
    arquivo SQLite temporário (nunca o vortex.db real). app.py executa sua
    inicialização de banco no import (padrão do módulo, sem app factory), por
    isso a variável de ambiente precisa ser definida antes do import."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["FLASK_DEBUG"] = "0"

    import app as _app_module

    yield _app_module

    with _app_module.app.app_context():
        _app_module.db.engine.dispose()
    try:
        os.remove(db_path)
    except OSError:
        pass  # Windows pode manter o handle preso por mais um instante; arquivo temp, sem risco


@pytest.fixture
def app(app_module):
    """Devolve a app Flask com o banco recriado e semeado do zero para cada teste."""
    app_module.app.config.update(TESTING=True)
    with app_module.app.app_context():
        app_module.db.drop_all()
        app_module.inicializar_banco()
    yield app_module.app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_client(client):
    resposta = client.post("/api/login", json={"senha": "vortex2026"})
    assert resposta.status_code == 200
    return client


@pytest.fixture
def membro_client(client):
    resposta = client.post("/api/login", json={"senha": "membro2026"})
    assert resposta.status_code == 200
    return client


@pytest.fixture
def criar_jogador(app_module, app):
    """Fábrica para criar um Jogador direto no banco, dentro do contexto da app."""
    def _criar(nome, poder_combate=0, level=1, status="Ativo"):
        with app.app_context():
            jogador = app_module.Jogador(
                nome=nome, poder_combate=poder_combate, level=level, status=status
            )
            app_module.db.session.add(jogador)
            app_module.db.session.commit()
            return jogador.id
    return _criar


@pytest.fixture
def criar_evento_item(app_module, app):
    """Fábrica para criar um EventoSorteio ativo com um único EventoItem.
    Retorna (evento_id, item_id)."""
    def _criar(nome_item="Item Teste", max_pontos=100.0, restricao="Todos", prazo_encerramento=""):
        with app.app_context():
            evento = app_module.EventoSorteio(titulo="Evento Teste", prazo_encerramento=prazo_encerramento)
            app_module.db.session.add(evento)
            app_module.db.session.flush()
            item = app_module.EventoItem(
                evento_id=evento.id, nome_item=nome_item, max_pontos=max_pontos, restricao=restricao
            )
            app_module.db.session.add(item)
            app_module.db.session.commit()
            return evento.id, item.id
    return _criar


@pytest.fixture
def dar_pontos(app_module, app):
    """Fábrica para lançar pontos direto no banco para um jogador em uma semana/atividade."""
    def _dar(jogador_id, pontos, semana="Semana 1", atividade="Verificado"):
        with app.app_context():
            registro = app_module.Pontuacao(
                jogador_id=jogador_id, semana=semana, atividade=atividade, pontos=pontos
            )
            app_module.db.session.add(registro)
            app_module.db.session.commit()
    return _dar
