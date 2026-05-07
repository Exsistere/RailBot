from app.services.db.connection import db_manager

if db_manager.is_available():
    conn = db_manager.get_connection()
    with conn.cursor() as c:
        c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
        tables = [r[0] for r in c.fetchall()]
    print("Tables:", tables)
    expected = {"users", "conversations", "messages", "interactions", "tool_executions", "pnrs", "user_pnrs"}
    missing = expected - set(tables)
    extra   = set(tables) - expected
    print("Missing:", missing or "none")
    print("Extra (unexpected):", extra or "none")
    print("Schema OK!" if not missing else "SCHEMA INCOMPLETE")
else:
    print("DB not available — skipping schema check")
