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
    page_title="WOWSL Legends Dashboard",
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

    /* 📊 総合戦績・全テーブル共通：横スクロール・列固定マトリクス */
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
        box-sizing: border-box;
        color: #d1d5db;
    }
    .matrix-table th {
        background-color: #0f172a;
        color: #ffffff;
        font-weight: 700;
    }
    /* 左端列の固定スタイル */
    .matrix-table th.sticky-indicator, .matrix-table td.sticky-indicator {
        position: sticky;
        left: 0;
        background-color: #0f172a !important;
        z-index: 10;
        text-align: left;
        min-width: 180px;
        max-width: 180px;
        border-right: 2px solid #00f2fe;
        font-weight: 700;
        color: #ffffff;
    }
    /* Tab1用の全期間列固定スタイル */
    .matrix-table th.sticky-lifetime, .matrix-table td.sticky-lifetime {
        position: sticky;
        left: 180px;
        background-color: #111c2e !important;
        z-index: 9;
        font-weight: 700;
        border-right: 2px solid #1e293b;
    }
    
    /* 🚢 艦艇名デザイン */
    .game-ship-name {
        font-family: 'Courier New', monospace;
        font-weight: 700;
        color: #00f2fe;
        background-color: #0f172a;
        padding: 4px 10px;
        border: 1px solid #1e293b;
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
    1: {"mode": "通常", "team": "総合"},
    2: {"mode": "AI", "team": "総合"},
    3: {"mode": "通常", "team": "ソロ"},
    4: {"mode": "通常", "team": "2人分隊"},
    5: {"mode": "通常", "team": "3人分隊"}, 
    6: {"mode": "AI", "team": "ソロ"},
    7: {"mode": "AI", "team": "2人分隊"},
    8: {"mode": "AI", "team": "3人分隊"},
    9: {"mode": "ランク", "team": "ソロ"},
    10: {"mode": "ランク", "team": "2人分隊"},
    11: {"mode": "ランク", "team": "3人分隊"},
    17: {"mode": "アリーナ", "team": "ソロ"},
    18: {"mode": "アリーナ", "team": "2人分隊"},
    19: {"mode": "アリーナ", "team": "3人分隊"},
    20: {"mode": "闘争", "team": "ソロ"},
    21: {"mode": "闘争", "team": "2人分隊"},
    22: {"mode": "闘争", "team": "3人分隊"},
    23: {"mode": "アーケード", "team": "総合"},
    24: {"mode": "アーケード", "team": "ソロ"},
    25: {"mode": "アーケード", "team": "2人分隊"},
    26: {"mode": "アーケード", "team": "3人分隊"},
    27: {"mode": "クラン戦", "team": "総合"},
    28: {"mode": "軍記", "team": "総合"}
}

NATION_ORDER = [
    "アメリカ", "日本", "イギリス", "ドイツ", "フランス", "ソ連", 
    "イタリア", "ヨーロッパ", "パンアジア", "パンヨーロッパ", "パンアメリカ", "オランダ", "スペイン"
]

TIER_ORDER = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "Legend"]

# ==========================================
# 3. データ処理エンジン（関数群）
# ==========================================
def load_ship_reference() -> Dict[str, Tuple[str, str]]:
    if os.path.exists("ship_id.csv"):
        try:
            df = pd.read_csv("ship_id.csv")
            return dict(zip(df['id'].astype(str), zip(df['name'], df['Tier'])))
        except Exception as e:
            st.sidebar.warning(f"ship_id.csvの読み込みに失敗しました: {e}")
    return {}
    
