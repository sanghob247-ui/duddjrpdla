"""알파벳 캐치! — Streamlit 단일 서버용 3인 실시간 게임.
실행: streamlit run app.py
배포: GitHub에 app.py와 requirements.txt 업로드 → Streamlit Community Cloud.
QR은 배포된 공개 URL을 입력하면 생성됩니다. 외부 DB는 필요 없습니다.
주의: 방은 서버 메모리에만 존재하며 재시작/절전 시 초기화됩니다.
여러 서버 인스턴스를 사용하는 배포에서는 공유 DB가 추가로 필요합니다.
"""
import io
import random
import re
import secrets
import string
import threading
import time
from urllib.parse import urlsplit, urlunsplit, urlencode

import qrcode
import streamlit as st

st.set_page_config(page_title="알파벳 캐치!", page_icon="🎯", layout="centered")

# 존재하는 영단어 예시에서 얻은 시작/끝 조합. 예시 자체는 정답 판정에 쓰지 않습니다.
WORDS = "apple animal artist ant airport basket boat bread book bird beach cake cat cloud coat cup clock dance desk dog dream door earth egg elephant energy eye face fish flower food friend game garden gift girl glass grape hand hat heart hill home horse house ice idea island jacket juice jump key king kite kitchen lake lamp leaf lemon light lion magic map milk moon mouse music name night nose ocean orange page park pen pencil phone piano picture pizza plant plate queen question rabbit rain river road robot rock room rose school sea seed sheep ship shoe shop snake snow song spoon star stone story street sugar sun table tea team tiger time tomato train tree truck umbrella uncle valley vegetable video village voice water wave whale wind window wing winter wolf wood world year yellow zebra zero zoo".split()
PAIRS = sorted({(w[0].upper(), w[-1].upper()) for w in WORDS})

@st.cache_resource
def shared_store():
    return {"lock": threading.RLock(), "rooms": {}}

STORE = shared_store()

def make_round(room):
    options = [p for p in PAIRS if p != room.get("letters")]
    room.update(letters=random.choice(options), catcher=None, blocked=set(), answer="", status="playing")
    room["round"] += 1

def create_room():
    with STORE["lock"]:
        now = time.time()
        for code in list(STORE["rooms"]):
            if now - STORE["rooms"][code]["touched"] > 86400:
                del STORE["rooms"][code]
        while True:
            code = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
            if code not in STORE["rooms"]:
                break
        room = {"host": secrets.token_urlsafe(24), "players": {}, "scores": {1: 0, 2: 0, 3: 0},
                "round": 0, "letters": None, "catcher": None, "blocked": set(), "answer": "",
                "status": "lobby", "winner": None, "used": set(), "notice": "참가자를 기다리는 중입니다.",
                "touched": now}
        STORE["rooms"][code] = room
        return code, room["host"]

def snapshot(code):
    with STORE["lock"]:
        r = STORE["rooms"].get(code)
        if not r:
            return None
        r["touched"] = time.time()
        return {**r, "players": {k: dict(v) for k, v in r["players"].items()},
                "scores": dict(r["scores"]), "blocked": set(r["blocked"]), "used": set(r["used"])}

