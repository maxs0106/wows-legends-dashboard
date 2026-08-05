import io
import os
import re
from datetime import datetime, date
from typing import Dict, List, Tuple, Optional, Any
import zipfile

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

# ==========================================
# 1. ページ初期設定 & カスタムゲームUI風CSS
# ==========================================
st.set_page_config(
    page_title="WOWS Legends Dashboard",
    page_icon="⚓",
    layout="wide",
    initial_sidebar_state="expanded"
)

CSS_STYLE = """
<style>
    .stApp {
        background-color: #0b131e;
        color: #d1d5db;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    section[data-testid="stSidebar"] {
        background-color: #070d14 !important;
        border-right: 1px solid #1e293b;
    }
    
    /* ⚓ タイトル & クラン情報 UI */
    .game-header-container {
        background: linear-gradient(90deg, #111c2e 0%, #070d14 100%);
        border-left: 5px solid #00f2fe;
        padding: 20px 24px;
        border-radius: 4px;
        margin-bottom: 25px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5);
    }
    .game-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: 2px;
        margin: 0 0 10px 0;
        text-transform: uppercase;
        text-shadow: 0 0 15px rgba(0, 242, 254, 0.5);
    }
    .player-clan-info {
        font-size: 1.4rem;
        color: #ffffff;
        font-weight: 700;
    }

    /* 🧭 モード選択用ヘッダー */
    .mode-selection-header {
        font-size: 1.1rem;
        font-weight: 700;
        color: #00f2fe;
        margin: 15px 0 10px 0;
        text-transform: uppercase;
    }

    /* 📊 マトリクス共通デザイン */
    .matrix-scroll-wrapper {
        position: relative;
        width: 100%;
        overflow-x: auto;
        margin: 20px 0 40px 0;
        border: 1px solid #1e293b;
        background-color: #070d14;
    }
    .matrix-table {
        border-collapse: separate;
        border-spacing: 0;
        width: 100%;
        font-size: 0.95rem;
        text-align: center;
    }
    .matrix-table th, .matrix-table td {
        padding: 15px;
        border-bottom: 1px solid #1e293b;
        border-right: 1px solid #1e293b;
        min-width: 150px;
        max-width: 180px;
        color: #d1d5db;
    }
    .matrix-table th {
        background-color: #0f172a;
        color: #ffffff;
        font-weight: 700;
    }
    .matrix-table th.sticky-indicator, .matrix-table td.sticky-indicator {
        position: sticky;
        left: 0;
        background-color: #0f172a !important;
        z-index: 10;
        text-align: left;
        border-right: 2px solid #00f2fe;
        font-weight: 700;
        color: #ffffff;
    }
    .matrix-table th.sticky-lifetime, .matrix-table td.sticky-lifetime {
        position: sticky;
        left: 180px;
        background-color: #111c2e !important;
        z-index: 9;
        font-weight: 700;
        border-right: 2px solid #1e293b;
    }
    
    .chart-section-title {
        font-size: 1.3rem;
        font-weight: 700;
        color: #ffffff;
        margin: 40px 0 20px 0;
        padding-left: 10px;
        border-left: 5px solid #00f2fe;
    }
    .empty-cell {
        color: #4b5563 !important;
    }
</style>
"""
st.markdown(CSS_STYLE, unsafe_allow_html=True)

# ==========================================
# 2. マッピング定義
# ==========================================
CSV_MAPPING = {
    "WOWSL_Game_Sessions.csv": "game_sessions",
    "Clans.csv": "clans",
    "WOWSL_Account_Statistics.csv": "account_stats",
    "WOWSL_Battle_Types_Statistics.csv": "battle_types",
    "WOWSL_Ship_Statistics_By_Type.csv": "ship_stats",
    "Account_Info.csv": "account_info"    
}

IMAGE_NATION_MAP = {
    "a": "アメリカ", "j": "日本", "b": "イギリス", "g": "ドイツ",
    "f": "フランス", "r": "ソ連", "i": "イタリア", "w": "ヨーロッパ",
    "z": "パンアジア", "e": "パンヨーロッパ", "u": "イギリス連邦",
    "h": "オランダ", "n": "オランダ", "s": "スペイン", "v": "パンアメリカ"
}
IMAGE_CLASS_MAP = {"a": "空母", "b": "戦艦", "c": "巡洋艦", "d": "駆逐艦"}

BATTLE_TYPE_MAP = {
    1: {"mode": "通常", "team": "総合"}, 2: {"mode": "AI", "team": "総合"},
    3: {"mode": "通常", "team": "ソロ"}, 4: {"mode": "通常", "team": "2人分隊"}, 5: {"mode": "通常", "team": "3人分隊"}, 
    6: {"mode": "AI", "team": "ソロ"}, 7: {"mode": "AI", "team": "2人分隊"}, 8: {"mode": "AI", "team": "3人分隊"},
    9: {"mode": "ランク", "team": "ソロ"}, 10: {"mode": "ランク", "team": "2人分隊"}, 11: {"mode": "ランク", "team": "3人分隊"},
    17: {"mode": "アリーナ", "team": "ソロ"}, 18: {"mode": "アリーナ", "team": "2人分隊"}, 19: {"mode": "アリーナ", "team": "3人分隊"},
    20: {"mode": "闘争", "team": "ソロ"}, 21: {"mode": "闘争", "team": "2人分隊"}, 22: {"mode": "闘争", "team": "3人分隊"},
    23: {"mode": "アーケード", "team": "総合"}, 24: {"mode": "アーケード", "team": "ソロ"},
    25: {"mode": "アーケード", "team": "2人分隊"}, 26: {"mode": "アーケード", "team": "3人分隊"},
    27: {"mode": "クラン戦", "team": "総合"}, 28: {"mode": "軍記", "team": "総合"}
}

