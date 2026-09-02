# Vortex Command Center

Painel de gestão para a guilda Vortex: ranking de pontuação, controle de participação semanal, sorteios de itens (com aposta de pontos e roleta ao vivo), sorteio "meme", importação de dados via XML/Excel e matriz de recompensas configurável.

Aplicação Flask com front-end server-rendered (Jinja) e atualização de dados via `fetch` (sem reload de página nas ações do dia a dia).

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

Os testes usam um banco SQLite temporário (nunca o `vortex.db` real) e cobrem autenticação/controle de acesso, renderização do dashboard, edição de jogadores, o parser de XML, importação de Excel e o fluxo de apostas/sorteio (participação mínima de 90%, saldo, restrição de faixa Mega/Titã, prazo de encerramento, sorteio de item e sorteio "meme").

## Deploy

`gunicorn` já está entre as dependências para deploy em plataformas como o Render (não há `Procfile` no repositório — configure o comando de start da plataforma para algo como `gunicorn app:app`). Configure a variável de ambiente `DATABASE_URL` apontando para o PostgreSQL de produção — o próprio `app.py` normaliza o prefixo `postgres://` para `postgresql://` quando necessário.
