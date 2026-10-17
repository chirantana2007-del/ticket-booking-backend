def test_test_database_is_ready(client):
    """Smoke test: the test DB works and has 500 seats."""
    r = client.get("/seats")
    assert r.status_code == 200
    assert len(r.json()) == 500