NATION_ORDER = [
    "アメリカ", "日本", "イギリス", "ドイツ", "フランス", "ソ連", 
    "イタリア", "ヨーロッパ", "パンアジア", "パンヨーロッパ", "パンアメリカ", "オランダ", "スペイン"
]

TIER_ORDER = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "★"]
TIER_VAL_MAP = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "★": 9}
VAL_TIER_MAP = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII", 9: "★"}

# ==========================================
# 3. データ処理エンジン（関数群）
# ==========================================
def load_ship_reference() -> Dict[str, Tuple[str, str]]:
    if os.path.exists("ship_id.csv"):
        try:
            df = pd.read_csv("ship_id.csv")
            return dict(zip(df['id'].astype(str), zip(df['name'], df['Tier'])))
        except Exception:
            pass
    return {}

def parse_ship_id(vehicle_name: str, ship_map: Dict[str, Tuple[str, str]]) -> Tuple[str, str, str, str]:
    clean_vname = str(vehicle_name).strip()
    if clean_vname in ship_map:
        display_name, raw_tier = ship_map[clean_vname]
        str_tier = str(raw_tier).strip()
        if str_tier in ["★", "L", "Legend", "Legendary", "11"]:
            tier = "★"
        else:
            tier = str_tier
    else:
        display_name = clean_vname
        tier = "その他"

    low_name = clean_vname.lower()
    nation, ship_class = "その他", "その他"
    
    if low_name.startswith('p') and len(low_name) >= 4:
        n_code = low_name[1]
        c_code = low_name[3] if low_name[2] == 's' else low_name[2]
        nation = IMAGE_NATION_MAP.get(n_code, "その他")
        ship_class = IMAGE_CLASS_MAP.get(c_code, "その他")
    
    return nation, ship_class, str(tier), display_name

def read_csv_smart(content_str: str) -> pd.DataFrame:
    """ヘッダー有無を自動判別してCSV文字列を読み込む"""
    lines = [l.strip() for l in content_str.splitlines() if l.strip()]
    if not lines:
        return pd.DataFrame()
    first_line = lines[0]
    # 日時パターンや特定のKeywordsが含まれ、かつ標準ヘッダーがない場合
    if re.search(r'\d{4}-\d{2}-\d{2}', first_line) and not ("CREATED_AT" in first_line or "UPDATED_AT" in first_line or "START_TIME" in first_line):
        return pd.read_csv(io.StringIO(content_str), header=None)
    return pd.read_csv(io.StringIO(content_str))

def get_snapshot_date(df: pd.DataFrame, file_name: str) -> datetime:
    if "WOWSL_Account_Statistics.csv" in file_name and not df.empty:
        if 'UPDATED_AT' in df.columns:
            valid_series = pd.to_numeric(df['UPDATED_AT'], errors='coerce').dropna()
            if not valid_series.empty:
                max_timestamp = valid_series.max()
                if max_timestamp > 1000000000:
                    return pd.to_datetime(datetime.fromtimestamp(max_timestamp).date())
            
            string_series = df['UPDATED_AT'].astype(str).str.strip()
            matches = string_series.str.extract(r'(\d{4}-\d{2}-\d{2})').dropna()
            if not matches.empty:
                return pd.to_datetime(matches[0].max())

    matches = re.findall(r'\d{4}-\d{2}-\d{2}', file_name)
    if matches:
        return pd.to_datetime(datetime.strptime(matches[0], '%Y-%m-%d').date())
        
    matches_no_dash = re.findall(r'\d{8}', file_name)
    if matches_no_dash:
        try:
            return pd.to_datetime(datetime.strptime(matches_no_dash[0], '%Y%m%d').date())
        except ValueError:
            pass

    target_columns = ['UPDATED_AT', 'LAST_BATTLE_TIME', 'LOG_OUT_TIME', 'DOSSIER_UPDATED_AT']
    for col in target_columns:
        if col in df.columns and not df.empty:
            valid_series = pd.to_numeric(df[col], errors='coerce').dropna()
            if not valid_series.empty:
                max_timestamp = valid_series.max()
                if max_timestamp > 1000000000:
                    return pd.to_datetime(datetime.fromtimestamp(max_timestamp).date())
            
            string_series = df[col].astype(str).str.strip().dropna()
            string_series = string_series[string_series.str.match(r'^\d{4}-\d{2}-\d{2}')]
            if not string_series.empty:
                max_str = string_series.max()
                return pd.to_datetime(datetime.strptime(max_str[:10], '%Y-%m-%d').date())

    return pd.to_datetime(date.today())

def extract_zip_data(uploaded_files: List[Any]) -> Tuple[Dict[str, List[pd.DataFrame]], List[str], List[str]]:
    all_data: Dict[str, List[pd.DataFrame]] = {k: [] for k in CSV_MAPPING.values()}
    success_zips, errors = [], []
    for up_file in uploaded_files:
        try:
            with zipfile.ZipFile(io.BytesIO(up_file.read())) as z:
                temp_dfs = {}
                detected_date = None
                
                for internal_path in z.namelist():
                    base_name = os.path.basename(internal_path)
                    if base_name in CSV_MAPPING:
                        try:
                            content = z.open(internal_path).read().decode('utf-8')
                        except:
                            content = z.open(internal_path).read().decode('shift_jis')
                        
                        df = read_csv_smart(content)
                        if not df.empty:
                            df.columns = [str(c).strip().upper() for c in df.columns]
                            temp_dfs[CSV_MAPPING[base_name]] = df
                
                for key in ["battle_types", "account_stats", "ship_stats"]:
                    if key in temp_dfs and detected_date is None:
                        date_candidate = get_snapshot_date(temp_dfs[key], up_file.name)
                        if date_candidate != pd.to_datetime(date.today()):
                            detected_date = date_candidate
                            break
                            
                if detected_date is None:
                    detected_date = get_snapshot_date(pd.DataFrame(), up_file.name)
                    
                for key, df in temp_dfs.items():
                    df['_SNAPSHOT_DATE'] = detected_date
                    all_data[key].append(df)
                success_zips.append(f"{up_file.name}")
        except Exception as e:
            errors.append(f"{up_file.name}: {str(e)}")
    return all_data, success_zips, errors

