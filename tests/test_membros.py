"""Testes da aba de gerenciamento de membros (cadastro e remoção, admin-only)."""


def test_criar_jogador_exige_admin(membro_client):
    resposta = membro_client.post("/api/criar-jogador", json={"nome": "Novato"})
    assert resposta.status_code == 401


def test_criar_jogador_sem_nome_retorna_400(admin_client):
    resposta = admin_client.post("/api/criar-jogador", json={"nome": "   "})
    assert resposta.status_code == 400


def test_criar_jogador_com_sucesso(app_module, app, admin_client):
    resposta = admin_client.post("/api/criar-jogador", json={
        "nome": "Novato", "level": 42, "poder_combate": 12345
    })
    assert resposta.status_code == 200

    with app.app_context():
        jogador = app_module.Jogador.query.filter_by(nome="Novato").first()
        assert jogador is not None
        assert jogador.level == 42
        assert jogador.poder_combate == 12345
        assert jogador.status == "Ativo"


def test_criar_jogador_usa_padroes_quando_campos_vazios(app_module, app, admin_client):
    resposta = admin_client.post("/api/criar-jogador", json={"nome": "SemAtributos"})
    assert resposta.status_code == 200

    with app.app_context():
        jogador = app_module.Jogador.query.filter_by(nome="SemAtributos").first()
        assert jogador.level == 1
        assert jogador.poder_combate == 0


def test_criar_jogador_duplicado_retorna_409(admin_client):
    admin_client.post("/api/criar-jogador", json={"nome": "Repetido"})
    resposta = admin_client.post("/api/criar-jogador", json={"nome": "repetido"})  # case-insensitive
    assert resposta.status_code == 409


def test_deletar_jogador_exige_admin(membro_client, criar_jogador):
    jogador_id = criar_jogador("Fulano")
    resposta = membro_client.delete(f"/api/deletar-jogador/{jogador_id}")
    assert resposta.status_code == 401


def test_deletar_jogador_inexistente_retorna_404(admin_client):
    resposta = admin_client.delete("/api/deletar-jogador/99999")
    assert resposta.status_code == 404


def test_deletar_jogador_remove_historico_associado(app_module, app, admin_client,
                                                      criar_jogador, dar_pontos, criar_evento_item):
    jogador_id = criar_jogador("ParaRemover")
    dar_pontos(jogador_id, 100)
    _, item_id = criar_evento_item()

    with app.app_context():
        app_module.db.session.add(app_module.ApostaSorteio(item_id=item_id, jogador_id=jogador_id, pontos=10))
        app_module.db.session.add(app_module.SorteioHistorico(jogador_id=jogador_id, observacao="Venceu: X", penalidade=10))
        app_module.db.session.add(app_module.SorteioMemeHistorico(jogador_id=jogador_id, item_sorteado="Meme"))
        app_module.db.session.commit()

    resposta = admin_client.delete(f"/api/deletar-jogador/{jogador_id}")
    assert resposta.status_code == 200

    with app.app_context():
        assert app_module.db.session.get(app_module.Jogador, jogador_id) is None
        assert app_module.Pontuacao.query.filter_by(jogador_id=jogador_id).count() == 0
        assert app_module.ApostaSorteio.query.filter_by(jogador_id=jogador_id).count() == 0
        assert app_module.SorteioHistorico.query.filter_by(jogador_id=jogador_id).count() == 0
        assert app_module.SorteioMemeHistorico.query.filter_by(jogador_id=jogador_id).count() == 0


def test_index_mostra_aba_membros_apenas_para_admin(client, admin_client):
    resposta_admin = admin_client.get("/")
    assert "Gerenciar Membros".encode("utf-8") in resposta_admin.data

    admin_client.post("/api/logout")
    resposta_visitante = client.get("/")
    assert "Gerenciar Membros".encode("utf-8") not in resposta_visitante.data
