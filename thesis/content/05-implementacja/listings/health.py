@router.get("/health")
async def get_health() -> dict:
    """Żywotność oraz status zależności. ZAWSZE HTTP 200."""
    dependencies = {
        "redis": await check_redis(),
        "spacy_model": check_spacy_model(),
    }
    healthy = all(
        dependency_status == "ok" for dependency_status in dependencies.values()
    )
    status = "ok" if healthy else "degraded"

    return {"status": status, "dependencies": dependencies}
