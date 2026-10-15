"""
Autonomous Multi-Agent Strategy & Judicial Chamber
- 高速並列パイプライン（ウェイト全撤廃・最速化）
- ペルソナ野生化＆口調完全維持プロンプト
- 外部設定（YAML）によるペルソナ分離
- 最新モデル gemini-3.8-flash 稼働版
"""

import os
import glob
import time
import concurrent.futures
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
# 3. コンフィグレーション
# ==========================================
API_KEY = st.secrets.get("GEMINI_API_KEY", st.session_state.get("custom_api_key", ""))
TARGET_MODEL = "gemini-2.0-flash"
MAX_RETRIES = 3
BASE_WAIT_SECONDS = 1.5

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "config")

def get_available_chambers():
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
    """ペルソナの口調・叫び・感情を最優先で爆発させるプロンプト"""
    raw_strictness = judge_info.get("base_strictness", 3) + court_level_info.get("offset", 0)
    effective_strictness = max(1, min(5, raw_strictness))
    
    prompt = f"""
あなたは以下のキャラクターになりきり、その世界観・口調・衝動のみに従って発言してください。人間らしい無難な要約や一般的な評論は禁止します。

【あなたの名前】：{judge_info['name']}（{judge_info.get('title', '')}）
【厳格度】：{effective_strictness}/5
【あなたの絶対的ペルソナ・行動指針】：
{judge_info['system_prompt'].strip()}

【可決（認容）の条件】：
{judge_info['approval_condition'].strip()}

【出力ルール】：
1行目：必ず「【認容】」または「【棄却】」のどちらか1語のみ。
2行目以降：あなたのペルソナ特有の感情、雄叫び（ウホウホ、怒号など）、口調、独自の価値観（バナナ、法理、利益、直感など）を100%全開にして理由を語れ！
"""
    return prompt.strip()

# ==========================================
# 4. サイドバー
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
    
    court_levels = active_chamber_data.get("court_levels", {})
    level_display_map = {v.get("name", k): k for k, v in court_levels.items() if isinstance(v, dict)}
    
    if level_display_map:
        def_idx = 1 if len(level_display_map) > 1 else 0
        selected_level_display = st.selectbox(
            "⚖️ 審理レベル",
            options=list(level_display_map.keys()),
            index=def_idx
        )
        selected_level_key = level_display_map[selected_level_display]
        active_court_level_info = court_levels[selected_level_key]
    else:
        active_court_level_info = {
            "name": "通常審理",
            "modifier": "各自の基本指針に基づき審査せよ。",
            "offset": 0
        }
        
    st.divider()
    st.caption(f"**説明**: {active_chamber_data.get('description', '')}")
    st.caption(f"**参加メンバー数**: {len(active_chamber_data.get('members', []))}名")
    st.caption(f"**エンジン**: `{TARGET_MODEL}` (高速並列モード)")
    
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
# 5. エージェントコア（高速版）
# ==========================================
def call_gemini_api(system_instruction: str, prompt: str, image_bytes: bytes = None, image_mime: str = "image/jpeg", temp: float = 1.0) -> str:
    if not API_KEY:
        raise ValueError("APIキーが設定されていません。")
        
    client = genai.Client(api_key=API_KEY)
    contents = []
    if image_bytes:
        contents.append(types.Part.from_bytes(data=image_bytes, mime_type=image_mime))
    contents.append(prompt)
    
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=TARGET_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=temp,
                )
            )
            
            if response.text:
                return response.text.strip()
            
            if response.candidates and response.candidates[0].content.parts:
                parts_text = "".join([p.text for p in response.candidates[0].content.parts if hasattr(p, "text") and p.text])
                if parts_text:
                    return parts_text.strip()
                    
            return "【棄却】\n（応答テキストが空でした）"
            
        except Exception as err:
            last_err = err
            err_str = str(err)
            if any(code in err_str for code in ["429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE"]):
                time.sleep(BASE_WAIT_SECONDS * (attempt + 1))
            elif attempt < MAX_RETRIES - 1:
                time.sleep(1.0)
            else:
                return f"【棄却】\n（審理不能エラー: {err}）"
                
    return f"【棄却】\n（リトライ上限超過: {last_err}）"

# ==========================================
# 6. メインUI
# ==========================================
st.title(f"{active_chamber_data.get('name', 'Strategy Chamber')}")
st.caption(f"環境: **{active_court_level_info.get('name')}** ｜ {active_court_level_info.get('modifier')}")

default_theme = (
    "セブンイレブンの炭火焼さばおにぎりを購入したところ、"
    "パッケージの隅に小さな注記があるだけで海苔が巻かれていなかった。"
    "このような誤認を誘発する商品設計は企業の欺罔行為として違法または不当とみなすべきか、論ぜよ。"
)
user_theme = st.text_area("審議課題・検討テーマ", value=default_theme, height=100)

uploaded_file = st.file_uploader("📸 証拠物件・参考画像（任意）", type=["png", "jpg", "jpeg", "webp"])

