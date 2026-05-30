# Achados e Perdidos em Microsserviços

Sistema de achados e perdidos com arquitetura orientada a microsserviços. O fluxo principal passa por cadastro e login, criação de itens perdidos/encontrados, sugestão automática de match e abertura de caso de recuperação quando um match é aceito.

## Visão rápida

- `gateway`: entrada HTTP única do sistema.
- `auth-service`: cadastro, login e JWT.
- `item-service`: cadastro, consulta, atualização e histórico de itens.
- `matching-service`: consome eventos de itens e sugere matches entre `LOST` e `FOUND`.
- `recovery-case-service`: consome `MatchAccepted` e orquestra a recuperação.
- Um PostgreSQL por serviço e RabbitMQ para eventos assíncronos.

## Principais características

- APIs em `FastAPI` com `Python 3.11`.
- Comunicação síncrona via HTTP e assíncrona via RabbitMQ.
- Padrão `Outbox` para publicar eventos com segurança.
- Idempotência de consumo com `processed_events`.
- Saga de recuperação entre `recovery-case-service` e `item-service`.
- JWT no `gateway` e correlação por `X-Correlation-ID`.
- DLQ para consumidores e retry finito na publicação de eventos.

## Stack

- Python 3.11
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL
- RabbitMQ
- Docker Compose
- Pytest

## Estrutura

```text
.
├── gateway/
├── auth-service/
├── item-service/
├── matching-service/
├── recovery-case-service/
├── infra/rabbitmq/
├── tests/e2e/
├── scripts/
└── docs/
```

## Como executar

### Pré-requisitos

- Docker
- Docker Compose
- Python 3.11, se quiser rodar testes fora dos containers

### Passo a passo

1. Copie as variáveis de ambiente:

```bash
cp .env.example .env
```

2. Suba toda a stack:

```bash
docker compose up --build -d
```

3. Confira se tudo ficou saudável:

```bash
docker compose ps
```

4. Acesse os serviços:

- Gateway: `http://localhost:8000`
- Auth: `http://localhost:8001`
- Item: `http://localhost:8002`
- Matching: `http://localhost:8003`
- Recovery Case: `http://localhost:8004`
- RabbitMQ Management: `http://localhost:15672`

As migrações dos serviços com banco são executadas automaticamente na inicialização dos containers.

### Migrações manuais

Se precisar rodar manualmente:

```bash
./scripts/migrate_all.sh
```

## Como testar

### Testes por serviço

Execute no diretório de cada serviço:

```bash
cd auth-service && pytest -q
cd item-service && pytest -q
cd matching-service && pytest -q
cd recovery-case-service && pytest -q
cd gateway && pytest -q
```

### Teste ponta a ponta

Com a stack já subida:

```bash
./scripts/run_e2e.sh
```

O fluxo E2E valida autenticação, criação de itens, geração de match, aceitação, abertura automática do caso, cancelamento, reabertura, conclusão e regras de proteção contra duplicidade.

## Rotas públicas principais

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET|POST /api/items`
- `GET|PATCH /api/items/{id}`
- `GET /api/matches`
- `POST /api/matches/{id}/accept`
- `POST /api/matches/{id}/reject`
- `GET /api/recovery-cases`
- `POST /api/recovery-cases/{id}/cancel`
- `POST /api/recovery-cases/{id}/complete`
- `GET /health`

O `gateway` bloqueia rotas internas como `/api/internal/*`.

## Eventos do domínio

Routing keys publicadas no broker:

- `item.created`
- `item.updated`
- `match.suggested`
- `match.accepted`
- `match.rejected`
- `recovery_case.opened`
- `recovery_case.cancelled`
- `recovery_case.completed`

## Documentação complementar

- [Arquitetura](docs/architecture.md)
- [Desenvolvimento](docs/development.md)
- [Eventos](docs/events.md)
- [Gateway](docs/api-gateway.md)
- [Auth Service](docs/auth-service.md)
- [Item Service](docs/item-service.md)
- [Matching Service](docs/matching-service.md)
- [Recovery Case Service](docs/recovery-case-service.md)
- [Testes Manuais Pelo Terminal](docs/testes-manuais-pelo-terminal.md)
