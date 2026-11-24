# Arquitetura do DevPilot AI

## Direção

O DevPilot começa como um monólito modular. Isso reduz custo operacional e complexidade enquanto as fronteiras entre domínio, API, persistência e ferramentas amadurecem.

## Componentes atuais

- **Interface:** HTML, CSS e JavaScript sem framework obrigatório; servida pela API.
- **API:** FastAPI com contratos Pydantic e rotas versionadas em `/api/v1`.
- **Persistência:** SQLAlchemy 2 e SQLite local. Acesso ao banco isolado para permitir futura troca por PostgreSQL.
- **Importação:** ZIP recebido pela API, extraído em diretório próprio dentro de `workspace/`.
- **Análise:** inventário de arquivos, manifestos, extensões, linguagens prováveis e pontos de entrada. Nenhum arquivo do projeto é executado.
- **Histórico:** eventos de cadastro, importação, atualização e análise persistidos por projeto.
- **Testes:** pytest e TestClient, usando SQLite em memória.
- **CI:** GitHub Actions instala dependências e executa os testes em pushes para `main` e pull requests.

## Fluxo atual

```text
Navegador -> Dashboard -> FastAPI -> Rotas/Serviços -> Workspace autorizado
                                         |                  |
                                         +-> SQLAlchemy -> SQLite
                                         +-> Histórico
```

## Importação e limites

A importação limita ZIP a 20 MB, até 2.000 entradas, 100 MB descompactados e 10 MB por arquivo. Caminhos absolutos, travessia de diretório, links simbólicos, arquivos protegidos por senha e taxas de compressão excessivas são recusados.

Diretórios comuns de dependências, ambientes virtuais e arquivos com nomes/extensões sensíveis comuns são ignorados. Isso reduz exposição acidental, mas não substitui um scanner de segredos: o usuário deve revisar o arquivo antes de enviá-lo.

## Limites de segurança

O caminho persistido é relativo ao workspace e é validado novamente antes da análise. A análise percorre somente a raiz autorizada, ignora diretórios comuns de dependências e não segue links simbólicos. Nenhum script, instalador ou comando do projeto é executado.

Ainda não há autenticação ou autorização multiusuário. A aplicação deve permanecer local até a implementação dessas camadas. Execução de código de terceiros exigirá isolamento real (por exemplo, contêineres com limites de recursos), escopo de arquivos autorizado, allowlist de operações, trilha de auditoria e aprovações para ações de risco. Uma lista de comandos permitidos, isoladamente, não é uma sandbox.

## Compatibilidade do banco

A inicialização aplica uma migração aditiva pequena para bancos SQLite já criados na Fase 1, adicionando os campos de análise sem apagar os projetos existentes. Migrações completas e versionadas (Alembic) devem ser adotadas antes de ampliar o esquema ou oferecer PostgreSQL em produção.

## Próximas fronteiras

1. Provedores de IA intercambiáveis, incluindo opção local.
2. Planejador que transforma solicitações em planos revisáveis.
3. Executor de ferramentas com checkpoints, limites de tempo e aprovação humana.
4. Validação baseada em testes e evidências persistidas.


## Planejamento com IA local (Fase 3)

O planejador envia ao Ollama local uma solicitação e um contexto textual limitado (até 80 KB), excluindo diretórios comuns de dependências/controle de versão e arquivos com nomes indicativos de credenciais. O resultado é validado como plano estruturado e persistido como tarefa pendente. A pessoa usuária pode aprovar ou rejeitar no painel.

A aprovação permite apenas escrita de arquivos dentro da raiz do projeto, com bloqueio de traversal, caminhos absolutos, symlinks, pastas protegidas e nomes sensíveis. O limite é de 20 arquivos e 200 KB por arquivo. Não há execução de shell, instalação de pacotes ou testes automáticos nesta fase. A validação de caminhos é defesa em profundidade, não substitui isolamento de sistema operacional contra processos locais concorrentes.
