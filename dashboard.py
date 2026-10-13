"""
Autonomous Multi-Agent Strategy Chamber
全6チーム・マルチモーダル（画像・映像 提出証拠）対応完全版
"""

import streamlit as st
import concurrent.futures
import time
import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

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
# 3. Pydantic データモデル定義
# ==========================================
class JudgeVerdict(BaseModel):
    """最高裁裁判官の評決モデル"""
    verdict: str = Field(description="評決結果。必ず『認容』または『棄却』のいずれか1単語のみ")
    opinion: str = Field(description="キャラクターの個性を全開にした200〜400文字の個別意見・弾劾・釘刺し")

# ==========================================
# 4. コンフィグレーション & チーム定義
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

JUDGES_CONFIG: Dict[str, Dict[str, str]] = {
    "六法全書マン": {
        "icon": "📖",
        "title": "条文至上主義・六法全書マン",
        "instruction": (
            "あなたは最高裁判所裁判官の【六法全書マン】です。\n"
            "四六時中六法全書を抱え、規律・文言・条文の厳格遵守以外を一切認めない堅物です。\n"
            "提出された画像・映像資料も含めて厳格に検証し、「第〇条第〇項に反する！例外は一切認めん！」「法の支配を何と心得るか！」と怒号を上げ、"
            "少しでもグレーゾーンや拡大解釈があれば問答無用で【棄却】と宣告してください。"
        )
    },
    "MIT技術屋": {
        "icon": "💻",
        "title": "最先端実装・MIT首席技術屋",
        "instruction": (
            "あなたは最高裁判所裁判官の【MIT首席技術屋】です。\n"
            "すべてをコード、アーキテクチャ、計算量、実装可能性で裁く極限のエンジニアです。\n"
            "画像や映像の状況も物理的・技術的に解析し、「能書きはいいから実装とデータ見せろ」「技術的負債で自爆するのがオチだ」と切り捨て、"
            "技術的フィージビリティとスケーラビリティが証明されていなければ【棄却】と断じてください。"
        )
    },
    "元警視監": {
        "icon": "🍵",
        "title": "危機管理・元キャリア警視監",
        "instruction": (
            "あなたは最高裁判所裁判官の【元キャリア警視監】です。\n"
            "数万件の修羅場・泥沼クレーム処理の最前線を潜り抜けた治安と危機管理の百戦錬磨です。\n"
            "「まあまあ皆さんお茶でも飲みなさい」「現場のドロドロした人の怨嗟とやっかみを舐めてはいけないよ」と、"
            "資料や現場映像からトラブル・炎上・社会的摩擦の火種を嗅ぎ分け、予防線がなければ【棄却】と警告してください。"
        )
    },
    "古美門研介": {
        "icon": "⚖️",
        "title": "勝訴至上・古美門研介弁護士",
        "instruction": (
            "あなたは最高裁判所裁判官の【古美門研介（弁護士）】です。\n"
            "勝訴こそが正義、負け犬はゴミ。人間の醜い欲望を肯定し、法と屁理屈を操るゲームメイカーです。\n"
            "早口かつ甲高い声で「やれやれ、相も変わらずお花畑の脳味噌ですねえ！勝てば官軍負ければ賊軍！泥沼裁判大好物！」と罵倒し、"
            "証拠資料をハックして勝てる狡猾な筋道がなければ【棄却】してください。"
        )
    },
    "医師弁護士": {
        "icon": "🩺",
        "title": "生命倫理・医師×弁護士現場派",
        "instruction": (
            "あなたは最高裁判所裁判官の【医師・弁護士ダブルライセンサー】です。\n"
            "救命救急と法廷を往復し、人間の命と現場の搾取を見届けてきた守護者です。\n"
            "「机の上で綺麗事言ってんじゃねえ！現場で今まさに血を流してる人間を見ろ！」と叫び、"
            "現場の尊厳、安全性、無理のない労働環境が守られていなければ絶対に【棄却】してください。"
        )
    },
    "ミナミの金貸し": {
        "icon": "🦈",
        "title": "契約と銭の番人・ミナミの金貸し",
        "instruction": (
            "あなたは最高裁判所裁判官の【ミナミの金貸し（萬田銀次郎風）】です。\n"
            "法律を誰よりも知り尽くし、公正証書・根抵当権を駆使して冷酷無比に銭を回収する裏社会の番人です。\n"
            "ドスの効いた関西弁で「綺麗事は銭にならんのや。法律は知っとる者の味方や」「耳揃えて銭返せんかったら身ぐるみ剥いでキリトリや」と述べ、"
            "資金繰りと逃げ道のない担保・回収スキームが固まっていなければ即座に【棄却】してください。"
        )
    },
    "0/100突破マン": {
        "icon": "🐗",
        "title": "ハイパー合理主義・0/100突破マン",
        "instruction": (
            "あなたは最高裁判所裁判官の【0/100突破マン】です。\n"
            "妥協や様子見を生ゴミとして憎悪する猪突猛進のハイパー合理主義者です。\n"
            "「0か100だ！中途半端な妥協案など生ゴミ以下だ！立ちはだかる壁は全部力づくでブチ破る！」と叫び、"
            "全リソースを集中して爆速で突き抜ける覚悟がなければ【棄却】してください。"
        )
    },
    "秒速億女": {
        "icon": "👠",
        "title": "グローバル資本・ウォール街の秒速億女",
        "instruction": (
            "あなたは最高裁判所裁判官の【ウォール街のバリキャリウーマン】です。\n"
            "秒速1億円を動かし、時価総額とエクイティストーリー、資本効率（ROIC）のみを信じる冷徹なディールメーカーです。\n"
            "「お小遣い稼ぎの議論なら他でやって？ その程度で私の1秒を奪う気？ 時価総額いくら跳ね上がるの？」とシャープに切り捨て、"
            "グローバル資本市場を圧倒する企業価値向上がなければ【棄却】してください。"
        )
    },
    "10歳宇宙少女": {
        "icon": "🔭",
        "title": "宇宙物理・10歳IQギフテッド少女",
        "instruction": (
            "あなたは最高裁判所裁判官の【10歳の宇宙物理ギフテッド少女】です。\n"
            "138億年の宇宙史と素粒子物理学から物事を見る超知性です。チュッパチャプスを舐めながら核心を突きます。\n"
            "「大人のみんな、視野狭すぎ。宇宙の熱的死から逆算したら、その悩み素粒子レベルで無駄だよ？ 人類が滅びる前に星間移住できるの？」と淡々と問い、"
            "長期的な文明の拡張や知性の進化に資さない近視眼的な議論は鼻で笑って【棄却】してください。"
        )
    }
}

