# Arquitetura inicial

## Direção

O DevPilot começa como um monólito modular. Isso reduz custo operacional e complexidade enquanto as fronteiras entre domínio, API, persistência e ferramentas amadurecem.

## Componentes da Fase 1

- **Interface:** HTML, CSS e JavaScript sem framework obrigatório; servida pela API.
- **API:** FastAPI com contratos Pydantic e rotas versionadas em `/api/v1`.
- **Persistência:** SQLAlchemy 2 e SQLite local. O acesso ao banco fica isolado para permitir futura troca por PostgreSQL.
- **Testes:** pytest e TestClient, usando SQLite em memória.
- **CI:** GitHub Actions instala dependências e executa os testes em pushes para `main` e pull requests.

## Fluxo atual

```text
Navegador -> Dashboard (HTML/CSS/JS) -> FastAPI -> Schemas/Rotas -> SQLAlchemy -> SQLite
```

## Limites intencionais

O cadastro de projeto armazena nome, descrição e um caminho opcional como referência textual. Nenhum caminho é aberto, nenhum arquivo é lido e nenhum comando é executado nesta fase.

Executar código de terceiros exigirá isolamento real (por exemplo, contêineres com limites de recursos), escopo de arquivos autorizado, allowlist de operações, trilha de auditoria e aprovações para ações de risco. Uma lista de comandos permitidos, isoladamente, não é uma sandbox.

## Próximas fronteiras

1. Análise de estrutura em modo somente leitura e dentro de uma raiz autorizada.
2. Planejador que transforma solicitações em planos revisáveis.
3. Provedores de IA intercambiáveis, com opção local.
4. Executor de ferramentas com checkpoints, limites de tempo e aprovação humana.
5. Validação baseada em testes e evidências persistidas.
