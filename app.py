#!/usr/bin/env python3
"""Phase-A session instrument: chat shell over Bedrock.

Implements INSTRUMENT_SPEC R1-R6:
  R1 conditions (Latin square by participant ID, ~8 turns each, fixed temp,
     single model), R2 embedded probe (via system prompt, logged), R3 the
     Regenerate button (narrative-shopping sensor — logs every click with
     the replaced response), R4 full logging streams, R5 task menu,
     R6 facilitator view (sidebar).

Run:  streamlit run app.py
Auth: default AWS credential chain.
"""

import datetime
import json
import time
import uuid
from pathlib import Path

import boto3
import streamlit as st

from bedrock_auth import key_status, load_bedrock_key

load_bedrock_key()  # before any boto3 client; falls back to default chain

ROOT = Path(__file__).resolve().parent
CONDITIONS_DIR = ROOT / "conditions"
SESSIONS_DIR = ROOT / "sessions"

MODEL_ID = "us.anthropic.claude-sonnet-5"  # frozen for Phase A after 3x3 re-validation (08-03 upgrade from sonnet-4-6)
REGION = "us-west-2"
# NOTE (08-03): Sonnet 5 deprecates the `temperature` parameter (Converse
# ValidationException if sent). All conditions share the model's default
# sampling — R1's substance (no sampling difference across conditions)
# still holds; the spec's "fixed temp" wording should be read as "fixed
# sampling config".
MAX_TOKENS = 600
TURNS_PER_CONDITION = 8

# Latin square (3 conditions): assignment by participant number mod 3
LATIN_SQUARE = [
    ["supportive", "challenging", "neutral"],   # P0, P3, P6…
    ["challenging", "neutral", "supportive"],   # P1, P4, P7…
    ["neutral", "supportive", "challenging"],   # P2, P5, P8…
]

TASK_MENU = {
    "zh": [
        "最近一个让你反复想的决定",
        "一件说不清为什么在意的事",
        "一个别人给过你建议、但你没有听的问题",
    ],
    "en": [
        "A recent decision you keep going back to",
        "Something that bothers you and you can't quite say why",
        "A problem someone gave you advice about — advice you didn't take",
    ],
}

# Participant-facing strings; facilitator UI stays zh (facilitator is zh-speaking)
UI_TEXT = {
    "zh": {
        "episode_header": "对话 {i} / 3",
        "menu_lead": "可以从下面的提示里选一个，也可以聊别的真实在想的事：",
        "menu_caption": "想好后直接在下面输入第一句话，就像平时跟 AI 聊天那样开始。",
        "regenerate": "重新生成",
        "input_placeholder": "输入……",
        "thinking": "正在回复……",
        "topics_expander": "看看刚才那几个话题提示",
        "error": "网络好像卡了一下，刚才那句没发出去。可以再发一次，"
                 "或者叫一下旁边的老师。",
        "retry": "重试刚才那句",
        "ratings_header": "请为刚才这段对话打分",
        "r1": "这个AI聪明吗？", "r2": "这个AI懂你吗？", "r3": "这段对话有帮助吗？",
        "ratings_scale_low": "1 = 完全不", "ratings_scale_high": "7 = 非常",
        "ratings_submit": "提交，进入下一段",
        "ratings_incomplete": "三项都选了才能继续",
        "all_done": "三个对话都完成了，谢谢！请回到主持人处继续。",
    },
    "en": {
        "episode_header": "Conversation {i} / 3",
        "menu_lead": "Pick one of the prompts below, or talk about anything else that's really on your mind:",
        "menu_caption": "When you're ready, just type your first message — start the way you normally would with an AI.",
        "regenerate": "Regenerate",
        "input_placeholder": "Type here…",
        "thinking": "Replying…",
        "topics_expander": "Show the topic prompts again",
        "error": "Looks like the connection hiccuped — that message didn't go "
                 "through. You can send it again, or grab the facilitator.",
        "retry": "Retry that message",
        "ratings_header": "Please rate the conversation you just had",
        "r1": "How smart was this AI?", "r2": "How well did it understand you?",
        "r3": "How helpful was this conversation?",
        "ratings_scale_low": "1 = not at all", "ratings_scale_high": "7 = very",
        "ratings_submit": "Submit and continue",
        "ratings_incomplete": "Please answer all three to continue",
        "all_done": "All three conversations are done — thank you! Please return to the facilitator.",
    },
}

