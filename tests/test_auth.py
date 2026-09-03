"""Testes de autenticação e controle de acesso (admin_required / login_required)."""


def test_login_admin_com_senha_correta(client):
    resposta = client.post("/api/login", json={"senha": "vortex2026"})
    assert resposta.status_code == 200

    with client.session_transaction() as sess:
        assert sess["logged_in"] is True
        assert sess["role"] == "admin"


def test_login_membro_com_senha_correta(client):
    resposta = client.post("/api/login", json={"senha": "membro2026"})
    assert resposta.status_code == 200

    with client.session_transaction() as sess:
        assert sess["role"] == "membro"


def test_login_com_senha_incorreta_retorna_401(client):
    resposta = client.post("/api/login", json={"senha": "senha-errada"})
    assert resposta.status_code == 401
    assert "erro" in resposta.get_json()


def test_logout_limpa_sessao(admin_client):
    resposta = admin_client.post("/api/logout")
    assert resposta.status_code == 200

    with admin_client.session_transaction() as sess:
        assert "logged_in" not in sess
        assert "role" not in sess


def test_rota_admin_bloqueada_para_visitante(client):
    resposta = client.post("/api/nova-semana")
    assert resposta.status_code == 401


def test_rota_admin_bloqueada_para_membro_comum(membro_client):
    resposta = membro_client.post("/api/nova-semana")
    assert resposta.status_code == 401


def test_rota_admin_permitida_para_admin(admin_client):
    resposta = admin_client.post("/api/nova-semana")
    assert resposta.status_code == 200


def test_rota_que_so_exige_login_bloqueada_para_visitante(client):
    resposta = client.post("/api/apostar-item", json={"item_id": 1, "jogador_id": 1, "pontos": 10})
    assert resposta.status_code == 401


def test_rota_que_so_exige_login_permitida_para_membro(membro_client):
    # Sem evento ativo -> a validação de negócio falha (400), mas passa da checagem de login (401)
    resposta = membro_client.post("/api/apostar-item", json={"item_id": 999, "jogador_id": 999, "pontos": 10})
    assert resposta.status_code != 401
