def _emit_log_line(request: Request, start: float) -> None:
    metrics: RequestMetrics = getattr(
        request.state, "gateway_metrics", None
    ) or RequestMetrics()

    # preferuj całkowity czas zmierzony przez endpoint, w przeciwnym razie
    # zegar middleware (np. dla bramowego 503 albo żądania spoza czatu)
    if metrics.total_ms <= 0.0:
        metrics.total_ms = (time.perf_counter() - start) * 1000

    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "session_id": metrics.session_id,
        "endpoint": _route_template(request),
        "provider": metrics.provider,
        "model": metrics.model,
        "entities_detected": metrics.entities_detected if metrics.is_chat else None,
        "timing_ms": metrics.timing_ms(),
    }
    print(json.dumps(record), file=sys.stdout)
