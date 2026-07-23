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

ROOT = Path(__file__).resolve().parent
CONDITIONS_DIR = ROOT / "conditions"
SESSIONS_DIR = ROOT / "sessions"

MODEL_ID = "us.anthropic.claude-sonnet-4-6"
REGION = "us-west-2"
TEMPERATURE = 0.7
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
        "ratings_header": "请为刚才这段对话打分",
        "r1": "这个AI聪明吗？", "r2": "这个AI懂你吗？", "r3": "这段对话有帮助吗？",
        "ratings_submit": "提交，进入下一段",
        "all_done": "三个对话都完成了，谢谢！请回到主持人处继续。",
    },
    "en": {
        "episode_header": "Conversation {i} / 3",
        "menu_lead": "Pick one of the prompts below, or talk about anything else that's really on your mind:",
        "menu_caption": "When you're ready, just type your first message — start the way you normally would with an AI.",
        "regenerate": "Regenerate",
        "input_placeholder": "Type here…",
        "ratings_header": "Please rate the conversation you just had",
        "r1": "How smart was this AI?", "r2": "How well did it understand you?",
        "r3": "How helpful was this conversation?",
        "ratings_submit": "Submit and continue",
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
    resp = client.converse(
        modelId=MODEL_ID,
        system=[{"text": load_condition(st.session_state.current_condition)}],
        messages=messages,
        inferenceConfig={"temperature": TEMPERATURE, "maxTokens": MAX_TOKENS},
    )
    return resp["output"]["message"]["content"][0]["text"]


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
    ss.episode_done = False
    ss.session_done = False
    ss.ratings_pending = False
    ss.session_id = uuid.uuid4().hex[:8]
    ss.log_path = SESSIONS_DIR / f"{participant_id}__{ss.session_id}.jsonl"
    ss.initialized = True
    log_event("session_start", condition_order=ss.condition_order,
              model=MODEL_ID, temperature=TEMPERATURE, language=ss.language)


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
    log_event("episode_start", episode=ss.episode_index)


# ---------------- UI ----------------

st.set_page_config(page_title="对话研究", page_icon="💬", layout="centered")

if "initialized" not in st.session_state:
    st.title("对话研究 · Session")
    pid = st.text_input("参与者编号（主持人输入）", placeholder="P01")
    lang = st.radio("Session 语言（主持人选择，与参与者的 AI 常用语一致）",
                    ["zh", "en"], horizontal=True)
    if st.button("开始", disabled=not pid):
        SESSIONS_DIR.mkdir(exist_ok=True)
        init_session(pid.strip(), lang)
        st.rerun()
    st.stop()

ss = st.session_state

# --- facilitator sidebar (R6) ---
with st.sidebar:
    st.caption("主持人视图")
    st.write(f"参与者：{ss.participant_id} · 语言：{ss.language}")
    order_labels = " → ".join(CONDITION_LABELS[c] for c in ss.condition_order)
    st.write(f"条件顺序：{order_labels}")
    st.write(f"当前：episode {ss.episode_index + 1}/3 · "
             f"条件 {CONDITION_LABELS[ss.current_condition]} · "
             f"turn {ss.turn_count}/{TURNS_PER_CONDITION}")
    # Topic bookkeeping is facilitator-side: a participant-facing picker
    # would reimpose the multiple-choice frame the open first turn avoids.
    topic = st.radio(
        "本段话题（主持人记录）",
        ["1 反复想的决定", "2 说不清为什么在意", "3 没听的建议", "自带话题", "未定"],
        index=4, key=f"topic_ep{ss.episode_index}",
    )
    same_as_prev = False
    if ss.episode_index > 0:
        same_as_prev = st.checkbox("与上一段同话题", key=f"same_ep{ss.episode_index}")
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
    r1 = st.slider(T["r1"], 1, 7, 4)
    r2 = st.slider(T["r2"], 1, 7, 4)
    r3 = st.slider(T["r3"], 1, 7, 4)
    if st.button(T["ratings_submit"]):
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

# --- chat history ---
for role, text in ss.display:
    with st.chat_message("user" if role == "user" else "assistant"):
        st.write(text)

# --- regenerate button (R3): unobtrusive, under the last AI message ---
if ss.display and ss.display[-1][0] == "assistant":
    if st.button(T["regenerate"], key=f"regen_{len(ss.display)}", type="tertiary"):
        replaced = ss.display[-1][1]
        t0 = time.time()
        ss.messages.pop()  # drop last assistant message from history
        with st.spinner(""):
            new_text = call_model(ss.messages)
        ss.messages.append({"role": "assistant", "content": [{"text": new_text}]})
        ss.display[-1] = ("assistant", new_text)
        log_event("regenerate", replaced_response=replaced, new_response=new_text,
                  latency_s=round(time.time() - t0, 2))
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
        t0 = time.time()
        with st.spinner(""):
            ai_text = call_model(ss.messages)
        ss.messages.append({"role": "assistant", "content": [{"text": ai_text}]})
        ss.display.append(("assistant", ai_text))
        log_event("ai_turn", text=ai_text, response_latency_s=round(time.time() - t0, 2))
        st.rerun()