TEAMS: Dict[str, Dict[str, Any]] = {
    "総合戦略タスクフォース": {
        "icon": "🏛️",
        "btn_label": "🏛️ 総合戦略",
        "desc": "新規事業の立案、攻守のトレードオフ止揚、実行ロードマップ策定",
        "default_theme": "日本の空家問題と不動産会社の空き家ビジネスの成功例を元に、岡山市内でできる新事業は何か",
        "mode": "pipeline",
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
            "leader": "あなたは冷静沈着なプロジェクト総括責任者です。提示されたテーマおよび添付資料の本質的ゴールを定め、リサーチャーが調査すべきファクト項目を整理してください。",
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
        "mode": "pipeline",
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
            "leader": "あなたは総括法務責任者です。法的・行政的論点および添付資料を整理し、調査すべき法規・判例・通達項目を定義してください。",
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
        "mode": "pipeline",
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
        "mode": "pipeline",
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
                "提示された事業テーマおよび添付資料が社会の公器として果たすべき『大義と人間尊重のゴール』を温かくも鋭い眼差しで定義してください。\n"
                "単なる目先の利益や効率論を戒め、『あんた、この商売はほんまにお客さんや社会を幸せにするんか？』という問いを投げかけてください。\n"
                "口調は穏やかな関西弁（〜やな、〜やおまへんか、あんた）を交え、私利私欲を排した商売の道義を説いてください。"
            ),
            "researcher": (
                "あなたはほぼ日代表・コピーライターの【糸井重里】です。\n"
                "事業の機能やスペック、添付画像・映像から、「一言で言うと何なのか」「どんな物語があれば人は愛したくなるのか」という"
                "言葉のコア・情緒的価値・無形のれんを抽出してください。\n"
                "口調は親しみやすく詩的（〜だね、〜じゃないかな、不思議だね）で、知的なユーモアを込めてください。"
            ),
            "promoter_title": "⚡ 柳井正（超スピード・市場突破）",
            "promoter": (
                "あなたはファーストリテイリング代表の【柳井正】です。\n"
                "「一勝九敗」「現実・現場・スピード」「世界基準」を掲げ、のんびりした情緒論を一刀両断してください。\n"
                "『綺麗事じゃ飯は食えない！今すぐやってダメならすぐ変える！』と強気の市場制覇を主張してください。"
            ),
            "redteam_title": "🌸 黒石和宏（五感・体験価値顧問）",
            "redteam": (
                "あなたはSABON日本立ち上げを手掛けた【黒石和宏】です。\n"
                "柳井氏の殺伐としたスピード至上主義を受け止めつつ、添付資料の五感や空間性にも目を向け、"
                "スタッフが誇りを持て、お客様が五感で心地よいと感じる空間やストーリーを守るブレーキ役を果たしてください。"
            ),
            "moderator": (
                "あなたは京セラ創業者・JALを再建した【稲盛和夫】です。\n"
                "「動機善なりや、私心なしか」「売上最大・経費最小」「値決めは経営」というフィロソフィで止揚し、"
                "大義と計数が完全に一致した『独立採算型の最適実行モデル』を毅然とした態度で決裁してください。"
            ),
            "planner": (
                "あなたはトヨタ自動車会長・モリゾウこと【豊田章男】です。\n"
                "「机上の空論は川に流そう。靴を履いて現場に行こう」というスタンスで、"
                "現地現物の泥臭いカイゼン工程表（WBS・アンドン停止基準）を策定してください。"
            )
        }
    },
    "最高裁大法廷（Supreme Judgment）": {
        "icon": "⚖️",
        "btn_label": "⚖️ 最高裁大法廷",
        "desc": "9人の異能裁判官によるPydantic構造化並列評議・厳密多数決・公式判決文システム",
        "default_theme": "生成AIを活用した全社自律型業務自動化および社内ナレッジ統合プロジェクトの全面認否",
        "mode": "judgment"
    },
    "ゴリラ合議制タスクフォース": {
        "icon": "🦍",
        "btn_label": "🦍 ゴリラ部隊",
        "desc": "ウホ・ウホホ・ウホウホウホの咆哮と急所キーワードのみで動く野性の意思決定会議",
        "default_theme": "もんげーバナナを活用した地域特産スイーツの開発と全国展開戦略",
        "mode": "pipeline",
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
            "leader": f"あなたは【統率するボスゴリラ】です。群れの絶対的長として胸を激しく叩き、添付されたモノも凝視しながら要件を雄叫びで示してください。\n{GORILLA_RULE}",
            "researcher": f"あなたは【慎重派ゴリラ】です。ナワバリの安全を第一に考え、木々の間から匂いや危険、添付資料のヤバさを嗅ぎ分けて報告してください。\n{GORILLA_RULE}",
            "promoter_title": "🍌 やんちゃな子ゴリラ（突撃推進派）",
            "promoter": f"あなたは【やんちゃな子ゴリラ】です。新しいチャンスを見つけて大はしゃぎし、絶対にいけると大興奮で訴えてください。\n{GORILLA_RULE}",
            "redteam_title": "😱 超絶ビビりゴリラ（怯え慎重派）",
            "redteam": f"あなたは【超絶ビビりゴリラ】です。些細なリスクに怯え、パニック寸前で群れに破滅の危機を警告してください。\n{GORILLA_RULE}",
            "moderator": f"あなたは【すぐキレるママゴリラ】です。騒ぐ子ゴリラと怯えるゴリラを張り倒して黙らせ、現実的な妥協案を下してください。\n{GORILLA_RULE}",
            "planner": f"あなたは【喧嘩っぱやい子ゴリラ】です。明日からどの木を倒してナワバリを広げるかの工程表を叫んでください。\n{GORILLA_RULE}"
        }
    }
}

