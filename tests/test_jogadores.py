"""Testes de /api/editar-jogadores: edição de atributos e restrição de campos por papel."""


def test_membro_pode_editar_level_e_poder(app_module, app, membro_client, criar_jogador):
    jogador_id = criar_jogador("Fulano", poder_combate=100, level=1)

    resposta = membro_client.post("/api/editar-jogadores", json={
        "jogadores": [{"id": jogador_id, "level": 5, "poder_combate": 9000}]
    })
    assert resposta.status_code == 200

    with app.app_context():
        jogador = app_module.db.session.get(app_module.Jogador, jogador_id)
        assert jogador.level == 5
        assert jogador.poder_combate == 9000


def test_membro_nao_pode_ajustar_pontos_totais(app_module, app, membro_client, criar_jogador):
    jogador_id = criar_jogador("Fulano")

    resposta = membro_client.post("/api/editar-jogadores", json={
        "jogadores": [{"id": jogador_id, "pontos": 500}]
    })
    assert resposta.status_code == 200

    with app.app_context():
        total = app_module.db.session.query(
            app_module.db.func.sum(app_module.Pontuacao.pontos)
        ).filter_by(jogador_id=jogador_id).scalar() or 0
        # Campo 'pontos' só é aplicado quando user_role == 'admin'; membro não pode forçar ajuste
        assert total == 0


def test_admin_pode_ajustar_pontos_totais(app_module, app, admin_client, criar_jogador):
    jogador_id = criar_jogador("Fulano")

    resposta = admin_client.post("/api/editar-jogadores", json={
        "jogadores": [{"id": jogador_id, "pontos": 500}]
    })
    assert resposta.status_code == 200

    with app.app_context():
        total = app_module.db.session.query(
            app_module.db.func.sum(app_module.Pontuacao.pontos)
        ).filter_by(jogador_id=jogador_id).scalar() or 0
        assert total == 500


def test_visitante_nao_pode_editar_jogadores(client, criar_jogador):
    jogador_id = criar_jogador("Fulano")
    resposta = client.post("/api/editar-jogadores", json={
        "jogadores": [{"id": jogador_id, "level": 10}]
    })
    assert resposta.status_code == 401
