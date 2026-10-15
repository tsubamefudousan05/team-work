"""
Autonomous Multi-Agent Strategy & Judicial Chamber
- 外部設定（YAML）によるペルソナ完全分離
- 3審制動的難易度コントロール
- マルチモーダル証拠画像精査（安定化版）
- レート制限（429）自動リトライ＆指数バックオフ実装
"""

import os
import glob
import time
import concurrent.futures
from PIL import Image
import yaml
import streamlit as st
from google import genai
from google.genai import types

# ==========================================
# 1. ページ基本設定 & デザイン
# ==========================================
st.set_page_config(
    page_title="Autonomous Strategy & Judicial Chamber",
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
    .vote-badge-approve {
        display: inline-block;
        background-color: #065f46;
        color: #34d399;
        font-weight: bold;
        padding: 0.2rem 0.6rem;
        border-radius: 4px;
        margin-bottom: 0.5rem;
    }
    .vote-badge-reject {
        display: inline-block;
        background-color: #7f1d1d;
        color: #f87171;
        font-weight: bold;
        padding: 0.2rem 0.6rem;
        border-radius: 4px;
        margin-bottom: 0.5rem;
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
    st.caption("Autonomous Multi-Agent Chamber")
    
    col1, col2, _ = st.columns([2, 1, 3])
    with col1:
        input_pw = st.text_input("パスワードを入力してください", type="password", key="login_field")
    with col2:
        st.write("")
        st.write("")
        login_btn = st.button("解除", type="primary", use_container_width=True)
    
    if login_btn or input_pw:
        if input_pw == APP_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("パスワードが正しくありません。")
            
    st.stop()

# ==========================================
# 3. コンフィグレーション & 共通設定
# ==========================================
API_KEY = st.secrets.get("GEMINI_API_KEY", st.session_state.get("custom_api_key", ""))

# 無料枠クォータ上限ゼロ（limit: 0）を回避するため Flash モデルで統一
TARGET_MODEL = "gemini-2.5-flash"
MAX_WORKERS = 3       # レート制限（RPM/TPM）を回避する安全な並列数
MAX_RETRIES = 4       # レート制限発生時のリトライ上限回数
BASE_WAIT_SECONDS = 3 # バックオフ初期待機秒数

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "config")

def get_available_chambers():
    """configフォルダ内の全YAMLファイルをスキャンして取得"""
    chambers = {}
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR, exist_ok=True)
    
    yaml_files = glob.glob(os.path.join(CONFIG_DIR, "*.yaml")) + glob.glob(os.path.join(CONFIG_DIR, "*.yml"))
    for yf in yaml_files:
        try:
            with open(yf, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data and "id" in data and "name" in data:
                    chambers[data["name"]] = yf
        except Exception as e:
            st.sidebar.error(f"YAMLロードエラー ({os.path.basename(yf)}): {e}")
    return chambers

def load_chamber_data(filepath: str):
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def build_judge_prompt(judge_info: dict, court_level_info: dict) -> str:
    """各裁判官のプロンプトを審理レベルに応じて動的生成"""
    raw_strictness = judge_info.get("base_strictness", 3) + court_level_info.get("offset", 0)
    effective_strictness = max(1, min(5, raw_strictness))
    
    prompt = f"""
【審理環境】：{court_level_info['name']}
【環境方針】：{court_level_info['modifier']}

【あなたの役割】：{judge_info['name']}（{judge_info.get('title', '')}）
【厳格度レベル】：{effective_strictness}/5
（Lv1: 改善的・支援的 〜 Lv3: 実利・証拠次第 〜 Lv5: 原則門前払い・絶対棄却）

【行動・思考指針】：
{judge_info['system_prompt'].strip()}

【認容の絶対条件】：
{judge_info['approval_condition'].strip()}

【出力フォーマット要件】：
あなたの意見表明は必ず以下の形式で簡潔かつ鋭く出力してください。
1行目：【認容】または【棄却】のどちらか一方のみを記述。
2行目以降：提出されたテキストおよび【証拠画像】が存在する場合はその視覚情報（文字サイズ、文字配置、写真の占有面積、全体デザイン等）も精査した上で、あなたのペルソナ全開で論理・糾弾・条件・アドバイスを述べること。
"""
    return prompt.strip()

# ==========================================
# 4. サイドバー & コントロールUI
# ==========================================
available_chambers = get_available_chambers()

with st.sidebar:
    st.header("⚙️ システム構成")
    
    if not available_chambers:
        st.error("configフォルダに有効な設定ファイルがありません。")
        st.stop()
        
    selected_chamber_name = st.selectbox(
        "🏛️ 合議体（チャンバー）選択",
        options=list(available_chambers.keys()),
        index=0
    )
    active_chamber_file = available_chambers[selected_chamber_name]
    active_chamber_data = load_chamber_data(active_chamber_file)
    
    # 3審制レベル選択（court_levels がある合議体のみ表示）
    court_levels = active_chamber_data.get("court_levels", {})
    level_display_map = {v.get("name", k): k for k, v in court_levels.items() if isinstance(v, dict)}
    
    if level_display_map:
        def_idx = 1 if len(level_display_map) > 1 else 0
        selected_level_display = st.selectbox(
            "⚖️ 審理レベル（難易度コントロール）",
            options=list(level_display_map.keys()),
            index=def_idx
        )
        selected_level_key = level_display_map[selected_level_display]
        active_court_level_info = court_levels[selected_level_key]
    else:
        active_court_level_info = {
            "name": "通常審理（標準モード）",
            "modifier": "各自の基本指針に基づき、中立公正に審査せよ。",
            "offset": 0
        }
        
    st.divider()
    st.caption(f"**説明**: {active_chamber_data.get('description', '')}")
    st.caption(f"**参加メンバー数**: {len(active_chamber_data.get('members', []))}名")
    st.caption(f"**実行エンジン**: Gemini Flash (`{TARGET_MODEL}`)")
    st.caption(f"**並列処理キュー**: {MAX_WORKERS}スレッド並列")
    
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
# 5. エージェントコア（画像＆指数バックオフ対応）
# ==========================================
def ask_agent(role_title: str, system_instruction: str, prompt: str, image_bytes: bytes = None, image_mime: str = "image/jpeg") -> str:
    if not API_KEY:
        raise ValueError("APIキーが設定されていません。")
        
    client = genai.Client(api_key=API_KEY)
    text_content = (
        f"【あなたの役割・ペルソナ】\n{system_instruction}\n\n"
        f"【入力コンテキスト・検討課題】\n{prompt}\n"
    )
    
    contents = [text_content]
    if image_bytes:
        contents.append(
            types.Part.from_bytes(
                data=image_bytes,
                mime_type=image_mime
            )
        )
    
    # レート制限（429）を考慮した指数バックオフ付きリトライ
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=TARGET_MODEL,
                contents=contents
            )
            time.sleep(1.0) # 呼び出し後の安全インターバル
            return response.text
        except Exception as err:
            err_str = str(err)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                wait_time = BASE_WAIT_SECONDS * (2 ** attempt)
                time.sleep(wait_time)
            elif attempt < MAX_RETRIES - 1:
                time.sleep(BASE_WAIT_SECONDS)
            else:
                raise RuntimeError(f"[{role_title}] 呼出失敗: {err}")

