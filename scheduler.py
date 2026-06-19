"""
Migration scheduler — runs migrate() on a fixed interval.
Deploy as a separate Railway service with: python scheduler.py
"""
import logging
import time
from apscheduler.schedulers.blocking import BlockingScheduler
from migrate import migrate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("scheduler")


def job():
    log.info("Migration job started")
    try:
        migrate()
        log.info("Migration job completed")
    except Exception as e:
        log.error("Migration job failed: %s", e)


scheduler = BlockingScheduler()

# Runs every day at midnight — change cron args as needed:
# hour="*/6"  → every 6 hours
# hour="*"    → every hour
scheduler.add_job(job, trigger="cron", hour="0", minute="0")

log.info("Scheduler started — migration runs daily at midnight")

job()  # run once immediately on startup

scheduler.start()
