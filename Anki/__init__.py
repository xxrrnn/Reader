# Anki add-on: Repeat card in-session until 2x Good or 1x Easy
# Filename: __init__.py (put inside an add-on folder in addons21)
# Description:
# When you answer a review with Again(1) or Hard(2), this add-on will try to
# re-insert the card into the current review queue for the same day until you
# have answered Good (3) twice OR Easy (4) once.  IMPORTANT: the card's official
# scheduling (interval/ease) is NOT changed by the re-shows — only the first
# grading you gave the card will be used for scheduling. The add-on attempts
# to manipulate Anki's in-memory reviewer queue; this may not work on every
# Anki version (v3 scheduler / recent changes may break some internal names).

from aqt import gui_hooks, mw
from aqt.utils import tooltip
import os
import json
from datetime import datetime

# storage file (in addon folder)
ADDON_FOLDER = os.path.dirname(__file__)
STATE_FILE = os.path.join(ADDON_FOLDER, "repeat_until_good_state.json")

# thresholds
GOOD_THRESHOLD = 2
EASY_THRESHOLD = 1

# ease mapping (Anki uses ints: 1=Again, 2=Hard, 3=Good, 4=Easy)
EASE_AGAIN = 1
EASE_HARD = 2
EASE_GOOD = 3
EASE_EASY = 4

def _today_str():
    return datetime.now().strftime("%Y-%m-%d")

def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        # silent fail — not critical
        pass

# state structure: { "2025-10-05": {"cardid": {"good":n, "easy":m}} }

def increment_counter(card_id, ease):
    state = load_state()
    today = _today_str()
    if today not in state:
        state[today] = {}
    card_key = str(card_id)
    if card_key not in state[today]:
        state[today][card_key] = {"good": 0, "easy": 0}
    if ease == EASE_GOOD:
        state[today][card_key]["good"] += 1
    elif ease == EASE_EASY:
        state[today][card_key]["easy"] += 1
    save_state(state)
    return state[today][card_key]

def clear_card_state(card_id):
    state = load_state()
    today = _today_str()
    card_key = str(card_id)
    if today in state and card_key in state[today]:
        del state[today][card_key]
        save_state(state)

def get_card_state(card_id):
    state = load_state()
    today = _today_str()
    card_key = str(card_id)
    return state.get(today, {}).get(card_key, {"good":0, "easy":0})

# best-effort requeue: try a few attribute names for the queue (historically
# add-ons used reviewer.cardQueue, but internal names vary across versions).

def try_requeue_card(reviewer, card):
    candidates = [
        "cardQueue",
        "_cardQueue",
        "card_queue",
        "_card_queue",
        "_cards",
        "cards",
    ]
    for name in candidates:
        q = getattr(reviewer, name, None)
        if isinstance(q, list):
            try:
                # insert near front so it appears again soon but after current answer handling
                q.insert(0, card)
                return True
            except Exception:
                continue

    # Fallback: try mw.reviewer variations
    try:
        rev = mw.reviewer
        for name in candidates:
            q = getattr(rev, name, None)
            if isinstance(q, list):
                try:
                    q.insert(0, card)
                    return True
                except Exception:
                    continue
    except Exception:
        pass

    return False


def on_reviewer_did_answer_card(reviewer, card, ease):
    """Hook: runs after a card has been rated. We'll track counts and (if needed)
    try to put the card back into the *in-memory* review queue so it will be
    shown again that same day. We DO NOT modify scheduling or call any of the
    scheduler APIs — the official scheduling will remain determined by the
    first grade the user gave (as you requested).
    """
    try:
        card_id = card.id
    except Exception:
        # if card.id isn't present for some reason, abort
        return

    # If user pressed Good or Easy, increment and possibly clear
    if ease == EASE_GOOD:
        counts = increment_counter(card_id, ease)
        # if reached threshold, clear the state so it stops reappearing
        if counts.get("good", 0) >= GOOD_THRESHOLD or counts.get("easy", 0) >= EASY_THRESHOLD:
            clear_card_state(card_id)
        return
    elif ease == EASE_EASY:
        counts = increment_counter(card_id, ease)
        # easy threshold is 1, so immediately clear
        if counts.get("easy", 0) >= EASY_THRESHOLD:
            clear_card_state(card_id)
        return

    # ease is Again(1) or Hard(2)
    # create entry if not exists but do not change scheduling
    counts = get_card_state(card_id)

    # If already satisfied, do nothing
    if counts.get("good", 0) >= GOOD_THRESHOLD or counts.get("easy", 0) >= EASY_THRESHOLD:
        clear_card_state(card_id)
        return

    # Try to requeue the card in-session (best-effort)
    ok = try_requeue_card(reviewer, card)
    if ok:
        tooltip("卡片已加入本次复习队列（不会修改原始调度）。")
    else:
        # If we couldn't requeue, silently record state and inform user once
        # so they know the addon couldn't re-insert the card on this Anki version.
        # We still store the state so if requeue becomes possible later this session
        # (unlikely) it will be honored.
        state = load_state()
        today = _today_str()
        if today not in state:
            state[today] = {}
        state[today][str(card_id)] = state[today].get(str(card_id), {"good":0, "easy":0})
        save_state(state)
        tooltip("无法把卡片重新加入当前复习队列（你的 Anki 版本可能不支持）。")

# register hook
gui_hooks.reviewer_did_answer_card.append(on_reviewer_did_answer_card)

# Optional: cleanup old dates on startup

def _cleanup_old():
    state = load_state()
    today = _today_str()
    changed = False
    for k in list(state.keys()):
        if k != today:
            del state[k]
            changed = True
    if changed:
        save_state(state)

_cleanup_old()

# End of add-on
