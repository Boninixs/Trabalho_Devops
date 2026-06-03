# Matching Service

O `matching-service` e o microsservico responsavel por consumir eventos de itens perdidos/encontrados, manter uma projecao local desses itens e gerar sugestoes de match entre itens `LOST` e `FOUND`.

Este README foca em observabilidade e CI/CD: como o endpoint `/metrics` funciona, como o Prometheus coleta esses dados, como o Grafana usa essas metricas e como a pipeline do GitHub Actions valida e publica a imagem Docker do servico.

## Arquivos principais

| Arquivo | Responsabilidade |
| --- | --- |
| `app/core/metrics.py` | Define as metricas Prometheus, o middleware HTTP e a rota `GET /metrics`. |
| `app/main.py` | Registra as metricas quando `METRICS_ENABLED=true`. |
| `app/services/matching_service.py` | Incrementa metricas de matches sugeridos, decisoes e eventos de match enfileirados. |
| `app/messaging/consumer.py` | Incrementa metricas de eventos de item consumidos com resultado `processed` ou `failed`. |
| `../infra/prometheus/prometheus.yml` | Configura o Prometheus para fazer scrape do `matching-service`. |
| `../infra/grafana/provisioning/datasources/prometheus.yml` | Configura o Prometheus como datasource do Grafana. |
| `../infra/grafana/provisioning/dashboards/dashboards.yml` | Configura o carregamento automatico dos dashboards. |
| `../infra/grafana/dashboards/matching-service-overview.json` | Dashboard principal do `matching-service`. |
| `../.github/workflows/matching-service-ci.yml` | Pipeline de testes, build Docker e push para DockerHub. |

## Como o `/metrics` funciona

O endpoint `GET /metrics` e registrado por `register_metrics(app)` em `app/core/metrics.py`. Ele retorna o resultado de `generate_latest()` da biblioteca `prometheus_client`, usando o content type oficial do Prometheus.

Na pratica, a resposta e um texto no formato exposition do Prometheus. Esse formato contem linhas com metadados e linhas com valores numericos, por exemplo:

```text
# HELP matching_service_http_requests_total Total HTTP requests handled by matching-service.
# TYPE matching_service_http_requests_total counter
matching_service_http_requests_total{method="GET",path="/health",status_code="200"} 1.0
```

O arquivo `/metrics` nao e um arquivo fisico no disco. Ele e uma rota HTTP gerada em tempo de execucao pelo FastAPI. Cada vez que o Prometheus acessa `http://matching-service:8000/metrics`, o servico calcula a resposta atual a partir do registry de metricas em memoria.

## Habilitacao das metricas

As metricas sao controladas pela variavel `METRICS_ENABLED` do `matching-service`.

No `.env.example` do servico:

```env
METRICS_ENABLED=true
```

No Docker Compose raiz, essa configuracao e repassada por:

```env
MATCHING_METRICS_ENABLED=true
```

Quando `METRICS_ENABLED=true`, o `app/main.py` chama `register_metrics(app)` e registra:

- O middleware que mede requests HTTP.
- A rota `GET /metrics`.

Quando `METRICS_ENABLED=false`, a rota `/metrics` nao e registrada. Nesse caso, o Prometheus nao consegue coletar metricas do servico e o alvo tende a aparecer como indisponivel ou com erro de scrape.

## Middleware de metricas HTTP

O `PrometheusMetricsMiddleware` mede todas as rotas HTTP, exceto a propria rota `/metrics`.

Essa exclusao e importante porque o Prometheus acessa `/metrics` periodicamente. Se o scrape fosse contabilizado como request normal, o monitoramento geraria trafego artificial nas metricas do proprio servico.

Fluxo do middleware:

1. Recebe a request.
2. Ignora a request se o path for `/metrics`.
3. Incrementa `matching_service_http_requests_in_progress`.
4. Mede o tempo com `time.perf_counter()`.
5. Executa a rota real do FastAPI.
6. Registra a duracao em `matching_service_http_request_duration_seconds`.
7. Incrementa `matching_service_http_requests_total` com metodo, path e status code.
8. Decrementa `matching_service_http_requests_in_progress`.

Se uma excecao ocorrer durante o processamento, o middleware registra a request como status `500` e relanca a excecao.

O path usado nas labels tenta ser o template da rota FastAPI. Por exemplo, uma chamada para `/matches/123` tende a ser registrada como `/matches/{match_id}`. Isso evita criar uma serie diferente para cada ID.

## Metricas expostas pelo matching-service

### `matching_service_http_requests_total`

Tipo: `Counter`.

Conta o total de requests HTTP processadas pelo servico.

