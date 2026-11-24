import json
import re
import shutil
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import AUTH_REQUIRED, MAX_ARCHIVE_BYTES, WORKSPACE_DIR
from app.db.session import get_db
from app.models.event import ProjectEvent
from app.models.project import Project
from app.models.agent_task import AgentTask
from app.models.agent_approval import AgentApproval
from app.models.project_memory import ProjectMemory
from app.models.agent_run import AgentRun
from app.models.user import User
from app.schemas.agent import TaskCreate, TaskRead, AgentPlan, MemoryWrite, MemoryRead
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse
from app.services.auth import hash_password, verify_password, issue_token, read_token, _secret
from app.services.agent import AgentProviderError, create_plan, apply_plan
from app.services.rescue import rescue_project
from app.services.sandbox import SandboxUnavailable, run_python_tests
from app.schemas.project import (
    ProjectAnalysisRead, ProjectCreate, ProjectEventRead, ProjectRead, ProjectUpdate,
)
from app.services.project_analysis import analyze_project
from app.services.project_import import ArchiveValidationError, extract_project_archive

_current_user_id: ContextVar[int | None] = ContextVar("devpilot_user_id", default=None)
_bearer = HTTPBearer(auto_error=False)

async def enforce_auth(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)):
    if not AUTH_REQUIRED:
        return
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Autenticação necessária.", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = read_token(credentials.credentials)
        user = db.get(User, int(payload["sub"]))
    except (ValueError, RuntimeError, KeyError, TypeError):
        raise HTTPException(status_code=401, detail="Token inválido ou expirado.", headers={"WWW-Authenticate": "Bearer"})
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Conta inativa ou inexistente.")
    token = _current_user_id.set(user.id)
    try:
        yield
    finally:
        _current_user_id.reset(token)

auth_router = APIRouter(prefix="/auth", tags=["Autenticação"])
router = APIRouter(dependencies=[Depends(enforce_auth)])

@auth_router.post("/register", response_model=TokenResponse, status_code=201)
def register_account(payload: RegisterRequest, db: Session = Depends(get_db)):
    if not AUTH_REQUIRED:
        raise HTTPException(status_code=503, detail="Ative DEVPILOT_AUTH_REQUIRED para habilitar contas.")
    try:
        _secret()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    email = payload.email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(status_code=422, detail="Informe um e-mail válido.")
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="Este e-mail já possui uma conta.")
    user = User(email=email, password_hash=hash_password(payload.password), plan="free")
    db.add(user)
    db.commit()
    db.refresh(user)
    try:
        token = issue_token(user.id, user.email)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"access_token": token, "plan": user.plan}

@auth_router.post("/login", response_model=TokenResponse)
def login_account(payload: LoginRequest, db: Session = Depends(get_db)):
    if not AUTH_REQUIRED:
        raise HTTPException(status_code=503, detail="Ative DEVPILOT_AUTH_REQUIRED para habilitar contas.")
    try:
        _secret()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    email = payload.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")
    try:
        token = issue_token(user.id, user.email)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"access_token": token, "plan": user.plan}


def record_event(db: Session, project_id: int, event_type: str, summary: str, details: dict | None = None) -> None:
    db.add(ProjectEvent(
        project_id=project_id,
        event_type=event_type,
        summary=summary,
        details_json=json.dumps(details, ensure_ascii=False) if details is not None else None,
    ))

def get_existing_project(project_id: int, db: Session) -> Project:
    project = db.get(Project, project_id)
    user_id = _current_user_id.get()
    if project is None or (user_id is not None and project.user_id != user_id):
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    return project

def get_project_directory(project: Project) -> Path:
    if not project.root_path:
        raise HTTPException(status_code=409, detail="Este projeto ainda não possui arquivos importados.")
    candidate = (WORKSPACE_DIR / project.root_path).resolve()
    if not candidate.is_relative_to(WORKSPACE_DIR) or not candidate.is_dir():
        raise HTTPException(status_code=404, detail="A pasta autorizada do projeto não foi encontrada.")
    return candidate

