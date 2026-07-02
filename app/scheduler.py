from apscheduler.schedulers.background import BackgroundScheduler
import logging

logger = logging.getLogger("scheduler")

scheduler = BackgroundScheduler(job_defaults={"coalesce": True, "max_instances": 1})

def start_scheduler(job_func):
    scheduler.add_job(job_func, 'interval', minutes=5, id='status_job', replace_existing=True)
    scheduler.start()
    logger.info("Scheduler run started.")

def stop_scheduler(db_shutdown):
    logger.info("Finishing last scheduler run. This may take a while...")
    scheduler.shutdown(wait=True)
    logger.info("Scheduler run finished.")

    db_shutdown()