Labels:

- `method`: metodo HTTP, como `GET` ou `POST`.
- `path`: rota processada, preferencialmente no formato template.
- `status_code`: status HTTP retornado.

Exemplo de uso:

```promql
sum(rate(matching_service_http_requests_total[5m])) by (path)
```

Essa query mostra a taxa de requests por rota nos ultimos 5 minutos.

### `matching_service_http_request_duration_seconds`

Tipo: `Histogram`.

Mede a latencia das requests HTTP.

Labels:

- `method`: metodo HTTP.
- `path`: rota processada.

Buckets configurados:

```text
0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0 segundos
```

Exemplo de uso para percentil 95:

```promql
histogram_quantile(0.95, sum(rate(matching_service_http_request_duration_seconds_bucket[5m])) by (le))
```

Essa query estima o P95 de latencia das requests do servico.

### `matching_service_http_requests_in_progress`

Tipo: `Gauge`.

Mostra quantas requests HTTP estao em andamento no momento.

Esse valor sobe no inicio da request e desce quando a request termina.

### `matching_service_item_events_consumed_total`

Tipo: `Counter`.

Conta eventos de item consumidos pelo RabbitMQ.

Labels:

- `event_type`: tipo do evento recebido, como `ItemCreated` ou `ItemUpdated`.
- `result`: resultado do processamento, atualmente `processed` ou `failed`.

Onde e incrementada:

- `app/messaging/consumer.py`, dentro de `_process_message()`.

Exemplo de uso:

```promql
sum(increase(matching_service_item_events_consumed_total[24h])) by (event_type, result)
```

Essa query mostra quantos eventos foram processados ou falharam nas ultimas 24 horas.

### `matching_service_matches_suggested_total`

Tipo: `Counter`.

Conta quantas sugestoes de match foram criadas ou reativadas pelo servico.

Onde e incrementada:

- `app/services/matching_service.py`, depois que `consume_item_event()` gera novas sugestoes.

Exemplo de uso:

```promql
increase(matching_service_matches_suggested_total[24h])
```

Essa query mostra quantos matches foram sugeridos nas ultimas 24 horas.

### `matching_service_match_decisions_total`

Tipo: `Counter`.

Conta decisoes tomadas sobre sugestoes de match.

Labels:

- `decision`: decisao registrada, atualmente `accepted` ou `rejected`.

Onde e incrementada:

- `accept_match()` registra `accepted`.
- `reject_match()` registra `rejected`.

Exemplo de uso:

```promql
sum(increase(matching_service_match_decisions_total[24h])) by (decision)
```

Essa query mostra quantos matches foram aceitos ou rejeitados nas ultimas 24 horas.

### `matching_service_match_events_enqueued_total`

Tipo: `Counter`.

Conta eventos de match gravados no outbox para publicacao futura no RabbitMQ.

Labels:

- `event_type`: tipo do evento enfileirado, como `MatchSuggested`, `MatchAccepted` ou `MatchRejected`.

Onde e incrementada:

- Ao sugerir matches: `MatchSuggested`.
- Ao aceitar match: `MatchAccepted`.
- Ao rejeitar match: `MatchRejected`.

Exemplo de uso:

```promql
sum(increase(matching_service_match_events_enqueued_total[24h])) by (event_type)
```

Essa query mostra quantos eventos de match entraram no outbox nas ultimas 24 horas.

## Metricas padrao da biblioteca prometheus_client

A resposta de `/metrics` tambem pode conter metricas padrao do runtime Python, geradas pelo `prometheus_client`, alem das metricas customizadas do `matching-service`.

Exemplos comuns:

- `python_gc_objects_collected_total`
- `python_info`
- `process_cpu_seconds_total`
- `process_resident_memory_bytes`

Essas metricas ajudam a observar o processo Python, mas o dashboard atual do projeto foca nas metricas customizadas do `matching-service`.

## Como o Prometheus funciona neste projeto

O Prometheus roda como container no `docker-compose.yml` usando a imagem `prom/prometheus:v2.53.0`.

Configuracao principal:

```yaml
prometheus:
  image: prom/prometheus:v2.53.0
  command:
    - "--config.file=/etc/prometheus/prometheus.yml"
    - "--storage.tsdb.path=/prometheus"
  volumes:
    - prometheus_data:/prometheus
    - ./infra/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
  depends_on:
    matching-service:
      condition: service_healthy
```

O arquivo `../infra/prometheus/prometheus.yml` define dois jobs:

```yaml
scrape_configs:
  - job_name: prometheus
    static_configs:
      - targets:
          - prometheus:9090

  - job_name: matching-service
    metrics_path: /metrics
    static_configs:
      - targets:
          - matching-service:8000
```