def act(code, action, seat=None, value=None):
    """모든 판정과 캐치는 동일한 잠금 아래 처리해 중복 우승/동시 캐치를 방지합니다."""
    with STORE["lock"]:
        r = STORE["rooms"].get(code)
        if not r:
            return "방이 없어졌습니다. 새 방에 입장하세요."
        r["touched"] = time.time()
        uid = st.session_state["uid"]
        host = secrets.compare_digest(str(st.session_state.get("host_token", "")), r["host"])
        if action == "join":
            if r["status"] != "lobby":
                return "게임 시작 후에는 참가 번호를 바꿀 수 없습니다."
            if seat not in (1, 2, 3):
                return "참가 번호를 확인하세요."
            if seat in r["players"] and r["players"][seat]["uid"] != uid:
                return "이미 사용 중인 번호입니다. 다른 번호를 선택하세요."
            for old in list(r["players"]):
                if r["players"][old]["uid"] == uid:
                    del r["players"][old]
            r["players"][seat] = {"uid": uid, "name": (value or f"참가자 {seat}")[:16]}
            st.session_state["seat"] = seat
            return None
        if action in {"start", "correct", "wrong", "skip", "reset", "release"}:
            if not host:
                return "진행자만 사용할 수 있습니다."
            if action == "release":
                if r["status"] != "lobby":
                    return "대기실에서만 자리를 비울 수 있습니다."
                r["players"].pop(seat, None)
                return None
            if action == "reset":
                r.update(scores={1: 0, 2: 0, 3: 0}, round=0, status="lobby", winner=None,
                         letters=None, catcher=None, blocked=set(), answer="", used=set(),
                         notice="새 게임! 참가 번호를 확인한 뒤 시작하세요.")
                return None
            if action == "start":
                if r["status"] != "lobby":
                    return "이미 시작한 게임입니다."
                if len(r["players"]) < 2:
                    return "2명 이상 참가해야 시작할 수 있습니다."
                make_round(r)
                r["notice"] = "시작! 자신의 번호를 눌러 캐치하세요."
                return None
            if r["status"] != "playing":
                return "진행 중인 문제가 없습니다."
            # 오래된 화면의 판정이 새 문제에 적용되는 것을 방지합니다.
            if value != r["round"]:
                return "문제가 바뀌었습니다. 현재 화면을 확인하세요."
            if action == "skip":
                make_round(r)
                r["notice"] = "진행자가 새 문제로 넘겼습니다."
                return None
            who = r["catcher"]
            if who is None or not r["answer"]:
                return "캐치한 참가자가 답을 제출해야 판정할 수 있습니다."
            word = r["answer"]
            if action == "correct":
                r["scores"][who] += 1
                r["used"].add(word)
                r["notice"] = f"{who}번 참가자 정답! {word.upper()} · +1점"
                if r["scores"][who] >= 5:
                    r["winner"] = who
                    r["status"] = "finished"
                else:
                    make_round(r)
                return None
            r["blocked"].add(who)
            r["catcher"] = None
            r["answer"] = ""
            r["notice"] = f"{who}번 참가자 오답! 이번 문제에서는 다시 캐치할 수 없습니다."
            if set(r["players"]).issubset(r["blocked"]):
                make_round(r)
                r["notice"] = "모두 오답! 새로운 알파벳으로 다시 도전하세요."
            return None
        if seat not in r["players"] or r["players"][seat]["uid"] != uid:
            return "먼저 본인의 참가 번호를 선택하세요."
        if r["status"] != "playing":
            return "진행 중인 문제가 없습니다."
        if action == "catch":
            if value != r["round"]:
                return "문제가 바뀌었습니다. 다시 눌러 주세요."
            if seat in r["blocked"]:
                return "오답자는 이 문제에서 다시 캐치할 수 없습니다."
            if r["catcher"] is not None:
                return "다른 참가자가 먼저 캐치했습니다."
            r["catcher"] = seat
            r["notice"] = f"{seat}번 참가자 캐치! 답을 입력하세요."
        elif action == "answer":
            word, round_id = value
            if round_id != r["round"] or r["catcher"] != seat or r["answer"]:
                return "현재 답을 제출할 수 없습니다."
            word = word.strip().lower()
            if not re.fullmatch(r"[a-z]{2,}", word):
                return "공백 없이 영문 알파벳 2글자 이상 입력하세요."
            a, b = r["letters"]
            if not (word.startswith(a.lower()) and word.endswith(b.lower())):
                return f"{a}로 시작하고 {b}로 끝나는 단어를 입력하세요."
            if word in r["used"]:
                return "이번 게임에서 이미 정답으로 나온 단어입니다."
            r["answer"] = word
        return None

def feedback(error):
    if error:
        st.warning(error)
    else:
        st.rerun()

