from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List

from app.api.dependencies import get_db, get_current_user, require_roles
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
from app.core.audit import log_audit, get_client_ip

router = APIRouter(dependencies=[Depends(get_current_user)])
mutator = Depends(require_roles(["SUPER_ADMIN", "ADMIN", "OPERATOR"]))
admin_only = Depends(require_roles(["SUPER_ADMIN", "ADMIN"]))

# Health Check Collector Mock
@router.post("/health-checks", response_model=ExternalHealthCheckResponse, dependencies=[mutator])
def create_health_check(req: ExternalHealthCheckCreate, request: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    db_obj = ExternalHealthCheck(**req.model_dump())
    db.add(db_obj)
    db.flush()
    log_audit(db, current_user.user_id, "CREATE", "ExternalHealthCheck", str(db_obj.id), None, req.model_dump(), get_client_ip(request))
    db.commit()
    db.refresh(db_obj)
    return db_obj

@router.get("/health-checks", response_model=List[ExternalHealthCheckResponse])
def get_health_checks(db: Session = Depends(get_db)):
    return db.query(ExternalHealthCheck).all()


# Remote Command Approval
@router.post("/remote-commands", response_model=RemoteCommandApprovalResponse, dependencies=[mutator])
def request_remote_command(req: RemoteCommandApprovalCreate, request: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    ALLOWED_COMMANDS = ["ping", "netstat", "tail"]
    if req.command_type not in ALLOWED_COMMANDS:
        raise HTTPException(status_code=400, detail="Command not in allowlist")

    db_obj = RemoteCommandApproval(
        **req.model_dump(),
        requested_by=current_user.login_id,
        approval_state="PENDING",
        dry_run_result="Command accepted for dry-run simulation.",
        audit_event=f"User {current_user.login_id} requested {req.command_type} on {req.target_server}"
    )
    db.add(db_obj)
    db.flush()
    log_audit(db, current_user.user_id, "CREATE", "RemoteCommandApproval", str(db_obj.id), None, {"state": "PENDING", "command": req.command_type}, get_client_ip(request))
    db.commit()
    db.refresh(db_obj)
    return db_obj

@router.put("/remote-commands/{cmd_id}/approve", response_model=RemoteCommandApprovalResponse, dependencies=[admin_only])
def approve_remote_command(cmd_id: int, request: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    db_obj = db.query(RemoteCommandApproval).filter(RemoteCommandApproval.id == cmd_id).first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Command request not found")

    if db_obj.requested_by == current_user.login_id:
        raise HTTPException(status_code=403, detail="Requester cannot approve their own command")

    db_obj.approval_state = "APPROVED"
    db_obj.audit_event += f" | APPROVED BY {current_user.login_id}"
    log_audit(db, current_user.user_id, "UPDATE", "RemoteCommandApproval", str(db_obj.id), {"state": "PENDING"}, {"state": "APPROVED"}, get_client_ip(request))
    db.commit()
    db.refresh(db_obj)
    return db_obj

# Config Versioning
@router.post("/config-versions", response_model=ConfigVersionResponse, dependencies=[mutator])
def create_config_version(req: ConfigVersionCreate, request: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    db_obj = ConfigVersion(**req.model_dump())
    db.add(db_obj)
    db.flush()
    log_audit(db, current_user.user_id, "CREATE", "ConfigVersion", str(db_obj.id), None, req.model_dump(), get_client_ip(request))
    db.commit()
    db.refresh(db_obj)
    return db_obj

@router.get("/config-versions", response_model=List[ConfigVersionResponse])
def get_config_versions(db: Session = Depends(get_db)):
    return db.query(ConfigVersion).all()

# HA Cluster State
@router.post("/ha-cluster", response_model=HAClusterStateResponse, dependencies=[mutator])
def update_ha_cluster_state(req: HAClusterStateCreate, request: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    db_obj = db.query(HAClusterState).filter(HAClusterState.node_name == req.node_name).first()
    before_data = None
    if db_obj:
        before_data = {"role": db_obj.role, "health": db_obj.health_state}
        for k, v in req.model_dump().items():
            setattr(db_obj, k, v)
        action_type = "UPDATE"
    else:
        db_obj = HAClusterState(**req.model_dump())
        db.add(db_obj)
        action_type = "CREATE"

    db.flush()
    log_audit(db, current_user.user_id, action_type, "HAClusterState", str(db_obj.id), before_data, req.model_dump(), get_client_ip(request))
    db.commit()
    db.refresh(db_obj)
    return db_obj

@router.get("/ha-cluster", response_model=List[HAClusterStateResponse])
def get_ha_cluster_state(db: Session = Depends(get_db)):
    return db.query(HAClusterState).all()
