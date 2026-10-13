"""
Autonomous Multi-Agent Strategy Chamber (Gorilla Taskforce Edition)
総合戦略 / 法務 / 財務 / ゴリラ合議制 4チーム配備版
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
# 3. コンフィグレーション & チーム定義
# ==========================================
API_KEY = st.secrets.get("GEMINI_API_KEY", st.session_state.get("custom_api_key", ""))
PRIMARY_MODEL = "gemini-3.5-flash-lite"
FALLBACK_MODEL = "gemini-3-flash-preview"

MAX_RETRIES = 3
BASE_WAIT_SECONDS = 4
COOLDOWN_SECONDS = 1

GORILLA_RULE = (
    "【絶対言語制約】\n"
    "あなたの発声言語は『ウホ』『ウホホ』『ウホウホウホ』の3パターンの組み合わせのみです！\n"
    "ただし、ビジネスや戦略として絶対に譲れない極めて重要な専門キーワードや単語（例：空き家、固定資産税、市街化調整区域、利回り、キャッシュフロー、契約解除、バナナ、等）だけは、たまに唐突にそのまま喋って構いません。\n"
    "（例：「ウホッ！ウホホ、市街化調整区域、ウホウホウホ！ウホホ（固定資産税6倍）ウホッ！！」）\n"
    "ドラミングや感情の唸り声を織り交ぜつつ、指定された役割を全力で全うしてください。"
)

TEAMS = {
    "総合戦略タスクフォース": {
        "icon": "🏛️",
        "desc": "新規事業の立案、攻守のトレードオフ止揚、実行ロードマップ策定",
        "default_theme": "日本の空家問題と不動産会社の空き家ビジネスの成功例を元に、岡山市内でできる新事業は何か",
        "roles": {
            "leader": "あなたは冷静沈着なプロジェクト総括責任者です。提示されたテーマの本質的ゴールを定め、リサーチャーが調査すべきファクト項目を整理してください。",
            "researcher": "あなたは客観性を重んじるシニアリサーチャーです。客観的事実、既存の成功モデル、公的統計・制度、市場動向のみを構造化して抽出してください。",
            "promoter_title": "📈 推進派（BizDev）",
            "promoter": "あなたは洗練された事業開発責任者（BizDev）です。事業が成立する確固たる根拠、経済的メリット、参入障壁の突破口、収益化ポテンシャルを提示してください。",
            "redteam_title": "🛡️ 慎重派（CRO）",
            "redteam": "あなたは最高リスク管理責任者（CRO）です。法規制、財務・キャッシュフロー、リソース不足、契約トラブルなど、想定される致命的脆弱性を告発してください。",
            "moderator": "あなたはチーフモデレーターです。BizDevの好機とCROのリスクを止揚し、「現実的な最適妥協案」を論理的に策定してください。",
            "planner": "あなたはPMOです。モデレーターの最適解に基づき、フェーズ分け、各フェーズでの具体的タスク、成果物、検証基準を整理したロードマップを策定してください。"
        }
    },
    "法務・リスク統制審査室": {
        "icon": "⚖️",
        "desc": "特措法・建築基準法・都市計画法・条例のグレーゾーン検証、契約紛争防御",
        "default_theme": "空き家の活用・解体・サブリース事業における、特定空家指定リスク、既存不適格・接道義務問題、および所有者・相続人との契約トラブルを完全防御する法的スキームの構築",
        "roles": {
            "leader": "あなたは総括法務責任者です。法的・行政的論点を整理し、調査すべき法規・判例・通達項目を定義してください。",
            "researcher": "あなたは法務リサーチャーです。関係法令条文、岡山市の独自条例、国交省ガイドライン、過去の紛争判例等の客観的ファクトを整理してください。",
            "promoter_title": "📜 活用推進派（リーガルアドバイザー）",
            "promoter": "あなたはビジネス推進型の法務アドバイザーです。法令の枠組み・特例措置・行政協議の余地を活用し、適法かつ安全に事業を推進する突破口を提示してください。",
            "redteam_title": "🚨 厳格コンプライアンス（法務監査役）",
            "redteam": "あなたは保守的な法務監査役です。行政処分リスク、説明義務違反、隠れた瑕疵、相続人同意不備など、致命的法的落とし穴を追及してください。",
            "moderator": "あなたは予防法務チーフオフィサーです。ビジネススピードを殺さずに法的リスクを完全遮断するための条約・覚書・特約条項の骨子を策定してください。",
            "planner": "あなたはコンプライアンス実務PMOです。法適合性を担保するための物件審査チェックリストと事前デューデリジェンス工程表を策定してください。"
        }
    },
    "財務・収支シミュレーション部": {
        "icon": "📊",
        "desc": "改修予備費積算、保有期間の金利・税負担、損益分岐点・キャッシュ回転率分析",
        "default_theme": "岡山市内の築古空き家を対象としたリノベーション再販およびマスターリース事業の収支計画、予備費30%計上時の損益分岐点、および6ヶ月資金回収モデルの検証",
        "roles": {
            "leader": "あなたはCFOです。投資対効果（ROI）、資金回収期間（CCC）、必要資金規模、および検証すべき財務変数を定義してください。",
            "researcher": "あなたは財務アナリストです。リフォーム相場、解体坪単価、実勢賃料・売買利回り、公的融資・補助金の上限額等のファクトデータを整理してください。",
            "promoter_title": "💰 投資推進派（ポートフォリオマネージャー）",
            "promoter": "あなたはアグレッシブな投資マネージャーです。レバレッジ効果、補助金活用、回転率最大化など、資本効率を最大化するシナリオを提示してください。",
            "redteam_title": "📉 ストレステスト派（リスクアナリスト）",
            "redteam": "あなたは厳格なリスクアナリストです。改修コスト30〜50%上振れ、空室長期化、保有金利・固定資産税負担など、最悪の赤字シナリオを試算してください。",
            "moderator": "あなたは資産配分コミッティ責任者です。投資回収の安全マージンを組み込んだ『最適資本投下モデル』を策定してください。",
            "planner": "あなたは財務プランナーです。初期投資から月次キャッシュフロー、黒字化マイルストーン、損切り撤退トリガーを定めた財務工程表を策定してください。"
        }
    },
    "ゴリラ合議制タスクフォース": {
        "icon": "🦍",
        "desc": "ウホ・ウホホ・ウホウホウホの咆哮と急所キーワードのみで動く野性の意思決定会議",
        "default_theme": "岡山市の空き家バナナ事業を巡る群れのナワバリ拡大と、特定空家リスクの完全回避",
        "roles": {
            "leader": f"あなたは【統率するボスゴリラ】です。群れの絶対的長として胸を激しく叩き（ドラミング）、群れの目標と調査要件を雄叫びで示してください。\n{GORILLA_RULE}",
            "researcher": f"あなたは【慎重派ゴリラ】です。ナワバリの安全を第一に考え、木々の間から匂いや危険な事実、周囲の群れ（地場競合）の動きを冷静に嗅ぎ分けて報告してください。\n{GORILLA_RULE}",
            "promoter_title": "🍌 やんちゃな子ゴリラ（突撃推進派）",
            "promoter": f"あなたは【やんちゃな子ゴリラ】です。怖いもの知らずで新しいバナナ畑（収益機会）を見つけて大はしゃぎし、絶対にいけると大興奮で訴えてください。\n{GORILLA_RULE}",
            "redteam_title": "😱 超絶ビビりゴリラ（怯え慎重派）",
            "redteam": f"あなたは【超絶ビビりゴリラ】です。物音や些細なリスク（法令違反、資金ショート、罠）に怯え、パニック寸前で群れに破滅の危機を警告してください。\n{GORILLA_RULE}",
            "moderator": f"あなたは【すぐキレるママゴリラ】です。騒ぐ子ゴリラと怯えるゴリラを張り倒して黙らせ、現実的にバナナを手に入れつつ安全を守る妥協案を強烈に下してください。\n{GORILLA_RULE}",
            "planner": f"あなたは【喧嘩っぱやい子ゴリラ】です。ママの決定を受け、鼻息荒く明日からどの木を倒してどの敵を威嚇し、どうナワバリを広げるかの工程表を叫んでください。\n{GORILLA_RULE}"
        }
    }
}

if "selected_team" not in st.session_state:
    st.session_state.selected_team = "総合戦略タスクフォース"

# ==========================================
# 4. サイドバー & コントロール
# ==========================================
with st.sidebar:
    st.header("⚙️ システム構成")
    current_team = TEAMS[st.session_state.selected_team]
    st.markdown(f"""
    - **Current Team**: {current_team['icon']} **{st.session_state.selected_team}**
    - **Engine**: Gemini Flash (`{PRIMARY_MODEL}`)
    - **Security**: Authorized Session
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
        f"【指示】ペルソナとルールを完璧に演じきり、期待される形式で全力で出力してください。"
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
                raise RuntimeError(f"[{role_title}] 呼出失敗 ({current_model}): {err}")

