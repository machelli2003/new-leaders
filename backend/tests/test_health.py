from app import db as database


async def test_health_checks_database_and_sets_security_headers(client, monkeypatch):
    class ReadyDatabase:
        async def command(self, name):
            assert name == "ping"

    monkeypatch.setattr(database, "get_db", lambda: ReadyDatabase())
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["cache-control"] == "no-store"
    assert "Content-Security-Policy" in response.headers


async def test_health_returns_unavailable_when_database_ping_fails(client, monkeypatch):
    class UnavailableDatabase:
        async def command(self, name):
            raise RuntimeError("database unavailable")

    monkeypatch.setattr(database, "get_db", lambda: UnavailableDatabase())
    response = await client.get("/api/v1/health")
    assert response.status_code == 503
    assert response.json()["error"]["message"] == "Database is unavailable"