@router.get("/health", tags=["Sistema"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "DevPilot AI"}

@router.get("/projects", response_model=list[ProjectRead], tags=["Projetos"])
def list_projects(db: Session = Depends(get_db)) -> list[Project]:
    query = select(Project).order_by(Project.created_at.desc())
    if _current_user_id.get() is not None:
        query = query.where(Project.user_id == _current_user_id.get())
    return list(db.scalars(query).all())

@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED, tags=["Projetos"])
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> Project:
    user_id = _current_user_id.get()
    if user_id is not None:
        user = db.get(User, user_id)
        limit = 3 if user.plan == "free" else 25
        existing = len(db.scalars(select(Project.id).where(Project.user_id == user_id)).all())
        if existing >= limit:
            raise HTTPException(status_code=429, detail=f"Limite do plano {user.plan}: {limit} projetos.")
    project = Project(user_id=user_id, name=payload.name.strip(), description=payload.description, root_path=payload.root_path)
    db.add(project)
    db.flush()
    record_event(db, project.id, "project_created", "Projeto cadastrado.")
    db.commit()
    db.refresh(project)
    return project

@router.post("/projects/import", response_model=ProjectRead, status_code=status.HTTP_201_CREATED, tags=["Projetos"])
async def import_project(
    name: str = Form(min_length=1, max_length=120),
    description: str | None = Form(default=None, max_length=2000),
    archive: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> Project:
    if not name.strip():
        raise HTTPException(status_code=422, detail="Informe um nome para o projeto.")
    if not archive.filename or Path(archive.filename).suffix.lower() != ".zip":
        raise HTTPException(status_code=422, detail="Envie um arquivo com extensão .zip.")
    if archive.content_type not in {"application/zip", "application/x-zip-compressed", "application/octet-stream"}:
        raise HTTPException(status_code=415, detail="O tipo de arquivo enviado não é aceito.")
    archive_bytes = await archive.read(MAX_ARCHIVE_BYTES + 1)
    await archive.close()
    try:
        result = extract_project_archive(archive_bytes)
    except ArchiveValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    user_id = _current_user_id.get()
    if user_id is not None:
        user = db.get(User, user_id)
        limit = 3 if user.plan == "free" else 25
        existing = len(db.scalars(select(Project.id).where(Project.user_id == user_id)).all())
        if existing >= limit:
            raise HTTPException(status_code=429, detail=f"Limite do plano {user.plan}: {limit} projetos.")
    project = Project(
        name=name.strip(),
        description=description,
        root_path=result.storage_path,
        user_id=user_id,
        status="imported",
    )
    try:
        db.add(project)
        db.flush()
        record_event(db, project.id, "project_imported", "Arquivos do projeto importados com segurança.", {
            "files_imported": result.files_imported,
            "files_skipped": result.files_skipped,
            "bytes_imported": result.bytes_imported,
        })
        db.commit()
        db.refresh(project)
        return project
    except Exception:
        db.rollback()
        shutil.rmtree(WORKSPACE_DIR / result.storage_path, ignore_errors=True)
        raise

@router.get("/projects/{project_id}", response_model=ProjectRead, tags=["Projetos"])
def get_project(project_id: int, db: Session = Depends(get_db)) -> Project:
    return get_existing_project(project_id, db)

@router.patch("/projects/{project_id}", response_model=ProjectRead, tags=["Projetos"])
def update_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)) -> Project:
    project = get_existing_project(project_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "name" and value is not None:
            value = value.strip()
        if value is not None or field != "name":
            setattr(project, field, value)
    record_event(db, project.id, "project_updated", "Dados do projeto atualizados.")
    db.commit()
    db.refresh(project)
    return project

@router.post("/projects/{project_id}/analyze", response_model=ProjectAnalysisRead, tags=["Análise"])
def analyze_registered_project(project_id: int, db: Session = Depends(get_db)) -> dict:
    project = get_existing_project(project_id, db)
    root = get_project_directory(project)
    try:
        analysis = analyze_project(root)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Não foi possível ler a estrutura do projeto.") from exc
    analyzed_at = datetime.now(timezone.utc)
    project.analysis_data = json.dumps(analysis, ensure_ascii=False)
    project.last_analyzed_at = analyzed_at
    project.status = "analyzed"
    record_event(db, project.id, "project_analyzed", "Estrutura e tecnologias do projeto analisadas.", {
        "total_files": analysis["total_files"],
        "detected_technologies": analysis["detected_technologies"],
    })
    db.commit()
    return {"project_id": project.id, "project_name": project.name, "analyzed_at": analyzed_at, **analysis}

@router.get("/projects/{project_id}/analysis", response_model=ProjectAnalysisRead, tags=["Análise"])
def get_project_analysis(project_id: int, db: Session = Depends(get_db)) -> dict:
    project = get_existing_project(project_id, db)
    if not project.analysis_data or not project.last_analyzed_at:
        raise HTTPException(status_code=404, detail="Este projeto ainda não foi analisado.")
    return {
        "project_id": project.id,
        "project_name": project.name,
        "analyzed_at": project.last_analyzed_at,
        **json.loads(project.analysis_data),
    }

@router.get("/projects/{project_id}/events", response_model=list[ProjectEventRead], tags=["Histórico"])
def list_project_events(project_id: int, db: Session = Depends(get_db)) -> list[ProjectEvent]:
    get_existing_project(project_id, db)
    return list(db.scalars(
        select(ProjectEvent).where(ProjectEvent.project_id == project_id)
        .order_by(ProjectEvent.created_at.desc(), ProjectEvent.id.desc())
    ).all())


@router.post("/projects/{project_id}/tasks", response_model=TaskRead, status_code=201, tags=["Agente"])
def create_agent_task(project_id: int, payload: TaskCreate, db: Session = Depends(get_db)) -> AgentTask:
    project = get_existing_project(project_id, db)
    root = get_project_directory(project)
    user_id = _current_user_id.get()
    if user_id is not None:
        user = db.get(User, user_id)
        now = datetime.now(timezone.utc)
        reset = user.usage_reset_at
        if reset.tzinfo is None:
            reset = reset.replace(tzinfo=timezone.utc)
        if (now - reset).days >= 1:
            user.tasks_used_today = 0
            user.usage_reset_at = now
        limit = 10 if user.plan == "free" else 250
        if user.tasks_used_today >= limit:
            raise HTTPException(status_code=429, detail=f"Limite diário do plano {user.plan}: {limit} tarefas.")
    try:
        memories = db.scalars(select(ProjectMemory).where(ProjectMemory.project_id == project.id)).all()
        memory_context = "\n".join(f"{item.memory_key}: {item.content}" for item in memories)
        plan = create_plan(root, payload.instruction.strip(), memory_context)
    except AgentProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if user_id is not None:
        user.tasks_used_today += 1
    task = AgentTask(project_id=project.id, instruction=payload.instruction.strip(),
                     status="awaiting_approval", plan_json=plan.model_dump_json())
    db.add(task)
    db.flush()
    db.add(AgentRun(project_id=project.id, task_id=task.id, run_type="planning", status="completed", summary="Plano criado pelo provedor de IA local."))
    record_event(db, project.id, "agent_plan_created", "Plano criado e aguardando aprovação.", {"task_id": task.id})
    db.commit()
    db.refresh(task)
    return task

@router.get("/projects/{project_id}/tasks", response_model=list[TaskRead], tags=["Agente"])
def list_agent_tasks(project_id: int, db: Session = Depends(get_db)) -> list[AgentTask]:
    get_existing_project(project_id, db)
    return list(db.scalars(select(AgentTask).where(AgentTask.project_id == project_id)
                           .order_by(AgentTask.created_at.desc())).all())

@router.post("/tasks/{task_id}/approve", response_model=TaskRead, tags=["Agente"])
def approve_agent_task(task_id: int, db: Session = Depends(get_db)) -> AgentTask:
    task = db.get(AgentTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
    if task.status != "awaiting_approval":
        raise HTTPException(status_code=409, detail="Esta tarefa não aguarda aprovação.")
    project = get_existing_project(task.project_id, db)
    root = get_project_directory(project)
    try:
        plan = AgentPlan.model_validate_json(task.plan_json)
        written = apply_plan(root, plan)
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=f"Alterações não aplicadas: {exc}") from exc
    task.status = "applied"
    task.result_json = json.dumps({"files_written": written}, ensure_ascii=False)
    db.add(AgentApproval(task_id=task.id, decision="approved"))
    record_event(db, project.id, "agent_changes_applied", "Alterações aprovadas e aplicadas.", {"task_id": task.id, "files_written": written})
    db.commit()
    db.refresh(task)
    return task

@router.post("/tasks/{task_id}/reject", response_model=TaskRead, tags=["Agente"])
def reject_agent_task(task_id: int, db: Session = Depends(get_db)) -> AgentTask:
    task = db.get(AgentTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
    if task.status != "awaiting_approval":
        raise HTTPException(status_code=409, detail="Esta tarefa não aguarda decisão.")
    get_existing_project(task.project_id, db)
    task.status = "rejected"
    db.add(AgentApproval(task_id=task.id, decision="rejected"))
    record_event(db, task.project_id, "agent_plan_rejected", "Plano do agente rejeitado.", {"task_id": task.id})
    db.commit()
    db.refresh(task)
    return task


@router.get("/projects/{project_id}/memory", response_model=list[MemoryRead], tags=["Memória"])
def list_project_memory(project_id: int, db: Session = Depends(get_db)):
    get_existing_project(project_id, db)
    return list(db.scalars(select(ProjectMemory).where(ProjectMemory.project_id == project_id)
                           .order_by(ProjectMemory.updated_at.desc())).all())

@router.put("/projects/{project_id}/memory", response_model=MemoryRead, tags=["Memória"])
def write_project_memory(project_id: int, payload: MemoryWrite, db: Session = Depends(get_db)):
    get_existing_project(project_id, db)
    memory = db.scalar(select(ProjectMemory).where(
        ProjectMemory.project_id == project_id, ProjectMemory.memory_key == payload.memory_key
    ))
    if memory is None:
        memory = ProjectMemory(project_id=project_id, memory_key=payload.memory_key,
                               content=payload.content, source="user")
        db.add(memory)
    else:
        memory.content = payload.content
        memory.source = "user"
    record_event(db, project_id, "project_memory_updated", "Memória técnica atualizada.", {"memory_key": payload.memory_key})
    db.commit()
    db.refresh(memory)
    return memory

@router.post("/projects/{project_id}/rescue", tags=["Modo Resgate"])
def rescue_registered_project(project_id: int, db: Session = Depends(get_db)):
    project = get_existing_project(project_id, db)
    root = get_project_directory(project)
    report = rescue_project(root)
    db.add(AgentRun(project_id=project.id, run_type="rescue", status="completed",
                    summary="Diagnóstico estático do Modo Resgate concluído.",
                    details_json=json.dumps(report, ensure_ascii=False)))
    record_event(db, project.id, "rescue_completed", "Diagnóstico do Modo Resgate concluído.",
                 {"score": report["score"], "total_findings": report["total_findings"]})
    db.commit()
    return report

@router.post("/projects/{project_id}/validate", tags=["Validação"])
def validate_project_in_sandbox(project_id: int, db: Session = Depends(get_db)):
    project = get_existing_project(project_id, db)
    root = get_project_directory(project)
    try:
        result = run_python_tests(root)
    except SandboxUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    db.add(AgentRun(project_id=project.id, run_type="pytest", status=result["status"],
                    summary="Validação automatizada isolada do projeto.",
                    details_json=json.dumps(result, ensure_ascii=False)))
    record_event(db, project.id, "sandbox_validation", "Validação em sandbox concluída.",
                 {"status": result["status"], "exit_code": result["exit_code"]})
    db.commit()
    return result

@router.get("/projects/{project_id}/runs", tags=["Execuções"])
def list_project_runs(project_id: int, db: Session = Depends(get_db)):
    get_existing_project(project_id, db)
    runs = db.scalars(select(AgentRun).where(AgentRun.project_id == project_id)
                      .order_by(AgentRun.created_at.desc()).limit(50)).all()
    return [{"id": run.id, "run_type": run.run_type, "status": run.status,
             "summary": run.summary, "details": json.loads(run.details_json) if run.details_json else None,
             "created_at": run.created_at} for run in runs]