def merge_and_optimize(raw_data: Dict[str, List[pd.DataFrame]]) -> Dict[str, pd.DataFrame]:
    merged: Dict[str, pd.DataFrame] = {}
    for key, dfs in raw_data.items():
        if not dfs:
            merged[key] = pd.DataFrame()
            continue
        
        df_concat = pd.concat(dfs, ignore_index=True)
        if '_SNAPSHOT_DATE' in df_concat.columns:
            df_concat['_SNAPSHOT_DATE'] = pd.to_datetime(df_concat['_SNAPSHOT_DATE'])
        
        if key == 'clans':
            merged[key] = df_concat.drop_duplicates().reset_index(drop=True)
        else:
            id_cols = ['_SNAPSHOT_DATE'] if '_SNAPSHOT_DATE' in df_concat.columns else []
            if key == 'battle_types' and 'TYPE' in df_concat.columns: 
                id_cols.append('TYPE')
            elif key == 'ship_stats' and 'VEHICLE_NAME' in df_concat.columns and 'TYPE' in df_concat.columns: 
                id_cols.extend(['VEHICLE_NAME', 'TYPE'])
            
            if id_cols:
                merged[key] = df_concat.drop_duplicates(subset=id_cols, keep='last').reset_index(drop=True)
            else:
                merged[key] = df_concat.reset_index(drop=True)
            
    return merged

def calc_metrics_from_row(df: pd.DataFrame) -> Dict[str, Any]:
    if df.empty or 'BATTLES_COUNT' not in df.columns or df['BATTLES_COUNT'].sum() <= 0:
        return {"battles": 0, "win_rate": None, "survived_rate": None, "avg_damage": None, "kd": None, "avg_frags": None, "avg_xp": None}
    b = float(df['BATTLES_COUNT'].sum())
    d = b - float(df['SURVIVED'].sum() if 'SURVIVED' in df.columns else 0)
    return {
        "battles": int(b), 
        "win_rate": (float(df['WINS'].sum()) / b * 100),
        "survived_rate": (float(df['SURVIVED'].sum() if 'SURVIVED' in df.columns else 0) / b * 100),
        "avg_damage": (float(df['DAMAGE_DEALT'].sum() if 'DAMAGE_DEALT' in df.columns else 0) / b),
        "kd": (float(df['FRAGS'].sum() if 'FRAGS' in df.columns else 0) / (1.0 if d <= 0 else d)),
        "avg_frags": (float(df['FRAGS'].sum() if 'FRAGS' in df.columns else 0) / b),
        "avg_xp": (float(df['ORIGINAL_EXP'].sum() if 'ORIGINAL_EXP' in df.columns else 0) / b)
    }

def calc_period_diff_metrics(df_new: pd.DataFrame, df_old: pd.DataFrame) -> Dict[str, Any]:
    b = float(df_new['BATTLES_COUNT'].sum() - df_old['BATTLES_COUNT'].sum())
    if b <= 0:
        return {"battles": 0, "win_rate": None, "survived_rate": None, "avg_damage": None, "kd": None, "avg_frags": None, "avg_xp": None}
    d = b - float(df_new['SURVIVED'].sum() - df_old['SURVIVED'].sum())
    return {
        "battles": int(b), 
        "win_rate": max(0.0, min(100.0, (float(df_new['WINS'].sum() - df_old['WINS'].sum()) / b * 100))),
        "survived_rate": max(0.0, min(100.0, (float(df_new['SURVIVED'].sum() - df_old['SURVIVED'].sum()) / b * 100))),
        "avg_damage": max(0.0, float(df_new['DAMAGE_DEALT'].sum() - df_old['DAMAGE_DEALT'].sum()) / b),
        "kd": max(0.0, float(df_new['FRAGS'].sum() - df_old['FRAGS'].sum()) / (1.0 if d <= 0 else d)),
        "avg_frags": max(0.0, float(df_new['FRAGS'].sum() - df_old['FRAGS'].sum()) / b),
        "avg_xp": max(0.0, float(df_new['ORIGINAL_EXP'].sum() - df_old['ORIGINAL_EXP'].sum()) / b)
    }

def generate_matrix_html(headers: List[str], rows_data: List[Tuple[str, List[Any]]], formats: List[str]) -> str:
    html = '<div class="matrix-scroll-wrapper"><table class="matrix-table"><thead><tr><th class="sticky-indicator">分類・項目</th>'
    for h in headers: html += f'<th>{h}</th>'
    html += '</tr></thead><tbody>'
    for row_title, values in rows_data:
        html += f'<tr><td class="sticky-indicator">{row_title}</td>'
        for val, fmt in zip(values, formats):
            if val is not None and pd.notna(val):
                html += f'<td>{fmt.format(val)}</td>'
            else:
                html += '<td class="empty-cell">-</td>'
        html += '</tr>'
    html += '</tbody></table></div>'
    return html

