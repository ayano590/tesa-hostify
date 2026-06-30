from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

def start_scheduler(job_func):
    scheduler.add_job(job_func, 'interval', minutes=5, id='status_job', replace_existing=True)
    scheduler.start()

def stop_scheduler():
    scheduler.shutdown()