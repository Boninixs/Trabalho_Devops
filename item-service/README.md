# Item Service

README tecnico exclusivo do `item-service`. Este servico e o dono do dominio de itens perdidos e encontrados: ele persiste itens, controla status, registra historico, gera eventos de dominio por Outbox e fornece endpoints internos usados pelo fluxo de recovery.

## Indice

- [Resumo do servico](#resumo-do-servico)
- [Responsabilidades e limites](#responsabilidades-e-limites)
- [Como se relaciona com os outros servicos](#como-se-relaciona-com-os-outros-servicos)
- [Fluxos principais](#fluxos-principais)
- [Arquitetura interna](#arquitetura-interna)
- [Estrutura de pastas e arquivos](#estrutura-de-pastas-e-arquivos)
- [Modelo de dominio](#modelo-de-dominio)
- [API HTTP](#api-http)
- [Eventos e Outbox](#eventos-e-outbox)
- [Banco de dados e migrations](#banco-de-dados-e-migrations)
- [Observabilidade](#observabilidade)
- [Variaveis de ambiente](#variaveis-de-ambiente)
- [Como executar](#como-executar)
- [Como testar](#como-testar)
- [Pontos de atencao](#pontos-de-atencao)

## Resumo do servico

O `item-service` gerencia o ciclo de vida de itens classificados como `LOST` ou `FOUND`.

Ele e responsavel por:

- Criar itens perdidos ou encontrados.
- Listar itens com filtros.
- Buscar um item por ID.
- Atualizar dados descritivos de um item.
- Alterar status por fluxos publicos permitidos.
- Alterar status por fluxos internos de recovery.
- Registrar historico de todas as mudancas relevantes de status.
- Incrementar versao do agregado a cada alteracao de dominio.
- Criar eventos `ItemCreated` e `ItemUpdated` na tabela `outbox_events`.
- Publicar eventos do Outbox no RabbitMQ quando o publisher esta habilitado.
- Expor healthcheck em `/health`.

Tecnologias usadas neste servico:

- Python 3.11.
- FastAPI.
- SQLAlchemy.
- Alembic.
- PostgreSQL.
- RabbitMQ via `aio-pika`.
- Pydantic e `pydantic-settings`.
- Pytest.

## Responsabilidades e limites

### O que o item-service faz

- Mantem o banco autoritativo de itens no PostgreSQL `item-postgres`.
- Decide se uma transicao de status e valida ou invalida.
- Registra historico em `item_status_history` para auditoria de status.
- Gera eventos de dominio no formato esperado pelo restante do sistema.
- Publica eventos de item para que o `matching-service` consiga manter sua propria projecao.
- Recebe comandos internos do `recovery-case-service` para mudar itens para `IN_RECOVERY`, restaurar para `AVAILABLE` ou `MATCHED`, ou concluir como `RECOVERED`.

### O que o item-service nao faz

- Nao autentica usuario diretamente.
- Nao valida JWT diretamente.
- Nao consulta o `auth-service` para validar se `reporter_user_id` existe.
- Nao calcula matches entre itens.
- Nao abre nem gerencia casos de recuperacao.
- Nao envia notificacoes para usuarios.
- Nao consome eventos de outros servicos no codigo atual.

As rotas publicas devem ser protegidas pelo `gateway`. As rotas `/internal/recovery/*` tambem nao possuem autenticacao propria no codigo do `item-service`; elas devem ficar acessiveis apenas dentro da rede interna da stack e nao devem ser expostas publicamente.

## Como se relaciona com os outros servicos

### Gateway

Fluxo esperado para chamadas externas:

```text
Cliente -> gateway -> item-service
```

O `gateway` e a entrada HTTP publica do sistema. Ele valida ou autoriza o acesso antes de encaminhar chamadas para o `item-service`. Diretamente no `item-service`, as rotas sao expostas como `/items`; pelo gateway, o sistema costuma expor essas operacoes com prefixo publico como `/api/items`.

O `item-service` assume que os dados recebidos ja passaram pela borda correta. Por isso, `reporter_user_id` e aceito no payload e persistido sem consulta ao `auth-service`.

### Auth Service

Nao existe chamada direta do `item-service` para o `auth-service`.

Relacao indireta:

- O `auth-service` autentica usuarios e emite JWT.
- O `gateway` usa esse contexto para proteger rotas.
- O `item-service` recebe `reporter_user_id` como UUID nos payloads.

Se o sistema precisar garantir no proprio `item-service` que o usuario existe ou que o item pertence ao usuario autenticado, isso ainda precisaria ser implementado.

### Matching Service

Fluxo de eventos:

```text
item-service -> outbox_events -> RabbitMQ domain.events -> matching-service.item-events -> matching-service
```

O `item-service` publica:

- `ItemCreated` com routing key `item.created`.
- `ItemUpdated` com routing key `item.updated`.

O `matching-service` consome esses eventos para manter sua propria projecao de itens e sugerir matches entre itens `LOST` e `FOUND`. O `item-service` nao calcula o match; ele apenas fornece os eventos de origem.

### Recovery Case Service

Fluxo interno:

```text
recovery-case-service -> item-service /internal/recovery/*
```

Quando um caso de recuperacao e aberto, cancelado ou concluido, o `recovery-case-service` chama endpoints internos do `item-service` para refletir a mudanca no status dos itens relacionados.

Endpoints usados nesse relacionamento:

- `POST /internal/recovery/open`: move itens para `IN_RECOVERY`.
- `POST /internal/recovery/cancel`: restaura itens para `AVAILABLE` ou `MATCHED`.
- `POST /internal/recovery/complete`: move itens para `RECOVERED`.

No `docker-compose.yml`, o `recovery-case-service` recebe `ITEM_SERVICE_BASE_URL=http://item-service:8000`, apontando para o nome DNS interno do container.

### RabbitMQ

O RabbitMQ e o broker de eventos do monorepo. O `item-service` usa RabbitMQ somente para publicar eventos do seu Outbox.

Exchange principal:

- `domain.events`

Exchange de dead letter:

- `domain.events.dlx`

Filas declaradas pelo publisher do `item-service`:

- `matching-service.item-events`, ligada a `item.created` e `item.updated`.
- `recovery-case-service.match-events`, ligada a `match.accepted`.
- `matching-service.item-events.dlq`, DLQ dos eventos de item.
- `recovery-case-service.match-events.dlq`, DLQ dos eventos de match aceito.
- `domain.events.audit`, ligada a todas as routing keys conhecidas.

Mesmo que o `item-service` publique apenas eventos de item, o publisher tambem declara parte da topologia compartilhada do broker.

## Fluxos principais

### Criacao de item

Fluxo executado por `POST /items`:

```text
HTTP POST /items
-> app/api/items.py
-> create_item em app/services/item_service.py
-> cria Item com status AVAILABLE e version 1
-> salva Item no banco
-> registra ItemStatusHistory com from_status NULL e to_status AVAILABLE
-> cria evento ItemCreated no Outbox
-> commit da transacao
-> retorna ItemResponse
```

Pontos importantes:

- O ID do item e gerado com `uuid4()`.
- O status inicial sempre e `AVAILABLE`.
- A versao inicial sempre e `1`.
- O evento `ItemCreated` e gravado na mesma transacao do item.
- A publicacao no RabbitMQ nao acontece dentro da request; ela e feita pelo publisher assincrono do Outbox.

### Listagem de itens

Fluxo executado por `GET /items`:

```text
HTTP GET /items
-> monta ItemFilters com query params
-> repositories/item_repository.py aplica filtros SQL
-> ordena por created_at desc
-> retorna lista de ItemResponse
```

Filtros suportados:

- `classification`.
- `category`.
- `color`.
- `location`.
- `status`.
- `reporter_user_id`.

Filtros textuais como `category`, `color` e `location` usam `ilike`, portanto fazem busca parcial case-insensitive no PostgreSQL.

### Busca por ID

Fluxo executado por `GET /items/{item_id}`:

```text
HTTP GET /items/{item_id}
-> retrieve_item
-> get_item_or_raise
-> session.get(Item, item_id)
-> 200 com ItemResponse ou 404 se nao existir
```

### Atualizacao parcial de dados

Fluxo executado por `PATCH /items/{item_id}`:

```text
HTTP PATCH /items/{item_id}
-> update_item
-> valida se item existe
-> pega campos enviados no payload
-> rejeita payload vazio
-> rejeita payload sem alteracao efetiva
-> altera somente campos enviados
-> incrementa version
-> atualiza updated_at
-> cria evento ItemUpdated no Outbox
-> commit
-> retorna ItemResponse
```

Campos atualizaveis:

- `title`.
- `description`.
- `category`.
- `color`.
- `location_description`.
- `approximate_date`.
- `reporter_user_id`.

O status nao e alterado por essa rota; status tem rota e regras proprias.

### Transicao publica de status

Fluxo executado por `PATCH /items/{item_id}/status`:

```text
HTTP PATCH /items/{item_id}/status
-> update_item_status
-> bloqueia tentativa publica de IN_RECOVERY ou RECOVERED
-> apply_status_transition modo public
-> validate_transition
-> altera status
-> incrementa version
-> registra historico
-> cria ItemUpdated no Outbox
-> commit
-> retorna ItemResponse
```

Transicoes publicas permitidas:

| Status atual | Pode ir para |
| --- | --- |
| `AVAILABLE` | `MATCHED`, `CANCELLED`, `CLOSED` |
| `MATCHED` | `AVAILABLE`, `CANCELLED`, `CLOSED` |
| `IN_RECOVERY` | nenhuma transicao publica |
| `RECOVERED` | `CLOSED` |
| `CANCELLED` | nenhuma |
| `CLOSED` | nenhuma |

Regras adicionais:

- Nao e permitido mudar para o mesmo status atual.
- `CANCELLED` e `CLOSED` sao status terminais para o fluxo de matching.
- `IN_RECOVERY` e `RECOVERED` sao reservados para o fluxo interno de recovery.

### Fluxo interno de recovery

O fluxo interno e chamado pelo `recovery-case-service`, nao por clientes externos.

#### Abertura de recovery

Endpoint:

```http
POST /internal/recovery/open
```

Regra:

- Permite mover itens `AVAILABLE` ou `MATCHED` para `IN_RECOVERY`.
- Rejeita qualquer outro status.
- Remove IDs duplicados internamente mantendo a ordem logica enviada.
- Se algum item nao existir, a operacao falha.

#### Cancelamento de recovery

Endpoint:

```http
POST /internal/recovery/cancel
```

Regra:

- Permite mover itens `IN_RECOVERY` para `AVAILABLE` ou `MATCHED`.
- `target_status` default e `AVAILABLE`.
- O schema rejeita `target_status` diferente de `AVAILABLE` ou `MATCHED`.

#### Conclusao de recovery

Endpoint:

```http
POST /internal/recovery/complete
```

Regra:

- Permite mover itens `IN_RECOVERY` para `RECOVERED`.
- Rejeita itens que nao estejam em `IN_RECOVERY`.

### Publicacao de evento por Outbox

Fluxo de evento:

```text
create/update/status/recovery
-> record_item_event
-> to_item_event_payload
-> EventEnvelope
-> OutboxEvent status PENDING
-> commit junto com a alteracao de dominio
-> OutboxPublisher busca PENDING/FAILED disponiveis
-> publica no RabbitMQ com mensagem persistente
-> marca PUBLISHED ou FAILED/EXHAUSTED
```

Esse padrao evita publicar evento no RabbitMQ sem que a alteracao no banco tenha sido confirmada.

## Arquitetura interna

O servico segue uma arquitetura em camadas simples:

```text
FastAPI app
-> API routers
-> Services
-> Repositories
-> SQLAlchemy models
-> PostgreSQL

Services
-> Mappers
-> Pydantic schemas

Services
-> Outbox
-> OutboxPublisher
-> RabbitMQ
```

### Camada API

Arquivos em `app/api/` recebem requests HTTP, validam payloads por schemas Pydantic, transformam excecoes de dominio em `HTTPException` e retornam responses.

Essa camada nao contem regra de negocio complexa. Ela delega para `app/services/item_service.py`.

### Camada Service

`app/services/item_service.py` contem a regra de negocio principal:

- Criacao de item.
- Atualizacao parcial.
- Transicoes publicas.
- Transicoes internas de recovery.
- Validacao de status.
- Registro de historico.
- Geracao de eventos de dominio.

### Camada Repository

Arquivos em `app/repositories/` isolam operacoes de banco:

- Buscar por ID.
- Listar por filtros.
- Adicionar entidades.
- Listar eventos pendentes de Outbox.
- Marcar eventos como publicados, falhos ou esgotados.

### Camada Model

Arquivos em `app/models/` representam tabelas SQLAlchemy.

### Camada Schema

Arquivos em `app/schemas/` representam contratos HTTP e contratos de eventos.

### Camada Messaging

Arquivos em `app/messaging/` implementam Outbox, topologia RabbitMQ, publisher e helpers de idempotencia.

## Estrutura de pastas e arquivos

```text
item-service/
|-- .env.example
|-- Dockerfile
|-- README.md
|-- alembic.ini
|-- alembic/
|   |-- env.py
|   |-- script.py.mako
|   `-- versions/
|       |-- phase0_base.py
|       `-- phase2_item_domain.py
|-- app/
|   |-- __init__.py
|   |-- api/
|   |-- core/
|   |-- db/
|   |-- mappers/
|   |-- messaging/
|   |-- models/
|   |-- repositories/
|   |-- schemas/
|   |-- services/
|   `-- main.py
|-- pytest.ini
|-- requirements.txt
`-- tests/
```

### Raiz do item-service

| Arquivo | Funcao |
| --- | --- |
| `.env.example` | Exemplo de variaveis para rodar o servico isolado/localmente. |
| `Dockerfile` | Build da imagem Python 3.11, instala dependencias, copia app e Alembic, roda migrations e inicia Uvicorn. |
| `README.md` | Este README tecnico especifico do `item-service`. |
| `alembic.ini` | Configuracao base do Alembic; `env.py` substitui a URL pela `DATABASE_URL` real. |
| `pytest.ini` | Configura descoberta de testes e markers `integration` e `contract`. |
| `requirements.txt` | Dependencias Python exclusivas do `item-service`. |

### `app/main.py`

Cria a aplicacao FastAPI.

Responsabilidades:

- Carrega settings com `get_settings()`.
- Configura logging JSON.
- Instancia `OutboxPublisher`.
- Define o `lifespan` do FastAPI.
- Inicia o publisher se `OUTBOX_PUBLISHER_ENABLED=true`.
- Para o publisher no shutdown.
- Registra middleware de logging de request.
- Inclui `api_router`.

### `app/api/`

| Arquivo | Funcao |
| --- | --- |
| `health.py` | Expoe `GET /health` e retorna payload de saude com status, service, version e environment. |
| `items.py` | Expoe rotas publicas de CRUD parcial, listagem, detalhe, status e historico de itens. |
| `internal_recovery.py` | Expoe rotas internas usadas pelo `recovery-case-service` para abrir, cancelar e completar recovery. |
| `router.py` | Agrega routers de health, items e internal recovery em um unico `api_router`. |

### `app/core/`

| Arquivo | Funcao |
| --- | --- |
| `config.py` | Define `Settings` com variaveis de ambiente e defaults usando `pydantic-settings`; `get_settings()` usa cache com `lru_cache`. |
| `exceptions.py` | Define excecoes de dominio: `ItemNotFoundError`, `InvalidItemTransitionError`, `InvalidItemUpdateError`. |
| `logging.py` | Configura logs JSON, `X-Correlation-ID` e middleware de logging HTTP. |

### `app/db/`

| Arquivo | Funcao |
| --- | --- |
| `base.py` | Importa os models para que `Base.metadata` conheca todas as tabelas. |
| `database.py` | Reexporta `Base` e `engine`. |
| `session.py` | Cria `engine`, `SessionLocal` e dependency `get_db()` para FastAPI. |

Detalhes de `session.py`:

- Usa `create_engine(settings.database_url)`.
- Usa `pool_pre_ping=True` para validar conexoes antes do uso.
- Usa `expire_on_commit=False` para manter objetos acessiveis apos commit.
- Fecha a sessao ao final da request por meio de `get_db()`.

### `app/mappers/`

| Arquivo | Funcao |
| --- | --- |
| `.gitkeep` | Mantem a pasta versionada mesmo se ficar vazia em algum momento. |
| `item_mapper.py` | Converte models SQLAlchemy para schemas Pydantic de resposta e payload de evento. |

Funcoes:

- `to_item_response(item)` retorna `ItemResponse`.
- `to_item_history_response(history_entry)` retorna `ItemStatusHistoryResponse`.
- `to_item_event_payload(item)` retorna `ItemEventPayload`.

### `app/messaging/`

| Arquivo | Funcao |
| --- | --- |
| `outbox.py` | Cria registros `OutboxEvent` a partir de `EventEnvelope` ou `BrokerMessage`. |
| `publisher.py` | Loop assincrono que busca eventos pendentes/falhos no banco e publica no RabbitMQ. |
| `topology.py` | Define exchanges, routing keys, filas, DLQs e fila de auditoria. |
| `idempotency.py` | Helpers para verificar e registrar eventos processados em `processed_events`; preparado para consumidores idempotentes. |

### `app/models/`

| Arquivo | Funcao |
| --- | --- |
| `common.py` | Define `Base`, `UUIDPrimaryKeyMixin` e `TimestampMixin`. |
| `item.py` | Define enums `Classification`, `ItemStatus` e model `Item`. |
| `item_status_history.py` | Define model `ItemStatusHistory`, usado para historico de mudancas de status. |
| `outbox.py` | Define model `OutboxEvent`, usado pelo padrao Outbox. |
| `processed_event.py` | Define model `ProcessedEvent`, usado para idempotencia de consumo de eventos. |

### `app/repositories/`

| Arquivo | Funcao |
| --- | --- |
| `item_repository.py` | Adiciona item, busca por ID, busca lista por IDs e lista itens com filtros. |
| `item_status_history_repository.py` | Adiciona entrada de historico e lista historico por item. |
| `outbox_repository.py` | Lista eventos pendentes/falhos com lock e atualiza status de publicacao. |
| `processed_event_repository.py` | Consulta/adiciona registros em `processed_events`. |

Detalhe importante do Outbox:

- `list_pending_outbox_events()` usa `with_for_update(skip_locked=True)`, permitindo que mais de um publisher possa operar sem processar o mesmo evento simultaneamente.

### `app/schemas/`

| Arquivo | Funcao |
| --- | --- |
| `events.py` | Define envelope generico de evento (`EventEnvelope`) e mensagem para broker (`BrokerMessage`). |
| `item.py` | Define requests, filtros e responses da API HTTP de itens e recovery. |
| `item_event.py` | Define payload e envelopes especificos `ItemCreatedEnvelope` e `ItemUpdatedEnvelope`. |

### `app/services/`

| Arquivo | Funcao |
| --- | --- |
| `health_service.py` | Monta payload retornado em `/health`. |
| `item_service.py` | Implementa a regra de negocio principal do dominio de itens. |

### `alembic/`

| Arquivo | Funcao |
| --- | --- |
| `env.py` | Configura Alembic para usar `DATABASE_URL` e `Base.metadata`. |
| `script.py.mako` | Template usado pelo Alembic para novas revisions. |
| `versions/phase0_base.py` | Cria infraestrutura base: `outbox_events` e `processed_events`. |
| `versions/phase2_item_domain.py` | Cria dominio de item: `items`, `item_status_history`, enums e indices. |

### `tests/`

| Arquivo | Funcao |
| --- | --- |
| `.gitkeep` | Mantem a pasta versionada. |
| `conftest.py` | Configura `TestClient`, fixtures de banco de integracao e override de `get_db`. |
| `contracts/test_item_events.py` | Valida contrato dos eventos `ItemCreated` e `ItemUpdated`. |
| `integration/test_item_api.py` | Testa API real com banco PostgreSQL configurado por `ITEM_SERVICE_TEST_DATABASE_URL`. |
| `unit/test_item_schemas.py` | Testa validacoes dos schemas Pydantic. |
| `unit/test_item_service.py` | Testa regras de dominio de criacao e transicao de status com session fake. |
| `unit/test_outbox_publisher.py` | Testa serializacao e comportamento do publisher de Outbox. |

## Modelo de dominio

### Classification

Enum definido em `app/models/item.py`.

| Valor | Significado |
| --- | --- |
| `LOST` | Item perdido por um usuario. |
| `FOUND` | Item encontrado por um usuario. |

### ItemStatus

Enum definido em `app/models/item.py`.

| Valor | Significado |
| --- | --- |
| `AVAILABLE` | Item disponivel para matching ou fluxo normal. |
| `MATCHED` | Item associado a um possivel match. |
| `IN_RECOVERY` | Item envolvido em um caso de recuperacao aberto. |
| `RECOVERED` | Item recuperado/concluido no fluxo de recovery. |
| `CANCELLED` | Item cancelado e fora do fluxo. |
| `CLOSED` | Item encerrado e fora do fluxo. |

### Item

Tabela: `items`.

Campos principais:

- `id`: UUID primario.
- `classification`: `LOST` ou `FOUND`.
- `title`: titulo curto do item.
- `description`: descricao detalhada.
- `category`: categoria textual.
- `color`: cor textual.
- `location_description`: local aproximado.
- `approximate_date`: data aproximada da perda ou achado.
- `reporter_user_id`: UUID do usuario que reportou.
- `status`: status atual.
- `version`: versao do agregado.
- `created_at`: data de criacao.
- `updated_at`: data de atualizacao.

Indices criados por migration:

- `classification`.
- `category`.
- `color`.
- `reporter_user_id`.
- `status`.

### ItemStatusHistory

Tabela: `item_status_history`.

Registra mudancas de status.

Campos principais:

- `id`: UUID primario.
- `item_id`: FK para `items.id`, com `ondelete=CASCADE`.
- `from_status`: status anterior ou `NULL` quando o item foi criado.
- `to_status`: novo status.
- `reason`: motivo informado pelo fluxo.
- `actor_user_id`: usuario/ator que causou a transicao, quando informado.
- `occurred_at`: data/hora da transicao.

### OutboxEvent

Tabela: `outbox_events`.

Guarda eventos que precisam ser publicados no RabbitMQ.

Campos principais:

- `id`: UUID do evento, tambem usado como `event_id` no envelope.
- `event_type`: tipo do evento, por exemplo `ItemCreated`.
- `aggregate_id`: ID do item.
- `aggregate_version`: versao do item no momento do evento.
- `exchange_name`: exchange RabbitMQ.
- `routing_key`: routing key de publicacao.
- `correlation_id`: ID de correlacao.
- `causation_id`: ID de causalidade, quando existir.
- `payload`: JSONB com dados do item.
- `headers`: headers adicionais da mensagem.
- `occurred_at`: quando o evento ocorreu.
- `available_at`: quando o evento fica elegivel para publicacao.
- `published_at`: quando foi publicado com sucesso.
- `status`: `PENDING`, `FAILED`, `PUBLISHED` ou `EXHAUSTED`.
- `publish_attempts`: quantidade de tentativas.
- `last_error`: ultimo erro de publicacao.

### ProcessedEvent

Tabela: `processed_events`.

Existe para suportar idempotencia de consumidores de eventos. No codigo atual do `item-service`, ela esta preparada por infraestrutura, mas o servico nao possui consumidor ativo de eventos.

## API HTTP

### Health

| Metodo | Rota | Descricao |
| --- | --- | --- |
| `GET` | `/health` | Retorna status basico do servico. |

Exemplo de resposta:

```json
{
  "status": "ok",
  "service": "item-service",
  "version": "0.1.0",
  "environment": "development"
}
```

### Itens

| Metodo | Rota | Descricao | Possiveis erros tratados |
| --- | --- | --- | --- |
| `POST` | `/items` | Cria item. | Erros de validacao Pydantic retornam 422. |
| `GET` | `/items` | Lista itens com filtros opcionais. | Erros de validacao Pydantic retornam 422. |
| `GET` | `/items/{item_id}` | Busca item por ID. | 404 se item nao existir. |
| `PATCH` | `/items/{item_id}` | Atualiza campos descritivos. | 404 se item nao existir; 400 para update invalido. |
| `PATCH` | `/items/{item_id}/status` | Altera status por fluxo publico. | 404 se item nao existir; 400 para transicao invalida. |
| `GET` | `/items/{item_id}/history` | Lista historico de status. | 404 se item nao existir. |

Exemplo de criacao:

```bash
curl -X POST http://localhost:8002/items \
  -H 'Content-Type: application/json' \
  -d '{
    "classification": "LOST",
    "title": "Carteira preta",
    "description": "Carteira perdida na biblioteca",
    "category": "Carteira",
    "color": "Preta",
    "location_description": "Biblioteca",
    "approximate_date": "2026-04-10",
    "reporter_user_id": "6f8f0be4-1dcb-421c-9f2a-2db26d8bb089"
  }'
```

Exemplo de listagem com filtros:

```bash
curl 'http://localhost:8002/items?classification=LOST&status=AVAILABLE&category=Carteira'
```

Exemplo de atualizacao parcial:

```bash
curl -X PATCH http://localhost:8002/items/<item_id> \
  -H 'Content-Type: application/json' \
  -d '{"title": "Carteira preta atualizada", "color": "Preta"}'
```

Exemplo de mudanca publica de status:

```bash
curl -X PATCH http://localhost:8002/items/<item_id>/status \
  -H 'Content-Type: application/json' \
  -d '{
    "status": "MATCHED",
    "reason": "Match confirmado manualmente",
    "actor_user_id": "6f8f0be4-1dcb-421c-9f2a-2db26d8bb089"
  }'
```

### Rotas internas de recovery

| Metodo | Rota | Descricao |
| --- | --- | --- |
| `POST` | `/internal/recovery/open` | Move itens para `IN_RECOVERY`. |
| `POST` | `/internal/recovery/cancel` | Move itens de `IN_RECOVERY` para `AVAILABLE` ou `MATCHED`. |
| `POST` | `/internal/recovery/complete` | Move itens de `IN_RECOVERY` para `RECOVERED`. |

Exemplo de abertura:

```bash
curl -X POST http://localhost:8002/internal/recovery/open \
  -H 'Content-Type: application/json' \
  -d '{
    "item_ids": ["<lost_item_id>", "<found_item_id>"],
    "reason": "Caso de recuperacao aberto"
  }'
```

Exemplo de cancelamento:

```bash
curl -X POST http://localhost:8002/internal/recovery/cancel \
  -H 'Content-Type: application/json' \
  -d '{
    "item_ids": ["<lost_item_id>", "<found_item_id>"],
    "reason": "Caso cancelado",
    "target_status": "AVAILABLE"
  }'
```

Exemplo de conclusao:

```bash
curl -X POST http://localhost:8002/internal/recovery/complete \
  -H 'Content-Type: application/json' \
  -d '{
    "item_ids": ["<lost_item_id>", "<found_item_id>"],
    "reason": "Caso concluido"
  }'
```

## Eventos e Outbox

### Eventos publicados

| Evento | Routing key | Quando e criado | Consumidor principal |
| --- | --- | --- | --- |
| `ItemCreated` | `item.created` | Ao criar um item. | `matching-service` |
| `ItemUpdated` | `item.updated` | Ao atualizar dados ou status de um item. | `matching-service` |

### Envelope do evento

Formato serializado pelo publisher:

```json
{
  "event_id": "uuid",
  "event_type": "ItemCreated",
  "aggregate_id": "uuid-do-item",
  "aggregate_version": 1,
  "occurred_at": "2026-04-10T12:00:00+00:00",
  "correlation_id": "uuid",
  "causation_id": null,
  "payload": {
    "id": "uuid-do-item",
    "classification": "LOST",
    "title": "Carteira preta",
    "description": "Carteira perdida na biblioteca",
    "category": "Carteira",
    "color": "Preta",
    "location_description": "Biblioteca",
    "approximate_date": "2026-04-10",
    "reporter_user_id": "uuid-do-usuario",
    "status": "AVAILABLE",
    "version": 1,
    "created_at": "2026-04-10T12:00:00+00:00",
    "updated_at": "2026-04-10T12:00:00+00:00"
  }
}
```

### Estados do Outbox

| Status | Significado |
| --- | --- |
| `PENDING` | Evento criado e ainda nao publicado. |
| `FAILED` | Tentativa falhou, mas o evento pode ser tentado novamente depois de `available_at`. |
| `PUBLISHED` | Evento publicado com sucesso. |
| `EXHAUSTED` | Evento falhou ate atingir `OUTBOX_PUBLISH_MAX_ATTEMPTS`. |

### Retry de publicacao

O retry usa base configuravel e crescimento exponencial:

```text
retry_delay = min(60, OUTBOX_PUBLISH_RETRY_DELAY_SECONDS * 2^publish_attempts)
```

O limite maximo hardcoded no codigo e `60` segundos por tentativa.

Se uma publicacao falha dentro de um batch, o publisher registra a falha, faz commit e interrompe o batch atual. O proximo ciclo tentara novamente eventos elegiveis.

## Banco de dados e migrations

### Banco do servico

No Docker Compose, o banco do `item-service` e `item-postgres`:

```text
Host interno: item-postgres
Porta interna: 5432
Porta no host: ${ITEM_DB_PORT:-5434}
Database: ${ITEM_DB_NAME:-item_service}
User: ${ITEM_DB_USER:-postgres}
Password: ${ITEM_DB_PASSWORD:-postgres}
```

### Tabelas

| Tabela | Funcao |
| --- | --- |
| `items` | Estado atual dos itens. |
| `item_status_history` | Historico das transicoes de status. |
| `outbox_events` | Eventos a publicar/publicados no RabbitMQ. |
| `processed_events` | Controle de idempotencia para consumidores de eventos. |

### Migrations existentes

| Revision | Arquivo | O que cria |
| --- | --- | --- |
| `phase0_base` | `alembic/versions/phase0_base.py` | `outbox_events` e `processed_events`. |
| `phase2_item_domain` | `alembic/versions/phase2_item_domain.py` | `items`, `item_status_history`, enums e indices. |

### Execucao de migrations

No container, o `Dockerfile` inicia com:

```bash
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${SERVICE_PORT:-8000}
```

Ou seja, ao subir o container, as migrations rodam antes da API iniciar.

Para rodar manualmente dentro da pasta `item-service`:

```bash
alembic upgrade head
```

## Observabilidade

### Healthcheck

Endpoint:

```http
GET /health
```

Usado pelo Docker Compose para saber se o container esta saudavel.

### Logging

O servico usa logs JSON em stdout.

Campos comuns:

- `timestamp`.
- `level`.
- `logger`.
- `message`.
- `service`.
- `correlation_id`.
- `method`.
- `path`.
- `status_code`.
- `duration_ms`.
- `exception`, quando houver erro.

O middleware `RequestLoggingMiddleware`:

- Le `X-Correlation-ID` da request.
- Gera um UUID se o header nao vier.
- Retorna `X-Correlation-ID` na response.
- Registra `request_completed` ou `request_failed`.

## Variaveis de ambiente

Existem dois contextos de configuracao:

- Variaveis lidas diretamente pelo codigo do `item-service`, definidas em `app/core/config.py` e exemplificadas em `item-service/.env.example`.
- Variaveis da raiz do monorepo, definidas em `.env.example` e usadas pelo `docker-compose.yml` para montar containers, portas e URLs.

### Variaveis lidas pelo item-service

| Variavel | Default no codigo | Exemplo em `item-service/.env.example` | Uso |
| --- | --- | --- | --- |
| `SERVICE_NAME` | `item-service` | `item-service` | Nome do servico em logs, health e titulo FastAPI. |
| `SERVICE_VERSION` | `0.1.0` | `0.1.0` | Versao retornada no health e metadata da API. |
| `SERVICE_PORT` | `8000` | `8000` | Porta usada pelo Uvicorn dentro do container/processo. |
| `ENVIRONMENT` | `development` | `development` | Nome logico do ambiente retornado no health. |
| `LOG_LEVEL` | `INFO` | `INFO` | Nivel do logger raiz. Exemplos: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5434/item_service` | igual ao default | URL SQLAlchemy do PostgreSQL. |
| `DATABASE_ECHO` | `false` | `false` | Se `true`, SQLAlchemy loga SQL gerado. Util para debug, ruidoso em producao. |
| `RABBITMQ_URL` | `amqp://app:app@localhost:5672/` | igual ao default | URL de conexao AMQP com RabbitMQ. |
| `RABBITMQ_EVENTS_EXCHANGE` | `domain.events` | `domain.events` | Exchange topic principal para eventos de dominio. |
| `RABBITMQ_DEAD_LETTER_EXCHANGE` | `domain.events.dlx` | `domain.events.dlx` | Exchange usada como dead letter. |
| `OUTBOX_PUBLISHER_ENABLED` | `true` | `false` | Liga/desliga o loop de publicacao do Outbox no processo do `item-service`. |
| `OUTBOX_PUBLISH_POLL_INTERVAL_SECONDS` | `1.0` | `1` | Intervalo de espera quando nao ha eventos pendentes. |
| `OUTBOX_PUBLISH_BATCH_SIZE` | `50` | `50` | Quantidade maxima de eventos buscados por ciclo do publisher. |
| `OUTBOX_PUBLISH_RETRY_DELAY_SECONDS` | `2.0` | `2` | Base do calculo de retry exponencial. |
| `OUTBOX_PUBLISH_MAX_ATTEMPTS` | `10` | `10` | Numero maximo de tentativas antes de marcar evento como `EXHAUSTED`. |

Observacao sobre `OUTBOX_PUBLISHER_ENABLED`:

- No codigo, o default e `true`.
- Em `item-service/.env.example`, esta como `false` para facilitar execucao local sem RabbitMQ.
- No `docker-compose.yml`, o valor vem de `ITEM_OUTBOX_PUBLISHER_ENABLED`, com default `true`.

### Variaveis do Docker Compose relacionadas ao item-service

Essas variaveis ficam no `.env` da raiz do monorepo e sao usadas pelo `docker-compose.yml`.

| Variavel | Default | Uso no Compose |
| --- | --- | --- |
| `ITEM_DB_NAME` | `item_service` | Nome do database criado no container `item-postgres`. |
| `ITEM_DB_USER` | `postgres` | Usuario do PostgreSQL do `item-service`. |
| `ITEM_DB_PASSWORD` | `postgres` | Senha do PostgreSQL do `item-service`. |
| `ITEM_DB_PORT` | `5434` | Porta no host que aponta para `item-postgres:5432`. |
| `ITEM_OUTBOX_PUBLISHER_ENABLED` | `true` | Alimenta `OUTBOX_PUBLISHER_ENABLED` dentro do container `item-service`. |
| `ITEM_SERVICE_HTTP_PORT` | `8002` | Porta no host que aponta para `item-service:8000`. |
| `ENVIRONMENT` | `development` | Propagada para o backend service env compartilhado. |
| `LOG_LEVEL` | `INFO` | Propagada para o backend service env compartilhado. |
| `RABBITMQ_DEFAULT_USER` | `app` | Usuario do RabbitMQ e parte de `RABBITMQ_URL`. |
| `RABBITMQ_DEFAULT_PASS` | `app` | Senha do RabbitMQ e parte de `RABBITMQ_URL`. |
| `RABBITMQ_EVENTS_EXCHANGE` | `domain.events` | Propagada para o `item-service`. |
| `RABBITMQ_DEAD_LETTER_EXCHANGE` | `domain.events.dlx` | Propagada para o `item-service`. |
| `OUTBOX_PUBLISH_POLL_INTERVAL_SECONDS` | `1` | Propagada para publisher do `item-service` e outros servicos com Outbox. |
| `OUTBOX_PUBLISH_BATCH_SIZE` | `50` | Propagada para publisher do `item-service` e outros servicos com Outbox. |
| `OUTBOX_PUBLISH_RETRY_DELAY_SECONDS` | `2` | Propagada para publisher do `item-service` e outros servicos com Outbox. |
| `OUTBOX_PUBLISH_MAX_ATTEMPTS` | `10` | Propagada para publisher do `item-service` e outros servicos com Outbox. |

### Exemplo de `.env` local isolado para item-service

Arquivo dentro de `item-service/.env`:

```env
SERVICE_NAME=item-service
SERVICE_VERSION=0.1.0
SERVICE_PORT=8000
ENVIRONMENT=development
LOG_LEVEL=INFO
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5434/item_service
DATABASE_ECHO=false
RABBITMQ_URL=amqp://app:app@localhost:5672/
RABBITMQ_EVENTS_EXCHANGE=domain.events
RABBITMQ_DEAD_LETTER_EXCHANGE=domain.events.dlx
OUTBOX_PUBLISHER_ENABLED=false
OUTBOX_PUBLISH_POLL_INTERVAL_SECONDS=1
OUTBOX_PUBLISH_BATCH_SIZE=50
OUTBOX_PUBLISH_RETRY_DELAY_SECONDS=2
OUTBOX_PUBLISH_MAX_ATTEMPTS=10
```

### Recomendacoes para producao

- Trocar senhas default de PostgreSQL e RabbitMQ.
- Usar secrets do ambiente ou do orquestrador, nao versionar `.env` real.
- Manter `OUTBOX_PUBLISHER_ENABLED=true` em pelo menos uma instancia responsavel por publicar eventos.
- Evitar `DATABASE_ECHO=true` em producao.
- Garantir que `/internal/recovery/*` nao seja acessivel pela internet.

## Como executar

### Executar pela stack completa

Na raiz do monorepo:

```bash
cp .env.example .env
docker compose up --build -d
```

Validar containers:

```bash
docker compose ps
```

URLs principais:

- Gateway: `http://localhost:8000`.
- Item Service direto: `http://localhost:8002`.
- Item Service health: `http://localhost:8002/health`.

### Executar somente dependencias e rodar local

Se quiser rodar a API localmente fora do container, mantenha PostgreSQL e RabbitMQ acessiveis e use um ambiente Python:

```bash
cd item-service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Se `OUTBOX_PUBLISHER_ENABLED=false`, o servico cria eventos na tabela `outbox_events`, mas nao tenta publicar no RabbitMQ.

## Como testar

### Testes unitarios

Na pasta `item-service`:

```bash
pytest tests/unit -q
```

Esses testes nao exigem PostgreSQL real.

### Testes de contrato

```bash
pytest tests/contracts -q
```

Validam se os eventos gerados pelo servico continuam compativeis com os envelopes esperados.

### Testes de integracao

Os testes de integracao exigem uma URL de banco real em `ITEM_SERVICE_TEST_DATABASE_URL`.

Exemplo:

```bash
export ITEM_SERVICE_TEST_DATABASE_URL='postgresql+psycopg://postgres:postgres@localhost:5434/item_service_test'
pytest tests/integration -q
```

O `conftest.py` roda Alembic no banco de teste e trunca as tabelas entre cenarios.

### Todos os testes do item-service

```bash
pytest -q
```

Se `ITEM_SERVICE_TEST_DATABASE_URL` nao estiver configurada, os testes de integracao sao pulados.

### CI

A pipeline GitHub Actions do monorepo executa os unitarios do `item-service` com:

```bash
pytest tests/unit -q
```

O job do item-service fica separado dos demais servicos para facilitar diagnostico e branch protection.

## Pontos de atencao

- O `item-service` nao valida JWT; a protecao deve acontecer no `gateway` ou em infraestrutura.
- `reporter_user_id` e aceito como UUID, mas nao e validado contra o `auth-service`.
- As rotas `/internal/recovery/*` nao devem ser expostas publicamente.
- O Outbox so publica no RabbitMQ se `OUTBOX_PUBLISHER_ENABLED=true`.
- Se o publisher estiver desligado, eventos ficam acumulados como `PENDING`.
- Eventos `EXHAUSTED` precisam de observabilidade operacional e possivel reprocessamento manual.
- `processed_events` existe para idempotencia, mas o servico nao possui consumidor ativo no codigo atual.
- `DATABASE_ECHO=true` pode vazar SQL e aumentar muito o volume de logs.
- Alteracoes em payload de evento devem ser acompanhadas por testes de contrato.
- Alteracoes em status ou transicoes devem atualizar testes unitarios e, se necessario, consumidores downstream.
