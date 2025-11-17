"""
Scheduler jobs module - Wrapper để APScheduler có thể import đúng
Tránh lỗi Windows path: I:\AI GPT\app.py → ModuleNotFoundError: No module named 'I'

GIẢI PHÁP: Không import app, mà nhận function references từ app.py khi init
"""

# Global references - sẽ được set từ app.py
_do_push_ref = None
_sync_users_ref = None
_first_fire_ref = None
_push_task_ref = None
_tick_ref = None

def set_callbacks(do_push_fn, sync_users_fn, first_fire_fn, push_task_fn, tick_fn):
    """
    Được gọi từ app.py để inject function references.
    Cách này tránh circular import.
    """
    global _do_push_ref, _sync_users_ref, _first_fire_ref, _push_task_ref, _tick_ref
    _do_push_ref = do_push_fn
    _sync_users_ref = sync_users_fn
    _first_fire_ref = first_fire_fn
    _push_task_ref = push_task_fn
    _tick_ref = tick_fn
    print("✅ [scheduler_jobs] Đã nhận callbacks từ app.py")

def _do_push(user_id_str: str, noti_text: str):
    """Wrapper cho _do_push - gọi function reference"""
    if _do_push_ref:
        return _do_push_ref(user_id_str, noti_text)
    else:
        print("[scheduler_jobs] ERROR: _do_push_ref not set!")
        return None

def _sync_users_from_api_sync():
    """Wrapper cho _sync_users_from_api_sync"""
    if _sync_users_ref:
        return _sync_users_ref()
    else:
        print("[scheduler_jobs] ERROR: _sync_users_ref not set!")
        return None

def _first_fire_escalation_job(user_id_str: str, text: str, every_sec: int):
    """Wrapper cho _first_fire_escalation_job"""
    if _first_fire_ref:
        return _first_fire_ref(user_id_str, text, every_sec)
    else:
        print("[scheduler_jobs] ERROR: _first_fire_ref not set!")
        return None

def _push_task_notification(internal_session_id: str, task_title: str, task_id: int, repeat_min):
    """Wrapper cho _push_task_notification"""
    if _push_task_ref:
        return _push_task_ref(internal_session_id, task_title, task_id, repeat_min)
    else:
        print("[scheduler_jobs] ERROR: _push_task_ref not set!")
        return None

def _tick_job_sync(user_id_str: str, text: str, repeat_job_id: str):
    """Wrapper cho _tick_job_sync - escalation job"""
    if _tick_ref:
        return _tick_ref(user_id_str, text, repeat_job_id)
    else:
        print("[scheduler_jobs] ERROR: _tick_ref not set!")
        return None
