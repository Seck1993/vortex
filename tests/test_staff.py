"""Testes do cadastro de Staff (CRUD usado para escolher quem representa a
fatia fixa de 15% na roleta de item, no lugar de um rótulo genérico)."""


def test_criar_staff_exige_admin(membro_client):
    resposta = membro_client.post("/api/criar-staff", json={"nome": "Zeca"})
    assert resposta.status_code == 401


def test_criar_staff_sem_nome_retorna_400(admin_client):
    resposta = admin_client.post("/api/criar-staff", json={"nome": "   "})
    assert resposta.status_code == 400


def test_criar_staff_com_sucesso(app_module, app, admin_client):
    resposta = admin_client.post("/api/criar-staff", json={"nome": "Zeca"})
    assert resposta.status_code == 200

    with app.app_context():
        assert app_module.StaffMembro.query.filter_by(nome="Zeca").first() is not None


def test_criar_staff_duplicado_retorna_409(admin_client):
    admin_client.post("/api/criar-staff", json={"nome": "Zeca"})
    resposta = admin_client.post("/api/criar-staff", json={"nome": "zeca"})  # case-insensitive
    assert resposta.status_code == 409


def test_editar_staff_renomeia(app_module, app, admin_client):
    admin_client.post("/api/criar-staff", json={"nome": "Zeca"})
    with app.app_context():
        staff_id = app_module.StaffMembro.query.filter_by(nome="Zeca").first().id

    resposta = admin_client.post("/api/editar-staff", json={
        "staff": [{"id": staff_id, "nome": "Zeca Renomeado"}]
    })
    assert resposta.status_code == 200

    with app.app_context():
        membro = app_module.db.session.get(app_module.StaffMembro, staff_id)
        assert membro.nome == "Zeca Renomeado"


def test_deletar_staff_remove_registro(app_module, app, admin_client):
    admin_client.post("/api/criar-staff", json={"nome": "Zeca"})
    with app.app_context():
        staff_id = app_module.StaffMembro.query.filter_by(nome="Zeca").first().id

    resposta = admin_client.delete(f"/api/deletar-staff/{staff_id}")
    assert resposta.status_code == 200

    with app.app_context():
        assert app_module.db.session.get(app_module.StaffMembro, staff_id) is None


def test_deletar_staff_inexistente_retorna_404(admin_client):
    resposta = admin_client.delete("/api/deletar-staff/99999")
    assert resposta.status_code == 404


def test_deletar_staff_exige_admin(membro_client):
    resposta = membro_client.delete("/api/deletar-staff/1")
    assert resposta.status_code == 401


def test_index_lista_staff_cadastrada(client, admin_client):
    admin_client.post("/api/criar-staff", json={"nome": "Zeca"})
    resposta = client.get("/")
    assert "Zeca".encode("utf-8") in resposta.data