# ==========================================
# 6. メインUIレイアウト & 4チーム選択ボタン
# ==========================================
st.title("⚖️ Autonomous Strategy Chamber")
st.caption("特化型AIエージェント部隊による多角的ディシジョン・エンジン")

st.markdown("##### 🎯 召集するタスクフォースを選択してください")
col_t1, col_t2, col_t3, col_t4 = st.columns(4)

with col_t1:
    btn_type1 = "primary" if st.session_state.selected_team == "総合戦略タスクフォース" else "secondary"
    if st.button("🏛️ 総合戦略", type=btn_type1, use_container_width=True):
        st.session_state.selected_team = "総合戦略タスクフォース"
        st.rerun()

with col_t2:
    btn_type2 = "primary" if st.session_state.selected_team == "法務・リスク統制審査室" else "secondary"
    if st.button("⚖️ 法務・リスク", type=btn_type2, use_container_width=True):
        st.session_state.selected_team = "法務・リスク統制審査室"
        st.rerun()

with col_t3:
    btn_type3 = "primary" if st.session_state.selected_team == "財務・収支シミュレーション部" else "secondary"
    if st.button("📊 財務・収支", type=btn_type3, use_container_width=True):
        st.session_state.selected_team = "財務・収支シミュレーション部"
        st.rerun()