O job `matching-service` faz scrape de `http://matching-service:8000/metrics` dentro da rede Docker. Esse hostname funciona porque os containers estao na mesma rede do Compose e o nome do servico e resolvido pelo DNS interno do Docker.

Configuracoes globais:

- `scrape_interval: 15s`: Prometheus coleta metricas a cada 15 segundos.
- `evaluation_interval: 15s`: regras de avaliacao, se existirem, rodam a cada 15 segundos.

## Como verificar o Prometheus

Com a stack em execucao:

```bash
docker compose up --build -d
```

Verifique a saude do Prometheus:

```bash
curl http://localhost:9090/-/healthy
```

Verifique se o `matching-service` esta expondo metricas:

```bash
curl http://localhost:8003/metrics
```

Abra o Prometheus no navegador:

```text
http://localhost:9090
```

Consultas uteis no Prometheus:

```promql
up{job="matching-service"}
```

```promql
sum(rate(matching_service_http_requests_total[5m]))
```

```promql
histogram_quantile(0.95, sum(rate(matching_service_http_request_duration_seconds_bucket[5m])) by (le))
```

Se `up{job="matching-service"}` retornar `1`, o Prometheus esta coletando o alvo. Se retornar `0`, o scrape falhou.

## Como o Grafana funciona neste projeto

O Grafana roda como container no `docker-compose.yml` usando a imagem `grafana/grafana:11.1.0`.

Configuracao principal:

```yaml
grafana:
  image: grafana/grafana:11.1.0
  environment:
    GF_SECURITY_ADMIN_USER: ${GRAFANA_ADMIN_USER:-admin}
    GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD:-admin}
    GF_USERS_ALLOW_SIGN_UP: "false"
  volumes:
    - grafana_data:/var/lib/grafana
    - ./infra/grafana/provisioning:/etc/grafana/provisioning:ro
    - ./infra/grafana/dashboards:/var/lib/grafana/dashboards:ro
  depends_on:
    prometheus:
      condition: service_started
```

O Grafana e provisionado automaticamente por arquivos versionados no repositorio.

### Datasource

O arquivo `../infra/grafana/provisioning/datasources/prometheus.yml` cria um datasource chamado `Prometheus` com UID `prometheus`:

```yaml
datasources:
  - name: Prometheus
    uid: prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
```

O `access: proxy` significa que o navegador nao acessa o Prometheus diretamente. O Grafana recebe a requisicao do usuario e faz a consulta ao Prometheus pelo backend do proprio Grafana.

### Dashboard

O arquivo `../infra/grafana/provisioning/dashboards/dashboards.yml` instrui o Grafana a carregar dashboards a partir de `/var/lib/grafana/dashboards`.

Esse caminho recebe o volume:

```yaml
./infra/grafana/dashboards:/var/lib/grafana/dashboards:ro
```

O dashboard principal e `../infra/grafana/dashboards/matching-service-overview.json`, com titulo `Matching Service Overview`.

Paineis atuais:

| Painel | Query PromQL | O que mostra |
| --- | --- | --- |
| `Matching Service Up` | `max(up{job="matching-service"})` | Se o Prometheus consegue coletar o servico. |
| `Requests / Second` | `sum(rate(matching_service_http_requests_total[5m]))` | Taxa geral de requests por segundo. |
| `HTTP Latency P95` | `histogram_quantile(0.95, sum(rate(matching_service_http_request_duration_seconds_bucket[5m])) by (le))` | Percentil 95 de latencia HTTP. |
| `Matches Suggested (24h)` | `increase(matching_service_matches_suggested_total[24h])` | Sugestoes de match criadas ou reativadas em 24h. |
| `Request Rate by Path` | `sum(rate(matching_service_http_requests_total[5m])) by (path)` | Volume de requests por rota. |
| `Item Events Consumed (24h)` | `sum(increase(matching_service_item_events_consumed_total[24h])) by (event_type, result)` | Eventos de item processados ou com falha. |
| `Match Decisions (24h)` | `sum(increase(matching_service_match_decisions_total[24h])) by (decision)` | Matches aceitos e rejeitados. |
| `Match Events Enqueued (24h)` | `sum(increase(matching_service_match_events_enqueued_total[24h])) by (event_type)` | Eventos de match gravados no outbox. |

## Como verificar o Grafana

Com a stack em execucao, acesse:

```text
http://localhost:3000
```

Credenciais padrao, se nao forem alteradas no `.env` raiz:

```text
Usuario: admin
Senha: admin
```

