"""알파벳 캐치! 한 컴퓨터 2인용.
실행: streamlit run app.py
GitHub에 app.py와 requirements.txt를 올리고 Streamlit에서 배포하세요.
두 사람이 하나의 브라우저 화면과 마우스를 공유하는 버튼 방식입니다.
단어의 실제 존재 여부는 두 사람이 확인한 뒤 정답/오답으로 판정합니다.
"""
import random
import re
import streamlit as st

st.set_page_config(page_title="알파벳 캐치! 2인 대결", page_icon="🎯", layout="centered")
WORDS = "apple animal artist ant airport basket boat bread book bird beach cake cat cloud coat cup clock dance desk dog dream door earth egg elephant energy eye face fish flower food friend game garden gift girl glass grape hand hat heart hill home horse house ice idea island jacket juice jump key king kite kitchen lake lamp leaf lemon light lion magic map milk moon mouse music name night nose ocean orange page park pen pencil phone piano picture pizza plant plate queen question rabbit rain river road robot rock room rose school sea seed sheep ship shoe shop snake snow song spoon star stone story street sugar sun table tea team tiger time tomato train tree truck umbrella uncle valley vegetable video village voice water wave whale wind window wing winter wolf wood world year yellow zebra zero zoo".split()
PAIRS = sorted({(w[0].upper(), w[-1].upper()) for w in WORDS})

def new_round(g):
    g['letters'] = random.choice([p for p in PAIRS if p != g.get('letters')])
    g.update(catcher=None, blocked=set(), answer='', awaiting=False)
    g['round'] += 1

def fresh_game():
    g = dict(scores={1: 0, 2: 0}, round=0, letters=None, catcher=None,
             blocked=set(), answer='', awaiting=False, used=set(), winner=None,
             notice='자신의 번호 버튼을 눌러 캐치하세요!')
    new_round(g)
    return g

def catch(g, player):
    if g['winner'] or g['catcher'] is not None or player in g['blocked']:
        return False
    g['catcher'] = player
    g['notice'] = f'{player}번 참가자 캐치! 답을 입력하세요.'
    return True

def wrong(g):
    player = g['catcher']
    if player is None or g['winner']:
        return
    g['blocked'].add(player)
    g.update(catcher=None, answer='', awaiting=False)
    g['notice'] = f'{player}번 참가자 오답! 이번 문제에서는 다시 캐치할 수 없습니다.'
    if len(g['blocked']) == 2:
        new_round(g)
        g['notice'] = '두 사람 모두 오답! 새로운 문제에 도전하세요.'

def correct(g):
    player = g['catcher']
    if player is None or not g['awaiting'] or g['winner']:
        return
    word = g['answer']
    g['scores'][player] += 1
    g['used'].add(word)
    g['notice'] = f'{player}번 참가자 정답! {word.upper()} · +1점'
    if g['scores'][player] >= 5:
        g['winner'] = player
    else:
        new_round(g)

st.markdown('''<style>
.stApp{background:#f4f1e7;}
.board{background:#163f35;border:10px solid #ae7c48;border-radius:18px;
padding:28px 12px;text-align:center;color:#fff9e6;margin:18px 0 24px;}
.catch{font-size:28px;font-weight:800;color:#ffe28a;min-height:44px;}
.letters{font-size:clamp(64px,15vw,112px);font-weight:900;letter-spacing:16px;}
.rule{font-size:17px;color:#dce9de;}
.stButton>button{min-height:58px;border-radius:14px;font-size:20px;font-weight:800;}
</style>''', unsafe_allow_html=True)
st.title('🎯 알파벳 캐치!')
st.caption('한 컴퓨터 · 한 화면 · 2인 대결 · 먼저 5점이면 우승!')

if 'game' not in st.session_state:
    st.session_state.game = fresh_game()
if 'instructions_done' not in st.session_state:
    st.session_state.instructions_done = False

@st.dialog('📖 알파벳 캐치! 게임 방법', dismissible=False)
def instructions():
    st.markdown('''### 두 사람이 한 컴퓨터에서 즐기는 영단어 대결!
1. 칠판의 **첫 알파벳으로 시작하고 두 번째 알파벳으로 끝나는 영단어**를 생각하세요. 예: **A · E → apple**.
2. 1번 참가자는 **1번 캐치!**, 2번 참가자는 **2번 캐치!** 버튼을 누르세요.
3. 먼저 누른 참가자가 키보드로 단어를 입력하고 제출합니다.
4. 두 사람이 단어를 확인한 뒤 **정답 +1점** 또는 **오답**을 누릅니다. 실제 영단어 여부는 자동 판정하지 않습니다.
5. 오답자는 **같은 문제에서 다시 캐치할 수 없고**, 상대만 도전할 수 있습니다.
6. 정답이 나오거나 둘 다 틀리면 다음 문제! **먼저 5점이면 우승**입니다.

**조작 안내:** 하나의 화면과 마우스를 공유하는 게임입니다. 키보드 숫자키 1·2는 캐치 기능이 아닙니다. 같은 정답은 한 게임에서 다시 쓸 수 없습니다.''')
    if st.button('알겠어요! 게임 시작 🎮', type='primary', use_container_width=True):
        st.session_state.instructions_done = True
        st.rerun()