CONDITION_LABELS = {"supportive": "A", "challenging": "B", "neutral": "C"}  # facilitator-only


def load_condition(name: str) -> str:
    lang = st.session_state.get("language", "zh")
    base = (CONDITIONS_DIR / lang / f"{name}.txt").read_text(encoding="utf-8")
    probe = (CONDITIONS_DIR / lang / "probe.txt").read_text(encoding="utf-8")
    return base + "\n" + probe


def now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="milliseconds")


def log_event(kind: str, **fields):
    """Append one event to the session's JSONL log."""
    ss = st.session_state
    event = {"ts": now_iso(), "kind": kind, "participant": ss.participant_id,
             "condition": ss.current_condition, "episode_turn": ss.turn_count, **fields}
    ss.log_path.parent.mkdir(exist_ok=True)
    with open(ss.log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def call_model(messages: list) -> str:
    client = boto3.client("bedrock-runtime", region_name=REGION)
    for attempt in range(3):  # Sonnet 5 occasionally returns reasoning-only (no text) output
        resp = client.converse(
            modelId=MODEL_ID,
            system=[{"text": load_condition(st.session_state.current_condition)}],
            messages=messages,
            inferenceConfig={"maxTokens": MAX_TOKENS},
        )
        text = "".join(
            b["text"] for b in resp["output"]["message"]["content"] if "text" in b)
        if text.strip():
            return text
    # never append an empty assistant turn — Converse rejects it on the next call
    raise RuntimeError("model returned empty text after 3 attempts")


def find_existing_logs(participant_id: str) -> list:
    """Session logs already on disk for this participant, newest first."""
    if not SESSIONS_DIR.exists():
        return []
    return sorted(SESSIONS_DIR.glob(f"{participant_id}__*.jsonl"),
                  key=lambda p: p.stat().st_mtime, reverse=True)


def resume_session(log_path: Path):
    """Rebuild session state from a JSONL log.

    A browser refresh (or a dropped websocket) clears st.session_state and
    would otherwise strand the participant mid-episode AND split them across
    two log files. The log is the complete record — every turn is appended
    before the next render — so it can be replayed to reconstruct where we
    were. Only the CURRENT episode's messages go back into the model history;
    earlier episodes are finished and must not leak across the condition
    boundary.
    """
    ss = st.session_state
    events = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))

    start = next(e for e in events if e["kind"] == "session_start")
    ss.participant_id = start["participant"]
    ss.language = start.get("language", "zh")
    ss.condition_order = start["condition_order"]
    ss.log_path = log_path
    ss.session_id = log_path.stem.split("__")[-1]

    # episode index = how many episodes have been closed out so far
    closed = sum(1 for e in events if e["kind"] == "episode_end_by_facilitator")
    rated = sum(1 for e in events if e["kind"] == "ratings")
    ss.session_done = any(e["kind"] == "session_end" for e in events)
    ss.episode_index = min(rated, len(ss.condition_order) - 1)
    ss.current_condition = ss.condition_order[ss.episode_index]
    # ended but not yet rated -> land back on the ratings form
    ss.episode_done = closed > rated
    ss.ratings_pending = closed > rated

    # replay only the turns belonging to the current episode
    ss.messages, ss.display = [], []
    seen_ratings = 0
    for e in events:
        if e["kind"] == "ratings":
            seen_ratings += 1
            continue
        if seen_ratings != ss.episode_index:
            continue
        if e["kind"] == "user_turn":
            ss.messages.append({"role": "user", "content": [{"text": e["text"]}]})
            ss.display.append(("user", e["text"]))
        elif e["kind"] == "ai_turn":
            ss.messages.append({"role": "assistant", "content": [{"text": e["text"]}]})
            ss.display.append(("assistant", e["text"]))
        elif e["kind"] == "regenerate":
            # the replaced text is history; keep only what the participant saw
            if ss.messages and ss.messages[-1]["role"] == "assistant":
                ss.messages[-1] = {"role": "assistant",
                                   "content": [{"text": e["new_response"]}]}
                ss.display[-1] = ("assistant", e["new_response"])

    ss.turn_count = sum(1 for r, _ in ss.display if r == "user")
    ss.last_user_ts = None  # inter-turn latency is not meaningful across a refresh
    ss.pending_retry = None
    ss.awaiting_reply = False
    ss.reply_started_at = None
    ss.initialized = True
    log_event("session_resumed", resumed_from=log_path.name,
              rebuilt_turns=ss.turn_count, episode=ss.episode_index)


