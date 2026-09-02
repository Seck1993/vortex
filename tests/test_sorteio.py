"""Testes do fluxo de sorteio de item (roleta) e do sorteio 'meme'."""


def test_simular_sorteio_exige_admin(membro_client, criar_evento_item):
    _, item_id = criar_evento_item()
    resposta = membro_client.post("/api/simular-sorteio-item", json={"item_id": item_id})
    assert resposta.status_code == 401


def test_simular_sorteio_sem_apostas_retorna_400(admin_client, criar_evento_item):
    _, item_id = criar_evento_item()
    resposta = admin_client.post("/api/simular-sorteio-item", json={"item_id": item_id})
    assert resposta.status_code == 400


def test_simular_sorteio_com_apostas_retorna_fatias(app_module, app, membro_client,
                                                      criar_jogador, dar_pontos, criar_evento_item):
    jogador_id = criar_jogador("Fulano")
    dar_pontos(jogador_id, 100)
    _, item_id = criar_evento_item()
    membro_client.post("/api/apostar-item", json={"item_id": item_id, "jogador_id": jogador_id, "pontos": 50})

    # Mesmo client, trocando a sessão para admin (fixtures admin_client/membro_client
    # compartilham o mesmo cookie jar e não podem ser usadas juntas no mesmo teste)
    membro_client.post("/api/login", json={"senha": "vortex2026"})
    resposta = membro_client.post("/api/simular-sorteio-item", json={"item_id": item_id})
    assert resposta.status_code == 200
    dados = resposta.get_json()

    assert dados["nome_item"]
    assert "Staff (Administração)" in dados["fatias"]
    assert dados["fatias"]["Staff (Administração)"] == 15.0
    assert dados["fatias"]["Fulano"] == 85.0  # único apostador -> fica com os 85% restantes

    with app.app_context():
        item = app_module.db.session.get(app_module.EventoItem, item_id)
        assert item.em_andamento is True


def test_confirmar_sorteio_finaliza_item_e_registra_historico(app_module, app, membro_client,
                                                                criar_jogador, dar_pontos, criar_evento_item):
    jogador_id = criar_jogador("Fulano")
    dar_pontos(jogador_id, 100)
    _, item_id = criar_evento_item(nome_item="Espada Lendária")
    membro_client.post("/api/apostar-item", json={"item_id": item_id, "jogador_id": jogador_id, "pontos": 50})

    membro_client.post("/api/login", json={"senha": "vortex2026"})
    resposta_final = membro_client.post("/api/confirmar-sorteio-item", json={
        "item_id": item_id,
        "vencedor_id": jogador_id,
        "vencedor_nome": "Fulano",
        "is_staff": False,
        "pontos_apostados": 50,
    })
    assert resposta_final.status_code == 200

    with app.app_context():
        item = app_module.db.session.get(app_module.EventoItem, item_id)
        assert item.sorteado is True
        assert item.em_andamento is False

        historico = app_module.SorteioHistorico.query.filter_by(jogador_id=jogador_id).first()
        assert historico is not None
        assert historico.penalidade == 50
        assert "Espada Lendária" in historico.observacao


def test_confirmar_sorteio_vencedor_staff_nao_gera_historico(app_module, app, admin_client, criar_evento_item):
    _, item_id = criar_evento_item()

    resposta = admin_client.post("/api/confirmar-sorteio-item", json={
        "item_id": item_id,
        "vencedor_id": None,
        "vencedor_nome": "Staff (Administração)",
        "is_staff": True,
        "pontos_apostados": 0,
    })
    assert resposta.status_code == 200

    with app.app_context():
        assert app_module.SorteioHistorico.query.count() == 0


def test_confirmar_sorteio_ja_finalizado_retorna_400(admin_client, criar_evento_item):
    _, item_id = criar_evento_item()
    payload = {"item_id": item_id, "vencedor_id": None, "vencedor_nome": "X", "is_staff": True, "pontos_apostados": 0}

    admin_client.post("/api/confirmar-sorteio-item", json=payload)
    resposta_repetida = admin_client.post("/api/confirmar-sorteio-item", json=payload)

    assert resposta_repetida.status_code == 400


def test_sorteio_meme_exige_admin(membro_client, criar_jogador):
    jogador_id = criar_jogador("Fulano")
    resposta = membro_client.post("/api/realizar-sorteio-meme", json={
        "jogadores_ids": [jogador_id], "item": "Capa do Batman"
    })
    assert resposta.status_code == 401


def test_sorteio_meme_sem_participantes_retorna_400(admin_client):
    resposta = admin_client.post("/api/realizar-sorteio-meme", json={"jogadores_ids": [], "item": "Item X"})
    assert resposta.status_code == 400


def test_sorteio_meme_registra_vencedor(app_module, app, admin_client, criar_jogador):
    jogador_id = criar_jogador("Único")
    resposta = admin_client.post("/api/realizar-sorteio-meme", json={
        "jogadores_ids": [jogador_id], "item": "Capa do Batman"
    })
    assert resposta.status_code == 200
    dados = resposta.get_json()
    assert dados["vencedor_id"] == jogador_id
    assert dados["vencedor_nome"] == "Único"

    with app.app_context():
        registro = app_module.SorteioMemeHistorico.query.filter_by(jogador_id=jogador_id).first()
        assert registro is not None
        assert registro.item_sorteado == "Capa do Batman"
