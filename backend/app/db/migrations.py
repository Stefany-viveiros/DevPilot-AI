from sqlalchemy import Engine, inspect, text

def upgrade_sqlite_schema(engine: Engine) -> None:
    """Aplica ajustes aditivos mínimos em bancos SQLite da versão anterior."""
    if engine.dialect.name != "sqlite":
        return
    inspector = inspect(engine)
    if "projects" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("projects")}
    additions = {
        "analysis_data": "TEXT",
        "last_analyzed_at": "DATETIME",\n        "user_id": "INTEGER REFERENCES users(id)",
    }
    with engine.begin() as connection:
        for column_name, column_type in additions.items():
            if column_name not in existing:
                connection.execute(text(
                    f"ALTER TABLE projects ADD COLUMN {column_name} {column_type}"
                ))