# ==========================================
# 4. メインアプリケーションルーチン
# ==========================================
def main():
    st.sidebar.header("データインポート")
    uploaded_files = st.sidebar.file_uploader("ZIPデータダンプ投入", type="zip", accept_multiple_files=True)
    
    if not uploaded_files:
        st.info("サイドバーから個人データZIPファイルを複数アップロードしてください。")
        return

    raw_data, success_zips, errors = extract_zip_data(uploaded_files)
    data = merge_and_optimize(raw_data)
    
    all_dates = []
    for df in data.values():
        if not df.empty and '_SNAPSHOT_DATE' in df.columns:
            all_dates.extend(df['_SNAPSHOT_DATE'].dropna().tolist())
    
    if not all_dates:
        st.error("有効な日付データを含むCSVファイルが見つかりません。")
        return
        
    unique_dates = sorted(list(set(pd.to_datetime(all_dates))))

    ship_name_map = load_ship_reference()
    ship_df = data["ship_stats"]
    
    if not ship_df.empty:
        parsed_meta = ship_df['VEHICLE_NAME'].apply(lambda x: parse_ship_id(x, ship_name_map))
        ship_df['_NATION'] = [x[0] for x in parsed_meta]
        ship_df['_SHIP_TYPE'] = [x[1] for x in parsed_meta]
        ship_df['_ESTIMATED_TIER'] = [x[2] for x in parsed_meta]
        ship_df['_CLEAN_NAME'] = [x[3] for x in parsed_meta]
        data["ship_stats"] = ship_df

    # ⚓ クラン・プレイヤー情報抽出
    clan_tag, p_name = None, "プレイヤーデータ"
    if not data["account_info"].empty:
        l_info = data["account_info"].iloc[-1]
        for nick_col in ['NICKNAME', 0]:
            if nick_col in l_info.index and pd.notna(l_info[nick_col]):
                p_name = str(l_info[nick_col])
                break
        
    if p_name == "プレイヤーデータ" and not data["account_stats"].empty:
        l_stats = data["account_stats"].iloc[-1]
        for name_col in ['NICKNAME', 'PLAYER_NAME', 'NAME', 'ACCOUNT_NAME']:
            if name_col in l_stats.index and pd.notna(l_stats[name_col]):
                p_name = str(l_stats[name_col])
                break

    player_display_string = f"【{clan_tag}】{p_name}" if clan_tag else p_name
    st.markdown(f'<div class="game-header-container"><div class="game-title">WOWSL Legends Dashboard</div><div class="player-clan-info">{player_display_string}</div></div>', unsafe_allow_html=True)

    # ==========================================
    # 全タブ共通：モード・部隊形式の選択とデータ生成
    # ==========================================
    bt_df = data["battle_types"]
    
    if 'sel_mode' not in st.session_state: st.session_state.sel_mode = "通常"
    current_mode = st.session_state.sel_mode

    st.markdown('<div class="mode-selection-header">■ STEP1: モード選択</div>', unsafe_allow_html=True)
    mode_order = ["通常", "AI", "ランク", "アリーナ", "闘争", "アーケード", "クラン戦", "軍記"]
    m_cols = st.columns(len(mode_order))
    for idx, m_name in enumerate(mode_order):
        with m_cols[idx]:
            if st.button(m_name, key=f"btn_m_{m_name}", use_container_width=True, type="primary" if current_mode == m_name else "secondary"):
                st.session_state.sel_mode = m_name
                st.session_state.sel_team = "総合"
                st.rerun()

    st.markdown('<div class="mode-selection-header">■ STEP2: 部隊形式選択</div>', unsafe_allow_html=True)
    team_options = ["総合"] if current_mode in ["クラン戦", "軍記"] else ["総合", "ソロ", "2人分隊", "3人分隊"]
    if 'sel_team' not in st.session_state or st.session_state.sel_team not in team_options:
        st.session_state.sel_team = "総合"
        
    t_cols = st.columns(4)
    for idx, t_name in enumerate(team_options):
        if idx < len(team_options):
            with t_cols[idx]:
                if st.button(t_name, key=f"btn_t_{t_name}", use_container_width=True, type="primary" if st.session_state.sel_team == t_name else "secondary"):
                    st.session_state.sel_team = t_name
                    st.rerun()

    # --- 選択されたモードによるデータフィルタリング ---
    DIRECT_MODE_MODES = ["通常", "AI", "アーケード", "クラン戦", "軍記"]
    sum_cols = ['BATTLES_COUNT', 'WINS', 'SURVIVED', 'DAMAGE_DEALT', 'FRAGS', 'ORIGINAL_EXP']
    
    if st.session_state.sel_team == "総合":
        if current_mode in DIRECT_MODE_MODES:
            target_type_code = next((tid for tid, meta in BATTLE_TYPE_MAP.items() if meta["mode"] == current_mode and meta["team"] == "総合"), None)
            mode_bt_df = bt_df[bt_df['TYPE'] == target_type_code] if not bt_df.empty and target_type_code else pd.DataFrame()
            mode_filtered_ship_df = ship_df[ship_df['TYPE'] == target_type_code] if not ship_df.empty and target_type_code else pd.DataFrame()
        else:
            target_type_codes = [tid for tid, meta in BATTLE_TYPE_MAP.items() if meta["mode"] == current_mode and meta["team"] in ["ソロ", "2人分隊", "3人分隊"]]
            raw_bt_df = bt_df[bt_df['TYPE'].isin(target_type_codes)] if not bt_df.empty else pd.DataFrame()
            mode_bt_df = raw_bt_df.groupby('_SNAPSHOT_DATE')[sum_cols].sum().reset_index() if not raw_bt_df.empty else pd.DataFrame()
            if not mode_bt_df.empty: mode_bt_df['TYPE'] = 0
            
            raw_ship_df = ship_df[ship_df['TYPE'].isin(target_type_codes)] if not ship_df.empty else pd.DataFrame()
            if not raw_ship_df.empty:
                group_keys = ['_SNAPSHOT_DATE', 'VEHICLE_NAME', '_NATION', '_SHIP_TYPE', '_ESTIMATED_TIER', '_CLEAN_NAME']
                extra_cols = [c for c in raw_ship_df.columns if str(c).startswith('MAX_')]
                agg_dict = {col: 'sum' for col in sum_cols}
                for ec in extra_cols: agg_dict[ec] = 'max'
                mode_filtered_ship_df = raw_ship_df.groupby(group_keys).agg(agg_dict).reset_index()
                mode_filtered_ship_df['TYPE'] = 0
            else:
                mode_filtered_ship_df = pd.DataFrame()
    else:
        target_type_code = next((tid for tid, meta in BATTLE_TYPE_MAP.items() if meta["mode"] == current_mode and meta["team"] == st.session_state.sel_team), None)
        mode_bt_df = bt_df[bt_df['TYPE'] == target_type_code] if not bt_df.empty and target_type_code else pd.DataFrame()
        mode_filtered_ship_df = ship_df[ship_df['TYPE'] == target_type_code] if not ship_df.empty and target_type_code else pd.DataFrame()

    st.markdown("<hr style='border:1px solid #1e293b; margin: 25px 0;'>", unsafe_allow_html=True)

    # ==========================================
    # タブ生成
    # ==========================================
    t_summary, t_structural, t_ship, t_best, t_other = st.tabs([
        "総合戦績", "国・艦種・ティア別分析", "艦艇別詳細", "自己ベスト", "その他"
    ])

    # ------------------------------------------
    # Tab 1: 総合戦績
    # ------------------------------------------
    with t_summary:
        matrix_columns = {}
        if not mode_bt_df.empty:
            max_date = mode_bt_df['_SNAPSHOT_DATE'].max()
            global_kpi = calc_metrics_from_row(mode_bt_df[mode_bt_df['_SNAPSHOT_DATE'] == max_date])
        else:
            global_kpi = calc_metrics_from_row(pd.DataFrame())
        matrix_columns["全期間"] = global_kpi

        period_keys = []
        if len(unique_dates) > 1:
            for i in range(len(unique_dates) - 1, 0, -1):
                d_start, d_end = unique_dates[i-1], unique_dates[i]
                period_label = f"{d_start.strftime('%Y/%m/%d')}<br>～ {d_end.strftime('%Y/%m/%d')}"
                period_keys.append(period_label)
                
                df_end_snap = mode_bt_df[mode_bt_df['_SNAPSHOT_DATE'] == d_end] if not mode_bt_df.empty else pd.DataFrame()
                df_start_snap = mode_bt_df[mode_bt_df['_SNAPSHOT_DATE'] == d_start] if not mode_bt_df.empty else pd.DataFrame()
                
                if not df_end_snap.empty and not df_start_snap.empty:
                    matrix_columns[period_label] = calc_period_diff_metrics(df_end_snap, df_start_snap)
                else:
                    matrix_columns[period_label] = {"battles": 0, "win_rate": None, "survived_rate": None, "avg_damage": None, "kd": None, "avg_frags": None, "avg_xp": None}

        row_indicators = [
            ("戦闘", "battles", "{:,}"), ("勝率", "win_rate", "{:.2f}%"),
            ("生還", "survived_rate", "{:.2f}%"), ("与ダメージ", "avg_damage", "{:,.0f}"),
            ("キル/デス比", "kd", "{:.2f}"), ("艦船撃沈", "avg_frags", "{:.2f}"),
            ("取得経験値", "avg_xp", "{:,.0f}")
        ]

        html_table = '<div class="matrix-scroll-wrapper"><table class="matrix-table"><thead><tr><th class="sticky-indicator">各種データ</th><th class="sticky-lifetime">全期間</th>'
        for p_key in period_keys: html_table += f'<th>{p_key}</th>'
        html_table += '</tr></thead><tbody>'
        for label, key, fmt in row_indicators:
            html_table += f'<tr><td class="sticky-indicator">{label}</td>'
            lt_val = matrix_columns["全期間"][key]
            html_table += f'<td class="sticky-lifetime">{fmt.format(lt_val)}</td>' if lt_val is not None and pd.notna(lt_val) else '<td class="sticky-lifetime empty-cell">-</td>'
            for p_key in period_keys:
                p_val = matrix_columns[p_key][key]
                html_table += f'<td>{fmt.format(p_val)}</td>' if p_val is not None and pd.notna(p_val) else '<td class="empty-cell">-</td>'
            html_table += '</tr>'
        html_table += '</tbody></table></div>'
        st.markdown(html_table, unsafe_allow_html=True)

        st.markdown('<div class="chart-section-title">📈 選択モード 日程別推移トレンド</div>', unsafe_allow_html=True)
        trend_records = []
        if not mode_bt_df.empty:
            for d in unique_dates:
                snap_df = mode_bt_df[mode_bt_df['_SNAPSHOT_DATE'] == d]
                if not snap_df.empty:
                    kpi = calc_metrics_from_row(snap_df)
                    if kpi["battles"] is not None and kpi["battles"] > 0:
                        trend_records.append({
                            "日付_obj": d,
                            "勝率": round(kpi["win_rate"], 2) if kpi["win_rate"] is not None else 0,
                            "平均ダメージ": round(kpi["avg_damage"], 0) if kpi["avg_damage"] is not None else 0,
                            "平均経験値": round(kpi["avg_xp"], 0) if kpi["avg_xp"] is not None else 0
                        })
        
        trend_df = pd.DataFrame(trend_records)
        if not trend_df.empty:
            fig = make_subplots(rows=1, cols=3, subplot_titles=("勝率推移", "平均ダメージ推移", "平均経験値推移"))
            
            # マウスオーバー時のみ表示 (mode='lines+markers', hovertemplate)
            fig.add_trace(go.Scatter(
                x=trend_df["日付_obj"], y=trend_df["勝率"], mode='lines+markers', name="勝率",
                hovertemplate="%{x|%Y/%m/%d}<br>勝率: %{y:.2f}%<extra></extra>",
                line=dict(color="#00f2fe")
            ), row=1, col=1)
            
            fig.add_trace(go.Scatter(
                x=trend_df["日付_obj"], y=trend_df["平均ダメージ"], mode='lines+markers', name="平均ダメ",
                hovertemplate="%{x|%Y/%m/%d}<br>平均ダメージ: %{y:,.0f}<extra></extra>",
                line=dict(color="#38bdf8")
            ), row=1, col=2)
            
            fig.add_trace(go.Scatter(
                x=trend_df["日付_obj"], y=trend_df["平均経験値"], mode='lines+markers', name="平均EXP",
                hovertemplate="%{x|%Y/%m/%d}<br>平均経験値: %{y:,.0f}<extra></extra>",
                line=dict(color="#fbbf24")
            ), row=1, col=3)
            
            fig.update_xaxes(type='date', tickformat='%Y/%m/%d', gridcolor="#1e293b")
            fig.update_yaxes(gridcolor="#1e293b")
            fig.update_layout(template="plotly_dark", paper_bgcolor="#070d14", plot_bgcolor="#070d14", showlegend=False, height=400, margin=dict(l=20, r=20, t=50, b=20))
            st.plotly_chart(fig, use_container_width=True)

        st.markdown('<div class="chart-section-title">📊 選択モード 戦闘数分布</div>', unsafe_allow_html=True)
        if not mode_filtered_ship_df.empty:
            l_date = mode_filtered_ship_df['_SNAPSHOT_DATE'].max()
            l_ships_latest = mode_filtered_ship_df[mode_filtered_ship_df['_SNAPSHOT_DATE'] == l_date]
            
            sc1, sc2, sc3 = st.columns(3)
            
            with sc1:
                nat_data = l_ships_latest.groupby("_NATION")["BATTLES_COUNT"].sum().reset_index()
                nat_data["_NATION"] = pd.Categorical(nat_data["_NATION"], categories=NATION_ORDER, ordered=True)
                nat_data = nat_data.dropna(subset=["_NATION"]).sort_values(by="_NATION")
                f_nat_bar = px.bar(nat_data, x="_NATION", y="BATTLES_COUNT", text="BATTLES_COUNT",
                                   title="国家別戦闘数", labels={"BATTLES_COUNT": "戦闘数", "_NATION": "国家"})
                f_nat_bar.update_traces(marker_color="#00f2fe", texttemplate='%{text:,}', textposition='outside')
                f_nat_bar.update_layout(template="plotly_dark", paper_bgcolor="#070d14", plot_bgcolor="#070d14")
                st.plotly_chart(f_nat_bar, use_container_width=True)
                
            with sc2:
                typ_data = l_ships_latest.groupby("_SHIP_TYPE")["BATTLES_COUNT"].sum().reset_index()
                f_typ_bar = px.bar(typ_data, x="_SHIP_TYPE", y="BATTLES_COUNT", text="BATTLES_COUNT",
                                   title="艦種別戦闘数", labels={"BATTLES_COUNT": "戦闘数", "_SHIP_TYPE": "艦種"})
                f_typ_bar.update_traces(marker_color="#38bdf8", texttemplate='%{text:,}', textposition='outside')
                f_typ_bar.update_layout(template="plotly_dark", paper_bgcolor="#070d14", plot_bgcolor="#070d14")
                st.plotly_chart(f_typ_bar, use_container_width=True)
                
            with sc3:
                tier_data = l_ships_latest.groupby("_ESTIMATED_TIER")["BATTLES_COUNT"].sum().reset_index()
                tier_data["_ESTIMATED_TIER"] = pd.Categorical(tier_data["_ESTIMATED_TIER"], categories=TIER_ORDER, ordered=True)
                tier_data = tier_data.dropna(subset=["_ESTIMATED_TIER"]).sort_values(by="_ESTIMATED_TIER")
                f_tier_bar = px.bar(tier_data, x="_ESTIMATED_TIER", y="BATTLES_COUNT", text="BATTLES_COUNT",
                                   title="ティア別戦闘数", labels={"BATTLES_COUNT": "戦闘数", "_ESTIMATED_TIER": "ティア"})
                f_tier_bar.update_traces(marker_color="#fbbf24", texttemplate='%{text:,}', textposition='outside')
                f_tier_bar.update_layout(template="plotly_dark", paper_bgcolor="#070d14", plot_bgcolor="#070d14")
                st.plotly_chart(f_tier_bar, use_container_width=True)

    # ------------------------------------------
    # Tab 2: 国・艦種・ティア別分析（データが無くても全項目表示）
    # ------------------------------------------
    with t_structural:
        l_ships = pd.DataFrame()
        if not mode_filtered_ship_df.empty:
            l_date = mode_filtered_ship_df['_SNAPSHOT_DATE'].max()
            l_ships = mode_filtered_ship_df[mode_filtered_ship_df['_SNAPSHOT_DATE'] == l_date]
            
        headers = ["戦闘数", "勝率", "平均経験値", "平均ダメージ", "キルデス比(K/D)"]
        formats = ["{:,}", "{:.2f}%", "{:,.0f}", "{:,.0f}", "{:.2f}"]
        
        # 国家別マトリクス
        st.markdown('<div class="chart-section-title">🌍 構造分析：国家別マトリクス</div>', unsafe_allow_html=True)
        nation_rows = []
        for n in NATION_ORDER:
            sub_df = l_ships[l_ships['_NATION'] == n] if not l_ships.empty else pd.DataFrame()
            kpi = calc_metrics_from_row(sub_df)
            nation_rows.append((n, [kpi["battles"], kpi["win_rate"], kpi["avg_xp"], kpi["avg_damage"], kpi["kd"]]))
        st.markdown(generate_matrix_html(headers, nation_rows, formats), unsafe_allow_html=True)
            
        # 艦種別マトリクス
        st.markdown('<div class="chart-section-title">🚢 構造分析：艦種別マトリクス</div>', unsafe_allow_html=True)
        type_rows = []
        for t in ["駆逐艦", "巡洋艦", "戦艦", "空母", "その他"]:
            sub_df = l_ships[l_ships['_SHIP_TYPE'] == t] if not l_ships.empty else pd.DataFrame()
            kpi = calc_metrics_from_row(sub_df)
            type_rows.append((t, [kpi["battles"], kpi["win_rate"], kpi["avg_xp"], kpi["avg_damage"], kpi["kd"]]))
        st.markdown(generate_matrix_html(headers, type_rows, formats), unsafe_allow_html=True)
            
        # ティア別マトリクス
        st.markdown('<div class="chart-section-title">🎖️ 構造分析：ティア別マトリクス</div>', unsafe_allow_html=True)
        tier_rows = []
        for tier in TIER_ORDER:
            sub_df = l_ships[l_ships['_ESTIMATED_TIER'] == tier] if not l_ships.empty else pd.DataFrame()
            kpi = calc_metrics_from_row(sub_df)
            tier_rows.append((f"Tier {tier}" if tier != "★" else "★", [kpi["battles"], kpi["win_rate"], kpi["avg_xp"], kpi["avg_damage"], kpi["kd"]]))
        st.markdown(generate_matrix_html(headers, tier_rows, formats), unsafe_allow_html=True)

    # ------------------------------------------
    # Tab 3: 艦艇別詳細 (複数選択・ボタン上下でティア選択)
    # ------------------------------------------
    with t_ship:
        if not mode_filtered_ship_df.empty:
            l_ships = mode_filtered_ship_df[mode_filtered_ship_df['_SNAPSHOT_DATE'] == mode_filtered_ship_df['_SNAPSHOT_DATE'].max()].copy()
            
            c_f1, c_f2 = st.columns([3, 1])
            
            with c_f1:
                sel_types = st.pills("艦種", ["すべて", "駆逐艦", "巡洋艦", "戦艦", "空母"], selection_mode="multi", key="pills_types", label_visibility="collapsed")
                sel_nations = st.pills("国家", ["すべて"] + NATION_ORDER, selection_mode="multi", key="pills_nations", label_visibility="collapsed")
            
            with c_f2:
                st.caption("表示Tier範囲 ")
                ct1, ct2, ct3 = st.columns([4,1,4])
                with ct1:
                    min_t = st.number_input("",min_value=1, max_value=9, value=1, step=1, help="1: Tier I 〜 9: ★")
                with ct2:
                    st.markdown("<div style='text-align: center; padding-top: 35px; font-weight: bold;'>～</div>", unsafe_allow_html=True)
                with ct3:
                    max_t = st.number_input("",min_value=1, max_value=9, value=9, step=1, help="1: Tier I 〜 9: ★")
            
            has_selection = bool(sel_types) or bool(sel_nations)

            if has_selection:
                # マスク処理
                mask = pd.Series(True, index=l_ships.index)
                
                # 【修正】選択肢が存在し、かつ「すべて」が含まれていない場合のみ絞り込む
                if sel_types and "すべて" not in sel_types:
                    mask = mask & (l_ships['_SHIP_TYPE'].isin(sel_types))
                    
                # 【修正】選択肢が存在し、かつ「すべて」が含まれていない場合のみ絞り込む
                if sel_nations and "すべて" not in sel_nations:
                    mask = mask & (l_ships['_NATION'].isin(sel_nations))
                        
                # ティア範囲フィルタ
                min_val = min(min_t, max_t)
                max_val = max(min_t, max_t)
                allowed_tiers = [VAL_TIER_MAP[v] for v in range(min_val, max_val + 1) if v in VAL_TIER_MAP]
                mask = mask & (l_ships['_ESTIMATED_TIER'].isin(allowed_tiers))
                    
                query_df = l_ships[mask].sort_values(by="BATTLES_COUNT", ascending=False)
                
                if not query_df.empty:
                    df_show = query_df[['_NATION', '_SHIP_TYPE', '_ESTIMATED_TIER', '_CLEAN_NAME', 
                                        'BATTLES_COUNT', 'WINS', 'SURVIVED', 'DAMAGE_DEALT', 'FRAGS', 'ORIGINAL_EXP']].copy()
                    
                    df_show['勝率(%)'] = (df_show['WINS'] / df_show['BATTLES_COUNT'] * 100).round(2)
                    df_show['平均経験値'] = (df_show['ORIGINAL_EXP'] / df_show['BATTLES_COUNT']).round(0)
                    df_show['平均ダメージ'] = (df_show['DAMAGE_DEALT'] / df_show['BATTLES_COUNT']).round(0)
                    df_show['キルデス比'] = (df_show['FRAGS'] / (df_show['BATTLES_COUNT'] - df_show['SURVIVED']).replace(0, 1)).round(2)
                    
                    df_show = df_show[['_NATION', '_SHIP_TYPE', '_ESTIMATED_TIER', '_CLEAN_NAME', 'BATTLES_COUNT', '勝率(%)', '平均経験値', '平均ダメージ', 'キルデス比']]
                    df_show.columns = ['国家', '艦種', 'ティア', '艦艇名', '戦闘数', '勝率(%)', '平均経験値', '平均ダメージ', 'キルデス比']
                    
                    st.dataframe(
                        df_show.style.format({
                            '勝率(%)': '{:.2f}%',
                            '平均経験値': '{:,.0f}',
                            '平均ダメージ': '{:,.0f}',
                            'キルデス比': '{:.2f}'
                        }),
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("条件に一致する艦艇データがありません。")
            else:
                # 初期状態（何も選択されていない場合）のメッセージ
                st.info("艦種または国家を選択するとデータが表示されます。")
        else:
            st.info("データがありません。")

    # ------------------------------------------
    # Tab 4: 自己ベスト（文字を通常表示・分類を削除）
    # ------------------------------------------
    with t_best:
        if not mode_filtered_ship_df.empty:
            st.markdown(f'<div class="chart-section-title">🏆 選択モード({current_mode}/{st.session_state.sel_team})の最高記録</div>', unsafe_allow_html=True)
            
            plane_col = None
            for col in ['MAX_PLANES_KILLED', 'MAX_AIRCRAFTS_KILLED', 'MAX_PLANES_KILLED_BY_AA']:
                if col in mode_filtered_ship_df.columns:
                    plane_col = col
                    break
                    
            best_targets = [
                ("最高与ダメージ", "MAX_DAMAGE_DEALT"),
                ("最高取得経験値", "MAX_ORIGINAL_EXP"),
                ("最高撃沈数", "MAX_FRAGS")
            ]
            if plane_col:
                best_targets.append(("最高撃墜数", plane_col))
            
            best_headers = ["記録数値", "達成艦艇"]
            best_formats = ["{}", "{}"]
            best_rows = []
            
            for label, col_name in best_targets:
                if col_name in mode_filtered_ship_df.columns:
                    valid_df = mode_filtered_ship_df[pd.to_numeric(mode_filtered_ship_df[col_name], errors='coerce').notna()]
                    if not valid_df.empty:
                        idx_max = valid_df[col_name].idxmax()
                        best_row = valid_df.loc[idx_max]
                        
                        val_num = int(best_row[col_name])
                        val_str = f"{val_num:,}"
                        
                        ship_name = str(best_row.get('_CLEAN_NAME', best_row.get('VEHICLE_NAME', '不明')))
                        best_rows.append((label, [val_str, ship_name]))
                        
            if best_rows:
                st.markdown(generate_matrix_html(best_headers, best_rows, best_formats), unsafe_allow_html=True)
            else:
                st.warning("選択したモードの記録が見つかりません。")
        else:
            st.info("データがありません。")

    # ------------------------------------------
    # Tab 5: その他 (クラン履歴・累計プレイ時間)
    # ------------------------------------------
    with t_other:
        c1, c2 = st.columns(2)
        
        # 🛡️ クラン履歴表示
        with c1:
            st.markdown('<div class="chart-section-title">🛡️ クラン入退隊履歴</div>', unsafe_allow_html=True)
            clan_df = data["clans"]
            if not clan_df.empty:
                try:
                    df_c = clan_df.copy()
                    
                    if 'CREATED_AT' in df_c.columns:
                        col_created = 'CREATED_AT'
                        col_clan = 'CLAN_NAME' if 'CLAN_NAME' in df_c.columns else df_c.columns[0]
                        col_op = 'OPERATION_NAME' if 'OPERATION_NAME' in df_c.columns else df_c.columns[2]
                    else:
                        col_clan = df_c.columns[0]
                        col_created = df_c.columns[1]
                        col_op = df_c.columns[2]
                        
                    df_c['DT'] = pd.to_datetime(df_c[col_created], errors='coerce')
                    df_c = df_c.dropna(subset=['DT'])
                    
                    df_c = df_c[df_c[col_op].astype(str).str.strip().isin(['join_clan', 'leave_clan'])]
                    
                    op_symbol_map = {
                        "join_clan": "＞",
                        "leave_clan": "＜"
                    }
                    
                    df_c['区分'] = df_c[col_op].astype(str).str.strip().map(op_symbol_map)
                    df_c['クラン名'] = df_c[col_clan].fillna("-").astype(str)
                    df_c['年月日'] = df_c['DT'].dt.strftime("%Y-%m-%d")
                    
                    # 【変更】順番を「区分 → 年月日 → クラン名」に変更して重複削除
                    result_df = df_c[['区分', '年月日', 'クラン名']].drop_duplicates()
                    result_df = result_df.sort_values(by='年月日', ascending=False)
                    
                    # 【変更】ヘッダー文字（区分、年月日、クラン名）を削除（空文字化）
                    result_df.columns = [' ', '  ', '   ']
                    
                    if not result_df.empty:
                        st.dataframe(result_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("有効な入退隊履歴データがありません。")
                except Exception as e:
                    st.error(f"クランデータの解析中にエラーが発生しました: {e}")
            else:
                st.info("クランデータ（Clans.csv）がありません。")

        # ⏱️ 累計プレイ時間の計算
        with c2:
            st.markdown('<div class="chart-section-title">⏱️ 累計プレイ時間</div>', unsafe_allow_html=True)
            sess_df = data["game_sessions"]
            if not sess_df.empty:
                try:
                    col_start = sess_df.columns[0]
                    col_end = sess_df.columns[1]
                    
                    start_dt = pd.to_datetime(sess_df[col_start],format="%Y-%m-%d %H:%M:%S.%f", errors='coerce')
                    end_dt = pd.to_datetime(sess_df[col_end],format="%Y-%m-%d %H:%M:%S.%f", errors='coerce')
                                        
                    # データが格納されているすべての行について差分（秒）を計算して合計
                    durations = (end_dt - start_dt)
                    
                    total_seconds = durations.dt.total_seconds().sum()
                    if total_seconds > 0:
                        hours = int(total_seconds // 3600)
                        minutes = int((total_seconds % 3600) // 60)
                        st.metric("累計プレイ時間", f"{hours:,} 時間 {minutes} 分")
                    else:
                        st.info("有効なセッション時間データがありません。")
                except Exception as e:
                    st.error(f"プレイ時間の計算中にエラーが発生しました: {e}")
            else:
                st.info("セッションデータ（WOWSL_Game_Sessions.csv）がありません。")

if __name__ == '__main__':
    main()
