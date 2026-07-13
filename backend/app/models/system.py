from sqlalchemy import Column, String, Integer, ForeignKey, CHAR, TIMESTAMP, Text
from app.core.database import Base


class SysUser(Base):
    """sys_user - 시스템 사용자"""
    __tablename__ = "sys_user"

    user_id = Column(Integer, primary_key=True)
    login_id = Column(String(50), nullable=False, unique=True)
    user_name = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)
    dept_name = Column(String(100))
    position_name = Column(String(50))
    email = Column(String(100))
    phone = Column(String(50))
    status_code = Column(String(30), nullable=False)
    last_login_at = Column(TIMESTAMP)
    pwd_changed_at = Column(TIMESTAMP)
    use_yn = Column(CHAR(1), nullable=False, default='Y')
    created_at = Column(TIMESTAMP)
    created_by = Column(String(100))
    updated_at = Column(TIMESTAMP)
    updated_by = Column(String(100))


class SysRole(Base):
    """sys_role - 역할(Role) 정의"""
    __tablename__ = "sys_role"

    role_id = Column(Integer, primary_key=True)
    role_code = Column(String(30), nullable=False, unique=True)
    role_name = Column(String(100), nullable=False)
    description = Column(String(1000))
    use_yn = Column(CHAR(1), nullable=False, default='Y')
    created_at = Column(TIMESTAMP)
    created_by = Column(String(100))


class SysPermission(Base):
    """sys_permission - 권한 정의"""
    __tablename__ = "sys_permission"

    permission_id = Column(Integer, primary_key=True)
    permission_code = Column(String(50), nullable=False, unique=True)
    permission_name = Column(String(100), nullable=False)
    description = Column(String(1000))


class SysRolePermission(Base):
    """sys_role_permission - 역할-권한 매핑"""
    __tablename__ = "sys_role_permission"

    role_id = Column(Integer, primary_key=True)       # FK 제약조건 DB에 없음
    permission_id = Column(Integer, primary_key=True)  # FK 제약조건 DB에 없음
    created_at = Column(TIMESTAMP)
    created_by = Column(String(100))


class SysUserRole(Base):
    """sys_user_role - 사용자-역할 매핑"""
    __tablename__ = "sys_user_role"

    user_id = Column(Integer, primary_key=True)        # FK 제약조건 DB에 없음
    role_id = Column(Integer, primary_key=True)        # FK 제약조건 DB에 없음
    created_at = Column(TIMESTAMP)
    created_by = Column(String(100))


class SysCodeGroup(Base):
    """sys_code_group - 공통코드 그룹"""
    __tablename__ = "sys_code_group"

    group_code = Column(String(30), primary_key=True)
    group_name = Column(String(100), nullable=False)
    description = Column(String(1000))
    use_yn = Column(CHAR(1), nullable=False, default='Y')
    created_at = Column(TIMESTAMP)
    created_by = Column(String(100))
    updated_at = Column(TIMESTAMP)
    updated_by = Column(String(100))


class SysCode(Base):
    """sys_code - 공통코드"""
    __tablename__ = "sys_code"

    code = Column(String(30), primary_key=True)
    group_code = Column(String(30), primary_key=True)  # FK 제약조건 DB에 없음
    code_name = Column(String(100), nullable=False)
    sort_order = Column(Integer)
    description = Column(String(1000))
    use_yn = Column(CHAR(1), nullable=False, default='Y')
    created_at = Column(TIMESTAMP)
    created_by = Column(String(100))
    updated_at = Column(TIMESTAMP)
    updated_by = Column(String(100))


class SysAuditLog(Base):
    """sys_audit_log - 감사 로그"""
    __tablename__ = "sys_audit_log"

    log_id = Column(Integer, primary_key=True)
    user_id = Column(Integer)              # FK 제약조건 DB에 없음
    action_type = Column(String(100))
    target_entity = Column(String(100))
    target_id = Column(String(100))
    ip_address = Column(String(45))
    before_data = Column(Text)             # Oracle CLOB
    after_data = Column(Text)              # Oracle CLOB
    created_at = Column(TIMESTAMP)
