# DevPilot AI

Agente de desenvolvimento de software para analisar, planejar, modificar e validar projetos reais com autonomia controlada.

> **Status:** Fase 1 — Fundação em desenvolvimento.

## Objetivos da primeira versão

- API HTTP com FastAPI.
- Cadastro e listagem de projetos com persistência SQLite.
- Dashboard web responsivo conectado à API.
- Testes automatizados com pytest.
- Integração contínua no GitHub Actions.

Nesta fase, o DevPilot **não executa código arbitrário de projetos importados**, não altera repositórios externos e não realiza deploy. Essas capacidades dependem das camadas de isolamento, autorização e auditoria planejadas para fases posteriores.

## Requisitos

- Python 3.11 ou superior.
- Git.
- Navegador moderno.

## Executar localmente

No terminal, na raiz do repositório:

```bash
python -m venv .venv
```

Ative o ambiente virtual:

**Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
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
- Verificação de saúde: http://127.0.0.1:8000/api/v1/health
- Documentação interativa: http://127.0.0.1:8000/docs

O banco SQLite é criado em `backend/data/devpilot.db` na inicialização. Esse arquivo é local e não deve ser versionado.

## Testes

```bash
pip install -r backend/requirements.txt
cd backend
pytest -q
```

## Estrutura

```text
backend/
  app/
    api/          # Rotas HTTP
    core/         # Configurações
    db/           # Engine, sessão e base ORM
    models/       # Entidades persistentes
    schemas/      # Contratos de entrada e saída
    services/     # Regras de negócio
    main.py       # Composição da aplicação
  tests/
frontend/
  index.html
  assets/
    css/
    js/
docs/
.github/workflows/
```

## Segurança e limites atuais

- A API não recebe nem executa comandos de terminal.
- O cadastro de projeto nesta fase é apenas metadado; importação e acesso ao sistema de arquivos serão implementados com escopo autorizado.
- Não armazene senhas, tokens ou arquivos `.env` no repositório.
- Antes de disponibilizar a aplicação em rede, será necessário implementar autenticação, autorização e proteção de origem adequada.

## Roadmap

1. Fundação (API, banco, dashboard e testes).
2. Gerenciamento e importação segura de projetos.
3. Integração com modelos de IA, planejamento e ferramentas.
4. Execução isolada, testes e correções controladas.
5. Memória técnica persistente.
6. Modo Resgate.
7. Preparação SaaS.

Consulte [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) para as decisões iniciais.
