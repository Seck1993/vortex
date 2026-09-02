"""Testes da rota principal (dashboard)."""


def test_index_carrega_sem_erro_com_banco_vazio(client):
    resposta = client.get("/")
    assert resposta.status_code == 200
    assert "BANCO DE DADOS VAZIO".encode("utf-8") in resposta.data


def test_index_lista_jogador_no_ranking(client, criar_jogador):
    criar_jogador("Fulano", poder_combate=1000)

    resposta = client.get("/")

    assert resposta.status_code == 200
    assert "Fulano".encode("utf-8") in resposta.data


def test_index_esconde_controles_de_admin_para_visitante(client):
    resposta = client.get("/")
    assert "Matriz de Pontos".encode("utf-8") not in resposta.data


def test_index_mostra_controles_de_admin_para_admin(admin_client):
    resposta = admin_client.get("/")
    assert "Matriz de Pontos".encode("utf-8") in resposta.data


def test_index_referencia_assets_estaticos_versionados(client):
    resposta = client.get("/")
    html = resposta.data.decode("utf-8")
    assert "/static/css/dashboard.css?v=" in html
    assert "/static/js/dashboard.js?v=" in html


def test_participacao_100_para_unico_jogador_ativo(client, criar_jogador, dar_pontos):
    jogador_id = criar_jogador("Fulano")
    dar_pontos(jogador_id, 10, semana="Semana 1", atividade="Verificado")

    resposta = client.get("/")

    assert resposta.status_code == 200
    # Único jogador com pontos na semana -> ele é a própria moda -> 100% de participação
    assert "100.0%".encode("utf-8") in resposta.data or "100%".encode("utf-8") in resposta.data
