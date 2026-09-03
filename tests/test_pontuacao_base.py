"""Testes unitários para calcular_pontuacao_base_semanal (a "moda" que define
o teto de 100% de participação semanal). Função pura, extraída de app.py para
eliminar a duplicação entre index() e apostar_item() — ver commit da refatoração."""


def test_sem_valores_retorna_zero(app_module):
    assert app_module.calcular_pontuacao_base_semanal([]) == 0


def test_ignora_valores_zero_ou_negativos(app_module):
    assert app_module.calcular_pontuacao_base_semanal([0, 0, -5]) == 0


def test_valor_unico(app_module):
    assert app_module.calcular_pontuacao_base_semanal([42]) == 42


def test_moda_e_o_valor_mais_frequente(app_module):
    # 100 aparece 3x, 50 aparece 1x -> moda é 100
    assert app_module.calcular_pontuacao_base_semanal([100, 100, 100, 50]) == 100


def test_empate_de_frequencia_resolvido_pelo_maior_valor(app_module):
    # 50 e 100 aparecem 2x cada -> desempate pelo maior valor (100)
    assert app_module.calcular_pontuacao_base_semanal([50, 50, 100, 100]) == 100


def test_aceita_generator(app_module):
    valores = (v for v in [10, 10, 20])
    assert app_module.calcular_pontuacao_base_semanal(valores) == 10