# ==========================================
# 6. メインUIレイアウト
# ==========================================
st.title(f"{active_chamber_data.get('name', 'Strategy Chamber')}")
st.caption(f"審理環境: **{active_court_level_info.get('name')}** ｜ {active_court_level_info.get('modifier')}")

default_theme = (
    "セブンイレブンの炭火焼さばおにぎりを購入したところ、"
    "パッケージの隅に小さな注記があるだけで海苔が巻かれていなかった。"
    "このような誤認を誘発する商品設計は企業の欺罔行為として違法または不当とみなすべきか、論ぜよ。"
)
user_theme = st.text_area(
    "審理請求・検討課題（テーマ）",
    value=default_theme,
    height=100,
    help="事業アイデア、司法判断、思想検証、商品への不服申立てなどを入力してください。"
)

# 証拠画像アップローダー
uploaded_file = st.file_uploader(
    "📸 証拠物件・参考画像の提出（任意）", 
    type=["png", "jpg", "jpeg", "webp"],
    help="パッケージ写真、契約書、図面などを添付すると、メンバー全員が画像を直接精査します。"
)

evidence_bytes = None
evidence_mime = "image/jpeg"

if uploaded_file is not None:
    evidence_bytes = uploaded_file.getvalue()
    evidence_mime = uploaded_file.type or "image/jpeg"
    st.image(evidence_bytes, caption="【提出証拠物件 甲第1号証】", use_container_width=False, width=320)

