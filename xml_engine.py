import xml.etree.ElementTree as ET
import hashlib

NS = {'ss': 'urn:schemas-microsoft-com:office:spreadsheet'}
ATTR_INDEX = '{urn:schemas-microsoft-com:office:spreadsheet}Index'

# O XML usa 'þ' para marcado e '¨' para desmarcado (fonte Wingdings).
MARCADO = 'þ'


def _mapear_celulas_por_coluna(linha):
    """Mapeia {índice da coluna: célula} respeitando o atributo ss:Index.

    No formato SpreadsheetML o Excel pode OMITIR células vazias e indicar a
    posição real da célula seguinte com ss:Index (1-based). Percorrer as células
    por posição sequencial, sem olhar esse atributo, desloca todas as colunas
    após a primeira lacuna e credita os pontos na atividade errada.
    """
    celulas = {}
    coluna = 0
    for celula in linha.findall('ss:Cell', NS):
        indice_declarado = celula.get(ATTR_INDEX)
        if indice_declarado:
            try:
                coluna = int(indice_declarado) - 1
            except ValueError:
                pass  # índice inválido: mantém a contagem sequencial
        celulas[coluna] = celula
        coluna += 1
    return celulas


def _texto_da_celula(celula):
    if celula is None:
        return None
    dado = celula.find('ss:Data', NS)
    return dado.text if dado is not None else None


def analisar_xml_guilda(caminho_arquivo, map_atividades_ativas):
    """
    Lê o XML e extrai os jogadores e suas atividades validadas.
    map_atividades_ativas: dict com { 'Nome da Coluna': Pontos } vindo do BD.
    """
    tree = ET.parse(caminho_arquivo)
    root = tree.getroot()

    # Gerar hash para evitar que o mesmo arquivo seja upado duas vezes na mesma semana
    with open(caminho_arquivo, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    worksheet = root.find(".//ss:Worksheet[@ss:Name='GuildParticipation']", NS)
    if worksheet is None:
        raise ValueError("Aba 'GuildParticipation' não encontrada no XML. Verifique o arquivo.")

    linhas = worksheet.findall(".//ss:Row", NS)
    if not linhas:
        raise ValueError("O XML parece estar vazio.")

    # 1. Mapear os cabeçalhos para saber a posição de cada atividade
    cabecalhos = {
        indice: (_texto_da_celula(celula) or "")
        for indice, celula in _mapear_celulas_por_coluna(linhas[0]).items()
    }

    idx_nome = next((i for i, titulo in cabecalhos.items() if titulo == "Name / Content"), None)
    if idx_nome is None:
        raise ValueError("A coluna 'Name / Content' obrigatória não foi encontrada.")

    # 2. Processar os dados dos jogadores
    resultado = []

    for linha in linhas[1:]:
        celulas = _mapear_celulas_por_coluna(linha)

        nome_jogador = _texto_da_celula(celulas.get(idx_nome))
        if not nome_jogador or not nome_jogador.strip():
            continue

        pontos_conquistados = []

        # Analisa as outras colunas da linha
        for indice, celula in celulas.items():
            if indice == idx_nome:
                continue

            # Coluna sem cabeçalho correspondente é simplesmente ignorada
            nome_atividade = cabecalhos.get(indice)

            # Checa se a coluna faz parte das atividades pontuáveis configuradas
            if nome_atividade in map_atividades_ativas and _texto_da_celula(celula) == MARCADO:
                pontos_conquistados.append({
                    "atividade": nome_atividade,
                    "pontos": map_atividades_ativas[nome_atividade]
                })

        # Jogadores sem nenhuma atividade marcada TAMBÉM são retornados: eles
        # continuam na guilda, apenas não pontuaram no período. Omiti-los fazia
        # com que fossem tratados como ausentes do export e marcados como
        # inativos, sumindo do ranking.
        resultado.append({
            "nome": nome_jogador.strip(),
            "atividades": pontos_conquistados
        })

    return resultado, file_hash
