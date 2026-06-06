import queue

engine_state = {}

active_action_queues = {}

def get_or_create_session_state(session_id: str):
    return engine_state.setdefault(session_id, {
        "chat_session": None,
        "latest_pdf": None,
        "previous_visual_desc": "",
    })

def set_active_queue(session_id: str, q: queue.Queue):
    active_action_queues[session_id] = q

def get_active_queue(session_id: str):
    return active_action_queues.get(session_id)