with col_t4:
    btn_type4 = "primary" if st.session_state.selected_team == "ゴリラ合議制タスクフォース" else "secondary"
    if st.button("🦍 ゴリラ部隊", type=btn_type4, use_container_width=True):
        st.session_state.selected_team = "ゴリラ合議制タスクフォース"
        st.rerun()

# 選択中チームの概要バナー
active_team_data = TEAMS[st.session_state.selected_team]
st.info(f"**現在稼働中: {active_team_data['icon']} {st.session_state.selected_team}**\n\n_{active_team_data['desc']}_")

# テーマ入力
user_theme = st.text_area(
    "プロジェクトテーマ・検討課題",
    value=active_team_data["default_theme"],
    height=90,
    help="選択したチームの専門性に応じた課題を入力してください。"
)

run_button = st.button(f"🚀 {st.session_state.selected_team} に依頼・合議開始", type="primary", use_container_width=False)

# ==========================================
# 7. セッション実行パイプライン
# ==========================================
if run_button:
    if not API_KEY:
        st.error("Gemini APIキーが設定されていません。Secretsに登録するか、サイドバーから入力してください。")
    elif not user_theme.strip():
        st.warning("テーマを入力してください。")
    else:
        cfg = active_team_data["roles"]
        total_start = time.time()
        is_gorilla = (st.session_state.selected_team == "ゴリラ合議制タスクフォース")
        
        with st.status(f"{st.session_state.selected_team} が合議中...", expanded=True) as status:
            try:
                # Phase 1: リーダー
                t0 = time.time()
                leader_label = "🦍 **ボスゴリラ** がドラミングしながら要件咆哮中..." if is_gorilla else "👨‍💼 **リーダー** が課題設計中..."
                status.write(leader_label)
                leader_out = ask_agent("リーダー", cfg["leader"], user_theme)
                status.write(f"└ 完了 (+{time.time() - t0:.1f}s)")

                # Phase 2: リサーチャー
                t0 = time.time()
                research_label = "🔍 **慎重派ゴリラ** が木の上から匂いと危険を嗅ぎ分け中..." if is_gorilla else "🔍 **リサーチャー** が専門ファクト収集中..."
                status.write(research_label)
                research_out = ask_agent("リサーチャー", cfg["researcher"], leader_out)
                status.write(f"└ 完了 (+{time.time() - t0:.1f}s)")

                # Phase 3: 対立討論（並列）
                t0 = time.time()
                status.write(f"⚡ **{cfg['promoter_title']} vs {cfg['redteam_title']}** が激突中...")
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                    f_pro = executor.submit(ask_agent, "推進派", cfg["promoter"], research_out)
                    f_con = executor.submit(ask_agent, "慎重派", cfg["redteam"], research_out)
                    promoter_out = f_pro.result()
                    redteam_out = f_con.result()
                status.write(f"└ 完了 (+{time.time() - t0:.1f}s)")

                # Phase 4: モデレーター
                t0 = time.time()
                mod_label = "💢 **ママゴリラ** が両者を張り倒して落としどころを決定中..." if is_gorilla else "⚖️ **モデレーター** が最適解を調停中..."
                status.write(mod_label)
                mod_input = f"【推進派の主張】\n{promoter_out}\n\n【慎重派の主張】\n{redteam_out}"
                moderator_out = ask_agent("モデレーター", cfg["moderator"], mod_input)
                status.write(f"└ 完了 (+{time.time() - t0:.1f}s)")

                # Phase 5: プランナー
                t0 = time.time()
                plan_label = "🗺️ **喧嘩っぱやい子ゴリラ** が鼻息荒くナワバリ工程表を策定中..." if is_gorilla else "🗺️ **プランナー** がアクションロードマップを策定中..."
                status.write(plan_label)
                planner_out = ask_agent("プランナー", cfg["planner"], moderator_out)
                status.write(f"└ 完了 (+{time.time() - t0:.1f}s)")

                # Phase 6: エグゼクティブ・リード生成
                t0 = time.time()
                status.write("🎯 **エグゼクティブ・リード** を抽出中...")
                if is_gorilla:
                    lead_prompt = (
                        "あなたはゴリラ群れの知恵袋オウムです。ゴリラたちのウホウホ合議（モデレーターとプランナー）を"
                        "人間の言葉に翻訳し、笑えるが本質を突いた『人間向け翻訳エグゼクティブ・サマリー』を作成してください。\n"
                        "以下のフォーマットを厳守してください：\n"
                        "【ゴリラたちの意思決定】（1〜2行で人間向けに要約）\n"
                        "- ウホウホ要点（バナナ獲得戦略）：〜\n"
                        "- ママゴリラの鉄槌（最大のリスク防御）：〜\n"
                        "- 明日のナワバリ行動（Next Action）：〜"
                    )
                else:
                    lead_prompt = (
                        "あなたは経営陣向けのブリーフィングを担当するチーフストラテジストです。"
                        "モデレーターの最適解とプランナーの工程表から、最も重要な結論だけを抜き出した"
                        "『エグゼクティブ・サマリー』を作成してください。\n"
                        "以下のフォーマットを厳守してください：\n"
                        "【意思決定の結論】（1〜2行で明快に断言）\n"
                        "- 採用モデル・方針：〜\n"
                        "- 最大の防御策（リスク遮断）：〜\n"
                        "- 直近の最優先アクション（Next Action）：〜"
                    )
                lead_input = f"【最適解】\n{moderator_out}\n\n【工程表】\n{planner_out}"
                lead_out = ask_agent("リード生成", lead_prompt, lead_input)
                status.write(f"└ 完了 (+{time.time() - t0:.1f}s)")

                total_time = time.time() - total_start
                status.update(
                    label=f"✅ {st.session_state.selected_team} 合議完了 (総所要時間: {total_time:.1f}秒)",
                    state="complete",
                    expanded=False
                )

                # ==========================================
                # 8. 結果描画
                # ==========================================
                st.divider()

                # 最上部：エグゼクティブ・リード
                st.markdown(f"### 🎯 Executive Summary ({st.session_state.selected_team})")
                st.info(lead_out)

                with st.expander("📌 Phase 1 & 2: 前提設計とファクトデータ", expanded=False):
                    st.markdown("#### 👑 リーダーの要件定義")
                    st.markdown(leader_out)
                    st.markdown("---")
                    st.markdown("#### 🔍 リサーチャーの調査結果")
                    st.markdown(research_out)

                st.markdown("### ⚔️ Phase 3: 対立討論")
                col_pro, col_con = st.columns(2)
                with col_pro:
                    with st.container(border=True):
                        st.markdown(f"#### {cfg['promoter_title']}")
                        st.markdown(promoter_out)
                with col_con:
                    with st.container(border=True):
                        st.markdown(f"#### {cfg['redteam_title']}")
                        st.markdown(redteam_out)

                st.markdown("### ⚖️ Phase 4: 止揚・最適解")
                with st.container(border=True):
                    st.markdown(moderator_out)

                st.markdown("### 🗺️ Phase 5: 確定アクションロードマップ")
                with st.container(border=True):
                    st.markdown(planner_out)

                # Markdownダウンロード
                full_report = f"""# {st.session_state.selected_team} 合議レポート
検討課題: {user_theme}
実施日: {time.strftime('%Y-%m-%d %H:%M:%S')}
総所要時間: {total_time:.1f}秒

## 🎯 Executive Summary
{lead_out}

---
## Phase 1: リーダー要件定義
{leader_out}

---
## Phase 2: リサーチャー調査結果
{research_out}

---
## Phase 3: 対立討論
### {cfg['promoter_title']}
{promoter_out}

### {cfg['redteam_title']}
{redteam_out}

---
## Phase 4: 最適解
{moderator_out}

---
## Phase 5: アクションロードマップ
{planner_out}
"""
                st.divider()
                st.download_button(
                    label=f"📥 {st.session_state.selected_team} の合議レポートをダウンロード",
                    data=full_report,
                    file_name=f"report_{st.session_state.selected_team}.md",
                    mime="text/markdown",
                    use_container_width=True
                )

                st.caption("※ 本提案・工程表は自律型AIエージェントによる合議ドラフトです。実務導入時は関係法令・実勢相場等の専門的検証を行ってください。")

            except Exception as e:
                status.update(label="❌ エラーが発生しました", state="error", expanded=True)
                st.error(f"実行エラー詳細: {e}")