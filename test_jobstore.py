from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from sqlalchemy import create_engine
engine = create_engine('sqlite:///test_apscheduler.db')
jobstores = {'default': SQLAlchemyJobStore(engine=engine)}
try:
    scheduler = BackgroundScheduler(jobstores=jobstores)
    scheduler.start()
    print('Started successfully')
    scheduler.shutdown()
except Exception as e:
    print('Error:', e)
