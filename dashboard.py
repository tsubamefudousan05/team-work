"""
Autonomous Multi-Agent Strategy Chamber (High-Quota Free Tier Edition)
無料枠（1日1,500回）標準モデル適用・スレッドセーフ版
"""

import streamlit as st
import concurrent.futures
import time
from google import genai

# ==========================================
# 1. ページ基本設定 & デザイン
# ==========================================
st.set_page_config(
    page_title="Autonomous Strategy Chamber",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main { background-color: #0f1117; }
    .stTextArea textarea { font-size: 1.05rem !important; }
    div[data-testid="stExpander"] { 
        border-radius: 8px; 
        border: 1px solid #2d3748; 
        background-color: #1a202c; 
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. パスワード認証ゲート (Password: 708)
# ==========================================
APP_PASSWORD = "708"

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def check_password():
    input_pw = st.session_state.get("password_input", "")
    if input_pw == APP_PASSWORD:
        st.session_state.authenticated = True
        st.session_state.pop("password_input", None)
        st.rerun()
    else:
        st.error("パスワードが正しくありません。")

if not st.session_state.authenticated:
    st.title("🔒 Access Restricted")
    st.caption("Autonomous Strategy Chamber")
    
    col1, col2, _ = st.columns([2, 1, 3])
    with col1:
        st.text_input(
            "パスワードを入力してください",
            type="password",
            key="password_input",
            on_change=check_password
        )
    with col2:
        st.write("")
        st.write("")
        st.button("解除", type="primary", on_click=check_password, use_container_width=True)
    st.stop()

# ==========================================
# 3. コンフィグレーション
# ==========================================
API_KEY = st.secrets.get("GEMINI_API_KEY", st.session_state.get("custom_api_key", ""))

# 無料枠で1日1,500回使える安定モデルを指定
PRIMARY_MODEL = "gemini-2.5-flash"
FALLBACK_MODEL = "gemini-1.5-flash"

MAX_RETRIES = 3
BASE_WAIT_SECONDS = 4
COOLDOWN_SECONDS = 1

# ==========================================
# 4. サイドバー & コントロール
# ==========================================
with st.sidebar:
    st.header("⚙️ システム構成")
    st.markdown(f"""
    - **Security**: Authorized Session
    - **Engine**: Gemini Flash (`{PRIMARY_MODEL}`)
    - **Architecture**: 6-Agent Consensus
    - **Pipeline**:
      1. 👨‍💼 リーダー（要件定義）
      2. 🔍 リサーチャー（事実調査）
      3. ⚡ 肯定 vs 否定（並列討論）
      4. ⚖️ モデレーター（止揚・最適解）
      5. 🗺️ プランナー（工程表策定）
    """)
    st.divider()

    if not st.secrets.get("GEMINI_API_KEY"):
        key_input = st.text_input("Gemini API Key", type="password", value=API_KEY)
        if key_input:
            st.session_state.custom_api_key = key_input
            API_KEY = key_input
        st.divider()

    if st.button("ログアウト (再ロック)", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.pop("custom_api_key", None)
        st.rerun()

# ==========================================
# 5. エージェントコア
# ==========================================
def ask_agent(
    role_title: str,
    system_instruction: str,
    prompt: str,
    primary_model: str = PRIMARY_MODEL,
    fallback_model: str = FALLBACK_MODEL,
) -> str:
    if not API_KEY:
        raise ValueError("APIキーが設定されていません。")

    client = genai.Client(api_key=API_KEY)
    combined_prompt = (
        f"【あなたの役割・ルール】\n{system_instruction}\n"
        f"※回答は要点を整理し、箇条書きを活用して構造化してください。\n\n"
        f"【入力テキスト】\n{prompt}"
    )
    current_model = primary_model

    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=current_model,
                contents=combined_prompt,
            )
            time.sleep(COOLDOWN_SECONDS)
            return response.text
        except Exception as err:
            if attempt < MAX_RETRIES - 1:
                current_model = fallback_model
                time.sleep(BASE_WAIT_SECONDS)
            else:
                raise RuntimeError(f"[{role_title}] モデル呼び出し失敗 ({current_model}): {err}")

# ==========================================
# 6. メインUIレイアウト
# ==========================================
st.title("⚖️ Autonomous Strategy Chamber")
st.caption("6体の自律型AIエージェントによる多角的合議制ディシジョン・エンジン")

default_theme = "日本の空家問題と不動産会社の空き家ビジネスの成功例を元に、岡山市内でできる新事業は何か"
user_theme = st.text_area(
    "プロジェクトテーマ・検討課題",
    value=default_theme,
    height=90,
    help="事業アイデア、法務戦略、業務改善など多角的に検証したい課題を入力してください。"
)

run_button = st.button("🚀 合議セッションを開始", type="primary", use_container_width=False)

# ==========================================
# 7. セッション実行パイプライン
# ==========================================
if run_button:
    if not API_KEY:
        st.error("Gemini APIキーが設定されていません。Secretsに登録するか、サイドバーから入力してください。")
    elif not user_theme.strip():
        st.warning("テーマを入力してください。")
    else:
        total_start = time.time()
        with st.status("エージェントセッション実行中...", expanded=True) as status:
            try:
                # Phase 1: リーダー
                t0 = time.time()
                status.write("👨‍💼 **チームリーダー** が課題設計と調査要件を定義中...")
                leader_prompt = "優秀なリーダーとして、目標とリサーチャーが調べるべき調査項目を3〜4点箇条書きで示してください。"
                leader_out = ask_agent("リーダー", leader_prompt, user_theme)
                status.write(f"└ 完了 (+{time.time() - t0:.1f}s)")

                # Phase 2: リサーチャー
                t0 = time.time()
                status.write("🔍 **リサーチャー** が事例・ファクトデータを収集中...")
                researcher_prompt = "客観的なリサーチャーとして、事実・先行事例・データのみを整理してください。"
                research_out = ask_agent("リサーチャー", researcher_prompt, leader_out)
                status.write(f"└ 完了 (+{time.time() - t0:.1f}s)")

                # Phase 3: 並列討論
                t0 = time.time()
                status.write("⚡ **肯定派 vs 否定派** が並列スレッドで激論中...")
                promoter_prompt = "熱狂的なプロモーターとして、成功理由とビジネスの収益ポテンシャルを強調してください。"
                redteam_prompt = "冷酷なレッドチームとして、致命的な法的・コスト・運用リスクを容赦なく指摘してください。"

                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                    f_pro = executor.submit(ask_agent, "肯定派", promoter_prompt, research_out)
                    f_con = executor.submit(ask_agent, "否定派", redteam_prompt, research_out)
                    promoter_out = f_pro.result()
                    redteam_out = f_con.result()
                status.write(f"└ 完了 (+{time.time() - t0:.1f}s)")

                # Phase 4: モデレーター
                t0 = time.time()
                status.write("⚖️ **モデレーター** がトレードオフを最適化中...")
                moderator_prompt = "冷静なモデレーターとして、肯定派の利益と否定派のリスクを統合した最適妥協案を導いてください。"
                moderator_input = f"【肯定派】\n{promoter_out}\n\n【否定派】\n{redteam_out}"
                moderator_out = ask_agent("モデレーター", moderator_prompt, moderator_input)
                status.write(f"└ 完了 (+{time.time() - t0:.1f}s)")

                # Phase 5: プランナー
                t0 = time.time()
                status.write("🗺️ **プランナー** がアクションロードマップを策定中...")
                planner_prompt = "実行力のあるプランナーとして、明日から着手できる具体的な実行ロードマップを作成してください。"
                planner_out = ask_agent("プランナー", planner_prompt, moderator_out)
                status.write(f"└ 完了 (+{time.time() - t0:.1f}s)")

                status.update(
                    label=f"✅ 全合議プロセス完了 (総所要時間: {time.time() - total_start:.1f}秒)",
                    state="complete",
                    expanded=False
                )

                # ==========================================
                # 8. 結果描画セクション
                # ==========================================
                st.divider()

                with st.expander("📌 Phase 1 & 2: 前提設計とファクトデータ", expanded=False):
                    st.markdown("#### 👨‍💼 チームリーダーの要件定義")
                    st.markdown(leader_out)
                    st.markdown("---")
                    st.markdown("#### 🔍 リサーチャーの調査結果")
                    st.markdown(research_out)

                st.markdown("### ⚔️ Phase 3: 対立討論（プロモーター vs レッドチーム）")
                col_pro, col_con = st.columns(2)
                with col_pro:
                    with st.container(border=True):
                        st.markdown("#### ✨ 肯定派（プロモーター）")
                        st.markdown(promoter_out)
                with col_con:
                    with st.container(border=True):
                        st.markdown("#### 🔥 否定派（レッドチーム）")
                        st.markdown(redteam_out)

                st.markdown("### ⚖️ Phase 4: 止揚・最適解（モデレーター）")
                with st.container(border=True):
                    st.markdown(moderator_out)

                st.markdown("### 🗺️ Phase 5: 確定アクションロードマップ（プランナー）")
                with st.container(border=True):
                    st.markdown(planner_out)

            except Exception as e:
                status.update(label="❌ エラーが発生しました", state="error", expanded=True)
                st.error(f"実行エラー詳細: {e}")