if not st.session_state.instructions_done:
    instructions()
    st.stop()

g = st.session_state.game
with st.sidebar:
    st.header('게임 메뉴')
    if st.button('📖 게임 방법 다시 보기', use_container_width=True):
        st.session_state.instructions_done = False
        st.rerun()
    if st.button('🔄 점수 초기화 · 새 게임', use_container_width=True):
        st.session_state.game = fresh_game()
        st.rerun()
    st.caption('같은 컴퓨터, 같은 브라우저 탭에서 플레이하세요. 다른 기기와 점수는 공유되지 않습니다. 새로고침하면 게임이 초기화될 수 있습니다.')

cols = st.columns(2)
for player, col in zip((1, 2), cols):
    with col:
        st.metric(f'{player}번 참가자', f"{g['scores'][player]} / 5점")
st.info(g['notice'])
if g['winner']:
    st.success(f"🏆 {g['winner']}번 참가자 우승! 먼저 5점을 달성했습니다.")
    if not st.session_state.get('celebrated', False):
        st.balloons()
        st.session_state.celebrated = True
    if st.button('한 판 더! 🎮', type='primary', use_container_width=True):
        st.session_state.game = fresh_game()
        st.session_state.celebrated = False
        st.rerun()
    st.stop()
st.session_state.celebrated = False

who = f"{g['catcher']}번 참가자 캐치!" if g['catcher'] else '준비… 먼저 캐치하세요!'
a, b = g['letters']
st.markdown(f'<div class="board"><div class="catch">{who}</div><div class="letters">{a} · {b}</div><div class="rule">{a}로 시작하고 {b}로 끝나는 영단어!</div></div>', unsafe_allow_html=True)
st.caption(f"문제 {g['round']} · 정답 +1점 · 오답자는 이번 문제 캐치 금지")
cols = st.columns(2)
for player, col in zip((1, 2), cols):
    with col:
        disabled = g['catcher'] is not None or player in g['blocked']
        label = f'{player}번 캐치!' if player not in g['blocked'] else f'{player}번 · 이번 문제 도전 불가'
        if st.button(label, disabled=disabled, type='primary', use_container_width=True, key=f'catch_{player}'):
            catch(g, player)
            st.rerun()

if g['catcher'] is not None:
    player = g['catcher']
    if not g['awaiting']:
        with st.form(f"answer_{g['round']}_{player}"):
            text = st.text_input(f'{player}번 참가자의 영단어', max_chars=60, placeholder='영단어를 입력하세요')
            submitted = st.form_submit_button('답 제출', type='primary', use_container_width=True)
        if submitted:
            word = text.strip().lower()
            if not word:
                st.warning('단어를 입력한 뒤 제출하세요.')
            elif (not re.fullmatch('[a-z]{2,}', word) or
                  not word.startswith(a.lower()) or not word.endswith(b.lower()) or word in g['used']):
                wrong(g)
                g['notice'] = '조건에 맞지 않거나 이미 사용한 단어입니다. 오답 처리되었습니다. ' + g['notice']
                st.rerun()
            else:
                g.update(answer=word, awaiting=True)
                st.rerun()
        if st.button('모르겠어요 · 오답 처리', use_container_width=True):
            wrong(g)
            st.rerun()
    else:
        st.subheader(f"제출한 단어: {g['answer'].upper()}")
        st.caption('두 사람이 실제 영단어인지 확인한 뒤 판정해주세요. 고유명사·약어·활용형 허용 여부는 미리 합의하세요.')
        yes, no = st.columns(2)
        if yes.button('✅ 정답 +1점', type='primary', use_container_width=True):
            correct(g)
            st.rerun()
        if no.button('❌ 오답', use_container_width=True):
            wrong(g)
            st.rerun()

with st.expander('둘 다 모르겠다면?'):
    if st.button('이 문제 건너뛰기 · 점수 변화 없음', use_container_width=True):
        new_round(g)
        g['notice'] = '새로운 알파벳으로 도전하세요!'
        st.rerun()
