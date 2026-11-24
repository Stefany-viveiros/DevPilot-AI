from sqlalchemy import create_engine, inspect, text
from app.db.migrations import upgrade_sqlite_schema

def test_upgrade_adds_new_columns_to_existing_sqlite_database():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE projects (
                id INTEGER PRIMARY KEY,
                name VARCHAR(120) NOT NULL,
                description TEXT,
                root_path VARCHAR(500),
                status VARCHAR(30) NOT NULL,
                created_at DATETIME,
                updated_at DATETIME
            )
        """))
    upgrade_sqlite_schema(engine)
    columns = {column["name"] for column in inspect(engine).get_columns("projects")}
    assert "analysis_data" in columns
    assert "last_analyzed_at" in columns
    engine.dispose()
