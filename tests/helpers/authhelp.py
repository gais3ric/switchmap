"""Вход в приложение для тестов: создаёт администратора (если нет) и возвращает клиент с сессией и CSRF."""
ADMIN, PASSWORD = "admin", "adminpass123"


def ensure_admin(m):
    import security
    import sqlite3
    if not security.authenticate(m.DB, ADMIN, PASSWORD):  # копия рабочей базы: там свои пользователи
        with sqlite3.connect(m.DB) as conn:
            conn.execute("DELETE FROM users"); conn.commit()
        security.create_user(m.DB, ADMIN, PASSWORD, "admin")


def login(m, username=ADMIN, password=PASSWORD):
    c = m.app.test_client()
    c.get("/login")
    with c.session_transaction() as s:
        token = s["csrf"]
    r = c.post("/login", data={"username": username, "password": password, "csrf_token": token})
    assert r.status_code == 302, f"вход не удался: {r.status_code}"
    with c.session_transaction() as s:
        c.environ_base["HTTP_X_CSRF_TOKEN"] = s["csrf"]  # токен меняется при входе
    return c


def admin_client(m):
    ensure_admin(m)
    return login(m)
