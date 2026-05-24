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

# ==========================================
# 1. ページ初期設定 & カスタムゲームUI風CSS
# ==========================================
st.set_page_config(
    page_title="WoWs Legends Fleet Intelligence",
    page_icon="⚓",
    layout="wide",
    initial_sidebar_state="expanded"
)

CSS_STYLE = """
<style>
    /* 全体背景と基本フォント */
    .stApp {
        background-color: #0b131e;
        color: #d1d5db;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    section[data-testid="stSidebar"] {
        background-color: #070d14 !important;
        border-right: 1px solid #1e293b;
    }
    
    /* ⚓ 1. タイトル & クラン情報 UI */
    .game-header-container {
        background: linear-gradient(90deg, #111c2e 0%, #070d14 100%);
        border-left: 5px solid #00f2fe;
        padding: 18px 24px;
        border-radius: 4px;
        margin-bottom: 25px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    .game-title {
        font-size: 2.0rem;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: 1px;
        margin: 0 0 8px 0;
        text-transform: uppercase;
        text-shadow: 0 0 10px rgba(0, 242, 254, 0.6);
    }
    .player-clan-info {
        font-size: 1.1rem;
        color: #e2e8f0;
        font-weight: 600;
    }
    .clan-tag-highlight {
        color: #00f2fe;
        font-weight: 700;
        margin-right: 4px;
    }
    .player-id-sub {
        font-size: 0.85rem;
        color: #64748b;
        margin-top: 4px;
        font-family: monospace;
    }

    /* 📊 5. 総合戦績表（横スクロール・列固定・固定セルサイズ） */
    .matrix-scroll-wrapper {
        position: relative;
        width: 100%;
        overflow-x: auto;
        margin: 15px 0 30px 0;
        border: 1px solid #1e293b;
        border-radius: 4px;
        background-color: #0f172a;
    }
    .matrix-table {
        border-collapse: separate;
        border-spacing: 0;
        width: 100%;
        font-size: 0.9rem;
        text-align: center;
    }
    .matrix-table th, .matrix-table td {
        padding: 12px;
        border-bottom: 1px solid #1e293b;
        border-right: 1px solid #1e293b;
        /* セルサイズの一致・固定化仕様 */
        min-width: 140px;
        max-width: 140px;
        width: 140px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        box-sizing: border-box;
    }
    
    /* 「各種データ」列の固定表示 (最左) */
    .matrix-table th.sticky-indicator, .matrix-table td.sticky-indicator {
        position: sticky;
        left: 0;
        background-color: #131c2e !important;
        z-index: 10;
        text-align: left;
        min-width: 160px;
        max-width: 160px;
        width: 160px;
        font-weight: 600;
        color: #94a3b8;
        border-right: 2px solid #00f2fe;
    }
    /* 「全期間」列の固定表示 (左から2番目) */
    .matrix-table th.sticky-lifetime, .matrix-table td.sticky-lifetime {
        position: sticky;
        left: 160px;
        background-color: #162238 !important;
        z-index: 9;
        font-weight: 700;
        color: #ffffff;
        border-right: 2px solid #1e293b;
    }
    
    .matrix-table th {
        background-color: #1e293b;
        color: #94a3b8;
        font-size: 0.85rem;
        font-weight: 600;
        letter-spacing: 0.5px;
        border-top: none;
    }
    .matrix-table tr:hover td {
        background-color: #1e293b;
    }
    .matrix-table tr:hover td.sticky-indicator {
        background-color: #1a273d !important;
    }
    .matrix-table tr:hover td.sticky-lifetime {
        background-color: #1f2f4d !important;
    }
    
    /* 空欄・データなしマスの表現 */
    .empty-cell {
        color: #475569;
        font-style: italic;
    }
    
    /* 🚢 艦艇名デザイン */
    .game-ship-name {
        font-family: 'Courier New', Courier, monospace;
        font-weight: 700;
        color: #e2e8f0;
        background-color: #1e293b;
        padding: 2px 6px;
        border-radius: 3px;
        border: 1px solid #334155;
        letter-spacing: 0.5px;
    }
    
    .mode-selection-header {
        font-size: 0.85rem;
        color: #00f2fe;
        margin: 12px 0 6px 0;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
</style>
"""
st.markdown(CSS_STYLE, unsafe_allow_html=True)

