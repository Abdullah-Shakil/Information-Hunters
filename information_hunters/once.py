"""Process every queued hunt and exit. Used by Cloud Run Jobs and cron hosts."""

from information_hunters.db import init_db
from information_hunters.worker import claim_next_job, worker_identity
from information_hunters.pipeline import process_job


def main() -> None:
    init_db()
    worker_id = worker_identity()
    ran = 0
    while True:
        job_id = claim_next_job(worker_id)
        if not job_id:
            break
        process_job(job_id, worker_id)
        ran += 1
    print(f"Processed {ran} hunt(s).")


if __name__ == "__main__":
    main()