def parse_ship_id(vehicle_name: str, ship_map: Dict[str, Tuple[str, str]]) -> Tuple[str, str, str, str]:
    clean_vname = str(vehicle_name).strip()
    if clean_vname in ship_map:
        display_name, tier = ship_map[clean_vname]
    else:
        display_name = clean_vname
        tier = "その他"

    low_name = clean_vname.lower()
    nation, ship_class = "その他", "その他"
    
    if low_name.startswith('p') and len(low_name) >= 4:
        n_code = low_name[1]
        c_code = low_name[3] if low_name[2] == 's' else low_name[2]
        nation = IMAGE_NATION_MAP.get(n_code, "sound") if n_code in IMAGE_NATION_MAP else "その他"
        nation = IMAGE_NATION_MAP.get(n_code, "その他")
        ship_class = IMAGE_CLASS_MAP.get(c_code, "その他")
    
    return nation, ship_class, str(tier), display_name

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
                        df = pd.read_csv(io.StringIO(content))
                        if not df.empty:
                            df.columns = [c.strip().upper() for c in df.columns]
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
        df_concat['_SNAPSHOT_DATE'] = pd.to_datetime(df_concat['_SNAPSHOT_DATE'])
        
        if key == 'clans':
            merged[key] = df_concat.drop_duplicates().reset_index(drop=True)
        else:
            id_cols = ['_SNAPSHOT_DATE']
            if key == 'battle_types': 
                id_cols.append('TYPE')
            elif key == 'ship_stats': 
                id_cols.extend(['VEHICLE_NAME', 'TYPE'])
            merged[key] = df_concat.drop_duplicates(subset=id_cols, keep='last').reset_index(drop=True)
            
    return merged

def calc_metrics_from_row(df: pd.DataFrame) -> Dict[str, Any]:
    if df.empty or 'BATTLES_COUNT' not in df.columns or df['BATTLES_COUNT'].sum() <= 0:
        return {"battles": None, "win_rate": None, "survived_rate": None, "avg_damage": None, "kd": None, "avg_frags": None, "avg_xp": None}
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
        return {"battles": None, "win_rate": None, "survived_rate": None, "avg_damage": None, "kd": None, "avg_frags": None, "avg_xp": None}
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