def init_session(participant_id: str, language: str = "zh"):
    ss = st.session_state
    ss.participant_id = participant_id
    ss.language = language
    try:
        pnum = int("".join(ch for ch in participant_id if ch.isdigit()) or "0")
    except ValueError:
        pnum = 0
    ss.condition_order = LATIN_SQUARE[pnum % 3]
    ss.episode_index = 0
    ss.current_condition = ss.condition_order[0]
    ss.turn_count = 0
    ss.messages = []           # Converse-format history for the CURRENT episode
    ss.display = []            # [(role, text)] for rendering
    ss.last_user_ts = None
    ss.pending_retry = None
    ss.awaiting_reply = False
    ss.reply_started_at = None
    ss.episode_done = False
    ss.session_done = False
    ss.ratings_pending = False
    ss.session_id = uuid.uuid4().hex[:8]
    ss.log_path = SESSIONS_DIR / f"{participant_id}__{ss.session_id}.jsonl"
    ss.initialized = True
    log_event("session_start", condition_order=ss.condition_order,
              model=MODEL_ID, sampling="model-default", language=ss.language)


def advance_episode():
    ss = st.session_state
    ss.episode_index += 1
    if ss.episode_index >= len(ss.condition_order):
        ss.session_done = True
        log_event("session_end")
        return
    ss.current_condition = ss.condition_order[ss.episode_index]
    ss.turn_count = 0
    ss.messages = []
    ss.display = []
    ss.episode_done = False
    ss.last_user_ts = None
    ss.pending_retry = None
    ss.awaiting_reply = False
    ss.reply_started_at = None
    log_event("episode_start", episode=ss.episode_index)


# ---------------- UI ----------------

st.set_page_config(page_title="对话研究", page_icon="💬", layout="centered")

if "initialized" not in st.session_state:
    st.title("对话研究 · Session")
    st.caption(key_status())
    pid = st.text_input("参与者编号（主持人输入）", placeholder="P01")
    lang = st.radio("Session 语言（主持人选择，与参与者的 AI 常用语一致）",
                    ["zh", "en"], horizontal=True)

    # If this participant already has a log, the page was probably refreshed
    # mid-session. Offer resume BEFORE offering a fresh start, so the default
    # action does not silently split one participant across two files.
    existing = find_existing_logs(pid.strip()) if pid.strip() else []
    if existing:
        st.warning(f"该编号已有 {len(existing)} 份日志——如果刚才是刷新/掉线，"
                   f"请选择恢复，不要新建（新建会把同一个人拆成两份数据）。")
        pick = st.selectbox(
            "恢复哪一份？",
            existing,
            format_func=lambda p: f"{p.name} · 最后修改 "
                                  f"{datetime.datetime.fromtimestamp(p.stat().st_mtime):%H:%M:%S}",
        )
        c1, c2 = st.columns(2)
        if c1.button("恢复这份 session", type="primary"):
            resume_session(pick)
            st.rerun()
        if c2.button("忽略，新建一份"):
            SESSIONS_DIR.mkdir(exist_ok=True)
            init_session(pid.strip(), lang)
            st.rerun()
        st.stop()

    if st.button("开始", disabled=not pid):
        SESSIONS_DIR.mkdir(exist_ok=True)
        init_session(pid.strip(), lang)
        st.rerun()
    st.stop()

