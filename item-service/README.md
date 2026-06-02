# Item Service

O `item-service` e o servico responsavel pelo ciclo de vida dos itens perdidos e encontrados. Ele cria, lista, consulta, atualiza, muda status, registra historico e publica eventos de dominio para os outros microsservicos.

## Papel na arquitetura

Fluxo principal:

```text
Cliente -> gateway -> item-service -> PostgreSQL do item-service
```

Fluxo de eventos:

```text
item-service -> outbox_events -> RabbitMQ -> matching-service
```

Fluxo interno de recovery:

```text
recovery-case-service -> item-service (/internal/recovery/*)
```

Fluxo de observabilidade:

```text
Prometheus -> item-service (/metrics)
Grafana -> Prometheus
```

O `item-service` nao valida JWT diretamente. A protecao das rotas publicas vem do `gateway`. O `reporter_user_id` e recebido no payload e nao e validado contra o `auth-service`.

## Estrutura

```text
item-service/
├── app/
│   ├── api/
│   ├── core/
│   ├── db/
│   ├── mappers/
│   ├── messaging/
│   ├── models/
│   ├── repositories/
│   ├── schemas/
│   └── services/
├── alembic/
├── tests/
├── Dockerfile
├── requirements.txt
└── .env.example
```

## Arquivos principais

- `app/main.py`: cria a app FastAPI, configura logging, registra rotas, registra `/metrics` e inicia o publisher de outbox.
- `app/api/items.py`: rotas publicas de item.
- `app/api/internal_recovery.py`: rotas internas usadas pelo `recovery-case-service`.
- `app/core/config.py`: variaveis de ambiente do servico.
- `app/core/logging.py`: logs JSON e `X-Correlation-ID`.
- `app/core/metrics.py`: metricas Prometheus e endpoint `/metrics`.
- `app/services/item_service.py`: regra de negocio de item, status, history, outbox e metricas de dominio.
- `app/models/item.py`: modelo `Item`, `Classification` e `ItemStatus`.
- `app/models/item_status_history.py`: historico de status.
- `app/models/outbox.py`: tabela de eventos pendentes de publicacao.
- `app/repositories/*`: acesso ao banco.
- `app/schemas/*`: contratos Pydantic HTTP e de eventos.
- `app/messaging/publisher.py`: publica eventos do outbox no RabbitMQ.
- `alembic/versions/phase0_base.py`: cria `outbox_events` e `processed_events`.
- `alembic/versions/phase2_item_domain.py`: cria `items` e `item_status_history`.

## Endpoints

| Metodo | Rota | Uso |
| --- | --- | --- |
| `GET` | `/health` | healthcheck |
| `GET` | `/metrics` | metricas Prometheus |
| `POST` | `/items` | cria item |
| `GET` | `/items` | lista itens |
| `GET` | `/items/{item_id}` | detalha item |
| `PATCH` | `/items/{item_id}` | atualiza dados |
| `PATCH` | `/items/{item_id}/status` | muda status por fluxo publico |
| `GET` | `/items/{item_id}/history` | lista historico |
| `POST` | `/internal/recovery/open` | move itens para `IN_RECOVERY` |
| `POST` | `/internal/recovery/cancel` | restaura itens para `AVAILABLE` ou `MATCHED` |
| `POST` | `/internal/recovery/complete` | move itens para `RECOVERED` |

## Status e transicoes

Classificacoes:

- `LOST`
- `FOUND`

Status:

- `AVAILABLE`
- `MATCHED`
- `IN_RECOVERY`
- `RECOVERED`
- `CANCELLED`
- `CLOSED`

Transicoes publicas:

| Status atual | Pode ir para |
| --- | --- |
| `AVAILABLE` | `MATCHED`, `CANCELLED`, `CLOSED` |
| `MATCHED` | `AVAILABLE`, `CANCELLED`, `CLOSED` |
| `IN_RECOVERY` | nenhuma transicao publica |
| `RECOVERED` | `CLOSED` |
| `CANCELLED` | nenhuma |
| `CLOSED` | nenhuma |