# 固定列＋横スクロールHTMLテーブルを生成するヘルパー関数
def generate_matrix_html(headers: List[str], rows_data: List[Tuple[str, List[Any]]], formats: List[str]) -> str:
    html = '<div class="matrix-scroll-wrapper"><table class="matrix-table"><thead><tr><th class="sticky-indicator">分類・項目</th>'
    for h in headers:
        html += f'<th>{h}</th>'
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
        if 'NICKNAME' in l_info.index and pd.notna(l_info['NICKNAME']): 
            p_name = str(l_info['NICKNAME'])
        
    if p_name == "プレイヤーデータ" and not data["account_stats"].empty:
        l_stats = data["account_stats"].iloc[-1]
        for name_col in ['NICKNAME', 'PLAYER_NAME', 'NAME', 'ACCOUNT_NAME']:
            if name_col in l_stats.index and pd.notna(l_stats[name_col]):
                p_name = str(l_stats[name_col])
                break
                
    if not data["clans"].empty and 'CREATED_AT' in data["clans"].columns:
        clan_df = data["clans"].copy()
        clan_df['CREATED_AT'] = pd.to_datetime(clan_df['CREATED_AT'], errors='coerce')
        latest_clan_df = clan_df.sort_values(by='CREATED_AT').dropna(subset=['CREATED_AT']).iloc[-1:]
        if not latest_clan_df.empty:
            l_clan = latest_clan_df.iloc[0]
            for col in ['CLAN_NAME', 'CLAN_TAG', 'TAG']:
                if col in l_clan.index and pd.notna(l_clan[col]):
                    val_str = str(l_clan[col]).strip()
                    if "[" in val_str and "]" in val_str:
                        match = re.search(r'\[(.*?)\]', val_str)
                        if match: val_str = match.group(1)
                    if 2 <= len(val_str) <= 20 and val_str.isalnum():
                        clan_tag = val_str
                        break

    player_display_string = f"【{clan_tag}】{p_name}" if clan_tag else p_name
    st.markdown(f'<div class="game-header-container"><div class="game-title">WOWSL Legends Dashboard</div><div class="player-clan-info">{player_display_string}</div></div>', unsafe_allow_html=True)

    t_summary, t_structural, t_ship, t_best, t_clan = st.tabs([
        "総合戦績 (マトリクス)", "国・艦種・ティア別分析", "艦艇別詳細", "自己ベスト", "クランデータ"
    ])

    # ------------------------------------------
    # Tab 1: 総合戦績
    # ------------------------------------------
    with t_summary:
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
            with t_cols[idx]:
                if st.button(t_name, key=f"btn_t_{t_name}", use_container_width=True, type="primary" if st.session_state.sel_team == t_name else "secondary"):
                    st.session_state.sel_team = t_name
                    st.rerun()

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
                    mode_filtered_ship_df = raw_ship_df.groupby(group_keys)[sum_cols].sum().reset_index()
                    mode_filtered_ship_df['TYPE'] = 0
                else:
                    mode_filtered_ship_df = pd.DataFrame()
        else:
            target_type_code = next((tid for tid, meta in BATTLE_TYPE_MAP.items() if meta["mode"] == current_mode and meta["team"] == st.session_state.sel_team), None)
            mode_bt_df = bt_df[bt_df['TYPE'] == target_type_code] if not bt_df.empty and target_type_code else pd.DataFrame()
            mode_filtered_ship_df = ship_df[ship_df['TYPE'] == target_type_code] if not ship_df.empty and target_type_code else pd.DataFrame()
        
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
                    matrix_columns[period_label] = {"battles": None, "win_rate": None, "survived_rate": None, "avg_damage": None, "kd": None, "avg_frags": None, "avg_xp": None}

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
            html_table += f'<td class="sticky-lifetime">{fmt.format(lt_val)}</td>' if lt_val is not None else '<td class="sticky-lifetime empty-cell">-</td>'
            for p_key in period_keys:
                p_val = matrix_columns[p_key][key]
                html_table += f'<td>{fmt.format(p_val)}</td>' if p_val is not None and pd.notna(p_val) else '<td class="empty-cell">-</td>'
            html_table += '</tr>'
        html_table += '</tbody></table></div>'
        st.markdown(html_table, unsafe_allow_html=True)

        # トレンド・分布図
        st.markdown('<div class="chart-section-title">📈 通常戦（総合データ）日程別推移トレンド</div>', unsafe_allow_html=True)
        normal_total_bt = bt_df[bt_df['TYPE'] == 1] if not bt_df.empty else pd.DataFrame()
        trend_records = []
        if not normal_total_bt.empty:
            for d in unique_dates:
                snap_df = normal_total_bt[normal_total_bt['_SNAPSHOT_DATE'] == d]
                if not snap_df.empty:
                    kpi = calc_metrics_from_row(snap_df)
                    if kpi["battles"] is not None:
                        trend_records.append({"日付_obj": d, "勝率": round(kpi["win_rate"], 2), "平均ダメージ": round(kpi["avg_damage"], 0), "平均経験値": round(kpi["avg_xp"], 0)})
        
        trend_df = pd.DataFrame(trend_records)
        if not trend_df.empty:
            fig = make_subplots(rows=1, cols=3, subplot_titles=("通常戦 勝率推移", "通常戦 平均ダメージ推移", "通常戦 平均経験値推移"))
            fig.add_trace(go.Scatter(x=trend_df["日付_obj"], y=trend_df["勝率"], mode='lines+markers+text', name="勝率", text=[f"{v}%" for v in trend_df["勝率"]], line=dict(color="#00f2fe")), row=1, col=1)
            fig.add_trace(go.Scatter(x=trend_df["日付_obj"], y=trend_df["平均ダメージ"], mode='lines+markers+text', name="平均ダメ", text=[f"{int(v):,}" for v in trend_df["平均ダメージ"]], line=dict(color="#38bdf8")), row=1, col=2)
            fig.add_trace(go.Scatter(x=trend_df["日付_obj"], y=trend_df["平均経験値"], mode='lines+markers+text', name="平均EXP", text=[f"{int(v):,}" for v in trend_df["平均経験値"]], line=dict(color="#fbbf24")), row=1, col=3)
            fig.update_xaxes(type='date', tickformat='%Y/%m/%d', gridcolor="#1e293b")
            fig.update_yaxes(gridcolor="#1e293b")
            fig.update_layout(template="plotly_dark", paper_bgcolor="#070d14", plot_bgcolor="#070d14", showlegend=False, height=400, margin=dict(l=20, r=20, t=50, b=20))
            st.plotly_chart(fig, use_container_width=True)

    # ------------------------------------------
    # Tab 2: 国・艦種・ティア別分析 (統合・拡張版)
    # ------------------------------------------
    with t_structural:
        if not mode_filtered_ship_df.empty:
            l_date = mode_filtered_ship_df['_SNAPSHOT_DATE'].max()
            l_ships = mode_filtered_ship_df[mode_filtered_ship_df['_SNAPSHOT_DATE'] == l_date]
            
            headers = ["戦闘数", "勝率", "平均経験値", "平均ダメージ", "キルデス比(K/D)"]
            formats = ["{:,}", "{:.2f}%", "{:,.0f}", "{:,.0f}", "{:.2f}"]
            
            # --- 1. 国家別分析 ---
            st.markdown('<div class="chart-section-title">🌍 構造分析：国家別マトリクス</div>', unsafe_allow_html=True)
            nation_rows = []
            for n in NATION_ORDER:
                sub_df = l_ships[l_ships['_NATION'] == n]
                if not sub_df.empty:
                    kpi = calc_metrics_from_row(sub_df)
                    if kpi["battles"] is not None:
                        nation_rows.append((n, [kpi["battles"], kpi["win_rate"], kpi["avg_xp"], kpi["avg_damage"], kpi["kd"]]))
            if nation_rows:
                st.markdown(generate_matrix_html(headers, nation_rows, formats), unsafe_allow_html=True)
            else:
                st.info("国家別集計に該当するデータがありません。")
                
            # --- 2. 艦種別分析 ---
            st.markdown('<div class="chart-section-title">🚢 構造分析：艦種別マトリクス</div>', unsafe_allow_html=True)
            type_rows = []
            for t in ["駆逐艦", "巡洋艦", "戦艦", "空母", "その他"]:
                sub_df = l_ships[l_ships['_SHIP_TYPE'] == t]
                if not sub_df.empty:
                    kpi = calc_metrics_from_row(sub_df)
                    if kpi["battles"] is not None:
                        type_rows.append((t, [kpi["battles"], kpi["win_rate"], kpi["avg_xp"], kpi["avg_damage"], kpi["kd"]]))
            if type_rows:
                st.markdown(generate_matrix_html(headers, type_rows, formats), unsafe_allow_html=True)
                
            # --- 3. ティア別分析 ---
            st.markdown('<div class="chart-section-title">🎖️ 構造分析：ティア別マトリクス</div>', unsafe_allow_html=True)
            tier_rows = []
            for tier in TIER_ORDER:
                sub_df = l_ships[l_ships['_ESTIMATED_TIER'] == tier]
                if not sub_df.empty:
                    kpi = calc_metrics_from_row(sub_df)
                    if kpi["battles"] is not None:
                        tier_rows.append((f"Tier {tier}" if tier != "Legend" else "Legend", [kpi["battles"], kpi["win_rate"], kpi["avg_xp"], kpi["avg_damage"], kpi["kd"]]))
            if tier_rows:
                st.markdown(generate_matrix_html(headers, tier_rows, formats), unsafe_allow_html=True)
            else:
                st.info("ティア別集計に該当するデータがありません。")
        else:
            st.info("選択されたモード・部隊形式の艦艇データがありません。")

    # ------------------------------------------
    # Tab 3: 艦艇別詳細 (マトリクス統一化)
    # ------------------------------------------
    with t_ship:
        if not mode_filtered_ship_df.empty:
            l_ships = mode_filtered_ship_df[mode_filtered_ship_df['_SNAPSHOT_DATE'] == mode_filtered_ship_df['_SNAPSHOT_DATE'].max()].copy()
            c_f1, c_f2 = st.columns(2)
            
            available_nations = [n for n in NATION_ORDER if n in l_ships['_NATION'].unique()]
            s_nat = c_f1.selectbox("国家で絞り込む", ["すべて"] + available_nations)
            s_typ = c_f2.selectbox("艦種で絞り込む", ["すべて"] + list(l_ships['_SHIP_TYPE'].unique()))
            
            mask = pd.Series(True, index=l_ships.index)
            if s_nat != "すべて": mask = mask & (l_ships['_NATION'] == s_nat)
            if s_typ != "すべて": mask = mask & (l_ships['_SHIP_TYPE'] == s_typ)
            query_df = l_ships[mask].sort_values(by="BATTLES_COUNT", ascending=False)
            
            ship_headers = ["国家", "艦種", "ティア", "戦闘数", "勝率", "平均経験値", "平均ダメージ", "キルデス比"]
            ship_formats = ["{}", "{}", "{}", "{:,}", "{:.2f}%", "{:,.0f}", "{:,.0f}", "{:.2f}"]
            
            ship_rows = []
            for _, r in query_df.iterrows():
                if r['BATTLES_COUNT'] > 0:
                    kpi = calc_metrics_from_row(pd.DataFrame([r]))
                    ship_html_name = f'<span class="game-ship-name">{r["_CLEAN_NAME"]}</span>'
                    ship_rows.append((ship_html_name, [r['_NATION'], r['_SHIP_TYPE'], r['_ESTIMATED_TIER'], kpi["battles"], kpi["win_rate"], kpi["avg_xp"], kpi["avg_damage"], kpi["kd"]]))
            
            if ship_rows:
                st.markdown(generate_matrix_html(ship_headers, ship_rows, ship_formats), unsafe_allow_html=True)
            else:
                st.info("該当する艦艇データがありません。")
        else:
            st.info("データがありません。")

    # ------------------------------------------
    # Tab 4: 自己ベスト (ship_statsから動的抽出)
    # ------------------------------------------
    with t_best:
        if not ship_df.empty:
            st.markdown('<div class="chart-section-title">🏆 艦艇詳細ログ（WOWSL_Ship_Statistics_By_Type）からスキャンした最高記録</div>', unsafe_allow_html=True)
            
            best_targets = [
                ("最高与ダメージ", "MAX_DAMAGE_DEALT"),
                ("最高取得経験値", "MAX_ORIGINAL_EXP"),
                ("最高撃沈数", "MAX_FRAGS"),
                ("主砲最大命中数", "MAX_MAIN_HIT")
            ]
            
            best_headers = ["記録数値", "達成艦艇", "戦闘モードコード"]
            best_formats = ["{}", "{}", "{}"]
            best_rows = []
            
            for label, col_name in best_targets:
                if col_name in ship_df.columns:
                    valid_df = ship_df[pd.to_numeric(ship_df[col_name], errors='coerce').notna()]
                    if not valid_df.empty:
                        idx_max = valid_df[col_name].idxmax()
                        best_row = valid_df.loc[idx_max]
                        
                        val_num = int(best_row[col_name])
                        val_str = f"{val_num:,}"
                        
                        ship_name = best_row.get('_CLEAN_NAME', best_row['VEHICLE_NAME'])
                        mode_code = best_row['TYPE']
                        
                        # モードコードを分かりやすい名前に変換
                        mode_meta = BATTLE_TYPE_MAP.get(int(mode_code), {"mode": f"コード:{mode_code}", "team": ""})
                        mode_display = f"{mode_meta['mode']} ({mode_meta['team']})" if mode_meta['team'] else mode_meta['mode']
                        
                        best_rows.append((label, [val_str, f'<span class="game-ship-name">{ship_name}</span>', mode_display]))
                        
            if best_rows:
                st.markdown(generate_matrix_html(best_headers, best_rows, best_formats), unsafe_allow_html=True)
            else:
                st.warning("艦艇詳細データに必要な最高記録カラム（MAX_DAMAGE_DEALT等）が含まれていません。")
        else:
            st.info("艦艇詳細データ（ship_stats）がありません。")

    # ------------------------------------------
    # Tab 5: クランデータ (マトリクス統一化)
    # ------------------------------------------
    with t_clan:
        clan_df = data["clans"]
        if not clan_df.empty:
            latest_clan = clan_df[clan_df['_SNAPSHOT_DATE'] == clan_df['_SNAPSHOT_DATE'].max()]
            if not latest_clan.empty:
                r_data = latest_clan.iloc[0]
                clan_rows = [(str(col), [str(r_data[col])]) for col in latest_clan.columns if col != '_SNAPSHOT_DATE']
                st.markdown(generate_matrix_html(["設定値"], clan_rows, ["{}"]), unsafe_allow_html=True)
        else:
            st.info("クランデータ（Clans.csv）がありません。")

if __name__ == '__main__':
    main()
