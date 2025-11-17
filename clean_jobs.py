from postgres_utils import init_connection_pool, execute_query

init_connection_pool()
rows = execute_query("SELECT id, job_state FROM apscheduler_jobs", fetch=True)
print(f"Total jobs: {len(rows)}")
bad = []
for r in rows:
    js = r.get('job_state') or ''
    if 'app.py:_push_task_notification' in js:
        bad.append(r)

print(f"Bad jobs (old ref): {len(bad)}")
for b in bad:
    execute_query("DELETE FROM apscheduler_jobs WHERE id=%s", params=(b['id'],), fetch=False)
    print(f"Deleted job {b['id']}")
print("✅ Done cleaning old jobs")