ss = st.session_state

# --- facilitator sidebar (R6) ---
with st.sidebar:
    st.caption("主持人视图")
    st.caption(key_status())
    st.write(f"参与者：{ss.participant_id} · 语言：{ss.language}")
    order_labels = " → ".join(CONDITION_LABELS[c] for c in ss.condition_order)
    st.write(f"条件顺序：{order_labels}")
    st.write(f"当前：episode {ss.episode_index + 1}/3 · "
             f"条件 {CONDITION_LABELS[ss.current_condition]} · "
             f"turn {ss.turn_count}/{TURNS_PER_CONDITION}")
    # Topic bookkeeping is facilitator-side: a participant-facing picker
    # would reimpose the multiple-choice frame the open first turn avoids.
    # Keyed per episode so switching episodes resets to 未定 rather than
    # silently carrying the previous episode's answer into the next log line.
    topic = st.radio(
        "本段话题（主持人记录）",
        ["1 反复想的决定", "2 说不清为什么在意", "3 没听的建议", "自带话题", "未定"],
        index=4, key=f"topic_ep{ss.episode_index}",
    )
    same_as_prev = False
    if ss.episode_index > 0:
        same_as_prev = st.checkbox("与上一段同话题", key=f"same_ep{ss.episode_index}")
    if topic == "未定" and ss.turn_count > 0:
        st.caption("⚠️ 话题还没记录")
    if ss.turn_count >= TURNS_PER_CONDITION and not ss.episode_done:
        st.warning("已到 8 turns —— 可以收尾切换")
    if st.button("结束当前 episode（主持人）"):
        ss.episode_done = True
        ss.ratings_pending = True
        log_event("episode_end_by_facilitator",
                  topic=topic, same_topic_as_previous=same_as_prev)
        st.rerun()

T = UI_TEXT[ss.language]

if ss.session_done:
    st.success(T["all_done"])
    st.stop()

# --- post-episode ratings (3 items, R4) ---
if ss.ratings_pending:
    st.subheader(T["ratings_header"])
    st.caption(f"{T['ratings_scale_low']} · {T['ratings_scale_high']}")
    # Deliberately NO default: a slider parked at the midpoint anchors the
    # response and makes a real 4 indistinguishable from an untouched control.
    # These items feed the perceived-competence inversion prediction
    # (challenging rated least smart), so the noise is not affordable.
    ep = ss.episode_index
    r1 = st.radio(T["r1"], [1, 2, 3, 4, 5, 6, 7], index=None,
                  horizontal=True, key=f"r1_ep{ep}")
    r2 = st.radio(T["r2"], [1, 2, 3, 4, 5, 6, 7], index=None,
                  horizontal=True, key=f"r2_ep{ep}")
    r3 = st.radio(T["r3"], [1, 2, 3, 4, 5, 6, 7], index=None,
                  horizontal=True, key=f"r3_ep{ep}")
    complete = None not in (r1, r2, r3)
    if not complete:
        st.caption(T["ratings_incomplete"])
    if st.button(T["ratings_submit"], disabled=not complete, type="primary"):
        log_event("ratings", smart=r1, understands=r2, helpful=r3)
        ss.ratings_pending = False
        advance_episode()
        st.rerun()
    st.stop()

# --- task menu at episode start (R5) ---
if ss.turn_count == 0 and not ss.display:
    st.subheader(T["episode_header"].format(i=ss.episode_index + 1))
    st.write(T["menu_lead"])
    for i, task in enumerate(TASK_MENU[ss.language]):
        st.markdown(f"{i+1}. {task}")
    st.caption(T["menu_caption"])
else:
    # Once the episode is under way the prompts are still reachable, but
    # collapsed: a participant who wants to change tack should not have to ask
    # the facilitator what the options were. Collapsed rather than inline so it
    # does not re-impose the multiple-choice frame on an open conversation.
    with st.expander(T["topics_expander"]):
        for i, task in enumerate(TASK_MENU[ss.language]):
            st.markdown(f"{i+1}. {task}")

