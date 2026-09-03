"""Testes de /api/apostar-item: regras de negócio (participação mínima de 90%,
saldo disponível, restrição de faixa Mega/Titã, prazo de encerramento)."""
import time


def test_pontos_invalidos_retorna_400(membro_client, criar_jogador, criar_evento_item):
    jogador_id = criar_jogador("Fulano")
    _, item_id = criar_evento_item()

    resposta = membro_client.post("/api/apostar-item", json={
        "item_id": item_id, "jogador_id": jogador_id, "pontos": 0
    })
    assert resposta.status_code == 400


def test_prazo_encerrado_bloqueia_aposta(membro_client, criar_jogador, dar_pontos, criar_evento_item):
    jogador_id = criar_jogador("Fulano")
    dar_pontos(jogador_id, 100)
    prazo_passado = str(int((time.time() - 3600) * 1000))  # 1h atrás
    _, item_id = criar_evento_item(prazo_encerramento=prazo_passado)

    resposta = membro_client.post("/api/apostar-item", json={
        "item_id": item_id, "jogador_id": jogador_id, "pontos": 10
    })
    assert resposta.status_code == 400
    assert "prazo" in resposta.get_json()["erro"].lower()


def test_item_inexistente_retorna_400(membro_client, criar_jogador):
    jogador_id = criar_jogador("Fulano")
    resposta = membro_client.post("/api/apostar-item", json={
        "item_id": 99999, "jogador_id": jogador_id, "pontos": 10
    })
    assert resposta.status_code == 400


def test_jogador_inexistente_retorna_404(membro_client, criar_evento_item):
    _, item_id = criar_evento_item()
    resposta = membro_client.post("/api/apostar-item", json={
        "item_id": item_id, "jogador_id": 99999, "pontos": 10
    })
    assert resposta.status_code == 404


def test_restricao_mega_bloqueia_jogador_abaixo_do_cp(membro_client, criar_jogador, dar_pontos, criar_evento_item):
    # Régua Mega padrão semeada = 100000
    jogador_id = criar_jogador("Fraco", poder_combate=50000)
    dar_pontos(jogador_id, 100)
    _, item_id = criar_evento_item(restricao="Mega")

    resposta = membro_client.post("/api/apostar-item", json={
        "item_id": item_id, "jogador_id": jogador_id, "pontos": 10
    })
    assert resposta.status_code == 400
    assert "MEGA" in resposta.get_json()["erro"]


def test_restricao_mega_permite_jogador_acima_do_cp(membro_client, criar_jogador, dar_pontos, criar_evento_item):
    jogador_id = criar_jogador("Forte", poder_combate=200000)
    dar_pontos(jogador_id, 100)
    _, item_id = criar_evento_item(restricao="Mega")

    resposta = membro_client.post("/api/apostar-item", json={
        "item_id": item_id, "jogador_id": jogador_id, "pontos": 10
    })
    assert resposta.status_code == 200


def test_participacao_abaixo_de_90_por_cento_bloqueia_aposta(membro_client, criar_jogador, dar_pontos, criar_evento_item):
    # Jogador A define a moda (100 pts); Jogador B fica com só 10% disso -> abaixo dos 90% exigidos
    jogador_a = criar_jogador("Referencia")
    dar_pontos(jogador_a, 100)
    jogador_b = criar_jogador("Fraco")
    dar_pontos(jogador_b, 10)
    _, item_id = criar_evento_item()

    resposta = membro_client.post("/api/apostar-item", json={
        "item_id": item_id, "jogador_id": jogador_b, "pontos": 5
    })
    assert resposta.status_code == 400
    assert "participação" in resposta.get_json()["erro"].lower()


def test_saldo_insuficiente_bloqueia_aposta(membro_client, criar_jogador, dar_pontos, criar_evento_item):
    jogador_id = criar_jogador("Fulano")
    dar_pontos(jogador_id, 50)  # saldo real = 50
    _, item_id = criar_evento_item()

    resposta = membro_client.post("/api/apostar-item", json={
        "item_id": item_id, "jogador_id": jogador_id, "pontos": 999
    })
    assert resposta.status_code == 400
    assert "saldo" in resposta.get_json()["erro"].lower()


def test_aposta_valida_e_registrada(app_module, app, membro_client, criar_jogador, dar_pontos, criar_evento_item):
    jogador_id = criar_jogador("Fulano")
    dar_pontos(jogador_id, 100)
    _, item_id = criar_evento_item()

    resposta = membro_client.post("/api/apostar-item", json={
        "item_id": item_id, "jogador_id": jogador_id, "pontos": 30
    })
    assert resposta.status_code == 200

    with app.app_context():
        aposta = app_module.ApostaSorteio.query.filter_by(item_id=item_id, jogador_id=jogador_id).first()
        assert aposta is not None
        assert aposta.pontos == 30


def test_apostar_de_novo_atualiza_em_vez_de_duplicar(app_module, app, membro_client, criar_jogador, dar_pontos, criar_evento_item):
    jogador_id = criar_jogador("Fulano")
    dar_pontos(jogador_id, 100)
    _, item_id = criar_evento_item()

    membro_client.post("/api/apostar-item", json={"item_id": item_id, "jogador_id": jogador_id, "pontos": 20})
    resposta = membro_client.post("/api/apostar-item", json={"item_id": item_id, "jogador_id": jogador_id, "pontos": 40})
    assert resposta.status_code == 200

    with app.app_context():
        apostas = app_module.ApostaSorteio.query.filter_by(item_id=item_id, jogador_id=jogador_id).all()
        assert len(apostas) == 1
        assert apostas[0].pontos == 40
