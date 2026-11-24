from app.services.rescue import rescue_project

def test_rescue_reports_missing_docs_and_tests(tmp_path):
    (tmp_path / "main.py").write_text("print('hello')\n", encoding="utf-8")
    report = rescue_project(tmp_path)
    titles = {item["title"] for item in report["findings"]}
    assert "Documentação ausente" in titles
    assert "Testes não identificados" in titles
    assert 0 <= report["score"] <= 100

def test_rescue_does_not_execute_project_files(tmp_path):
    marker = tmp_path / "executed.txt"
    (tmp_path / "main.py").write_text(f"from pathlib import Path\nPath({str(marker)!r}).write_text('bad')\n", encoding="utf-8")
    rescue_project(tmp_path)
    assert not marker.exists()
