"""Testes unitários para xml_engine.analisar_xml_guilda, o parser do XML
(formato SpreadsheetML) exportado pelo jogo. Usa 'þ' para marcado e '¨' para
desmarcado nas células de atividade."""
import os

from xml_engine import analisar_xml_guilda

XML_TEMPLATE = """<?xml version="1.0"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
          xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
 <Worksheet ss:Name="GuildParticipation">
  <Table>
   <Row>
    <Cell><Data ss:Type="String">Name / Content</Data></Cell>
    <Cell><Data ss:Type="String">Verificado</Data></Cell>
    <Cell><Data ss:Type="String">Doar</Data></Cell>
   </Row>
   {linhas}
  </Table>
 </Worksheet>
</Workbook>
"""

LINHA_TEMPLATE = """
   <Row>
    <Cell><Data ss:Type="String">{nome}</Data></Cell>
    <Cell><Data ss:Type="String">{verificado}</Data></Cell>
    <Cell><Data ss:Type="String">{doar}</Data></Cell>
   </Row>
"""


def _escrever_xml(tmp_path, linhas_xml):
    caminho = os.path.join(tmp_path, "guilda.xml")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(XML_TEMPLATE.format(linhas=linhas_xml))
    return caminho


def test_extrai_jogador_com_atividades_marcadas(tmp_path):
    linha = LINHA_TEMPLATE.format(nome="Fulano", verificado="þ", doar="¨")
    caminho = _escrever_xml(str(tmp_path), linha)

    resultado, file_hash = analisar_xml_guilda(caminho, {"Verificado": 1, "Doar": 5})

    assert len(resultado) == 1
    assert resultado[0]["nome"] == "Fulano"
    assert resultado[0]["atividades"] == [{"atividade": "Verificado", "pontos": 1}]
    assert isinstance(file_hash, str) and len(file_hash) == 64  # sha256 hexdigest


def test_jogador_sem_nenhuma_atividade_marcada_e_omitido(tmp_path):
    linha = LINHA_TEMPLATE.format(nome="Zero", verificado="¨", doar="¨")
    caminho = _escrever_xml(str(tmp_path), linha)

    resultado, _ = analisar_xml_guilda(caminho, {"Verificado": 1, "Doar": 5})

    assert resultado == []


def test_atividade_nao_configurada_e_ignorada(tmp_path):
    linha = LINHA_TEMPLATE.format(nome="Fulano", verificado="þ", doar="þ")
    caminho = _escrever_xml(str(tmp_path), linha)

    # Apenas 'Verificado' está na matriz de configuração ativa
    resultado, _ = analisar_xml_guilda(caminho, {"Verificado": 1})

    assert resultado[0]["atividades"] == [{"atividade": "Verificado", "pontos": 1}]


def test_hash_muda_conforme_conteudo_do_arquivo(tmp_path):
    caminho_a = _escrever_xml(str(tmp_path), LINHA_TEMPLATE.format(nome="A", verificado="þ", doar="¨"))
    _, hash_a = analisar_xml_guilda(caminho_a, {"Verificado": 1})

    os.remove(caminho_a)
    caminho_b = _escrever_xml(str(tmp_path), LINHA_TEMPLATE.format(nome="B", verificado="þ", doar="¨"))
    _, hash_b = analisar_xml_guilda(caminho_b, {"Verificado": 1})

    assert hash_a != hash_b


def test_planilha_sem_aba_guildparticipation_leva_a_erro(tmp_path):
    caminho = os.path.join(str(tmp_path), "invalido.xml")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(
            '<?xml version="1.0"?>'
            '<Workbook xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">'
            '<Worksheet ss:Name="OutraAba"></Worksheet></Workbook>'
        )

    try:
        analisar_xml_guilda(caminho, {})
        assert False, "deveria ter levantado ValueError"
    except ValueError as e:
        assert "GuildParticipation" in str(e)
