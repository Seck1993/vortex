"""Testes de importação de Excel (atributos) e gerenciamento de logs de importação."""
import io

import openpyxl


def _gerar_excel_em_memoria():
    wb = openpyxl.Workbook()
    sheet = wb.active
    sheet.append(["Nome", "Level", "Poder de Combate"])
    sheet.append(["Fulano", 42, "1.234.567"])
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def test_importar_excel_exige_admin(membro_client):
    arquivo = _gerar_excel_em_memoria()
    resposta = membro_client.post(
        "/api/importar-excel",
        data={"excel_file": (arquivo, "atributos.xlsx")},
        content_type="multipart/form-data",
    )
    assert resposta.status_code == 401


def test_importar_excel_cadastra_jogador_novo(app_module, app, admin_client):
    arquivo = _gerar_excel_em_memoria()
    resposta = admin_client.post(
        "/api/importar-excel",
        data={"excel_file": (arquivo, "atributos.xlsx")},
        content_type="multipart/form-data",
    )
    assert resposta.status_code == 200

    with app.app_context():
        jogador = app_module.Jogador.query.filter_by(nome="Fulano").first()
        assert jogador is not None
        assert jogador.level == 42
        assert jogador.poder_combate == 1234567  # pontos/vírgulas removidos


def test_importar_excel_atualiza_jogador_existente(app_module, app, admin_client, criar_jogador):
    criar_jogador("Fulano", poder_combate=1, level=1)
    arquivo = _gerar_excel_em_memoria()

    resposta = admin_client.post(
        "/api/importar-excel",
        data={"excel_file": (arquivo, "atributos.xlsx")},
        content_type="multipart/form-data",
    )
    assert resposta.status_code == 200

    with app.app_context():
        assert app_module.Jogador.query.filter_by(nome="Fulano").count() == 1
        jogador = app_module.Jogador.query.filter_by(nome="Fulano").first()
        assert jogador.level == 42


def test_deletar_importacao_desfaz_pontos(app_module, app, admin_client, criar_jogador):
    jogador_id = criar_jogador("Fulano")
    with app.app_context():
        importacao = app_module.ImportacaoXML(
            semana="Semana 1", hash_arquivo="hash-teste", nome_personalizado="Upload Teste", tipo_arquivo="xml"
        )
        app_module.db.session.add(importacao)
        app_module.db.session.flush()
        app_module.db.session.add(app_module.Pontuacao(
            jogador_id=jogador_id, semana="Semana 1", atividade="Verificado", pontos=10,
            importacao_id=importacao.id
        ))
        app_module.db.session.commit()
        importacao_id = importacao.id

    resposta = admin_client.delete(f"/api/deletar-importacao/{importacao_id}")
    assert resposta.status_code == 200

    with app.app_context():
        assert app_module.db.session.get(app_module.ImportacaoXML, importacao_id) is None
        assert app_module.Pontuacao.query.filter_by(importacao_id=importacao_id).count() == 0


def test_deletar_importacao_inexistente_retorna_404(admin_client):
    resposta = admin_client.delete("/api/deletar-importacao/99999")
    assert resposta.status_code == 404