st.markdown('''<style>
.stApp {background:#f3f1e8;color:#192f2a;}
h1,h2,h3 {color:#173c33!important;}
.board {background:#143e34;border:10px solid #ad7948;border-radius:18px;padding:24px 12px;
text-align:center;color:#fffdf0;box-shadow:0 8px 0 #d7d1be;margin:12px 0 22px;}
.board .catch {font-size:clamp(20px,5vw,32px);font-weight:800;color:#ffe580;min-height:48px;}
.board .letters {font-size:clamp(64px,18vw,120px);letter-spacing:18px;font-weight:900;line-height:1.35;}
.board .rule {font-size:17px;color:#dce9dc;}
.stButton>button {border-radius:14px;min-height:52px;font-weight:800;}
</style>''', unsafe_allow_html=True)
st.title("🎯 알파벳 캐치!")
st.caption("먼저 캐치하고, 영단어를 쓰세요 · 2~3인 · 먼저 5점이면 우승!")
with st.expander("📖 어떤 게임인가요? 처음이라면 읽어 주세요", expanded="code" not in st.session_state):
    st.markdown("""1. 진행자가 방을 만들고 QR 또는 방 코드로 친구를 초대합니다.
2. 각자 **1번·2번·3번 중 서로 다른 번호**를 선택합니다. 진행자는 관전만 하거나 참가할 수 있습니다.
3. 칠판에 나온 **첫 알파벳으로 시작하고 두 번째 알파벳으로 끝나는 영단어**를 생각하세요. 예: **A → E = apple**.
4. 본인의 번호 버튼을 먼저 누르면 **‘N번 참가자 캐치!’**가 뜹니다. 캐치한 사람만 답을 입력합니다.
5. 진행자가 실제 영단어인지 판정합니다. 정답 **+1점**, 오답자는 **그 문제에서 재도전 불가**! 나머지 사람만 캐치할 수 있습니다.
6. 정답이 나오거나 모두 틀리면 새로운 문제로 넘어갑니다. **먼저 5점이면 우승**합니다.

같은 정답 재사용은 금지합니다. 고유명사·약어·활용형의 허용 여부는 시작 전 합의하세요.
번호 선택은 화면 버튼 방식입니다. 서로 다른 기기에서는 서버가 먼저 받은 캐치를 인정합니다.""")
if "uid" not in st.session_state:
    st.session_state["uid"] = secrets.token_urlsafe(24)
if "code" not in st.session_state:
    st.subheader("🏫 교실에 입장하기")
    if st.button("새 방 만들기 · 진행자", type="primary", use_container_width=True):
        code, token = create_room()
        st.session_state.update(code=code, host_token=token)
        st.query_params["room"] = code
        st.rerun()
    with st.form("enter"):
        code_input = st.text_input("방 코드", value=str(st.query_params.get("room", ""))).strip().upper()
        enter = st.form_submit_button("방에 들어가기", use_container_width=True)
    if enter:
        if snapshot(code_input):
            st.session_state["code"] = code_input
            st.session_state.pop("host_token", None)
            st.rerun()
        else:
            st.error("방을 찾을 수 없습니다. 코드를 확인하거나 새 방을 만드세요.")
    st.stop()

code = st.session_state["code"]
if not snapshot(code):
    st.error("서버가 재시작되었거나 방이 만료되었습니다. 새 방을 만들어 주세요.")
    if st.button("처음으로"):
        for key in ("code", "host_token", "seat"):
            st.session_state.pop(key, None)
        st.query_params.clear()
        st.rerun()
    st.stop()