Transicoes internas:

- `internal_open`: `AVAILABLE` ou `MATCHED` para `IN_RECOVERY`.
- `internal_cancel`: `IN_RECOVERY` para `AVAILABLE` ou `MATCHED`.
- `internal_complete`: `IN_RECOVERY` para `RECOVERED`.

## Eventos

O servico publica eventos por Outbox.

- `ItemCreated` com routing key `item.created`.
- `ItemUpdated` com routing key `item.updated`.

O `matching-service` consome esses eventos para manter `item_projections` e gerar ou expirar matches.

## Monitoramento

O endpoint `GET /metrics` expoe metricas no formato Prometheus. Ele e coletado pelo Prometheus configurado em `infra/prometheus/prometheus.yml`.

Metricas principais:

- `item_service_http_requests_total`
- `item_service_http_request_duration_seconds`
- `item_service_http_requests_in_progress`
- `item_service_items_created_total`
- `item_service_item_status_transitions_total`
- `item_service_item_events_enqueued_total`

O Grafana e provisionado com:

- datasource: `infra/grafana/provisioning/datasources/prometheus.yml`
- dashboards provider: `infra/grafana/provisioning/dashboards/dashboards.yml`
- dashboard: `infra/grafana/dashboards/item-service-overview.json`

## Variaveis de ambiente

| Variavel | Default | Papel |
| --- | --- | --- |
| `SERVICE_NAME` | `item-service` | nome usado em logs e health |
| `SERVICE_VERSION` | `0.1.0` | versao exposta no health |
| `SERVICE_PORT` | `8000` | porta interna do Uvicorn |
| `ENVIRONMENT` | `development` | ambiente logico |
| `LOG_LEVEL` | `INFO` | nivel de log |
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5434/item_service` | conexao com Postgres |
| `DATABASE_ECHO` | `false` | log SQL do SQLAlchemy |
| `RABBITMQ_URL` | `amqp://app:app@localhost:5672/` | conexao com RabbitMQ |
| `RABBITMQ_EVENTS_EXCHANGE` | `domain.events` | exchange principal |
| `RABBITMQ_DEAD_LETTER_EXCHANGE` | `domain.events.dlx` | exchange de DLQ |
| `OUTBOX_PUBLISHER_ENABLED` | `false` | liga o publisher local |
| `METRICS_ENABLED` | `true` | registra `/metrics` |
| `OUTBOX_PUBLISH_POLL_INTERVAL_SECONDS` | `1` | intervalo de polling do outbox |
| `OUTBOX_PUBLISH_BATCH_SIZE` | `50` | tamanho do lote do publisher |
| `OUTBOX_PUBLISH_RETRY_DELAY_SECONDS` | `2` | base do retry |
| `OUTBOX_PUBLISH_MAX_ATTEMPTS` | `10` | limite antes de `EXHAUSTED` |

No `docker-compose.yml`, `DATABASE_URL` aponta para `item-postgres`, `RABBITMQ_URL` aponta para `rabbitmq`, `OUTBOX_PUBLISHER_ENABLED` usa `ITEM_OUTBOX_PUBLISHER_ENABLED` e `METRICS_ENABLED` usa `ITEM_METRICS_ENABLED`.

## Como testar

Subir a stack:

```bash
docker compose up --build -d
```

Validar o servico:

```bash
curl http://localhost:8002/health
curl http://localhost:8002/metrics | grep item_service
```

Validar Prometheus e Grafana:

```bash
curl http://localhost:9090/-/healthy
curl http://localhost:3000/api/health
```

No navegador:

- Prometheus targets: `http://localhost:9090/targets`
- Grafana: `http://localhost:3000`
- Dashboard: `Item Service Overview`

Credenciais padrao do Grafana:

- usuario: `admin`
- senha: `admin`
