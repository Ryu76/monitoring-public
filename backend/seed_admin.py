import os
import secrets
import string
from passlib.context import CryptContext
from datetime import datetime, timezone

from app.core.database import SessionLocal, engine, Base
from app.models.system import SysUser

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def seed_admin():
    db = SessionLocal()
    try:
        # 관리자 계정 존재 여부 확인
        existing_admin = db.query(SysUser).filter(SysUser.login_id == 'admin').first()
        if existing_admin:
            print("관리자 'admin' 계정이 이미 존재합니다.")
            return

        # 환경변수 또는 무작위로 초기 비밀번호 생성
        password = os.getenv("INITIAL_ADMIN_PASSWORD", "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12)))
        hashed_password = pwd_context.hash(password)

        new_admin = SysUser(
            login_id='admin',
            user_name='System Administrator',
            password_hash=hashed_password,
            status_code='ACTIVE',
            use_yn='Y',
            created_at=datetime.now(timezone.utc),
            created_by='system'
        )

        db.add(new_admin)
        db.commit()
        print(f"✅ 초기 관리자 계정 생성이 완료되었습니다.")
        print(f" - Login ID: admin")
        print(f" - Password: {password}")
        print("로그인 후 반드시 비밀번호를 변경해 주십시오.")

    except Exception as e:
        print(f"❌ 관리자 계정 생성 중 오류 발생: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    seed_admin()