# ==========================================
# 2. 定数定義 & 24通り戦闘タイプマッピング
# ==========================================
CSV_MAPPING = {
    "WOWSL_Account_Statistics.csv": "account_stats",
    "WOWSL_Battle_Types_Statistics.csv": "battle_types",
    "WOWSL_Ship_Statistics.csv": "ship_base",
    "WOWSL_Ship_Statistics_By_Type.csv": "ship_stats",
    "WOWSL_Game_Sessions.csv": "sessions",
    "Clans.csv": "clans",
    "Account_Info.csv": "account_info"
}

NATION_PREFIX_MAP = {
    "ja": "日本", "us": "アメリカ", "ge": "ドイツ", "uk": "イギリス",
    "ru": "ソ連", "fr": "フランス", "it": "イタリア", "pa": "パンアジア",
    "cw": "コモンウェルス", "am": "パンアメリカ", "eu": "ヨーロッパ", "ch": "パンアジア"
}

SHIP_TYPE_LETTER_MAP = {
    "b": "戦艦", "c": "巡洋艦", "d": "駆逐艦", "a": "空母"
}

# 💡 3. 新しい拡張戦闘タイプ（全24カテゴリーの完全データマスター）
BATTLE_TYPE_MAP = {
    1:  {"mode": "通常", "team": "総合"},
    2:  {"mode": "AI", "team": "総合"},
    3:  {"mode": "通常", "team": "ソロ"},
    4:  {"mode": "通常", "team": "2人分隊"},
    5:  {"mode": "通常", "team": "3人分隊"},
    6:  {"mode": "AI", "team": "ソロ"},
    7:  {"mode": "AI", "team": "2人分隊"},
    8:  {"mode": "AI", "team": "3人分隊"},
    9:  {"mode": "ランク", "team": "ソロ"},
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

# ==========================================
# 3. 解析エンジン (艦艇名デコード含む)
# ==========================================
def parse_ship_id(vehicle_name: str) -> Tuple[str, str, int, str]:
    """
    🚢 6. 画像の規則を参考にしたゲーム内UI風名称処理
    """
    if not isinstance(vehicle_name, str) or len(vehicle_name) < 4:
        return "その他", "その他", 0, str(vehicle_name)
        
    prefix = vehicle_name[1:4].lower() 
    nation_code = prefix[0:2]
    nation = NATION_PREFIX_MAP.get(nation_code, "その他")
    
    type_code = prefix[2]
    ship_type = SHIP_TYPE_LETTER_MAP.get(type_code, "その他")
    
    tier_match = re.search(r'\d+', vehicle_name)
    if tier_match:
        val = int(tier_match.group())
        if val >= 100:
            tier = (val // 100)
            if tier > 10: tier = 5
        else:
            tier = val if val <= 10 else 5
    else:
        tier = 5
    
    # 内部ID的な文字列から実表示名を綺麗にクリーンアップする処理
    clean_name = vehicle_name.split('_')[-1] if '_' in vehicle_name else vehicle_name
    clean_name = clean_name.replace('clone', '(Clone)').replace('halloween', ' (HW)')
    
    return nation, ship_type, tier, clean_name

def extract_zip_data(uploaded_files: List[Any]) -> Tuple[Dict[str, List[pd.DataFrame]], List[str], List[str]]:
    all_data: Dict[str, List[pd.DataFrame]] = {k: [] for k in CSV_MAPPING.values()}
    success_zips = []
    errors = []
    
    for up_file in uploaded_files:
        try:
            file_bytes = up_file.read()
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                file_list = z.namelist()
                temp_dfs = {}
                detected_date = None
                
                for internal_path in file_list:
                    base_name = os.path.basename(internal_path)
                    if base_name in CSV_MAPPING:
                        key = CSV_MAPPING[base_name]
                        try:
                            with z.open(internal_path) as f:
                                content = f.read().decode('utf-8')
                        except UnicodeDecodeError:
                            with z.open(internal_path) as f:
                                content = f.read().decode('shift_jis')
                        
                        df = pd.read_csv(io.StringIO(content))
                        if not df.empty:
                            df.columns = [c.strip().upper() for c in df.columns]
                            temp_dfs[key] = df
                            
                            if key == "account_stats":
                                target_col = 'DOSSIER_UPDATED_AT' if 'DOSSIER_UPDATED_AT' in df.columns else ('UPDATED_AT' if 'UPDATED_AT' in df.columns else None)
                                if target_col:
                                    raw_val = str(df[target_col].iloc[0]).strip()
                                    if raw_val and raw_val != "nan":
                                        if raw_val.isdigit() or (raw_val.replace('.', '', 1).isdigit() and '.' in raw_val):
                                            timestamp_sec = float(raw_val)
                                            detected_date = datetime.fromtimestamp(timestamp_sec).date()
                                        else:
                                            if len(raw_val) >= 10:
                                                detected_date = datetime.strptime(raw_val[:10], '%Y-%m-%d').date()
                
                if not detected_date:
                    date_matches = re.findall(r'\d{4}-\d{2}-\d{2}', up_file.name)
                    if date_matches:
                        detected_date = datetime.strptime(date_matches[0], '%Y-%m-%d').date()
                    else:
                        date_digits = re.findall(r'\d{8}', up_file.name)
                        if date_digits:
                            detected_date = datetime.strptime(date_digits[0], '%Y%m%d').date()
                        else:
                            detected_date = date.today()
                
                matched_count = 0
                for key, df in temp_dfs.items():
                    df['_SNAPSHOT_DATE'] = pd.to_datetime(detected_date)
                    all_data[key].append(df)
                    matched_count += 1
                            
                if matched_count > 0:
                    success_zips.append(f"{up_file.name} ({detected_date.strftime('%Y-%m-%d')})")
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
        df_concat = df_concat.sort_values(by='_SNAPSHOT_DATE').reset_index(drop=True)
        
        if key in ["account_stats", "account_info", "clans"]:
            df_concat = df_concat.drop_duplicates(subset=['_SNAPSHOT_DATE'], keep='last')
        elif key == "battle_types" and 'TYPE' in df_concat.columns:
            df_concat = df_concat.drop_duplicates(subset=['_SNAPSHOT_DATE', 'TYPE'], keep='last')
        elif key == "ship_stats" and 'VEHICLE_NAME' in df_concat.columns and 'TYPE' in df_concat.columns:
            df_concat = df_concat.drop_duplicates(subset=['_SNAPSHOT_DATE', 'VEHICLE_NAME', 'TYPE'], keep='last')
            
        merged[key] = df_concat
    return merged

# ==========================================
# 4. アナリティクス計算関数
# ==========================================
def calc_metrics_from_row(df: pd.DataFrame) -> Dict[str, Any]:
    if df.empty:
        return {"battles": None, "win_rate": None, "survived_rate": None, "avg_damage": None, "avg_frags": None, "avg_xp": None, "kd": None}
    
    battles = float(df['BATTLES_COUNT'].sum() if 'BATTLES_COUNT' in df.columns else 0)
    if battles <= 0:
        return {"battles": None, "win_rate": None, "survived_rate": None, "avg_damage": None, "avg_frags": None, "avg_xp": None, "kd": None}
        
    wins = float(df['WINS'].sum() if 'WINS' in df.columns else 0)
    survived = float(df['SURVIVED'].sum() if 'SURVIVED' in df.columns else 0)
    damage = float(df['DAMAGE_DEALT'].sum() if 'DAMAGE_DEALT' in df.columns else 0)
    frags = float(df['FRAGS'].sum() if 'FRAGS' in df.columns else 0)
    xp = float(df['EXP'].sum() if 'EXP' in df.columns else 0)
    deaths = battles - survived
    if deaths <= 0: deaths = 1.0

    return {
        "battles": int(battles), "win_rate": (wins / battles * 100),
        "survived_rate": (survived / battles * 100), "avg_damage": (damage / battles),
        "avg_frags": (frags / battles), "avg_xp": (xp / battles), "kd": (frags / deaths)
    }

def calc_period_diff_metrics(df_new: pd.DataFrame, df_old: pd.DataFrame) -> Dict[str, Any]:
    battles = float(df_new['BATTLES_COUNT'].sum() - df_old['BATTLES_COUNT'].sum())
    if battles <= 0:
        return {"battles": None, "win_rate": None, "survived_rate": None, "avg_damage": None, "avg_frags": None, "avg_xp": None, "kd": None}
        
    wins = float(df_new['WINS'].sum() - df_old['WINS'].sum())
    survived = float(df_new['SURVIVED'].sum() - df_old['SURVIVED'].sum())
    damage = float(df_new['DAMAGE_DEALT'].sum() - df_old['DAMAGE_DEALT'].sum())
    frags = float(df_new['FRAGS'].sum() - df_old['FRAGS'].sum())
    xp = float(df_new['EXP'].sum() - df_old['EXP'].sum())
    deaths = battles - survived
    if deaths <= 0: deaths = 1.0

    return {
        "battles": int(max(0, battles)), "win_rate": max(0.0, min(100.0, (wins / battles * 100))),
        "survived_rate": max(0.0, min(100.0, (survived / battles * 100))), "avg_damage": max(0.0, damage / battles),
        "avg_frags": max(0.0, frags / battles), "avg_xp": max(0.0, xp / battles), "kd": max(0.0, frags / deaths)
    }
    # ==========================================
# 5. アプリケーションメインルーチン
# ==========================================
def main():
    # サイドバーインポート
    st.sidebar.header("データインポート")
    uploaded_files = st.sidebar.file_uploader("ZIPデータダンプ投入", type="zip", accept_multiple_files=True)
    
    if not uploaded_files:
        st.info("サイドバーから個人データZIPファイルを複数アップロードしてください。")
        return

    raw_data, success_zips, errors = extract_zip_data(uploaded_files)
    data = merge_and_optimize(raw_data)
    
    # タイムスタンプ・ユニーク日付のソート（最新が右になるよう一度ベースを用意）
    all_dates = []
    for df in data.values():
        if not df.empty and '_SNAPSHOT_DATE' in df.columns:
            all_dates.extend(df['_SNAPSHOT_DATE'].unique().tolist())
    unique_dates = sorted(list(set(pd.to_datetime(all_dates))))

    # 艦艇データのデコード事前処理
    ship_df = data["ship_stats"]
    if not ship_df.empty:
        parsed_meta = ship_df['VEHICLE_NAME'].apply(parse_ship_id)
        ship_df['_NATION'] = [x[0] for x in parsed_meta]
        ship_df['_SHIP_TYPE'] = [x[1] for x in parsed_meta]
        ship_df['_ESTIMATED_TIER'] = [x[2] for x in parsed_meta]
        ship_df['_CLEAN_NAME'] = [x[3] for x in parsed_meta]
        data["ship_stats"] = ship_df

    # ------------------------------------------
    # ⚓ 1 & 2. タイトル & 【クラン名】ID のヘッダー表示
    # ------------------------------------------
    clan_tag, clan_name, p_name, p_id = "---", "クラン未所属", "PlayerName", "xxxxxxxx"
    
    if not data["account_info"].empty:
        l_info = data["account_info"].iloc[-1]
        if 'NICKNAME' in l_info.index: p_name = str(l_info['NICKNAME'])
        if 'ACCOUNT_ID' in l_info.index: p_id = str(l_info['ACCOUNT_ID'])
        
    if not data["clans"].empty:
        l_clan = data["clans"].iloc[-1]
        if 'TAG' in l_clan.index and pd.notna(l_clan['TAG']): clan_tag = f"[{l_clan['TAG']}]"
        if 'NAME' in l_clan.index and pd.notna(l_clan['NAME']): clan_name = str(l_clan['NAME'])

    header_html = f"""
    <div class="game-header-container">
        <div class="game-title">Fleet Intelligence Dashboard</div>
        <div class="player-clan-info">
            <span class="clan-tag-highlight">{clan_tag}</span> {p_name} &nbsp;|&nbsp; <span style="color: #94a3b8; font-size:0.95rem;">クラン: {clan_name}</span>
        </div>
        <div class="player-id-sub">ID: {p_id}</div>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)

    # タブメニュー生成
    t_summary, t_nation, t_type, t_ship, t_best, t_clan = st.tabs([
        "総合戦績 (マトリクス)", "国家別分析", "艦種別分析", "艦艇別詳細", "自己ベスト", "クランデータ"
    ])

    # ------------------------------------------
    # Tab 1: 総合戦績（4 & 5. 2段構成UI・固定横スクロール表）
    # ------------------------------------------
    with t_summary:
        bt_df = data["battle_types"]
        
        # 存在する（データを持っている）戦闘タイプIDを抽出
        available_ids = set()
        if not bt_df.empty:
            available_ids.update(bt_df['TYPE'].unique().tolist())
        if not ship_df.empty:
            available_ids.update(ship_df['TYPE'].unique().tolist())
            
        # 4. 2段構成用：データが存在する「モード」と「部隊形式」を動的に判定
        available_modes = set()
        available_teams_map = {} # モードごとの部隊形式
        
        for tid, meta in BATTLE_TYPE_MAP.items():
            if tid in available_ids:
                m = meta["mode"]
                t = meta["team"]
                available_modes.add(m)
                if m not in available_teams_map:
                    available_teams_map[m] = []
                if t not in available_teams_map[m]:
                    available_teams_map[m].append(t)
                    
        if not available_modes:
            st.warning("アップロードされたデータに戦闘タイプ情報が見つかりません。")
            return

        # 状態保持の初期化
        if 'sel_mode' not in st.session_state:
            st.session_state.sel_mode = "通常" if "通常" in available_modes else list(available_modes)[0]
            
        current_mode = st.session_state.sel_mode
        if current_mode not in available_teams_map:
            current_mode = list(available_modes)[0]
            st.session_state.sel_mode = current_mode
            
        if 'sel_team' not in st.session_state:
            st.session_state.sel_team = available_teams_map[current_mode][0]
            
        if st.session_state.sel_team not in available_teams_map[current_mode]:
            st.session_state.sel_team = available_teams_map[current_mode][0]

        # --- 1段目: モード選択 (1/4サイズ・レスポンシブ配置) ---
        st.markdown('<div class="mode-selection-header">■ STEP1: モード選択</div>', unsafe_allow_html=True)
        mode_order = ["通常", "AI", "ランク", "アリーナ", "闘争", "アーケード", "クラン戦", "軍記"]
        actual_modes = [m for m in mode_order if m in available_modes]
        
        m_cols = st.columns(max(len(actual_modes), 4))
        for idx, m_name in enumerate(actual_modes):
            with m_cols[idx % len(m_cols)]:
                if st.button(m_name, key=f"btn_m_{m_name}", use_container_width=True, 
                             type="primary" if current_mode == m_name else "secondary"):
                    st.session_state.sel_mode = m_name
                    st.session_state.sel_team = available_teams_map[m_name][0] # 形式リセット
                    st.rerun()

        # --- 2段目: 部隊形式選択 (1/4サイズ・レスポンシブ配置) ---
        st.markdown('<div class="mode-selection-header">■ STEP2: 部隊形式選択</div>', unsafe_allow_html=True)
        team_order = ["総合", "ソロ", "2人分隊", "3人分隊"]
        actual_teams = [t for t in team_order if t in available_teams_map[current_mode]]
        
        t_cols = st.columns(max(len(actual_teams), 4))
        for idx, t_name in enumerate(actual_teams):
            with t_cols[idx % len(t_cols)]:
                if st.button(t_name, key=f"btn_t_{t_name}", use_container_width=True,
                             type="primary" if st.session_state.sel_team == t_name else "secondary"):
                    st.session_state.sel_team = t_name
                    st.rerun()

        # 現在選択されているターゲットIDを特定
        target_type_code = 1
        for tid, meta in BATTLE_TYPE_MAP.items():
            if meta["mode"] == st.session_state.sel_mode and meta["team"] == st.session_state.sel_team:
                target_type_code = tid
                break

        # データのフィルタリング
        mode_bt_df = bt_df[bt_df['TYPE'] == target_type_code] if not bt_df.empty else pd.DataFrame()
        mode_filtered_ship_df = ship_df[ship_df['TYPE'] == target_type_code] if not ship_df.empty else pd.DataFrame()

        # ---- 5. マトリクスデータの組み立て（最新順・固定セル表示） ----
        matrix_columns = {}
        
        # A. 全期間データの計算
        if not mode_bt_df.empty:
            l_snap = mode_bt_df['_SNAPSHOT_DATE'].max()
            global_kpi = calc_metrics_from_row(mode_bt_df[mode_bt_df['_SNAPSHOT_DATE'] == l_snap])
        elif not mode_filtered_ship_df.empty:
            l_snap = mode_filtered_ship_df['_SNAPSHOT_DATE'].max()
            global_kpi = calc_metrics_from_row(mode_filtered_ship_df[mode_filtered_ship_df['_SNAPSHOT_DATE'] == l_snap])
        else:
            global_kpi = calc_metrics_from_row(pd.DataFrame())
            
        matrix_columns["全期間"] = global_kpi

        # B. 期間別データの計算（左側が最新になるよう逆順ループに設定）
        if len(unique_dates) > 1:
            for i in range(len(unique_dates) - 1, 0, -1):
                d_start = unique_dates[i-1]
                d_end = unique_dates[i]
                # YYYY/MM/DD 形式に変更
                period_label = f"{d_start.strftime('%Y/%m/%d')}～{d_end.strftime('%Y/%m/%d')}"
                
                if not mode_bt_df.empty:
                    df_end_snap = mode_bt_df[mode_bt_df['_SNAPSHOT_DATE'] == d_end]
                    df_start_snap = mode_bt_df[mode_bt_df['_SNAPSHOT_DATE'] == d_start]
                elif not mode_filtered_ship_df.empty:
                    df_end_snap = mode_filtered_ship_df[mode_filtered_ship_df['_SNAPSHOT_DATE'] == d_end]
                    df_start_snap = mode_filtered_ship_df[mode_filtered_ship_df['_SNAPSHOT_DATE'] == d_start]
                else:
                    df_end_snap, df_start_snap = pd.DataFrame(), pd.DataFrame()
                
                if not df_end_snap.empty and not df_start_snap.empty:
                    matrix_columns[period_label] = calc_period_diff_metrics(df_end_snap, df_start_snap)
                else:
                    matrix_columns[period_label] = calc_metrics_from_row(pd.DataFrame())

        row_indicators = [
            ("戦闘数", "battles", "{:,}"),
            ("勝率", "win_rate", "{:.2f}%"),
            ("生存率", "survived_rate", "{:.2f}%"),
            ("平均与ダメージ", "avg_damage", "{:,.0f}"),
            ("K/D比", "kd", "{:.2f}"),
            ("平均撃沈数", "avg_frags", "{:.2f}"),
            ("平均経験値", "avg_xp", "{:,.0f}")
        ]

        # 📋 HTML/CSS による「各種データ」「全期間」固定＆スクロールテーブルレンダリング
        html_table = '<div class="matrix-scroll-wrapper"><table class="matrix-table"><thead><tr>'
        html_table += '<th class="sticky-indicator">各種データ</th>'
        html_table += '<th class="sticky-lifetime">全期間</th>'
        
        # 期間別ヘッダー（左側が最新）
        period_keys = [k for k in matrix_columns.keys() if k != "全期間"]
        for p_key in period_keys:
            html_table += f'<th>{p_key}</th>'
        html_table += '</tr></thead><tbody>'
        
        for label, key, fmt in row_indicators:
            html_table += f'<tr><td class="sticky-indicator">{label}</td>'
            
            # 全期間セル
            lt_val = matrix_columns["全期間"][key]
            if lt_val is not None:
                html_table += f'<td class="sticky-lifetime">{fmt.format(lt_val)}</td>'
            else:
                html_table += '<td class="sticky-lifetime empty-cell"></td>'
            
            # 期間別セル（データが存在しない場合は空欄）
            for p_key in period_keys:
                p_val = matrix_columns[p_key][key]
                if p_val is not None and pd.notna(p_val):
                    html_table += f'<td>{fmt.format(p_val)}</td>'
                else:
                    html_table += '<td class="empty-cell"></td>'
            html_table += '</tr>'
            
        html_table += '</tbody></table></div>'
        st.markdown(html_table, unsafe_allow_html=True)

    # ------------------------------------------
    # Tab 2: 国家別分析
    # ------------------------------------------
    with t_nation:
        if not mode_filtered_ship_df.empty:
            l_ships = mode_filtered_ship_df[mode_filtered_ship_df['_SNAPSHOT_DATE'] == mode_filtered_ship_df['_SNAPSHOT_DATE'].max()]
            nat_records = []
            for nat in l_ships['_NATION'].unique():
                nat_df = l_ships[l_ships['_NATION'] == nat]
                kpi = calc_metrics_from_row(nat_df)
                if kpi["battles"] is not None:
                    nat_records.append({"国家": nat, "戦闘数": kpi["battles"], "勝率": f"{kpi['win_rate']:.2f}%", "平均与ダメ": int(kpi["avg_damage"])})
            if nat_records:
                st.dataframe(pd.DataFrame(nat_records).sort_values("戦闘数", ascending=False), width='stretch', hide_index=True)

    # ------------------------------------------
    # Tab 3: 艦種別分析
    # ------------------------------------------
    with t_type:
        if not mode_filtered_ship_df.empty:
            l_ships = mode_filtered_ship_df[mode_filtered_ship_df['_SNAPSHOT_DATE'] == mode_filtered_ship_df['_SNAPSHOT_DATE'].max()]
            typ_records = []
            for typ in l_ships['_SHIP_TYPE'].unique():
                typ_df = l_ships[l_ships['_SHIP_TYPE'] == typ]
                kpi = calc_metrics_from_row(typ_df)
                if kpi["battles"] is not None:
                    typ_records.append({"艦種": typ, "戦闘数": kpi["battles"], "勝率": f"{kpi['win_rate']:.2f}%", "平均与ダメ": int(kpi["avg_damage"])})
            if typ_records:
                st.dataframe(pd.DataFrame(typ_records).sort_values("戦闘数", ascending=False), width='stretch', hide_index=True)

    # ------------------------------------------
    # Tab 4: 艦艇別詳細データ (🚢 6. 新しい表記デザイン適用)
    # ------------------------------------------
    with t_ship:
        if not mode_filtered_ship_df.empty:
            l_ships = mode_filtered_ship_df[mode_filtered_ship_df['_SNAPSHOT_DATE'] == mode_filtered_ship_df['_SNAPSHOT_DATE'].max()].copy()
            c_f1, c_f2 = st.columns(2)
            s_nat = c_f1.selectbox("国家絞り込み", ["すべて"] + list(l_ships['_NATION'].unique()))
            s_typ = c_f2.selectbox("艦種絞り込み", ["すべて"] + list(l_ships['_SHIP_TYPE'].unique()))
            
            query_df = l_ships.copy()
            if s_nat != "すべて": query_df = query_df[query_df['_NATION'] == s_nat]
            if s_typ != "すべて": query_df = query_df[query_df['_SHIP_TYPE'] == s_typ]
            
            # 6. HTML文字列表記によるゲームライクな等幅・シックデザイン適用
            records_list = []
            for _, row in query_df.iterrows():
                row_kpi = calc_metrics_from_row(pd.DataFrame([row]))
                if row_kpi["battles"] is not None:
                    ship_html = f'<span class="game-ship-name">{row["_CLEAN_NAME"]}</span>'
                    records_list.append({
                        "艦艇名": ship_html, "国家": row['_NATION'], "艦種": row['_SHIP_TYPE'],
                        "戦闘数": row_kpi["battles"], "勝率": f"{row_kpi['win_rate']:.2f}%", "平均与ダメ": int(row_kpi["avg_damage"])
                    })
            if records_list:
                # HTMLをレンダリングさせるため、st.write / st.markdown でテーブル出力
                sdf = pd.DataFrame(records_list).sort_values(by="戦闘数", ascending=False)
                st.write(sdf.to_html(escape=False, index=False), unsafe_allow_html=True)

    # ------------------------------------------
    # Tab 5: 自己ベスト
    # ------------------------------------------
    with t_best:
        acc_df = data["account_stats"]
        if not acc_df.empty:
            l_acc = acc_df[acc_df['_SNAPSHOT_DATE'] == acc_df['_SNAPSHOT_DATE'].max()]
            b_records = []
            best_fields = [
                ("最高与ダメージ", "MAX_DAMAGE_DEALT"), ("最高経験値", "MAX_EXP"),
                ("最高撃沉数", "MAX_FRAGS"), ("最大メイン砲命中", "MAX_MAIN_HIT")
            ]
            for label, col in best_fields:
                if col in l_acc.columns and pd.notna(l_acc[col].iloc[0]):
                    b_records.append({"項目": label, "記録": f"{int(l_acc[col].iloc[0]):,}"})
            if b_records:
                st.dataframe(pd.DataFrame(b_records), width='stretch', hide_index=True)
        else:
            st.info("自己ベストデータが見つかりません。")

    # ------------------------------------------
    # Tab 6: クランデータ
    # ------------------------------------------
    with t_clan:
        clan_df = data["clans"]
        if not clan_df.empty:
            l_clan = clan_df[clan_df['_SNAPSHOT_DATE'] == clan_df['_SNAPSHOT_DATE'].max()]
            st.dataframe(l_clan.T, width='stretch')
        else:
            st.info("クランデータ（Clans.csv）がZIPに含まれていません。")

if __name__ == '__main__':
    main()
