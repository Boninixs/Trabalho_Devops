def test_metrics_endpoint_exposes_prometheus_payload(client) -> None:
    health_response = client.get("/health")
    assert health_response.status_code == 200

    metrics_response = client.get("/metrics")

    assert metrics_response.status_code == 200
    assert "text/plain" in metrics_response.headers["content-type"]
    assert "item_service_http_requests_total" in metrics_response.text
    assert "item_service_http_request_duration_seconds" in metrics_response.text
    assert "item_service_http_requests_in_progress" in metrics_response.text
    assert 'path="/health"' in metrics_response.text
    assert 'path="/metrics"' not in metrics_response.text
