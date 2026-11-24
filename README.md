# DevPilot AI

Agente de desenvolvimento de software para analisar, planejar, modificar e validar projetos reais com autonomia controlada.

> **Status:** Base local ampliada: agente, memória, diagnóstico, validação em contêiner e autenticação opcional.

## Funcionalidades disponíveis

- API HTTP com FastAPI.
- Cadastro, listagem, consulta e atualização de projetos.
- Importação de projetos por arquivo ZIP.
- Extração em uma área de trabalho dedicada, sem executar arquivos.
- Filtros para diretórios de dependências, ambientes virtuais e arquivos sensíveis comuns.
- Limites de tamanho do arquivo, quantidade de itens e volume descompactado.
- Detecção inicial de linguagens, tecnologias, manifestos e pontos de entrada.
- Histórico de eventos e evidências de execução por projeto.
- Painel de tarefas com estados, comparação de diferenças antes da aprovação, aprovação/rejeição de planos pendentes e restauração de aplicações a partir do checkpoint.
- Dashboard web responsivo.
- Testes automatizados com pytest e integração contínua no GitHub Actions.
- Planejamento de tarefas via Ollama local, revisão do plano e aprovação/rejeição.
- Escrita de arquivos restrita à raiz do projeto e bloqueio de caminhos sensíveis.
- Checkpoint ZIP automático, armazenado fora da pasta do projeto, antes de cada aplicação aprovada; inclui versões anteriores dos arquivos existentes e registra arquivos novos.
- Restauração explícita de um checkpoint para desfazer uma aplicação aprovada, incluindo remoção dos arquivos que não existiam antes.
- Memória técnica persistente, incluindo perfil estrutural e notas manuais.
- Modo Resgate com diagnóstico estático e recomendações priorizadas.
- Validação isolada via Docker: executa testes Python com pytest quando encontrados, analisa sintaxe Python sem executar módulos e verifica sintaxe JavaScript (.js, .mjs, .cjs) e TypeScript/JSX (.ts, .tsx, .mts, .cts, .jsx), sem executar o código.
- Fluxo de reparo: após falhas nos testes, a IA analisa a saída e cria uma proposta de correção que exige aprovação antes de alterar arquivos. Depois, os testes podem ser executados novamente.
- Base de autenticação com hash de senha, tokens assinados, isolamento de projetos por conta e cotas iniciais.

**Limite importante:** a análise atual é estática e estrutural. Ela lista arquivos e identifica indícios por nomes/extensões; não instala dependências, não executa scripts e não garante que todas as tecnologias foram detectadas.

## Requisitos

- Python 3.11 ou superior.
- Git.
- Navegador moderno.

## Executar localmente

**Atalho para Windows com Git Bash:** na raiz do repositório, execute `bash scripts/iniciar.sh`. O script cria o ambiente virtual, instala as dependências, tenta construir a imagem Docker quando o serviço está disponível e inicia o painel. Ollama e Docker são opcionais para abrir o painel, mas necessários para planejamento por IA e validação isolada, respectivamente.

Para executar manualmente, na raiz do repositório:

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

Para validação isolada, construa a imagem de testes na raiz do repositório com: `docker build -t devpilot-sandbox:py311 sandbox/`. A imagem inclui pytest, Node.js e o compilador TypeScript. A validação analisa a sintaxe de arquivos Python sem executá-los, executa pytest quando encontra testes Python, usa `node --check` em JavaScript e analisa sintaxe de TypeScript/JSX. O contêiner não tem rede, monta o projeto como somente leitura e aplica limites de recursos. A execução tem limite de 120 segundos, tenta encerrar o contêiner ao exceder esse prazo e mantém no máximo 12 KB da saída em memória. Não instala dependências específicas, não executa scripts npm, não verifica tipos e não faz build completo de aplicações.