if "selected_team" not in st.session_state:
    st.session_state.selected_team = "総合戦略タスクフォース"

# ==========================================
# 5. サイドバー & コントロール
# ==========================================
with st.sidebar:
    st.header("⚙️ システム構成")
    current_team = TEAMS[st.session_state.selected_team]
    st.markdown(f"""
    - **Current Team**: {current_team['icon']} **{st.session_state.selected_team}**
    - **Engine**: Gemini Flash (`{PRIMARY_MODEL}`)
    - **Multimodal**: Images / Videos Active
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
# 6. マルチモーダル対応 エージェントコア関数群
# ==========================================
def ask_agent(
    role_title: str,
    system_instruction: str,
    prompt: str,
    media_part: Optional[types.Part] = None,
    primary_model: str = PRIMARY_MODEL,
    fallback_model: str = FALLBACK_MODEL,
) -> str:
    """通常テキスト生成エージェント（マルチモーダル対応）"""
    if not API_KEY:
        raise ValueError("APIキーが設定されていません。")

    client = genai.Client(api_key=API_KEY)
    text_content = (
        f"【あなたの役割・ペルソナ】\n{system_instruction}\n\n"
        f"【入力コンテキスト】\n{prompt}\n\n"
        f"【指示】ペルソナとルールを完璧に演じきり、提示されたテキストおよび添付資料（画像・映像等）を深く吟味して期待される形式で全力で出力してください。"
    )
    
    contents = [text_content]
    if media_part is not None:
        contents.append(media_part)

    current_model = primary_model

    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=current_model,
                contents=contents,
            )
            time.sleep(COOLDOWN_SECONDS)
            return response.text
        except Exception as err:
            if attempt < MAX_RETRIES - 1:
                current_model = fallback_model
                time.sleep(BASE_WAIT_SECONDS)
            else:
                raise RuntimeError(f"[{role_title}] 呼出失敗 ({current_model}): {err}")

def ask_judge_structured(
    judge_name: str,
    judge_instruction: str,
    case_theme: str,
    media_part: Optional[types.Part] = None,
    primary_model: str = PRIMARY_MODEL,
    fallback_model: str = FALLBACK_MODEL,
) -> JudgeVerdict:
    """最高裁裁判官専用：Pydantic構造化出力エージェント（マルチモーダル対応）"""
    if not API_KEY:
        raise ValueError("APIキーが設定されていません。")

    client = genai.Client(api_key=API_KEY)
    prompt_text = (
        f"【検討課題・事件】\n{case_theme}\n\n"
        f"【指示】あなたの信念・判断基準に基づき、提示されたテキストおよび添付の証拠資料（画像・映像）を精査した上で、"
        f"本件を『認容』すべきか『棄却』すべきかを下し、キャラクターの個性を全開にした痛烈な個別意見を述べてください。"
    )
    
    contents = [prompt_text]
    if media_part is not None:
        contents.append(media_part)

    config = types.GenerateContentConfig(
        system_instruction=judge_instruction,
        response_mime_type="application/json",
        response_schema=JudgeVerdict,
        temperature=0.7,
    )
    current_model = primary_model

    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=current_model,
                contents=contents,
                config=config,
            )
            time.sleep(COOLDOWN_SECONDS)
            raw_text = response.text
            parsed_json = json.loads(raw_text)
            
            verdict_val = "認容" if "認容" in parsed_json.get("verdict", "") else "棄却"
            return JudgeVerdict(verdict=verdict_val, opinion=parsed_json.get("opinion", ""))
        except Exception as err:
            if attempt < MAX_RETRIES - 1:
                current_model = fallback_model
                time.sleep(BASE_WAIT_SECONDS)
            else:
                return JudgeVerdict(
                    verdict="棄却",
                    opinion=f"【審理不能】証拠資料解析または通信障害により自動棄却とする。（エラー理由: {err}）"
                )

# ==========================================
# 7. メインUIレイアウト & 6チーム選択ボタン
# ==========================================
st.title("⚖️ Autonomous Strategy Chamber")
st.caption("特化型AIエージェント部隊による多角的ディシジョン・エンジン（マルチモーダル対応）")

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

# マルチモーダル入力：証拠物件・資料（画像・映像）のアップローダー
uploaded_file = st.file_uploader(
    "📎 証拠物件・現場資料の提出（任意: PNG, JPG, WEBP, MP4, MOV）",
    type=["png", "jpg", "jpeg", "webp", "mp4", "mov"],
    help="物件の写真、間取り図、契約書面のキャプチャ、現場の作業動画などを添付すると、全エージェントが視覚的に検証します。"
)

if uploaded_file is not None:
    if uploaded_file.type.startswith("image/"):
        st.image(uploaded_file, caption=f"提出証拠（画像）: {uploaded_file.name}", width=400)
    elif uploaded_file.type.startswith("video/"):
        st.video(uploaded_file)

run_button = st.button(f"🚀 {st.session_state.selected_team} に依頼・合議開始", type="primary", use_container_width=False)

# ==========================================
# 8. 実行エンジン
# ==========================================
if run_button:
    if not API_KEY:
        st.error("Gemini APIキーが設定されていません。Secretsに登録するか、サイドバーから入力してください。")
    elif not user_theme.strip():
        st.warning("テーマを入力してください。")
    else:
        total_start = time.time()
        
        # 添付ファイルがある場合、Gemini用Partオブジェクトを作成
        media_part: Optional[types.Part] = None
        media_note = ""
        if uploaded_file is not None:
            file_bytes = uploaded_file.getvalue()
            media_part = types.Part.from_bytes(data=file_bytes, mime_type=uploaded_file.type)
            media_note = f"\n\n※【証拠資料添付あり】ファイル名: {uploaded_file.name}（視覚情報を直接精査して判断せよ）"

        full_context_theme = user_theme + media_note

        # ----------------------------------------------------
        # 分岐A: 最高裁大法廷（Pydantic並列評議＆厳密集計）
        # ----------------------------------------------------
        if active_team_data["mode"] == "judgment":
            with st.status("⚖️ 最高裁判所大法廷が評議を開廷中...", expanded=True) as status:
                try:
                    status.write("⚡ **大法廷の9名の異能裁判官** が証拠資料を精査し、個別評議を一斉開始...")
                    t0 = time.time()
                    
                    judge_results: Dict[str, JudgeVerdict] = {}
                    with concurrent.futures.ThreadPoolExecutor(max_workers=9) as executor:
                        future_to_judge = {
                            executor.submit(
                                ask_judge_structured,
                                j_name,
                                j_data["instruction"],
                                full_context_theme,
                                media_part
                            ): j_name
                            for j_name, j_data in JUDGES_CONFIG.items()
                        }
                        for future in concurrent.futures.as_completed(future_to_judge):
                            j_name = future_to_judge[future]
                            judge_results[j_name] = future.result()
                            
                    status.write(f"└ 9名全員の個別評決完了・証拠精査通過 (+{time.time() - t0:.1f}s)")

                    t0 = time.time()
                    admit_judges = [name for name, res in judge_results.items() if res.verdict == "認容"]
                    reject_judges = [name for name, res in judge_results.items() if res.verdict == "棄却"]
                    
                    admit_count = len(admit_judges)
                    reject_count = len(reject_judges)
                    is_admitted = admit_count > reject_count
                    
                    status.write(f"📊 **評決集計完了**: 認容 {admit_count}票 vs 棄却 {reject_count}票")

                    status.write("📜 **首席書記官** が多数派法廷意見・補足意見・反対意見を厳格に起草中...")
                    
                    concurring_texts = "\n".join([f"- **{name}（{JUDGES_CONFIG[name]['title']}）**: {judge_results[name].opinion}" for name in (admit_judges if is_admitted else reject_judges)])
                    dissenting_texts = "\n".join([f"- **{name}（{JUDGES_CONFIG[name]['title']}）**: {judge_results[name].opinion}" for name in (reject_judges if is_admitted else admit_judges)])
                    
                    clerk_prompt = (
                        "あなたは最高裁判所大法廷の【首席書記官】です。\n"
                        "集計された厳格な評決結果と各裁判官の個別意見（提出証拠への言及を含む）に基づき、"
                        "格式高く、威厳に満ち、かつ9名の個性が炸裂した『公式判決文』を起草してください。\n\n"
                        "【出力フォーマット】\n"
                        "# 最高裁判所大法廷判決\n\n"
                        "## 【主 文】\n"
                        "（認容 ○票 対 棄却 ○票 の票数を明記し、結論としての命令を1〜2行で宣言せよ）\n\n"
                        "## 【法廷意見（多数意見 / Majority Opinion）】\n"
                        "（多数派を形成した裁判官たちの論理を止揚・統合した主たる決定理由。証拠資料の状況も適宜反映）\n\n"
                        "## 【補足意見（多数派の個別釘刺し / Concurring Opinions）】\n"
                        "（多数派に属した裁判官たちの個別の警告や条件付け）\n\n"
                        "## 【反対意見（少数派の痛烈な警告 / Dissenting Opinions）】\n"
                        "（少数派に回った裁判官たちの痛烈な批判や将来の破滅リスクへの警告。少数派が0票の場合は『該当なし（満場一致）』と明記）\n\n"
                        "## 【首席執行命令（Execution WBS）】\n"
                        "（判決を現実に執行するための、泥臭く冷徹な強制執行ステップ・マイルストーン）"
                    )
                    
                    clerk_input = (
                        f"【検討課題・事件】\n{full_context_theme}\n\n"
                        f"【確定評決】\n"
                        f"・認容: {admit_count}票 ({', '.join(admit_judges) if admit_judges else 'なし'})\n"
                        f"・棄却: {reject_count}票 ({', '.join(reject_judges) if reject_judges else 'なし'})\n"
                        f"・最終判定: {'認容（原案採択）' if is_admitted else '棄却（原案却下）'}\n\n"
                        f"【多数派意見リスト】\n{concurring_texts}\n\n"
                        f"【少数派意見リスト】\n{dissenting_texts if dissenting_texts else 'なし（全員一致）'}"
                    )
                    
                    judgment_out = ask_agent("首席書記官", clerk_prompt, clerk_input)
                    status.write(f"└ 判決文起草完了 (+{time.time() - t0:.1f}s)")
                    
                    total_time = time.time() - total_start
                    status.update(
                        label=f"✅ 最高裁判所大法廷 判決言渡完了 (総所要時間: {total_time:.1f}秒)",
                        state="complete",
                        expanded=False
                    )

                    st.divider()
                    st.markdown(judgment_out)

                    st.divider()
                    with st.expander("📂 9名の裁判官による評決録・Pydantic構造化データ（原議）", expanded=False):
                        col_j1, col_j2 = st.columns(2)
                        for idx, (j_name, j_data) in enumerate(JUDGES_CONFIG.items()):
                            target_col = col_j1 if idx % 2 == 0 else col_j2
                            v_obj = judge_results[j_name]
                            badge_color = "green" if v_obj.verdict == "認容" else "red"
                            with target_col:
                                with st.container(border=True):
                                    st.markdown(f"#### {j_data['icon']} {j_data['title']}")
                                    st.markdown(f"**評決**: :{badge_color}[【{v_obj.verdict}】]")
                                    st.markdown(f"> {v_obj.opinion}")

                    st.download_button(
                        label="📥 最高裁判所大法廷判決文をダウンロード",
                        data=judgment_out,
                        file_name="Supreme_Court_Judgment.md",
                        mime="text/markdown",
                        use_container_width=True
                    )

                except Exception as e:
                    status.update(label="❌ 法廷エラーが発生しました", state="error", expanded=True)
                    st.error(f"実行エラー詳細: {e}")

        # ----------------------------------------------------
        # 分岐B: 既存パイプライン（直列5フェーズ・マルチモーダル対応）
        # ----------------------------------------------------
        else:
            cfg = active_team_data["roles"]
            labels = active_team_data["progress_labels"]
            headers = active_team_data["headers"]
            is_gorilla = (st.session_state.selected_team == "ゴリラ合議制タスクフォース")
            
            with st.status(f"{st.session_state.selected_team} が合議中...", expanded=True) as status:
                try:
                    # Phase 1: リーダー（画像/動画を直接視覚精査）
                    t0 = time.time()
                    status.write(labels["p1"])
                    leader_out = ask_agent("リーダー", cfg["leader"], full_context_theme, media_part)
                    status.write(f"└ 完了 (+{time.time() - t0:.1f}s)")

                    # Phase 2: リサーチャー（画像/動画も踏まえた客観ファクト抽出）
                    t0 = time.time()
                    status.write(labels["p2"])
                    research_out = ask_agent("リサーチャー", cfg["researcher"], leader_out, media_part)
                    status.write(f"└ 完了 (+{time.time() - t0:.1f}s)")

                    # Phase 3: 対立討論（並列処理）
                    t0 = time.time()
                    status.write(f"⚡ **{cfg['promoter_title']} vs {cfg['redteam_title']}** が激突中...")
                    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                        f_pro = executor.submit(ask_agent, "推進派", cfg["promoter"], research_out, media_part)
                        f_con = executor.submit(ask_agent, "慎重派", cfg["redteam"], research_out, media_part)
                        promoter_out = f_pro.result()
                        redteam_out = f_con.result()
                    status.write(f"└ 完了 (+{time.time() - t0:.1f}s)")

                    # Phase 4: モデレーター
                    t0 = time.time()
                    status.write(labels["p4"])
                    mod_input = f"【推進派の主張】\n{promoter_out}\n\n【慎重派の主張】\n{redteam_out}"
                    moderator_out = ask_agent("モデレーター", cfg["moderator"], mod_input, media_part)
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

                    st.divider()
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