run_button = st.button("🚀 合議・開廷セッションを開始", type="primary", use_container_width=False)

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
        with st.status("合議セッション開廷中...", expanded=True) as status:
            try:
                members = active_chamber_data.get("members", [])
                status.write(f"🏛️ **合議体メンバー ({len(members)}名)** が審査に入ります（並列処理中）...")
                if evidence_bytes:
                    status.write("🔍 提出された【証拠画像】を全メンバーに回覧中...")
                
                individual_results = []
                def eval_member(member):
                    p = build_judge_prompt(member, active_court_level_info)
                    ans = ask_agent(member["name"], p, user_theme, image_bytes=evidence_bytes, image_mime=evidence_mime)
                    return member, ans
                
                t0 = time.time()
                with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    future_to_member = {executor.submit(eval_member, m): m for m in members}
                    for future in concurrent.futures.as_completed(future_to_member):
                        m, ans = future.result()
                        individual_results.append((m, ans))
                
                status.write(f"└ 全員個別審査完了 (+{time.time() - t0:.1f}s)")
                
                # 採決結果の集計
                approve_count = 0
                reject_count = 0
                opinions_text = ""
                
                for m, ans in individual_results:
                    is_approve = "【認容】" in ans.split("\n")[0]
                    if is_approve:
                        approve_count += 1
                    else:
                        reject_count += 1
                    opinions_text += f"\n\n### ■ {m['name']} ({m.get('title', '')})\n{ans}"
                
                # 主席統括官による総括判決文の生成
                t0 = time.time()
                status.write("📜 **統括判決文（総括サマリー）** を作成中...")
                
                summary_prompt = f"""
あなたは本合議体（{active_chamber_data.get('name')}）の主席統括官（首席判事）です。
各構成員の個別意見を統合し、厳格かつ説得力に富んだ「主文・法廷意見（総括）」を作成してください。

【審理環境】：{active_court_level_info['name']}
【採決結果】：認容 {approve_count}票 対 棄却 {reject_count}票
【証拠物件】：{'あり（画像精査済み）' if evidence_bytes else 'なし（テキストのみ）'}

【各構成員の個別意見】：
{opinions_text}

【出力要件】：
1. 【主文】：採決結果を明記（「本件請求を認容する」または「本件請求を棄却する」）
2. 【法廷意見（多数意見の骨子）】：なぜこの結論に至ったのか、本質的な理由を構造的に解説。
3. 【個別補足意見のハイライト】：特に鋭い指摘や面白い意見を1〜2行ずつ要約。
4. 【確定アクション命令】：今後取るべき現実的なアクション工程表を提示。
"""
                chief_summary = ask_agent(
                    "主席統括官",
                    summary_prompt,
                    f"【課題】: {user_theme}",
                    image_bytes=evidence_bytes,
                    image_mime=evidence_mime
                )
                status.write(f"└ 完了 (+{time.time() - t0:.1f}s)")
                
                total_time = time.time() - total_start
                status.update(
                    label=f"✅ 合議プロセス完了 (総所要時間: {total_time:.1f}秒)", 
                    state="complete", 
                    expanded=False
                )
                
                # ==========================================
                # 8. 結果描画セクション
                # ==========================================
                st.divider()
                
                col_res1, col_res2 = st.columns([1, 2])
                with col_res1:
                    if approve_count > reject_count:
                        st.success(f"### 判定：認容（可決）\n認容 {approve_count} vs 棄却 {reject_count}")
                    else:
                        st.error(f"### 判定：棄却（否決）\n認容 {approve_count} vs 棄却 {reject_count}")
                        
                with col_res2:
                    st.info(f"**審理基準**: {active_court_level_info.get('name')}\n\n{active_court_level_info.get('modifier')}")

                st.markdown("### 📜 統括判決・エグゼクティブサマリー")
                st.markdown(f"<div class='lead-box'>{chief_summary}</div>", unsafe_allow_html=True)
                
                st.markdown("### 🗣️ 構成員（裁判官・メンバー）の個別意見")
                cols = st.columns(2)
                for idx, (m, ans) in enumerate(individual_results):
                    col_target = cols[idx % 2]
                    with col_target:
                        with st.container(border=True):
                            is_approve = "【認容】" in ans.split("\n")[0]
                            if is_approve:
                                st.markdown("<span class='vote-badge-approve'>【認容】</span>", unsafe_allow_html=True)
                            else:
                                st.markdown("<span class='vote-badge-reject'>【棄却】</span>", unsafe_allow_html=True)
                                
                            st.markdown(f"**{m['name']}** （{m.get('title', '')}）")
                            st.markdown(ans)
                
                # ダウンロード用テキスト
                full_report = f"""# {active_chamber_data.get('name')} 合議判決レポート
検討課題: {user_theme}
実施日: {time.strftime('%Y-%m-%d %H:%M:%S')}
審理レベル: {active_court_level_info.get('name')}
証拠画像: {'あり' if evidence_bytes else 'なし'}
採決結果: 認容 {approve_count}票 対 棄却 {reject_count}票
所要時間: {total_time:.1f}秒

---
## ■ 統括判決文（主席統括官サマリー）
{chief_summary}

---
## ■ 各構成員の個別意見
{opinions_text}
"""
                st.divider()
                st.download_button(
                    label="📥 全合議レポートをMarkdownでダウンロード（UTF-8）",
                    data=full_report.encode("utf-8"),
                    file_name="chamber_judgment_report.md",
                    mime="text/markdown",
                    use_container_width=True
                )
                
            except Exception as e:
                status.update(label="❌ エラーが発生しました", state="error")
                st.error(f"実行中にエラーが発生しました: {e}")