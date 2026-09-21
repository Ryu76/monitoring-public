from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db, require_roles
from app.core.audit import get_client_ip, log_audit
from app.models.extension import (
    ConfigVersion,
    ExternalHealthCheck,
    HAClusterState,
    RemoteCommandApproval,
)
from app.models.system import SysUser
from app.schemas.extension import (
    ConfigVersionCreate,
    ConfigVersionResponse,
    ExternalHealthCheckCreate,
    ExternalHealthCheckResponse,
    HAClusterStateCreate,
    HAClusterStateResponse,
    RemoteCommandApprovalCreate,
    RemoteCommandApprovalResponse,
)

router = APIRouter(dependencies=[Depends(get_current_user)])
MUTATOR_ROLES = ["SUPER_ADMIN", "ADMIN", "OPERATOR"]
ADMIN_ROLES = ["SUPER_ADMIN", "ADMIN"]
ALLOWED_COMMANDS = {"ping", "netstat", "tail"}


def _commit_with_audit(db: Session) -> None:
    """Persist the P3 change and its audit event as one transaction."""
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="P3 mutation could not be recorded.",
        )


@router.post(
    "/health-checks",
    response_model=ExternalHealthCheckResponse,
    dependencies=[Depends(require_roles(MUTATOR_ROLES))],
)
def create_health_check(
    req: ExternalHealthCheckCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    db_obj = ExternalHealthCheck(**req.model_dump())
    db.add(db_obj)
    db.flush()
    log_audit(
        db, current_user.user_id, "CREATE", "ExternalHealthCheck", str(db_obj.id),
        None, req.model_dump(), get_client_ip(request),
    )
    _commit_with_audit(db)
    db.refresh(db_obj)
    return db_obj


@router.get("/health-checks", response_model=List[ExternalHealthCheckResponse])
def get_health_checks(db: Session = Depends(get_db)):
    return db.query(ExternalHealthCheck).all()


@router.post(
    "/remote-commands",
    response_model=RemoteCommandApprovalResponse,
    dependencies=[Depends(require_roles(MUTATOR_ROLES))],
)
def request_remote_command(
    req: RemoteCommandApprovalCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    if req.command_type not in ALLOWED_COMMANDS:
        raise HTTPException(status_code=400, detail="Command not in allowlist")

    # requested_by is deliberately derived from the authenticated database user,
    # never accepted in the request body.
    db_obj = RemoteCommandApproval(
        command_type=req.command_type,
        target_server=req.target_server,
        requested_by=current_user.login_id,
        approval_state="PENDING",
        dry_run_result="Command accepted for dry-run simulation.",
        audit_event=(
            f"User {current_user.login_id} requested {req.command_type} "
            f"on {req.target_server}"
        ),
    )
    db.add(db_obj)
    db.flush()
    log_audit(
        db, current_user.user_id, "CREATE", "RemoteCommandApproval", str(db_obj.id),
        None,
        {
            "state": "PENDING",
            "command": req.command_type,
            "target_server": req.target_server,
            "requested_by": current_user.login_id,
        },
        get_client_ip(request),
    )
    _commit_with_audit(db)
    db.refresh(db_obj)
    return db_obj


@router.put(
    "/remote-commands/{cmd_id}/approve",
    response_model=RemoteCommandApprovalResponse,
    dependencies=[Depends(require_roles(ADMIN_ROLES))],
)
def approve_remote_command(
    cmd_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    db_obj = db.get(RemoteCommandApproval, cmd_id)
    if not db_obj:
        raise HTTPException(status_code=404, detail="Command request not found")
    if db_obj.requested_by == current_user.login_id:
        raise HTTPException(status_code=403, detail="Requester cannot approve their own command")
    if db_obj.approval_state != "PENDING":
        raise HTTPException(status_code=409, detail="Only pending commands may be approved")

    before = {"state": db_obj.approval_state, "requested_by": db_obj.requested_by}
    db_obj.approval_state = "APPROVED"
    db_obj.audit_event = (
        f"{db_obj.audit_event or ''} | APPROVED BY {current_user.login_id}"
    )
    log_audit(
        db, current_user.user_id, "UPDATE", "RemoteCommandApproval", str(db_obj.id),
        before,
        {"state": "APPROVED", "approved_by": current_user.login_id},
        get_client_ip(request),
    )
    _commit_with_audit(db)
    db.refresh(db_obj)
    return db_obj


@router.post(
    "/config-versions",
    response_model=ConfigVersionResponse,
    dependencies=[Depends(require_roles(MUTATOR_ROLES))],
)
def create_config_version(
    req: ConfigVersionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    db_obj = ConfigVersion(**req.model_dump())
    db.add(db_obj)
    db.flush()
    log_audit(
        db, current_user.user_id, "CREATE", "ConfigVersion", str(db_obj.id),
        None, req.model_dump(), get_client_ip(request),
    )
    _commit_with_audit(db)
    db.refresh(db_obj)
    return db_obj


@router.get("/config-versions", response_model=List[ConfigVersionResponse])
def get_config_versions(db: Session = Depends(get_db)):
    return db.query(ConfigVersion).all()


@router.post(
    "/ha-cluster",
    response_model=HAClusterStateResponse,
    dependencies=[Depends(require_roles(MUTATOR_ROLES))],
)
def update_ha_cluster_state(
    req: HAClusterStateCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    db_obj = db.query(HAClusterState).filter(HAClusterState.node_name == req.node_name).first()
    before_data = None
    if db_obj:
        before_data = {"role": db_obj.role, "health_state": db_obj.health_state}
        for key, value in req.model_dump().items():
            setattr(db_obj, key, value)
        action_type = "UPDATE"
    else:
        db_obj = HAClusterState(**req.model_dump())
        db.add(db_obj)
        action_type = "CREATE"

    db.flush()
    log_audit(
        db, current_user.user_id, action_type, "HAClusterState", str(db_obj.id),
        before_data, req.model_dump(), get_client_ip(request),
    )
    _commit_with_audit(db)
    db.refresh(db_obj)
    return db_obj


@router.get("/ha-cluster", response_model=List[HAClusterStateResponse])
def get_ha_cluster_state(db: Session = Depends(get_db)):
    return db.query(HAClusterState).all()