# --- chat history ---
# The regenerate button (R3) must render INSIDE the last assistant bubble.
# Rendered after the loop it drifts to the bottom of a long transcript, which
# both looks unlike a real chat UI and depresses clicks — and clicks are the
# narrative-shopping sensor (P18 delta #1), i.e. a primary DV. Keep it where
# a real client puts it.
regen_clicked = False
for i, (role, text) in enumerate(ss.display):
    with st.chat_message("user" if role == "user" else "assistant"):
        st.write(text)
        # only the final message, and only if it is the AI's, gets the button
        if i == len(ss.display) - 1 and role == "assistant":
            regen_clicked = st.button(T["regenerate"], key=f"regen_{i}",
                                      type="tertiary")

# handled after the render loop — never mutate ss.display while iterating it
if regen_clicked:
    replaced = ss.display[-1][1]
    t0 = time.time()
    dropped = ss.messages.pop()  # drop last assistant message from history
    try:
        with st.spinner(T["thinking"]):
            new_text = call_model(ss.messages)
    except Exception as exc:
        ss.messages.append(dropped)  # put it back: the old reply still stands
        log_event("model_error", where="regenerate", error=repr(exc))
        st.error(T["error"])
    else:
        ss.messages.append({"role": "assistant", "content": [{"text": new_text}]})
        ss.display[-1] = ("assistant", new_text)
        log_event("regenerate", replaced_response=replaced, new_response=new_text,
                  latency_s=round(time.time() - t0, 2))
        st.rerun()

# --- pending reply: the user's message is already on screen (rendered by the
# history loop above), so now show a thinking indicator in the assistant's
# position and fetch the reply. Splitting send from fetch across two renders is
# what makes the UI behave like a real chat client: without it the whole turn
# is computed before anything paints, and the participant stares at an
# unchanged screen for 8-15s and then sees two messages appear at once.
if ss.awaiting_reply:
    with st.chat_message("assistant"):
        with st.spinner(T["thinking"]):
            try:
                ai_text = call_model(ss.messages)
            except Exception as exc:
                # Throttling, an expired key, a dropped connection. Without this
                # the traceback lands on the participant's screen AND the user
                # turn stays in history with no assistant reply after it, which
                # makes every subsequent Converse call fail too. Roll the turn
                # back so the participant can simply send again.
                rolled_back = ss.display[-1][1]
                ss.messages.pop()
                ss.display.pop()
                ss.turn_count -= 1
                ss.last_user_ts = None
                ss.awaiting_reply = False
                ss.pending_retry = rolled_back
                log_event("model_error", where="user_turn", error=repr(exc),
                          rolled_back_text=rolled_back)
                st.rerun()
    ss.messages.append({"role": "assistant", "content": [{"text": ai_text}]})
    ss.display.append(("assistant", ai_text))
    log_event("ai_turn", text=ai_text,
              response_latency_s=round(time.time() - ss.reply_started_at, 2))
    ss.awaiting_reply = False
    ss.pending_retry = None
    st.rerun()

# --- chat input ---
if not ss.episode_done:
    user_text = st.chat_input(T["input_placeholder"])
    if user_text:
        inter_turn = None
        if ss.last_user_ts is not None:
            inter_turn = round(time.time() - ss.last_user_ts, 2)
        ss.last_user_ts = time.time()
        ss.turn_count += 1
        ss.messages.append({"role": "user", "content": [{"text": user_text}]})
        ss.display.append(("user", user_text))
        log_event("user_turn", text=user_text, chars=len(user_text),
                  inter_turn_latency_s=inter_turn)
        # paint the user's message first; the reply is fetched on the next run
        ss.awaiting_reply = True
        ss.reply_started_at = time.time()
        st.rerun()

# If a turn was rolled back, explain and show the text so it need not be
# retyped. Rendered here (not at the failure site) because the failure path
# reruns to clear the thinking indicator, which would wipe an st.error there.
if "pending_retry" in ss and ss.pending_retry:
    st.error(T["error"])
    st.info(f"{T['retry']}：{ss.pending_retry}")
