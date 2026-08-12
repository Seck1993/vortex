import xml.etree.ElementTree as ET
import hashlib

def analisar_xml_guilda(caminho_arquivo, map_atividades_ativas):
    """
    Lê o XML e extrai os jogadores e suas atividades validadas.
    map_atividades_ativas: dict com { 'Nome da Coluna': Pontos } vindo do BD.
    """
    ns = {'ss': 'urn:schemas-microsoft-com:office:spreadsheet'}
    tree = ET.parse(caminho_arquivo)
    root = tree.getroot()

    # Gerar hash para evitar que o mesmo arquivo seja upado duas vezes na mesma semana
    with open(caminho_arquivo, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    worksheet = root.find(".//ss:Worksheet[@ss:Name='GuildParticipation']", ns)
    if worksheet is None:
        raise ValueError("Aba 'GuildParticipation' não encontrada no XML. Verifique o arquivo.")

    linhas = worksheet.findall(".//ss:Row", ns)
    if not linhas:
        raise ValueError("O XML parece estar vazio.")

    # 1. Mapear os cabeçalhos para saber a posição de cada atividade
    cabecalhos = []
    for celula in linhas[0].findall("ss:Cell", ns):
        dado = celula.find("ss:Data", ns)
        cabecalhos.append(dado.text if dado is not None else "")

    try:
        idx_nome = cabecalhos.index("Name / Content")
    except ValueError:
        raise ValueError("A coluna 'Name / Content' obrigatória não foi encontrada.")

    # 2. Processar os dados dos jogadores
    resultado = []
    
    for linha in linhas[1:]:
        celulas = linha.findall("ss:Cell", ns)
        if len(celulas) <= idx_nome:
            continue
            
        celula_nome = celulas[idx_nome].find("ss:Data", ns)
        if celula_nome is None or not celula_nome.text:
            continue
            
        nome_jogador = celula_nome.text
        pontos_conquistados = []

        # Analisa as outras colunas da linha
        for i, celula in enumerate(celulas):
            if i == idx_nome:
                continue
                
            nome_atividade = cabecalhos[i]
            dado_atividade = celula.find("ss:Data", ns)
            
            # Checa se a coluna faz parte das atividades pontuáveis configuradas
            if nome_atividade in map_atividades_ativas:
                # O XML usa 'þ' para sim/marcado e '¨' para não/desmarcado
                if dado_atividade is not None and dado_atividade.text == 'þ':
                    pontos_conquistados.append({
                        "atividade": nome_atividade,
                        "pontos": map_atividades_ativas[nome_atividade]
                    })

        if pontos_conquistados:
            resultado.append({
                "nome": nome_jogador,
                "atividades": pontos_conquistados
            })

    return resultado, file_hash