Depois do login:

1. Abra `Dashboards`.
2. Entre na pasta `Microservices`.
3. Abra `Matching Service Overview`.
4. Verifique se o painel `Matching Service Up` mostra `1`.

Se o dashboard nao aparecer, verifique:

- Se o volume `./infra/grafana/provisioning` esta montado no container.
- Se o volume `./infra/grafana/dashboards` esta montado no container.
- Se o container `grafana` foi reiniciado depois de alterar arquivos de provisioning.

## Pipeline do GitHub Actions

A pipeline especifica do `matching-service` esta em `../.github/workflows/matching-service-ci.yml`.

Ela e disparada por:

- `pull_request` para `main` ou `develop`, quando houver mudancas em `matching-service/**` ou no proprio workflow.
- `push` para `main` ou `develop`, com os mesmos filtros de path.
- `workflow_dispatch`, para execucao manual.

No disparo manual por `workflow_dispatch`, os testes rodam normalmente. Os jobs Docker continuam respeitando seus filtros: build sem push apenas em PR e publicacao apenas em `push` para `main`.

Permissao configurada:

```yaml
permissions:
  contents: read
```

Essa permissao e suficiente porque o workflow nao cria commits nem tags. O push para DockerHub usa credenciais externas via secrets.

### Job `matching-service / tests`

Nome tecnico: `tests`.

Responsabilidades:

- Sobe um PostgreSQL `postgres:16-alpine` como service container.
- Configura banco `matching_service_test`.
- Instala Python `3.11`.
- Usa cache de `pip` baseado em `matching-service/requirements.txt`.
- Instala dependencias com `pip install -r requirements.txt`.
- Executa `pytest -q` dentro de `matching-service`.

Variaveis importantes no job:

```env
ENVIRONMENT=test
DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/matching_service_test
MATCHING_SERVICE_TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/matching_service_test
EVENT_CONSUMER_ENABLED=false
OUTBOX_PUBLISHER_ENABLED=false
METRICS_ENABLED=true
```

O consumer RabbitMQ e o publisher de outbox ficam desligados nos testes para evitar dependencia de RabbitMQ no CI.

### Job `matching-service / docker build`

Nome tecnico: `docker-build`.

Quando roda:

- Apenas em `pull_request`.
- Apenas depois que `tests` passa.

Responsabilidades:

- Configura Docker Buildx.
- Faz build da imagem usando `./matching-service/Dockerfile`.
- Nao faz push da imagem.

Tag local usada no PR:

```text
matching-service:pr-<numero-do-pr>
```

Esse job valida que a imagem Docker continua buildavel antes do merge, sem expor secrets para PRs.

### Job `matching-service / dockerhub publish`

Nome tecnico: `docker-publish`.

Quando roda:

- Apenas em `push` para `refs/heads/main`.
- Apenas depois que `tests` passa.

Na pratica, se a `main` estiver protegida contra pushes diretos, esse `push` representa o merge aprovado de um pull request.

Responsabilidades:

- Configura Docker Buildx.
- Valida que os secrets do DockerHub existem.
- Faz login no DockerHub.
- Gera metadados e tags da imagem.
- Builda e publica a imagem.

Secrets obrigatorios no repositorio GitHub:

```text
DOCKERHUB_USERNAME
DOCKERHUB_TOKEN
```

Imagem publicada:

```text
docker.io/<DOCKERHUB_USERNAME>/matching-service:latest
docker.io/<DOCKERHUB_USERNAME>/matching-service:sha-<commit-curto>
```

### Relacao com tags semanticas

O workflow `matching-service-ci.yml` publica a imagem com `latest` e `sha-<commit-curto>`. A validacao de Conventional Commits e a criacao de tags semanticas ficam em outro workflow: `../.github/workflows/semantic-tags.yml`.

Isso separa responsabilidades:

- `matching-service-ci.yml`: qualidade do servico, build Docker e publicacao no DockerHub.
- `semantic-tags.yml`: validacao de Conventional Commits e criacao de tag semantica.

## Comandos uteis locais

Os comandos abaixo assumem que voce esta na raiz do repositorio, exceto quando indicado.

Rodar testes do servico:

```bash
cd matching-service
pytest -q
```

Build local da imagem Docker:

```bash
docker build -t matching-service:local ./matching-service
```

Subir a stack completa:

```bash
docker compose up --build -d
```

Verificar containers:

```bash
docker compose ps
```

Ver metricas diretamente:

```bash
curl http://localhost:8003/metrics
```

Consultar Prometheus:

```text
http://localhost:9090
```

Acessar Grafana:

```text
http://localhost:3000
```