@st.fragment(run_every=0.5)
def game():
    r = snapshot(code)
    if not r:
        st.error("방이 종료되었습니다. 페이지를 새로고침하세요.")
        return
    host = st.session_state.get("host_token") == r["host"]
    seat = next((n for n, p in r["players"].items() if p["uid"] == st.session_state["uid"]), None)
    st.caption(f"방 코드: {code}  |  {'👑 진행자' if host else '참가자/관전자'}" + (f" · 내 번호 {seat}번" if seat else ""))
    if r["status"] == "lobby":
        name = st.text_input("내 이름 (선택)", max_chars=16, key="player_name")
        columns = st.columns(3)
        for n, column in enumerate(columns, 1):
            p = r["players"].get(n)
            occupied = p is not None and p["uid"] != st.session_state["uid"]
            label = f"{n}번 · {p['name']}" if p else f"{n}번 참가하기"
            if column.button(label, key=f"join{n}", disabled=occupied, use_container_width=True):
                feedback(act(code, "join", n, name))
        if host:
            st.info("2~3명이 번호를 선택한 뒤 시작하세요. QR 초대는 아래에 있습니다.")
            if st.button("🚀 게임 시작", type="primary", disabled=len(r["players"]) < 2, use_container_width=True):
                feedback(act(code, "start"))
            with st.expander("연결이 끊긴 참가자 자리 비우기"):
                for n in sorted(r["players"]):
                    if st.button(f"{n}번 자리 비우기", key=f"release{n}"):
                        feedback(act(code, "release", n))
    cols = st.columns(3)
    for n, col in enumerate(cols, 1):
        p = r["players"].get(n)
        col.metric(f"{n}번 · {p['name'] if p else '빈 자리'}", f"{r['scores'][n]} / 5")
    if r["status"] == "playing":
        a, b = r["letters"]
        message = f"{r['catcher']}번 참가자 캐치!" if r["catcher"] else "준비… 먼저 캐치하세요!"
        st.markdown(f'<div class="board"><div class="catch">{message}</div><div class="letters">{a} {b}</div><div class="rule">{a}로 시작 → {b}로 끝나는 영단어</div></div>', unsafe_allow_html=True)
        st.caption(f"문제 {r['round']} · 오답으로 잠긴 번호: " + (", ".join(map(str, sorted(r["blocked"]))) or "없음"))
        cols = st.columns(3)
        for n, col in enumerate(cols, 1):
            disabled = seat != n or n in r["blocked"] or r["catcher"] is not None
            if col.button(f"{n}번 ⚡ 캐치!", key=f"catch{n}", disabled=disabled, type="primary", use_container_width=True):
                feedback(act(code, "catch", n, r["round"]))
        if seat == r["catcher"] and not r["answer"]:
            with st.form(f"answer_{r['round']}_{seat}"):
                word = st.text_input("영단어를 쓰세요", max_chars=45)
                submit = st.form_submit_button("답 제출", use_container_width=True)
            if submit:
                feedback(act(code, "answer", seat, (word, r["round"])))
        if r["answer"]:
            st.success(f"제출 답안: {r['answer'].upper()} — 진행자 판정 대기 중")
            if host:
                yes, no = st.columns(2)
                if yes.button("✅ 정답 +1", use_container_width=True):
                    feedback(act(code, "correct", value=r["round"]))
                if no.button("❌ 오답 · 캐치 잠금", use_container_width=True):
                    feedback(act(code, "wrong", value=r["round"]))
        if host and st.button("⏭ 답이 안 나오나요? 다음 문제", use_container_width=True):
            feedback(act(code, "skip", value=r["round"]))
    st.info(r["notice"])
    if r["status"] == "finished":
        winner = r["winner"]
        st.success(f"🏆 {winner}번 참가자 {r['players'][winner]['name']} 우승! 5점을 먼저 달성했습니다.")
        if st.session_state.get("celebrated") != (code, r["round"], winner):
            st.balloons()
            st.session_state["celebrated"] = (code, r["round"], winner)
    if host:
        with st.expander("🔗 QR로 초대하기 / 진행자 관리"):
            public_url = st.text_input("배포된 앱의 공개 주소", placeholder="https://your-game.streamlit.app", key="public_url")
            if public_url:
                parts = urlsplit(public_url.strip())
                if parts.scheme in ("http", "https") and parts.netloc and not parts.username:
                    join_url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode({"room": code}), ""))
                    image = qrcode.make(join_url)
                    output = io.BytesIO()
                    image.save(output, format="PNG")
                    st.image(output.getvalue(), width=230)
                    st.code(join_url, language=None)
                    st.caption("이 QR은 현재 방으로 연결됩니다. 참가자는 접속 후 방 입장 → 번호 선택을 해 주세요.")
                else:
                    st.warning("https://로 시작하는 올바른 공개 주소를 입력하세요.")
            st.warning("서버 재시작·절전 시 점수와 방이 초기화됩니다. 진행자 페이지를 닫거나 새로고침하면 진행자 권한이 사라질 수 있습니다.")
            confirm = st.checkbox("점수를 지우고 대기실로 돌아갈게요", key="confirm_reset")
            if st.button("새 게임 시작 · 점수 초기화", disabled=not confirm):
                st.session_state.pop("celebrated", None)
                feedback(act(code, "reset"))

game()
with st.expander("⚙️ GitHub · Streamlit 배포 안내"):
    st.markdown("""1. GitHub 저장소에 **app.py**, **requirements.txt** 두 파일을 올립니다.
2. Streamlit Community Cloud에서 저장소를 연결하고 실행 파일을 **app.py**로 지정해 배포합니다.
3. 배포된 주소로 접속해 **새 방 만들기**를 누릅니다.
4. 진행자의 **QR로 초대하기**에서 배포 주소를 입력하고 QR을 화면에 띄웁니다.
5. 참가자는 QR을 스캔하고 방에 입장한 뒤 서로 다른 번호를 선택합니다.

스마트폰과 진행자 PC가 같은 Wi-Fi일 필요는 없지만 모두 인터넷 연결이 필요합니다.
정답 판정은 진행자 수동 방식이며 외부 사전 API, 계정, 비밀 키는 필요 없습니다.
캐치 우선순위는 기기의 터치 시각이 아닌 서버 수신 순서입니다. 화면 반영은 약 0.5초 간격입니다.
참가 번호는 브라우저 세션에 연결됩니다. 경기 도중 새로고침·기기 변경은 피하세요.
이 앱은 수업용 단일 서버 버전입니다. 장기 기록 저장·다중 서버 운영에는 공유 데이터베이스가 필요합니다.""")
