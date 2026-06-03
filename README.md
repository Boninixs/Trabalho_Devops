# Achados e Perdidos em Microsserviços

Sistema de achados e perdidos com arquitetura orientada a microsserviços. O fluxo principal passa por cadastro e login, criação de itens perdidos/encontrados, sugestão automática de match e abertura de caso de recuperação quando um match é aceito.

## Visão rápida

- `gateway`: entrada HTTP única do sistema.
- `auth-service`: cadastro, login e JWT.
- `item-service`: cadastro, consulta, atualização e histórico de itens.
- `matching-service`: consome eventos de itens e sugere matches entre `LOST` e `FOUND`.
- `recovery-case-service`: consome `MatchAccepted` e orquestra a recuperação.
- `prometheus`: coleta métricas do `matching-service`.
- `grafana`: exibe dashboard do `matching-service`.
- Um PostgreSQL por serviço e RabbitMQ para eventos assíncronos.

## Principais características

- APIs em `FastAPI` com `Python 3.11`.
- Comunicação síncrona via HTTP e assíncrona via RabbitMQ.
- Padrão `Outbox` para publicar eventos com segurança.
- Idempotência de consumo com `processed_events`.
- Saga de recuperação entre `recovery-case-service` e `item-service`.
- JWT no `gateway` e correlação por `X-Correlation-ID`.
- DLQ para consumidores e retry finito na publicação de eventos.
- Métricas Prometheus expostas pelo `matching-service` em `/metrics`.
- Dashboard Grafana provisionado automaticamente para o `matching-service`.

## Stack

- Python 3.11
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL
- RabbitMQ
- Prometheus
- Grafana
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
├── infra/grafana/
├── infra/prometheus/
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
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

Credenciais padrão do Grafana:

- Usuário: `${GRAFANA_ADMIN_USER:-admin}`
- Senha: `${GRAFANA_ADMIN_PASSWORD:-admin}`

As migrações dos serviços com banco são executadas automaticamente na inicialização dos containers.

## Monitoramento

O monitoramento provisionado nesta stack cobre o `matching-service`.

- O `matching-service` expõe métricas Prometheus em `GET /metrics` diretamente na porta do serviço.
- O Prometheus faz scrape de `http://matching-service:8000/metrics` dentro da rede Docker.
- O Grafana sobe com datasource para o Prometheus já configurado.
- O dashboard `Matching Service Overview` é carregado automaticamente no Grafana.

Arquivos principais:

- `infra/prometheus/prometheus.yml`
- `infra/grafana/provisioning/datasources/prometheus.yml`
- `infra/grafana/provisioning/dashboards/dashboards.yml`
- `infra/grafana/dashboards/matching-service-overview.json`

### Migrações manuais

Se precisar rodar manualmente:

```bash
./scripts/migrate_all.sh
```

## CI/CD e proteção da main

O repositório possui pipeline de CI em `.github/workflows/ci.yml` para validar pull requests para a `main`.
Esta configuração cobre o gate de CI; a etapa de CD deve ser adicionada quando houver registry, ambiente de deploy e secrets definidos.

- A pipeline roda em `pull_request` para `main`, em `push` para `main` e também manualmente por `workflow_dispatch`.
- Cada microservice/gateway executa seus testes unitários em um job separado: `auth-service`, `item-service`, `matching-service`, `recovery-case-service` e `gateway`.
- O job agregado `unit-tests / required` só passa quando todos os jobs unitários passam.

Para bloquear pushes diretos na `main`, configure no GitHub um Branch Protection Rule ou Ruleset para a branch `main`:

- Ative `Require a pull request before merging`.
- Ative `Require status checks to pass before merging`.
- Marque como obrigatório o check `unit-tests / required`.
- Ative `Require branches to be up to date before merging`, se quiser exigir PR atualizado com a `main` antes do merge.
- Desative force pushes e branch deletion.
- Não permita bypass da regra, exceto se houver um administrador explicitamente responsável por emergências.

Essa configuração é necessária porque o GitHub Actions valida a qualidade do PR, mas o bloqueio de push direto é uma regra da plataforma GitHub, não do arquivo YAML da pipeline.

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