O agente usa Ollama local em `http://127.0.0.1:11434` e o modelo `qwen2.5-coder:3b` por padrão. Instale o Ollama e execute `ollama pull qwen2.5-coder:3b`. Configure `DEVPILOT_OLLAMA_URL` e `DEVPILOT_OLLAMA_MODEL` para personalizar. Sem Ollama, a função de planejamento retorna indisponibilidade; não há API paga obrigatória.

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
- `GET /api/v1/projects/{id}/memory` / `PUT /api/v1/projects/{id}/memory`
- `POST /api/v1/projects/{id}/rescue`
- `POST /api/v1/projects/{id}/validate`
- `POST /api/v1/projects/{id}/repair` — testa e, em caso de falha, prepara uma proposta de correção pendente de aprovação
- `GET /api/v1/projects/{id}/runs`
- `POST /api/v1/auth/register` / `POST /api/v1/auth/login` / `GET /api/v1/auth/me` (modo autenticado; consulta plano e consumo de cotas)
- `POST /api/v1/projects/{id}/tasks` — gera plano com IA local
- `GET /api/v1/projects/{id}/tasks`
- `GET /api/v1/tasks/{task_id}/diff` — compara os arquivos atuais com a proposta antes da aprovação
- `POST /api/v1/tasks/{task_id}/approve` — aplica alterações após aprovação
- `POST /api/v1/tasks/{task_id}/restore` — restaura o checkpoint da aplicação e marca a tarefa como restaurada
- `POST /api/v1/tasks/{task_id}/reject`

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
- O modo local mantém autenticação desativada por padrão. Para habilitar contas, configure DEVPILOT_AUTH_REQUIRED=true e DEVPILOT_AUTH_SECRET com pelo menos 32 caracteres aleatórios. As rotas da API passam a exigir Authorization: Bearer token; os projetos ficam isolados por conta. O plano gratuito tem limites iniciais de 3 projetos e 10 tarefas de IA por janela de 24 horas. O painel autenticado mostra o consumo atual e os limites da conta.
- A validação em Docker analisa sintaxe Python, JavaScript e TypeScript/JSX e executa pytest quando há testes; não instala dependências do projeto, não executa scripts npm e não faz verificação de tipos nem build completo de TypeScript/TSX. A segurança depende de Docker e host atualizados. Não exponha o daemon Docker.
- O Modo Resgate é estático e sua pontuação é indicativa, não uma avaliação de qualidade comprovada.
- O login possui bloqueio local após 5 tentativas inválidas por combinação de IP e e-mail durante uma janela de 15 minutos. Esse controle reside na memória do processo: reiniciar a aplicação limpa os contadores e múltiplas instâncias não compartilham estado. Antes de produção, substituir por limitação distribuída (por exemplo, Redis), adicionar proteção no proxy e monitoramento. Ainda faltam verificação de e-mail, recuperação de senha, sessões revogáveis, cobrança, portal de assinatura e revisão independente de segurança. Não exponha a aplicação à internet ainda.
- Projetos criados anteriormente no modo local sem autenticação ficam sem proprietário (`user_id` nulo) e não aparecem automaticamente em contas autenticadas. Antes de habilitar autenticação em uma base já utilizada, faça backup e planeje a adoção desses projetos por uma conta; não exponha a aplicação à internet.
- Antes de cada aplicação aprovada, o sistema cria um checkpoint ZIP em `workspace/.devpilot_checkpoints/`, fora da pasta do projeto. O checkpoint tem limite de 10 MB por arquivo e 50 MB por conjunto; se não puder ser criado, a aplicação é interrompida. Os arquivos novos são registrados como inexistentes antes da alteração.
- O checkpoint automático pode ser restaurado pela rota autenticada `POST /api/v1/tasks/{task_id}/restore`; essa ação substitui os arquivos alterados pelas versões anteriores e remove arquivos criados pela tarefa. Use-a apenas quando desejar desfazer aquela aplicação. Preserve também backups próprios.
- A aprovação autoriza escrita dos arquivos propostos, não garante correção do código.

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
7. Base SaaS inicial (autenticação e cotas implementadas; cobrança e operação de produção pendentes).

Consulte [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) para as decisões de arquitetura.