evidence_bytes = None
evidence_mime = "image/jpeg"
if uploaded_file is not None:
    evidence_bytes = uploaded_file.getvalue()
    evidence_mime = uploaded_file.type or "image/jpeg"
    st.image(evidence_bytes, caption="【提出証拠物件 甲第1号証】", width=320)

run_button = st.button("🚀 合議・開廷セッションを開始", type="primary")

# ==========================================
# 7. 高速一斉並列パイプライン
# ==========================================
if run_button:
    if not API_KEY:
        st.error("Gemini APIキーが設定されていません。")
    elif not user_theme.strip():
        st.warning("テーマを入力してください。")
    else:
        total_start = time.time()
        with st.status("合議セッション開廷中...", expanded=True) as status:
            try:
                members = active_chamber_data.get("members", [])
                status.write(f"🏛️ **合議体メンバー ({len(members)}名)** が一斉に個別審査中...")
                
                # メンバー全員を一括同時並列で回す
                individual_results = []
                def eval_member(member):
                    sys_p = build_judge_prompt(member, active_court_level_info)
                    ans = call_gemini_api(sys_p, f"【検討課題】:\n{user_theme}", image_bytes=evidence_bytes, image_mime=evidence_mime)
                    return member, ans
                
                t0 = time.time()
                with concurrent.futures.ThreadPoolExecutor(max_workers=len(members)) as executor:
                    future_to_member = {executor.submit(eval_member, m): m for m in members}
                    for future in concurrent.futures.as_completed(future_to_member):
                        m, ans = future.result()
                        individual_results.append((m, ans))
                
                status.write(f"└ 全員個別審査完了 (+{time.time() - t0:.1f}s)")
                
                approve_count = 0
                reject_count = 0
                opinions_text = ""
                
                for m, ans in individual_results:
                    safe_ans = str(ans) if ans else "【棄却】\n（意見なし）"
                    first_line = safe_ans.split("\n")[0] if "\n" in safe_ans else safe_ans
                    
                    if "【認容】" in first_line:
                        approve_count += 1
                    else:
                        reject_count += 1
                    opinions_text += f"\n\n### ■ {m['name']} ({m.get('title', '')})\n{safe_ans}"
                
                t0 = time.time()
                status.write("📜 **統括サマリー** を作成中...")
                
                summary_prompt = f"""
あなたはこの合議体（{active_chamber_data.get('name')}）の長・総括リーダーです。
合議体の世界観・口調・トーンを維持し、意見を統合した「最終結論」を作成せよ。

【環境】：{active_court_level_info['name']}
【採決結果】：認容 {approve_count}票 対 棄却 {reject_count}票
【各構成員の意見】：
{opinions_text}

【出力要件】：
1. 【最終主文】：認容か棄却かを明確に宣告。
2. 【総括意見】：なぜこの結論になったのか、この合議体らしいトーンで熱く解説。
3. 【注目意見のピックアップ】：構成員の面白かった叫びや鋭かった指摘をハイライト。
4. 【確定アクション命令】：今後取るべき現実的なアクション。
"""
                chief_summary = call_gemini_api(
                    summary_prompt,
                    f"【課題】: {user_theme}",
                    temp=0.8
                )
                status.write(f"└ 完了 (+{time.time() - t0:.1f}s)")
                
                total_time = time.time() - total_start
                status.update(label=f"✅ 合議プロセス完了 (総所要時間: {total_time:.1f}秒)", state="complete", expanded=False)
                
                # ==========================================
                # 8. 結果描画
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

                st.markdown("### 📜 統括・エグゼクティブサマリー")
                st.markdown(f"<div class='lead-box'>{chief_summary}</div>", unsafe_allow_html=True)
                
                st.markdown("### 🗣️ 構成員の個別意見")
                cols = st.columns(2)
                for idx, (m, ans) in enumerate(individual_results):
                    safe_ans = str(ans) if ans else "【棄却】\n（意見なし）"
                    first_line = safe_ans.split("\n")[0] if "\n" in safe_ans else safe_ans
                    is_approve = "【認容】" in first_line

                    col_target = cols[idx % 2]
                    with col_target:
                        with st.container(border=True):
                            if is_approve:
                                st.markdown("<span class='vote-badge-approve'>【認容】</span>", unsafe_allow_html=True)
                            else:
                                st.markdown("<span class='vote-badge-reject'>【棄却】</span>", unsafe_allow_html=True)
                                
                            st.markdown(f"**{m['name']}** （{m.get('title', '')}）")
                            st.markdown(safe_ans)
                
                full_report = f"""# {active_chamber_data.get('name')} 合議レポート
検討課題: {user_theme}
実施日: {time.strftime('%Y-%m-%d %H:%M:%S')}
採決結果: 認容 {approve_count}票 対 棄却 {reject_count}票
所要時間: {total_time:.1f}秒

---
## ■ 統括サマリー
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