# Arquitetura do DevPilot AI

## Direção

O DevPilot é um monólito modular. Essa escolha mantém a execução local simples e de baixo custo enquanto separa domínio, API, persistência, interface e ferramentas. A arquitetura permite evoluir para serviços gerenciados posteriormente, sem presumir que a versão atual já seja um SaaS de produção.

## Componentes atuais

- **Interface:** HTML, CSS e JavaScript sem framework obrigatório; servida pela API.
- **API:** FastAPI, contratos Pydantic e rotas versionadas em `/api/v1`.
- **Persistência:** SQLAlchemy 2 e SQLite local; configuração permite apontar para outro banco compatível, mas PostgreSQL ainda precisa de validação operacional.
- **Identidade:** cadastro/login opcionais, hash PBKDF2-SHA256, tokens HMAC com expiração e isolamento de projetos por conta.
- **Importação:** ZIP extraído em diretório próprio dentro de `workspace/`, sem executar arquivos.
- **Análise:** inventário estrutural de arquivos, manifestos, linguagens prováveis e pontos de entrada.
- **Planejamento:** Ollama local, contexto limitado, plano estruturado e aprovação humana antes de gravar arquivos.
- **Validação:** testes Python com pytest e verificação de sintaxe JavaScript com `node --check`, em contêiner Docker sem rede e com limites de recursos.
- **Memória e histórico:** memória técnica por projeto, eventos e registros de execução.
- **Modo Resgate:** diagnóstico estático e recomendações priorizadas.
- **CI:** GitHub Actions testa Python 3.11 e 3.13, valida a sintaxe do JavaScript e do inicializador Bash, constrói a imagem Docker e executa testes unitários e de integração.

## Fluxo atual

```text
Navegador -> Dashboard -> FastAPI -> Rotas/Serviços -> Workspace autorizado
                                         |                  |
                                         +-> SQLAlchemy -> SQLite
                                         +-> Ollama local (planejamento)
                                         +-> Docker (pytest isolado)
                                         +-> Eventos e relatórios persistidos
```

## Importação e análise

A importação limita ZIP a 20 MB, até 2.000 entradas, 100 MB descompactados e 10 MB por arquivo. Caminhos absolutos, travessia de diretório, links simbólicos, arquivos protegidos por senha e taxas de compressão excessivas são recusados.

Diretórios comuns de dependências, ambientes virtuais e arquivos com nomes/extensões sensíveis comuns são ignorados. Isso reduz exposição acidental, mas não substitui um scanner de segredos: o usuário deve revisar o arquivo antes de enviá-lo. A análise é estrutural e não comprova que todas as tecnologias foram detectadas.

## Limites de segurança

O caminho persistido é relativo ao workspace e é validado novamente antes das operações de arquivo. A análise não segue links simbólicos. Nenhum script, instalador ou comando arbitrário do projeto é executado pelo agente.

A autenticação é opcional e fica desativada no modo local padrão. Quando habilitada, os projetos são filtrados por proprietário. Projetos criados antes da autenticação podem permanecer sem proprietário e não são automaticamente associados à primeira conta. Faça backup e planeje a migração antes de ativar autenticação em uma base já utilizada.

A aprovação autoriza apenas os arquivos propostos; não comprova que o código esteja correto. O usuário deve revisar as alterações e executar novamente a validação. A aplicação deve permanecer vinculada a `127.0.0.1` durante o uso local. Não exponha a API ou o daemon Docker à internet.

## Planejamento com IA local

O planejador envia ao Ollama local uma solicitação e um contexto textual limitado a 80 KB, excluindo diretórios comuns de dependências/controle de versão e arquivos com nomes indicativos de credenciais. A resposta do modelo é limitada a 1 MB e validada como plano estruturado. O plano permite no máximo 20 arquivos e 200 KB por conteúdo.

A aplicação bloqueia traversal, caminhos absolutos, symlinks, pastas protegidas, nomes sensíveis e caminhos duplicados. A escrita é atômica, usa arquivos temporários exclusivos e preserva permissões. Arquivos existentes acima de 10 MB não são substituídos, para evitar backups grandes em memória. Se uma gravação falhar, as alterações anteriores da mesma operação são revertidas. Não há execução de shell, instalação de pacotes ou alterações automáticas sem aprovação.

