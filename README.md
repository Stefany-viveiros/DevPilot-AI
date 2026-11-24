# DevPilot AI

Agente de desenvolvimento de software para analisar, planejar, modificar e validar projetos reais com autonomia controlada.

> **Status:** Fase 2 — gerenciamento, importação segura e análise inicial de projetos.

## Funcionalidades disponíveis

- API HTTP com FastAPI.
- Cadastro, listagem, consulta e atualização de projetos.
- Importação de projetos por arquivo ZIP.
- Extração em uma área de trabalho dedicada, sem executar arquivos.
- Filtros para diretórios de dependências, ambientes virtuais e arquivos sensíveis comuns.
- Limites de tamanho do arquivo, quantidade de itens e volume descompactado.
- Detecção inicial de linguagens, tecnologias, manifestos e pontos de entrada.
- Histórico de eventos por projeto.
- Dashboard web responsivo.
- Testes automatizados com pytest e integração contínua no GitHub Actions.

**Limite importante:** a análise atual é estática e estrutural. Ela lista arquivos e identifica indícios por nomes/extensões; não instala dependências, não executa scripts e não garante que todas as tecnologias foram detectadas.

## Requisitos

- Python 3.11 ou superior.
- Git.
- Navegador moderno.

## Executar localmente

Na raiz do repositório:

```bash
python -m venv .venv
```

Ative o ambiente virtual:

**Windows (PowerShell):**
```powershell
.venv\\Scripts\\Activate.ps1
```

**Windows (Git Bash) / Linux / macOS:**
```bash
source .venv/Scripts/activate
# Linux/macOS: source .venv/bin/activate
```

Instale as dependências e inicie a API:

```bash
pip install -r backend/requirements.txt
uvicorn app.main:app --app-dir backend --reload
```

Acesse:

- Dashboard: http://127.0.0.1:8000/
- Saúde da API: http://127.0.0.1:8000/api/v1/health
- Documentação interativa: http://127.0.0.1:8000/docs

O banco SQLite é criado em `backend/data/devpilot.db`. Os projetos importados ficam em `workspace/`. Ambos são dados locais e não devem ser versionados.

## Importar um projeto

1. Comprima a pasta do projeto em um arquivo ZIP.
2. No dashboard, escolha **Importar ZIP**.
3. Informe um nome e selecione o arquivo.
4. Abra o projeto e solicite a análise estrutural.

A importação aplica limites de segurança e ignora diretórios de dependências e arquivos com nomes/extensões sensíveis comuns. Ainda assim, não envie segredos ou credenciais: nenhum filtro consegue reconhecer todos os formatos possíveis de segredo.

Limites atuais: ZIP de até 20 MB, até 2.000 itens, 100 MB descompactados e 10 MB por arquivo.

## API

- `GET /api/v1/health`
- `GET /api/v1/projects`
- `POST /api/v1/projects`
- `POST /api/v1/projects/import` (multipart/form-data: `name`, `description`, `archive`)
- `GET /api/v1/projects/{id}`
- `PATCH /api/v1/projects/{id}`
- `POST /api/v1/projects/{id}/analyze`
- `GET /api/v1/projects/{id}/analysis`
- `GET /api/v1/projects/{id}/events`

## Testes

```bash
pip install -r backend/requirements.txt
cd backend
pytest -q
```

## Segurança e limites atuais

- Arquivos importados nunca são executados nesta fase.
- Caminhos ZIP absolutos, com travessia de diretório e links simbólicos são recusados.
- Diretórios comuns de dependências, ambientes virtuais e metadados de controle de versão são ignorados.
- Arquivos com nomes e extensões sensíveis comuns são ignorados, mas isso não substitui uma ferramenta dedicada de detecção de segredos.
- A análise percorre apenas a pasta de workspace associada ao projeto.
- A aplicação ainda não tem autenticação. Não a exponha à internet ou a uma rede não confiável.
- Execução em sandbox, autenticação, autorização e auditoria ampliada continuam planejadas para fases futuras.

## Estrutura

```text
backend/
  app/
    api/          # Rotas HTTP
    core/         # Configurações
    db/           # Engine, sessão e base ORM
    models/       # Entidades persistentes
    schemas/      # Contratos de entrada e saída
    services/     # Importação e análise
    main.py
  tests/
frontend/
  index.html
  assets/css/
  assets/js/
docs/
.github/workflows/
workspace/        # Projetos importados localmente (não versionar)
```

## Roadmap

1. Fundação (concluída e validada no CI).
2. Gerenciamento e importação segura de projetos.
3. Integração com modelos de IA, planejamento e ferramentas.
4. Execução isolada, testes e correções controladas.
5. Memória técnica persistente.
6. Modo Resgate.
7. Preparação SaaS.

Consulte [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) para as decisões de arquitetura.
