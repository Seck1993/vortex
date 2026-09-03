# Vortex Command Center

Painel de gestão para a guilda Vortex: ranking de pontuação, controle de participação semanal, sorteios de itens (com aposta de pontos e roleta ao vivo), sorteio "meme", importação de dados via XML/Excel e matriz de recompensas configurável.

Aplicação Flask com front-end server-rendered (Jinja) e atualização de dados via `fetch` (sem reload de página nas ações do dia a dia).

## Funcionalidades

### Abas do painel

| Aba | Acesso | O que faz |
|---|---|---|
| Módulo de Jogadores | Todos (edição exige login) | Ranking com participação semanal, diamantes, penalidades e saldo. Coluna **Editar** abre um modal para atualizar Level e Poder de Combate de um personagem individualmente. |
| Ordem de Classes & Builds | Todos (edição exige login) | Progressão por poder de combate, com filtro por classe e destaque de Megas/Titãs. Coluna **Editar** abre um modal para atualizar classe e marcações (skills, constantes, trindade, mestre da técnica). |
| Registro de Espólios (Loot) | Todos | Histórico de itens ganhos e pontos deduzidos, paginado (10 por página). |
| Sorteio Items "Meme" | Todos (sorteio exige admin) | Sorteio uniforme entre participantes selecionados e histórico paginado. |
| Gerenciar Membros | 🔒 Admin | Cadastrar novos membros manualmente e remover membros (removendo junto todo o histórico deles). |
| Matriz de Pontos | 🔒 Admin | Cadastro de eventos/atividades e quantos pontos cada um vale. |
| Logs do Sistema | 🔒 Admin | Importações da semana ativa, com rollback de pontos e virada de semana. |

### Sorteio de itens (roleta)

1. Um admin publica um banner com um ou mais itens (cada um com custo de 100% de chance e restrição opcional: Livre, Titãs+ ou Megas).
2. Membros logados apostam pontos, respeitando as regras validadas no servidor: mínimo de **90% de participação** na semana ativa, saldo real disponível e restrição de faixa por Poder de Combate.
3. O admin escolhe **quem representa a Staff** naquele sorteio (cadastro próprio, com criar/editar/remover) e confere os jogadores presentes antes de girar.
4. O servidor calcula as fatias — **15% fixos para a Staff** e **85% divididos proporcionalmente às apostas** — e sorteia o vencedor com `random.choices`. A animação no navegador é apenas visual; o resultado já vem decidido do servidor.
5. Todos os usuários logados veem a mesma roleta girar ao vivo (polling a cada 2,5s).
6. Ao concluir, só o vencedor perde pontos (registrados como penalidade no histórico de espólios). Quem perdeu não perde nada.

### Controle de acesso

- **Admin:** acesso total — girar/confirmar roleta, gerenciar Staff, publicar/encerrar banners, cadastrar e remover membros, importar XML/Excel, ajustar pontuações e matriz de recompensas, virar a semana.
- **Membro:** apostar em itens, atualizar Level/Poder e Classe/Build dos personagens, e assistir aos sorteios ao vivo.
- **Visitante (sem login):** somente leitura do ranking, classes e históricos.

Todas as rotas sensíveis são protegidas no servidor (`admin_required` / `login_required`), não apenas escondendo botões no front-end.

### Idiomas

Seletor próprio com bandeiras (integrado ao Google Website Translator via cookie `googtrans`): Português, English, Español, Français, Русский, 日本語, 한국어, 中文 e Filipino.

## Importação de dados

### XML de participação (pontuação)

O jogo exporta um arquivo SpreadsheetML (Excel 2003 XML) com a aba `GuildParticipation`: uma coluna `Name / Content` com o nome do personagem e uma coluna por atividade, marcada com `þ` (fez) ou `¨` (não fez). O parser fica em [xml_engine.py](xml_engine.py) e trata:

- **`ss:Index`**: o Excel omite células vazias e declara a posição real da célula seguinte nesse atributo. Ignorá-lo desloca as colunas e credita pontos na atividade errada.
- **Colunas extras sem cabeçalho**: são ignoradas, sem quebrar a importação.
- **Jogadores sem nenhuma atividade marcada**: continuam sendo retornados, com lista de atividades vazia. Eles seguem na guilda — apenas não pontuaram no período — e omiti-los faria com que fossem tratados como ausentes do export e marcados como inativos.

A importação é feita em duas etapas: `/api/importar` gera um **preview** (nada é gravado), e `/api/confirmar` grava. Só as atividades marcadas pelo admin no preview são contabilizadas, e a gravação é **incremental (delta)**: para cada atividade, grava apenas a diferença entre o valor do XML e o que o jogador já tem na semana — reimportar o mesmo arquivo não duplica pontos.

O hash SHA-256 do arquivo impede que o mesmo XML seja importado duas vezes na mesma semana.

> ⚠️ **Atenção:** na guilda principal, todo jogador **ausente do XML** é marcado como `Inativo` e sai do ranking. Um membro cadastrado manualmente que ainda não apareça em nenhum export será inativado na próxima importação.

### Excel de atributos

`/api/importar-excel` atualiza nome, level e poder de combate a partir de uma planilha `.xlsx` (as colunas são detectadas pelo cabeçalho). Nomes de arquivo enviados passam por `secure_filename`, para que um nome como `../app.py` não escape da pasta de uploads.

## Requisitos

- Python 3.10+
- SQLite (padrão local) ou PostgreSQL (produção, via `DATABASE_URL`)

## Instalação

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

pip install -r requirements.txt
```

## Rodando localmente

```bash
python app.py
```

A aplicação sobe em `http://localhost:5000`. Por padrão o modo debug do Flask fica **desligado**; para ativá-lo em desenvolvimento:

```bash
set FLASK_DEBUG=1 && python app.py     # Windows
# FLASK_DEBUG=1 python app.py          # Linux/Mac
```

Na primeira execução o banco (`vortex.db`, SQLite local) é criado e semeado automaticamente com a matriz de atividades padrão e as réguas Mega/Titã.

### Acesso

O login (admin/membro) é validado por senha fixa no código (`/api/login` em [app.py](app.py)). Peça as credenciais a quem administra o projeto — não as publique aqui nem em nenhum outro lugar versionado.

## Estrutura do projeto

```
app.py                  # Rotas, modelos de evento/sorteio, regras de negócio
models.py               # Modelos base (Jogador, Pontuacao, ConfigAtividade, ImportacaoXML, ...)
xml_engine.py            # Parser do XML de participação exportado pelo jogo
templates/dashboard.html # Template único do painel (Jinja)
static/css/dashboard.css # Estilos do painel
static/js/dashboard.js   # Lógica do front-end (toasts, atualização sem reload, roleta, etc.)
tests/                   # Suíte de testes automatizados (pytest)
```

## Rodando os testes

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Os testes usam um banco SQLite temporário (nunca o `vortex.db` real) e cobrem:

- Autenticação e controle de acesso (`admin_required` / `login_required`)
- Renderização do dashboard e visibilidade de controles por papel
- Edição de jogadores e restrição de campos admin-only
- Cadastro e remoção de membros (incluindo limpeza do histórico associado)
- Cadastro de Staff usado na roleta
- Parser de XML: `ss:Index`, colunas extras, jogadores sem atividades e planilha inválida
- Importação de Excel e proteção contra path traversal no nome do arquivo
- Fluxo de apostas e sorteio: participação mínima de 90%, saldo, restrição Mega/Titã, prazo de encerramento, cálculo das fatias (15% Staff / 85% proporcional), confirmação com desconto de pontos e sorteio "meme"

## Deploy

`gunicorn` já está entre as dependências para deploy em plataformas como o Render (não há `Procfile` no repositório — configure o comando de start da plataforma para algo como `gunicorn app:app`). Configure a variável de ambiente `DATABASE_URL` apontando para o PostgreSQL de produção — o próprio `app.py` normaliza o prefixo `postgres://` para `postgresql://` quando necessário.