## Validação em sandbox

A execução de testes Python é delegada ao Docker por uma lista fixa de argumentos: sem shell, sem rede, filesystem raiz somente leitura, projeto montado como somente leitura, remoção de capabilities, `no-new-privileges`, limites de memória/CPU/processos e timeout de 120 segundos. A saída retida em memória é limitada a 12 KB. Em timeout, o executor tenta encerrar o contêiner identificado pelo arquivo CID.

A imagem `devpilot-sandbox:py311` contém pytest e Node.js. O executor encontra testes Python e executa pytest quando eles existem; também verifica até 100 arquivos JavaScript (`.js`, `.mjs`, `.cjs`) com `node --check` e analisa sintaxe de TypeScript/JSX (`.ts`, `.tsx`, `.mts`, `.cts`, `.jsx`) com `transpileModule`, limitando cada arquivo a 1 MB e o total a 20 MB. Essas verificações analisam sintaxe, não executam o código nem verificam tipos ou fazem build completo. Não há instalação de dependências específicas, execução de scripts npm, compilação TypeScript/TSX nem comandos arbitrários. Docker é requisito para esta operação. A CI constrói a imagem e executa um teste de integração real que confirma a execução de pytest e a montagem somente leitura. Quando os testes falham, a rota de reparo envia a saída limitada ao planejador local e gera uma tarefa pendente de aprovação. Timeout ou resultado inconclusivo não gera proposta de reparo. Após aprovação, a nova validação é uma ação separada e registrada.

## Memória, histórico e Modo Resgate

`ProjectMemory` armazena pares chave/conteúdo por projeto. A análise estrutural atualiza automaticamente o perfil de tecnologias, pontos de entrada e contagem de arquivos; notas manuais são incluídas no contexto do planejador.

`AgentRun` persiste o resumo e os resultados de planejamento, aplicação, diagnóstico e validação. O painel apresenta eventos do projeto e evidências das execuções.

O Modo Resgate identifica documentação, testes, manifestos e marcadores TODO/FIXME/NotImplementedError. Produz achados com severidade, recomendações e pontuação heurística. O diagnóstico é estático, não executa o projeto e não afirma que encontrou todos os defeitos.

## Preparação SaaS inicial

Há cadastro/login, hash PBKDF2-SHA256 com salt, tokens HMAC com expiração, isolamento de projetos por usuário e cotas iniciais. O plano gratuito possui limite de 3 projetos e 10 tarefas de IA por janela de 24 horas; os demais planos configurados no código têm limites provisórios de 25 projetos e 250 tarefas por janela. Esses valores não representam planos comerciais ativos.

Ainda faltam verificação de e-mail, recuperação de senha, rate limiting distribuído, revogação de tokens, organizações, cobrança, portal de assinatura, monitoramento/observabilidade operacional, migrações versionadas, revisão de segurança independente e implantação segura. Portanto, esta base é destinada ao uso local e testes controlados, não deve ser considerada pronta para produção pública.

## Inicialização local

No Windows com Git Bash, execute `bash scripts/iniciar.sh` na raiz do repositório. O inicializador cria o ambiente virtual, instala dependências, tenta construir a imagem Docker quando o serviço está disponível e inicia o servidor em `http://127.0.0.1:8000`. Ollama e Docker são opcionais para abrir o painel, mas necessários para planejamento por IA e validação isolada, respectivamente.

## Próximas fronteiras

1. Teste manual de ponta a ponta no notebook de desenvolvimento, incluindo Docker Desktop e Ollama.
2. Checkpoints persistentes e restauração segura de arquivos.
3. Melhor cobertura para stacks além de Python, sem comandos arbitrários.
4. Rate limiting, recuperação de conta, migrações versionadas e hardening antes de qualquer operação multiusuário pública.
5. Revisão independente de segurança, observabilidade, cobrança e implantação somente depois de validar a experiência local.
