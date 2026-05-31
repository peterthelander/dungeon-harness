import queue

engine_state = {
    "chat_session": None,
    "latest_pdf": None
}

active_action_queue = None

def set_active_queue(q: queue.Queue):
    global active_action_queue
    active_action_queue = q

def get_active_queue():
    global active_action_queue
    return active_action_queue