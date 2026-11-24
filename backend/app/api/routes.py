from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate

router = APIRouter()

@router.get("/health", tags=["Sistema"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "DevPilot AI"}

@router.get("/projects", response_model=list[ProjectRead], tags=["Projetos"])
def list_projects(db: Session = Depends(get_db)) -> list[Project]:
    return list(db.scalars(select(Project).order_by(Project.created_at.desc())).all())

@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED, tags=["Projetos"])
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> Project:
    project = Project(name=payload.name.strip(), description=payload.description, root_path=payload.root_path)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project

@router.get("/projects/{project_id}", response_model=ProjectRead, tags=["Projetos"])
def get_project(project_id: int, db: Session = Depends(get_db)) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    return project

@router.patch("/projects/{project_id}", response_model=ProjectRead, tags=["Projetos"])
def update_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "name" and value is not None:
            value = value.strip()
        if value is not None or field != "name":
            setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project
