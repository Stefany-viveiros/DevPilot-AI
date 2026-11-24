#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -x ".venv/Scripts/python.exe" ]]; then
  PYTHON=".venv/Scripts/python.exe"
elif [[ -x ".venv/bin/python" ]]; then
  PYTHON=".venv/bin/python"
else
  echo "Criando ambiente virtual..."
  if command -v py >/dev/null 2>&1; then
    py -3 -m venv .venv
  else
    python -m venv .venv
  fi
  if [[ -x ".venv/Scripts/python.exe" ]]; then
    PYTHON=".venv/Scripts/python.exe"
  else
    PYTHON=".venv/bin/python"
  fi
fi

echo "Instalando dependências do DevPilot AI..."
"$PYTHON" -m pip install -r backend/requirements.txt

if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then
    echo "Construindo o ambiente isolado de testes..."
    docker build -t devpilot-sandbox:py311 sandbox/
  else
    echo "AVISO: Docker está instalado, mas o serviço não está iniciado. A validação isolada ficará indisponível."
  fi
else
  echo "AVISO: Docker não encontrado. A validação isolada ficará indisponível."
fi

if command -v ollama >/dev/null 2>&1; then
  if ollama list 2>/dev/null | grep -q "qwen2.5-coder:3b"; then
    echo "Modelo local qwen2.5-coder:3b encontrado."
  else
    echo "AVISO: Para habilitar o planejamento por IA, execute em outro terminal: ollama pull qwen2.5-coder:3b"
  fi
else
  echo "AVISO: Ollama não encontrado. O painel abrirá, mas o planejamento por IA ficará indisponível."
fi

echo "Iniciando DevPilot AI em http://127.0.0.1:8000"
exec "$PYTHON" -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
