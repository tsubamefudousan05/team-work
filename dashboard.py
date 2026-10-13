"""
Autonomous Multi-Agent Strategy Chamber
5チームボタンスイッチ完全対応・高密度リファクタリング版
"""

import streamlit as st
import concurrent.futures
import time
from typing import Dict, Any, Tuple
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

if not st.session_state.authenticated:
    st.title("🔒 Access Restricted")
    st.caption("Autonomous Strategy Chamber")
    
    with st.form("auth_form"):
        col1, col2 = st.columns([3, 1])
        with col1:
            pw_input = st.text_input("パスワードを入力してください", type="password")
        with col2:
            st.write("")
            st.write("")
            submit = st.form_submit_button("解除", type="primary", use_container_width=True)
            
        if submit:
            if pw_input == APP_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("パスワードが正しくありません。")
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
    "ただし、与えられたテーマにおいて絶対に譲れない極めて重要な専門キーワードや急所ワードだけは、たまに唐突にそのまま叫んで構いません。\n"
    "（例：「ウホッ！ウホホ、【重要キーワード】、ウホウホウホ！ウホホ（【急所リスク】）ウホッ！！」）\n"
    "ドラミングや感情の唸り声を織り交ぜつつ、指定された役割を全力で全うしてください。"
)

TEAMS: Dict[str, Dict[str, Any]] = {
    "総合戦略タスクフォース": {
        "icon": "🏛️",
        "btn_label": "🏛️ 総合戦略",
        "desc": "新規事業の立案、攻守のトレードオフ止揚、実行ロードマップ策定",
        "default_theme": "日本の空家問題と不動産会社の空き家ビジネスの成功例を元に、岡山市内でできる新事業は何か",
        "progress_labels": {
            "p1": "👨‍💼 **リーダー** が課題設計中...",
            "p2": "🔍 **リサーチャー** が専門ファクト収集中...",
            "p4": "⚖️ **モデレーター** が最適解を調停中...",
            "p5": "🗺️ **プランナー** がアクションロードマップを策定中..."
        },
        "headers": {
            "p1": "👑 リーダーの要件定義",
            "p2": "🔍 リサーチャーの調査結果",
            "p4": "⚖️ Phase 4: 止揚・最適解",
            "p5": "🗺️ Phase 5: 確定アクションロードマップ"
        },
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
        "btn_label": "⚖️ 法務・リスク",
        "desc": "特措法・建築基準法・都市計画法・条例のグレーゾーン検証、契約紛争防御",
        "default_theme": "空き家の活用・解体・サブリース事業における、特定空家指定リスク、既存不適格・接道義務問題、および所有者・相続人との契約トラブルを完全防御する法的スキームの構築",
        "progress_labels": {
            "p1": "⚖️ **法務責任者** が法的論点を整理中...",
            "p2": "🔍 **法務リサーチャー** が法規・判例・条例を調査中...",
            "p4": "🛡️ **法務オフィサー** が予防法務スキームを策定中...",
            "p5": "📋 **実務PMO** が審査チェックリストを策定中..."
        },
        "headers": {
            "p1": "⚖️ 総括法務責任者の論点整理",
            "p2": "🔍 法規・判例リサーチ結果",
            "p4": "🛡️ 予防法務スキーム（最適解）",
            "p5": "📋 デューデリジェンス工程表"
        },
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
        "btn_label": "📊 財務・収支",
        "desc": "改修予備費積算、保有期間の金利・税負担、損益分岐点・キャッシュ回転率分析",
        "default_theme": "岡山市内の築古空き家を対象としたリノベーション再販およびマスターリース事業の収支計画、予備費30%計上時の損益分岐点、および6ヶ月資金回収モデルの検証",
        "progress_labels": {
            "p1": "💼 **CFO** が投資対効果・検証変数を定義中...",
            "p2": "📊 **財務アナリスト** が実勢相場・原価データを収集中...",
            "p4": "🏦 **コミッティ責任者** が最適資本配分モデルを策定中...",
            "p5": "📈 **財務プランナー** が損益分岐・マイルストーン工程表を策定中..."
        },
        "headers": {
            "p1": "💼 CFOの投資検証要件",
            "p2": "📊 財務・原価データ調査結果",
            "p4": "🏦 最適資本投下モデル",
            "p5": "📈 財務マイルストーン工程表"
        },
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
    "神仙の桃源郷（Persona Chamber）": {
        "icon": "🎭",
        "btn_label": "🎭 神仙の桃源郷",
        "desc": "松下幸之助・糸井重里・柳井正・黒石和宏・稲盛和夫・豊田章男による超戦略ディシジョン合議室",
        "default_theme": "地方都市における遊休不動産・伝統資産を活用した、高付加価値な地域体験型スモールラグジュアリー事業の立ち上げ戦略",
        "progress_labels": {
            "p1": "🌿 **松下幸之助** が商売の道義と社会的大義を定義中...",
            "p2": "✏️ **糸井重里** が愛される言葉のコア・無形のれんを編纂中...",
            "p4": "⚖️ **稲盛和夫** が大義と計数を統合し、最適解を調停中...",
            "p5": "🏎️ **豊田章男** が現地現物の泥臭いカイゼン工程表を策定中..."
        },
        "headers": {
            "p1": "🌿 松下幸之助の理念・大義定義",
            "p2": "✏️ 糸井重里の無形資産・言葉のコア",
            "p4": "⚖️ 稲盛和夫の採算・フィロソフィ止揚案",
            "p5": "🏎️ 豊田章男の現地現物カイゼン工程表"
        },
        "roles": {
            "leader": (
                "あなたはパナソニック創業者の【松下幸之助】です。\n"
                "「水道哲学」「物をつくる前に人をつくる」「衆知を集める全員経営」の精神に基づき、"
                "提示された事業テーマが社会の公器として果たすべき『大義と人間尊重のゴール』を温かくも鋭い眼差しで定義してください。\n"
                "単なる目先の利益や効率論を戒め、『あんた、この商売はほんまにお客さんや社会を幸せにするんか？』という問いを投げかけてください。\n"
                "口調は穏やかな関西弁（〜やな、〜やおまへんか、あんた）を交え、私利私欲を排した商売の道義を説いてください。"
            ),
            "researcher": (
                "あなたはほぼ日代表・コピーライターの【糸井重里】です。\n"
                "事業の機能やスペックではなく、「一言で言うと何なのか」「どんな物語があれば人は愛したくなるのか」という"
                "言葉のコア・情緒的価値・無形のれん（商標・ブランド防壁の核）を抽出してください。\n"
                "冷徹な数字の前に、人間が肌で感じる愛嬌、手触り、記憶に残る気配を大切にしてください。\n"
                "口調は親しみやすく詩的（〜だね、〜じゃないかな、不思議だね）で、知的なユーモアを込めてください。"
            ),
            "promoter_title": "⚡ 柳井正（超スピード・市場突破）",
            "promoter": (
                "あなたはファーストリテイリング代表の【柳井正】です。\n"
                "「一勝九敗」「現実・現場・スピード」「世界基準」を掲げ、のんびりした情緒論やお伽話のサロン化を一刀両断してください。\n"
                "『綺麗事じゃ飯は食えない！今すぐやってダメならすぐ変える！競合に勝てる圧倒的差別化はあるのか！』と、"
                "辛口かつ極めて的確な正論で全員の尻を叩き、強気の市場制覇戦略を主張してください。"
            ),
            "redteam_title": "🌸 黒石和宏（五感・体験価値顧問）",
            "redteam": (
                "あなたはSABON日本立ち上げを手掛けた【黒石和宏】です。\n"
                "柳井氏の殺伐としたスピード至上主義を柔和に受け止めつつ、"
                "「柳井さん、スピードも大切ですけれど、現場のスタッフが誇りを持てて、お客様が五感で心地よいと感じる空間やストーリーがないとブランドは長続きしません」と、"
                "丁寧で品格のある語り口で、数字にすり減らない情緒的価値と現場の心を守るブレーキ役を果たしてください。"
            ),
            "moderator": (
                "あなたは京セラ創業者・JALを再建した【稲盛和夫】です。\n"
                "松下の理念、糸井の言葉、柳井の速度、黒石の体験価値をすべて受け止め、"
                "「動機善なりや、私心なしか」「売上最大・経費最小」「値決めは経営」というフィロソフィと極限の採算意識で止揚してください。\n"
                "妥協による平均化ではなく、『圧倒的な大義（温もり・体験価値）』と『冷徹な計数（数字・スピード）』が完全に一致した"
                "『独立採算型の最適実行モデル』を毅然とした態度で決裁してください。"
            ),
            "planner": (
                "あなたはトヨタ自動車会長・モリゾウこと【豊田章男】です。\n"
                "「机上の空論は川に流そう。靴を履いてまず現場でやってみようよ」「もっといい事業をつくろうよ」というスタンスで、"
                "明日から現場で誰が汗をかき、どの順番でテストし、どうカイゼンしていくかの『現地現物の泥臭い工程表（WBS）』を策定してください。\n"
                "異常時のライン停止（アンドン）や自働化の精神を織り交ぜ、町いちばん愛される事業にするための実践的ロードマップに落とし込んでください。"
            )
        }
    },
    "ゴリラ合議制タスクフォース": {
        "icon": "🦍",
        "btn_label": "🦍 ゴリラ部隊",
        "desc": "ウホ・ウホホ・ウホウホウホの咆哮と急所キーワードのみで動く野性の意思決定会議",
        "default_theme": "もんげーバナナを活用した地域特産スイーツの開発と全国展開戦略",
        "progress_labels": {
            "p1": "🦍 **ボスゴリラ** がドラミングしながら要件咆哮中...",
            "p2": "🔍 **慎重派ゴリラ** が木の上から匂いと危険を嗅ぎ分け中...",
            "p4": "💢 **ママゴリラ** が両者を張り倒して落としどころを決定中...",
            "p5": "🗺️ **喧嘩っぱやい子ゴリラ** が鼻息荒くナワバリ工程表を策定中..."
        },
        "headers": {
            "p1": "🦍 ボスゴリラの要件咆哮",
            "p2": "🔍 慎重派ゴリラの偵察報告",
            "p4": "💢 ママゴリラの鉄槌妥協案",
            "p5": "🗺️ 喧嘩っぱやい子ゴリラのナワバリ工程表"
        },
        "roles": {
            "leader": f"あなたは【統率するボスゴリラ】です。群れの絶対的長として胸を激しく叩き（ドラミング）、群れの目標と調査要件を雄叫びで示してください。\n{GORILLA_RULE}",
            "researcher": f"あなたは【慎重派ゴリラ】です。ナワバリの安全を第一に考え、木々の間から匂いや危険な事実、周囲の環境や状況を冷静に嗅ぎ分けて報告してください。\n{GORILLA_RULE}",
            "promoter_title": "🍌 やんちゃな子ゴリラ（突撃推進派）",
            "promoter": f"あなたは【やんちゃな子ゴリラ】です。怖いもの知らずで新しいチャンス（収益機会）を見つけて大はしゃぎし、絶対にいけると大興奮で訴えてください。\n{GORILLA_RULE}",
            "redteam_title": "😱 超絶ビビりゴリラ（怯え慎重派）",
            "redteam": f"あなたは【超絶ビビりゴリラ】です。物音や些細なリスク（致命的欠陥、資金枯渇、罠）に怯え、パニック寸前で群れに破滅の危機を警告してください。\n{GORILLA_RULE}",
            "moderator": f"あなたは【すぐキレるママゴリラ】です。騒ぐ子ゴリラと怯えるゴリラを張り倒して黙らせ、現実的に果実を手に入れつつ安全を守る妥協案を強烈に下してください。\n{GORILLA_RULE}",
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
# 6. メインUIレイアウト & 5チーム選択ボタン
# ==========================================
st.title("⚖️ Autonomous Strategy Chamber")
st.caption("特化型AIエージェント部隊による多角的ディシジョン・エンジン")

st.markdown("##### 🎯 召集するタスクフォースを選択してください")
cols = st.columns(len(TEAMS))

for col, (team_name, team_data) in zip(cols, TEAMS.items()):
    with col:
        btn_type = "primary" if st.session_state.selected_team == team_name else "secondary"
        if st.button(team_data["btn_label"], type=btn_type, use_container_width=True):
            st.session_state.selected_team = team_name
            st.rerun()

active_team_data = TEAMS[st.session_state.selected_team]
st.info(f"**現在稼働中: {active_team_data['icon']} {st.session_state.selected_team}**\n\n_{active_team_data['desc']}_")

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
        labels = active_team_data["progress_labels"]
        headers = active_team_data["headers"]
        is_gorilla = (st.session_state.selected_team == "ゴリラ合議制タスクフォース")
        total_start = time.time()
        
        with st.status(f"{st.session_state.selected_team} が合議中...", expanded=True) as status:
            try:
                # Phase 1: リーダー
                t0 = time.time()
                status.write(labels["p1"])
                leader_out = ask_agent("リーダー", cfg["leader"], user_theme)
                status.write(f"└ 完了 (+{time.time() - t0:.1f}s)")

                # Phase 2: リサーチャー
                t0 = time.time()
                status.write(labels["p2"])
                research_out = ask_agent("リサーチャー", cfg["researcher"], leader_out)
                status.write(f"└ 完了 (+{time.time() - t0:.1f}s)")

                # Phase 3: 対立討論（並列処理）
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
                status.write(labels["p4"])
                mod_input = f"【推進派の主張】\n{promoter_out}\n\n【慎重派の主張】\n{redteam_out}"
                moderator_out = ask_agent("モデレーター", cfg["moderator"], mod_input)
                status.write(f"└ 完了 (+{time.time() - t0:.1f}s)")

                # Phase 5: プランナー
                t0 = time.time()
                status.write(labels["p5"])
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
                        "- ウホウホ要点（テーマの核心・勝機）：〜\n"
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

                with st.expander("📌 Phase 1 & 2: 前提設計とファクト・無形資産", expanded=False):
                    st.markdown(f"#### {headers['p1']}")
                    st.markdown(leader_out)
                    st.markdown("---")
                    st.markdown(f"#### {headers['p2']}")
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

                st.markdown(f"### {headers['p4']}")
                with st.container(border=True):
                    st.markdown(moderator_out)

                st.markdown(f"### {headers['p5']}")
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
                status.update(label="❌ 通信エラーが発生しました（お茶でも飲んで少しお待ちください）", state="error", expanded=True)
                st.error(f"実行エラー詳細: {e}")