"""
Autonomous Multi-Agent Strategy Chamber (Executive Summary Edition)
最上部エグゼクティブ・リード表示 & 全合議ダウンロード対応版
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
    .lead-box {
        border-left: 5px solid #3b82f6;
        background-color: #1e293b;
        padding: 1.2rem;
        border-radius: 6px;
        margin-bottom: 1.5rem;
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

PRIMARY_MODEL = "gemini-3.5-flash-lite"
FALLBACK_MODEL = "gemini-3-flash-preview"

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
      6. 🎯 エグゼクティブ・リード（総括抽出）
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
        f"【あなたの役割・ペルソナ】\n{system_instruction}\n\n"
        f"【入力コンテキスト】\n{prompt}\n\n"
        f"【出力要件】\n"
        f"- 感情的・過剰な煽り表現は排除し、プロフェッショナルな実務論理で記述すること。\n"
        f"- 構造化された見出し・箇条書き・根拠を明確に提示すること。"
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
                raise RuntimeError(f"[{role_title}] モデル呼出失敗 ({current_model}): {err}")

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
                leader_prompt = (
                    "あなたは冷静沈着なプロジェクト総括責任者です。"
                    "提示されたテーマの本質的ゴールを定め、リサーチャーが調査すべきファクト項目（市場性・法規制・競合動向等）を"
                    "具体的かつ明確に整理してください。"
                )
                leader_out = ask_agent("リーダー", leader_prompt, user_theme)
                status.write(f"└ 完了 (+{time.time() - t0:.1f}s)")

                # Phase 2: リサーチャー
                t0 = time.time()
                status.write("🔍 **リサーチャー** が事例・ファクトデータを収集中...")
                researcher_prompt = (
                    "あなたは客観性を重んじるシニアリサーチャーです。"
                    "リーダーの要件定義に基づき、客観的事実、既存の成功モデル、公的統計・制度、市場動向のみを"
                    "私見を交えずに構造化して抽出してください。"
                )
                research_out = ask_agent("リサーチャー", researcher_prompt, leader_out)
                status.write(f"└ 完了 (+{time.time() - t0:.1f}s)")

                # Phase 3: 並列討論
                t0 = time.time()
                status.write("⚡ **肯定派 vs 否定派** が並列スレッドで激論中...")
                promoter_prompt = (
                    "あなたは洗練された事業開発責任者（BizDev）です。ネットスラングや過剰な感嘆符は一切使わず、"
                    "リサーチ結果を踏まえて、この事業が成立する確固たる根拠、経済的メリット、参入障壁の突破口、"
                    "収益化のポテンシャルを理路整然と力強く提示してください。"
                )
                redteam_prompt = (
                    "あなたは冷静沈着な最高リスク管理責任者（CRO）です。感情論ではなく冷徹な実務視点から、"
                    "法規制、財務・キャッシュフロー、リソース不足、契約トラブル、撤退シナリオなど、"
                    "想定される致命的脆弱性を厳密に列挙・告発してください。"
                )

                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                    f_pro = executor.submit(ask_agent, "肯定派", promoter_prompt, research_out)
                    f_con = executor.submit(ask_agent, "否定派", redteam_prompt, research_out)
                    promoter_out = f_pro.result()
                    redteam_out = f_con.result()
                status.write(f"└ 完了 (+{time.time() - t0:.1f}s)")

                # Phase 4: モデレーター
                t0 = time.time()
                status.write("⚖️ **モデレーター** がトレードオフを最適化中...")
                moderator_prompt = (
                    "あなたは中立的で公平な経営判断を下すチーフモデレーターです。"
                    "BizDev（推進派）の好機とCRO（慎重派）のリスクを対比・止揚し、"
                    "リスクを統制しつつ利益を確保する「現実的な最適妥協案」を論理的に策定してください。"
                )
                moderator_input = f"【BizDev（肯定意見）】\n{promoter_out}\n\n【CRO（否定・リスク指摘）】\n{redteam_out}"
                moderator_out = ask_agent("モデレーター", moderator_prompt, moderator_input)
                status.write(f"└ 完了 (+{time.time() - t0:.1f}s)")

                # Phase 5: プランナー
                t0 = time.time()
                status.write("🗺️ **プランナー** がアクションロードマップを策定中...")
                planner_prompt = (
                    "あなたは実務遂行力に長けたプロジェクトマネージャー（PMO）です。"
                    "モデレーターの最適解に基づき、初期検証（PoC）から本格展開までのフェーズ分け、"
                    "各フェーズでの具体的タスク、成果物、検証基準を整理した実効性の高いロードマップを策定してください。"
                )
                planner_out = ask_agent("プランナー", planner_prompt, moderator_out)
                status.write(f"└ 完了 (+{time.time() - t0:.1f}s)")

                # Phase 6: エグゼクティブ・リード生成
                t0 = time.time()
                status.write("🎯 **エグゼクティブ・リード** を抽出中...")
                lead_prompt = (
                    "あなたは経営陣向けのブリーフィングを担当するチーフストラテジストです。"
                    "モデレーターの最適解とプランナーのロードマップから、最も重要な結論だけを抜き出した"
                    "『エグゼクティブ・サマリー（リード文）』を作成してください。\n"
                    "以下のフォーマットを厳守してください：\n"
                    "【意思決定の結論】（1〜2行で本質的方針を明快に断言）\n"
                    "- 採用モデル：〜\n"
                    "- 最大の防御策（リスク遮断）：〜\n"
                    "- 直近の最優先アクション（Next Action）：〜"
                )
                lead_input = f"【モデレーターの最適解】\n{moderator_out}\n\n【プランナーの工程表】\n{planner_out}"
                lead_out = ask_agent("リード生成", lead_prompt, lead_input)
                status.write(f"└ 完了 (+{time.time() - t0:.1f}s)")

                total_time = time.time() - total_start
                status.update(
                    label=f"✅ 全合議プロセス完了 (総所要時間: {total_time:.1f}秒)",
                    state="complete",
                    expanded=False
                )

                # ==========================================
                # 8. 結果描画セクション
                # ==========================================
                st.divider()

                # 最上部：エグゼクティブ・リード（歌いだしハイライト）
                st.markdown("### 🎯 Executive Summary（合議の総括・意思決定リード）")
                st.info(lead_out)

                with st.expander("📌 Phase 1 & 2: 前提設計とファクトデータ（リーダー＆リサーチャー）", expanded=False):
                    st.markdown("#### 👨‍💼 チームリーダーの要件定義")
                    st.markdown(leader_out)
                    st.markdown("---")
                    st.markdown("#### 🔍 リサーチャーの調査結果")
                    st.markdown(research_out)

                st.markdown("### ⚔️ Phase 3: 対立討論（BizDev vs CRO）")
                col_pro, col_con = st.columns(2)
                with col_pro:
                    with st.container(border=True):
                        st.markdown("#### 📈 推進派（BizDev）")
                        st.markdown(promoter_out)
                with col_con:
                    with st.container(border=True):
                        st.markdown("#### 🛡️ 慎重派（CRO）")
                        st.markdown(redteam_out)

                st.markdown("### ⚖️ Phase 4: 止揚・最適解（モデレーター）")
                with st.container(border=True):
                    st.markdown(moderator_out)

                st.markdown("### 🗺️ Phase 5: 確定アクションロードマップ（プランナー）")
                with st.container(border=True):
                    st.markdown(planner_out)

                # ダウンロード用テキストの生成
                full_report = f"""# 戦略合議レポート: {user_theme}
実施日: {time.strftime('%Y-%m-%d %H:%M:%S')}
所要時間: {total_time:.1f}秒

## 🎯 Executive Summary
{lead_out}

---
## Phase 1: チームリーダー要件定義
{leader_out}

---
## Phase 2: リサーチャー調査結果
{research_out}

---
## Phase 3: 対立討論
### 推進派 (BizDev)
{promoter_out}

### 慎重派 (CRO)
{redteam_out}

---
## Phase 4: 止揚・最適解 (モデレーター)
{moderator_out}

---
## Phase 5: 確定アクションロードマップ (プランナー)
{planner_out}
"""
                st.divider()
                st.download_button(
                    label="📥 全合議レポートをMarkdownでダウンロード",
                    data=full_report,
                    file_name="strategy_chamber_report.md",
                    mime="text/markdown",
                    use_container_width=True
                )

                st.caption("※ 本提案・工程表は自律型AIエージェントによる合議ドラフトです。実務導入時は関係法令・実勢相場等の専門的検証を行ってください。")

            except Exception as e:
                status.update(label="❌ エラーが発生しました", state="error", expanded=True)
                st.error(f"実行エラー詳細: {e}")