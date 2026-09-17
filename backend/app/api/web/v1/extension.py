from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.api.dependencies import get_db, get_current_user
from app.models.extension import (
    ExternalHealthCheck,
    RemoteCommandApproval,
    ConfigVersion,
    HAClusterState
)
from app.schemas.extension import (
    ExternalHealthCheckCreate,
    ExternalHealthCheckResponse,
    RemoteCommandApprovalCreate,
    RemoteCommandApprovalResponse,
    ConfigVersionCreate,
    ConfigVersionResponse,
    HAClusterStateCreate,
    HAClusterStateResponse
)

router = APIRouter(dependencies=[Depends(get_current_user)])

# Health Check Collector Mock
@router.post("/health-checks", response_model=ExternalHealthCheckResponse)
def create_health_check(req: ExternalHealthCheckCreate, db: Session = Depends(get_db)):
    db_obj = ExternalHealthCheck(**req.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

@router.get("/health-checks", response_model=List[ExternalHealthCheckResponse])
def get_health_checks(db: Session = Depends(get_db)):
    return db.query(ExternalHealthCheck).all()


# Remote Command Approval
@router.post("/remote-commands", response_model=RemoteCommandApprovalResponse)
def request_remote_command(req: RemoteCommandApprovalCreate, db: Session = Depends(get_db)):
    ALLOWED_COMMANDS = ["ping", "netstat", "tail"]
    if req.command_type not in ALLOWED_COMMANDS:
        raise HTTPException(status_code=400, detail="Command not in allowlist")

    db_obj = RemoteCommandApproval(
        **req.model_dump(),
        approval_state="PENDING",
        dry_run_result="Command accepted for dry-run simulation.",
        audit_event=f"User {req.requested_by} requested {req.command_type} on {req.target_server}"
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

@router.put("/remote-commands/{cmd_id}/approve", response_model=RemoteCommandApprovalResponse)
def approve_remote_command(cmd_id: int, db: Session = Depends(get_db)):
    db_obj = db.query(RemoteCommandApproval).filter(RemoteCommandApproval.id == cmd_id).first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Command request not found")

    db_obj.approval_state = "APPROVED"
    db_obj.audit_event += " | APPROVED"
    db.commit()
    db.refresh(db_obj)
    return db_obj

# Config Versioning
@router.post("/config-versions", response_model=ConfigVersionResponse)
def create_config_version(req: ConfigVersionCreate, db: Session = Depends(get_db)):
    db_obj = ConfigVersion(**req.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

@router.get("/config-versions", response_model=List[ConfigVersionResponse])
def get_config_versions(db: Session = Depends(get_db)):
    return db.query(ConfigVersion).all()

# HA Cluster State
@router.post("/ha-cluster", response_model=HAClusterStateResponse)
def update_ha_cluster_state(req: HAClusterStateCreate, db: Session = Depends(get_db)):
    db_obj = db.query(HAClusterState).filter(HAClusterState.node_name == req.node_name).first()
    if db_obj:
        for k, v in req.model_dump().items():
            setattr(db_obj, k, v)
    else:
        db_obj = HAClusterState(**req.model_dump())
        db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

@router.get("/ha-cluster", response_model=List[HAClusterStateResponse])
def get_ha_cluster_state(db: Session = Depends(get_db)):
    return db.query(HAClusterState).all()
