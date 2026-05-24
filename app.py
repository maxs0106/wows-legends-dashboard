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
# 1. ページ初期設定 & 画像準拠シックグリッドCSS
# ==========================================
st.set_page_config(
    page_title="WoWs Legends Fleet Intelligence",
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
    
    /* ⚓ ゲームUI風ヘッダー */
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
    }
    .player-clan-info {
        font-size: 1.1rem;
        color: #e2e8f0;
        font-weight: 600;
    }
    .clan-tag-highlight {
        color: #00f2fe;
        font-weight: 700;
    }
    .player-id-sub {
        font-size: 0.85rem;
        color: #64748b;
        margin-top: 4px;
        font-family: monospace;
    }

    /* 📊 縦横マス目固定・期間別横スクロールコンテナ */
    .matrix-scroll-wrapper {
        position: relative;
        width: 100%;
        overflow-x: auto;
        margin: 15px 0 30px 0;
        border: 1px solid #1e293b;
        background-color: #070d14;
    }
    .matrix-table {
        border-collapse: separate;
        border-spacing: 0;
        width: 100%;
        font-size: 0.9rem;
        text-align: center;
    }
    .matrix-table th, .matrix-table td {
        padding: 14px;
        border-bottom: 1px solid #1e293b;
        border-right: 1px solid #1e293b;
        min-width: 150px;
        max-width: 150px;
        width: 150px;
        white-space: nowrap;
        box-sizing: border-box;
    }
    
    /* 「各種データ」列の固定表示 */
    .matrix-table th.sticky-indicator, .matrix-table td.sticky-indicator {
        position: sticky;
        left: 0;
        background-color: #0f172a !important;
        z-index: 10;
        text-align: left;
        min-width: 180px;
        max-width: 180px;
        width: 180px;
        font-weight: 600;
        color: #94a3b8;
        border-right: 2px solid #1e293b;
    }
    /* 「全期間」列の固定表示 */
    .matrix-table th.sticky-lifetime, .matrix-table td.sticky-lifetime {
        position: sticky;
        left: 180px;
        background-color: #111c2e !important;
        z-index: 9;
        font-weight: 700;
        color: #ffffff;
        border-right: 2px solid #00f2fe;
    }
    
    .matrix-table th {
        background-color: #0f172a;
        color: #94a3b8;
        font-size: 0.85rem;
    }
    .matrix-table tr:hover td {
        background-color: #131c2e;
    }
    
    .empty-cell {
        color: #475569;
        font-weight: normal;
    }
    
    .game-ship-name {
        font-family: 'Courier New', Courier, monospace;
        font-weight: 700;
        color: #00f2fe;
        background-color: #0f172a;
        padding: 3px 8px;
        border-radius: 2px;
        border: 1px solid #1e293b;
    }
    
    .mode-selection-header {
        font-size: 0.85rem;
        color: #00f2fe;
        margin: 12px 0 6px 0;
        font-weight: 700;
    }
    
    .chart-section-title {
        font-size: 1.2rem;
        font-weight: 700;
        color: #ffffff;
        margin: 35px 0 15px 0;
        padding-left: 8px;
        border-left: 4px solid #00f2fe;
    }
</style>
"""
st.markdown(CSS_STYLE, unsafe_allow_html=True)

# ==========================================
# 2. 定数定義 & 戦闘タイプマスター
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

IMAGE_NATION_MAP = {
    "a": "米国", "b": "イギリス", "f": "フランス", "g": "ドイツ",
    "i": "イタリア", "j": "日本", "r": "ロシア", "w": "汎ヨーロッパ", "z": "パンアジア"
}

IMAGE_CLASS_MAP = {
    "a": "キャリア", "b": "戦艦", "c": "クルーザー", "d": "駆逐艦"
}

RARE_SHIPS_DECODER = {
    "pasb014_arkansas_1912_clone": "アーカンソー (通常)",
    "pasb004_arkansas_1912": "ワイオミング (TT)",
    "pasc597_1951年7月9日": "ボイシ",
    "pgsb110_大ドイツ": "総選挙人",
    "pgsd503_g_101_clone": "G-101 (通常)",
    "pjsc015_tatsuta_1912": "Tenryu",
    "pjsc027_iwaki_1944_clone": "イワキ (通常)",
    "pjsc510_azumaya": "アズマ",
    "pjsd025_true_kamikaze": "神風 (通常)",
    "pjsd718_azur_yukikaze": "normal Yukikaze",
    "prsc001_avrora_1917": "オーロラ",
    "prsc106_pr_94_budeny": "ブディオニー",
    "prsd206_pr_7": "怒っている",
    "prsd208_pr_30": "オグネヴォイ",
    "prsd106_pr_30_ognevoy": "ボエヴォイ",
    "pzsc102_チェスター": "シー・アン",
    "pasd518_benson": "Charles F Hughes",
    "pasc045_marblehead_1924_clone": "Marblehead (通常)",
    "pjsc727_blue_dragon": "東洋の龍",
    "pfsc507_charles_martel_prem_hw": "シャルルマーニュ",
    "pxsb004_tirpiz_1942_h2017": "Magnu-S (ハロウィン)",
    "pxsd003_kagero_h2017": "Urashima (ハロウィン)",
    "pxsc003_pr_68_chapaev_h2017": "スヴァトザル (ハロウィン)"
}

BATTLE_TYPE_MAP = {
    1:  {"mode": "通常", "team": "総合"},   2:  {"mode": "AI", "team": "総合"},
    3:  {"mode": "通常", "team": "ソロ"},   4:  {"mode": "通常", "team": "2人分隊"},
    5:  {"mode": "通常", "team": "3人分隊"}, 6:  {"mode": "AI", "team": "ソロ"},
    7:  {"mode": "AI", "team": "2人分隊"},  8:  {"mode": "AI", "team": "3人分隊"},
    9:  {"mode": "ランク", "team": "ソロ"},  10: {"mode": "ランク", "team": "2人分隊"},
    11: {"mode": "ランク", "team": "3人分隊"},17: {"mode": "アリーナ", "team": "ソロ"},
    18: {"mode": "アリーナ", "team": "2人分隊"},19: {"mode": "アリーナ", "team": "3人分隊"},
    20: {"mode": "闘争", "team": "ソロ"},   21: {"mode": "闘争", "team": "2人分隊"},
    22: {"mode": "闘争", "team": "3人分隊"}, 23: {"mode": "アーケード", "team": "総合"},
    24: {"mode": "アーケード", "team": "ソロ"}, 25: {"mode": "アーケード", "team": "2人分隊"},
    26: {"mode": "アーケード", "team": "3人分隊"},27: {"mode": "クラン戦", "team": "総合"},
    28: {"mode": "軍記", "team": "総合"}
}

# ==========================================
# 3. 解析・計算エンジン
# ==========================================
def parse_ship_id(vehicle_name: str) -> Tuple[str, str, int, str]:
    if not isinstance(vehicle_name, str) or len(vehicle_name) < 4:
        return "その他", "その他", 0, str(vehicle_name)
    
    low_name = vehicle_name.lower().strip()
    if low_name in RARE_SHIPS_DECODER:
        display_name = RARE_SHIPS_DECODER[low_name]
    else:
        found_rare = None
        for k, v in RARE_SHIPS_DECODER.items():
            if k in low_name or low_name in k:
                found_rare = v
                break
        display_name = found_rare if found_rare else (vehicle_name.split('_')[-1] if '_' in vehicle_name else vehicle_name)

    nation, ship_class = "その他", "その他"
    if low_name.startswith('p') and len(low_name) >= 4:
        n_code = low_name[1]
        c_code = low_name[3] if low_name[2] == 's' else low_name[2]
        nation = IMAGE_NATION_MAP.get(n_code, "その他")
        ship_class = IMAGE_CLASS_MAP.get(c_code, "その他")
        
    tier_match = re.search(r'\d+', vehicle_name)
    if tier_match:
        val = int(tier_match.group())
        tier = (val // 100) if val >= 100 else val
        if tier > 10: tier = 7
    else:
        tier = 7
        
    return nation, ship_class, tier, display_name

def extract_zip_data(uploaded_files: List[Any]) -> Tuple[Dict[str, List[pd.DataFrame]], List[str], List[str]]:
    all_data: Dict[str, List[pd.DataFrame]] = {k: [] for k in CSV_MAPPING.values()}
    success_zips, errors = [], []
    
    for up_file in uploaded_files:
        try:
            file_bytes = up_file.read()
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                temp_dfs = {}
                detected_date = None
                
                for internal_path in z.namelist():
                    base_name = os.path.basename(internal_path)
                    if base_name in CSV_MAPPING:
                        key = CSV_MAPPING[base_name]
                        try:
                            content = z.open(internal_path).read().decode('utf-8')
                        except UnicodeDecodeError:
                            content = z.open(internal_path).read().decode('shift_jis')
                        
                        df = pd.read_csv(io.StringIO(content))
                        if not df.empty:
                            df.columns = [c.strip().upper() for c in df.columns]
                            temp_dfs[key] = df
                            
                            if key == "account_stats" and detected_date is None:
                                t_col = 'DOSSIER_UPDATED_AT' if 'DOSSIER_UPDATED_AT' in df.columns else ('UPDATED_AT' if 'UPDATED_AT' in df.columns else None)
                                if t_col:
                                    raw_val = str(df[t_col].iloc[0]).strip()
                                    if raw_val.replace('.', '', 1).isdigit():
                                        detected_date = datetime.fromtimestamp(float(raw_val)).date()
                                    elif len(raw_val) >= 10:
                                        detected_date = datetime.strptime(raw_val[:10], '%Y-%m-%d').date()
                
                if not detected_date:
                    matches = re.findall(r'\d{4}-\d{2}-\d{2}', up_file.name)
                    detected_date = datetime.strptime(matches[0], '%Y-%m-%d').date() if matches else date.today()
                
                for key, df in temp_dfs.items():
                    df['_SNAPSHOT_DATE'] = pd.to_datetime(detected_date)
                    all_data[key].append(df)
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
        df_concat = pd.concat(dfs, ignore_index=True).sort_values(by='_SNAPSHOT_DATE').reset_index(drop=True)
        if key in ["account_stats", "account_info", "clans"]:
            df_concat = df_concat.drop_duplicates(subset=['_SNAPSHOT_DATE'], keep='last')
        elif key == "battle_types" and 'TYPE' in df_concat.columns:
            df_concat = df_concat.drop_duplicates(subset=['_SNAPSHOT_DATE', 'TYPE'], keep='last')
        elif key == "ship_stats" and 'VEHICLE_NAME' in df_concat.columns and 'TYPE' in df_concat.columns:
            df_concat = df_concat.drop_duplicates(subset=['_SNAPSHOT_DATE', 'VEHICLE_NAME', 'TYPE'], keep='last')
        merged[key] = df_concat
    return merged

def calc_metrics_from_row(df: pd.DataFrame) -> Dict[str, Any]:
    if df.empty or 'BATTLES_COUNT' not in df.columns or df['BATTLES_COUNT'].sum() <= 0:
        return {"battles": None, "win_rate": None, "survived_rate": None, "avg_damage": None, "kd": None, "avg_frags": None, "avg_xp": None}
    battles = float(df['BATTLES_COUNT'].sum())
    deaths = battles - float(df['SURVIVED'].sum() if 'SURVIVED' in df.columns else 0)
    return {
        "battles": int(battles),
        "win_rate": (float(df['WINS'].sum()) / battles * 100),
        "survived_rate": (float(df['SURVIVED'].sum() if 'SURVIVED' in df.columns else 0) / battles * 100),
        "avg_damage": (float(df['DAMAGE_DEALT'].sum() if 'DAMAGE_DEALT' in df.columns else 0) / battles),
        "kd": (float(df['FRAGS'].sum() if 'FRAGS' in df.columns else 0) / (1.0 if deaths <= 0 else deaths)),
        "avg_frags": (float(df['FRAGS'].sum() if 'FRAGS' in df.columns else 0) / battles),
        "avg_xp": (float(df['EXP'].sum() if 'EXP' in df.columns else 0) / battles)
    }

def calc_period_diff_metrics(df_new: pd.DataFrame, df_old: pd.DataFrame) -> Dict[str, Any]:
    battles = float(df_new['BATTLES_COUNT'].sum() - df_old['BATTLES_COUNT'].sum())
    if battles <= 0:
        return {"battles": None, "win_rate": None, "survived_rate": None, "avg_damage": None, "kd": None, "avg_frags": None, "avg_xp": None}
    deaths = battles - float(df_new['SURVIVED'].sum() - df_old['SURVIVED'].sum())
    return {
        "battles": int(battles),
        "win_rate": max(0.0, min(100.0, (float(df_new['WINS'].sum() - df_old['WINS'].sum()) / battles * 100))),
        "survived_rate": max(0.0, min(100.0, (float(df_new['SURVIVED'].sum() - df_old['SURVIVED'].sum()) / battles * 100))),
        "avg_damage": max(0.0, float(df_new['DAMAGE_DEALT'].sum() - df_old['DAMAGE_DEALT'].sum()) / battles),
        "kd": max(0.0, float(df_new['FRAGS'].sum() - df_old['FRAGS'].sum()) / (1.0 if deaths <= 0 else deaths)),
        "avg_frags": max(0.0, float(df_new['FRAGS'].sum() - df_old['FRAGS'].sum()) / battles),
        "avg_xp": max(0.0, float(df_new['EXP'].sum() - df_old['EXP'].sum()) / battles)
    }
    # ==========================================
# 4. アプリケーションメインルーチン
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
            all_dates.extend(df['_SNAPSHOT_DATE'].unique().tolist())
    
    if not all_dates:
        st.error("有効な日付データを含むCSVファイルが見つかりません。")
        return
        
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

    # 全6タブの構成
    t_summary, t_nation, t_type, t_ship, t_best, t_clan = st.tabs([
        "総合戦績 (マトリクス)", "国家別分析", "艦種別分析", "艦艇別詳細", "自己ベスト", "クランデータ"
    ])

    # ------------------------------------------
    # Tab 1: 総合戦績（固定形式ボタン＆各種グラフィカルアナリティクス）
    # ------------------------------------------
    with t_summary:
        bt_df = data["battle_types"]
        
        # 💡 モード（STEP1）の決定（固定オーダーから存在するものをアクティブ化）
        available_modes = set([meta["mode"] for meta in BATTLE_TYPE_MAP.values()])
        if 'sel_mode' not in st.session_state:
            st.session_state.sel_mode = "通常"
        current_mode = st.session_state.sel_mode

        # --- 1段目: モード選択 ---
        st.markdown('<div class="mode-selection-header">■ STEP1: モード選択</div>', unsafe_allow_html=True)
        mode_order = ["通常", "AI", "ランク", "アリーナ", "闘争", "アーケード", "クラン戦", "軍記"]
        
        m_cols = st.columns(len(mode_order))
        for idx, m_name in enumerate(mode_order):
            with m_cols[idx]:
                if st.button(m_name, key=f"btn_m_{m_name}", use_container_width=True, 
                             type="primary" if current_mode == m_name else "secondary"):
                    st.session_state.sel_mode = m_name
                    st.rerun()

        # 💡 改善点：選択されたモードにおける部隊形式（STEP2）を「データが空でもマスター定義から全て固定表示」
        team_order = ["総合", "ソロ", "2人分隊", "3人分隊"]
        
        # 現在のモード内で定義されている形式ボタンを抽出
        actual_teams = []
        for t_name in team_order:
            for tid, meta in BATTLE_TYPE_MAP.items():
                if meta["mode"] == current_mode and meta["team"] == t_name:
                    actual_teams.append(t_name)
                    break
        
        if 'sel_team' not in st.session_state or st.session_state.sel_team not in actual_teams:
            st.session_state.sel_team = actual_teams[0] if actual_teams else "総合"

        # --- 2段目: 部隊形式選択 ---
        st.markdown('<div class="mode-selection-header">■ STEP2: 部隊形式選択</div>', unsafe_allow_html=True)
        t_cols = st.columns(max(len(actual_teams), 4))
        for idx, t_name in enumerate(actual_teams):
            with t_cols[idx]:
                if st.button(t_name, key=f"btn_t_{t_name}", use_container_width=True,
                             type="primary" if st.session_state.sel_team == t_name else "secondary"):
                    st.session_state.sel_team = t_name
                    st.rerun()

        # ターゲット戦闘IDの特定
        target_type_code = 1
        for tid, meta in BATTLE_TYPE_MAP.items():
            if meta["mode"] == st.session_state.sel_mode and meta["team"] == st.session_state.sel_team:
                target_type_code = tid
                break

        mode_bt_df = bt_df[bt_df['TYPE'] == target_type_code] if not bt_df.empty else pd.DataFrame()
        mode_filtered_ship_df = ship_df[ship_df['TYPE'] == target_type_code] if not ship_df.empty else pd.DataFrame()

        # ---- マトリクスデータの構築 ----
        matrix_columns = {}
        
        # A. 全期間データの抽出
        if not mode_bt_df.empty:
            l_snap = mode_bt_df['_SNAPSHOT_DATE'].max()
            global_kpi = calc_metrics_from_row(mode_bt_df[mode_bt_df['_SNAPSHOT_DATE'] == l_snap])
        elif not mode_filtered_ship_df.empty:
            l_snap = mode_filtered_ship_df['_SNAPSHOT_DATE'].max()
            global_kpi = calc_metrics_from_row(mode_filtered_ship_df[mode_filtered_ship_df['_SNAPSHOT_DATE'] == l_snap])
        else:
            global_kpi = calc_metrics_from_row(pd.DataFrame())
            
        matrix_columns["全期間"] = global_kpi

        # B. 期間別データの抽出（最新日付が左側に来る逆順配置仕様）
        period_keys = []
        graph_periods = []  # グラフ用に時系列順のデータも保持するためのリスト
        
        if len(unique_dates) > 1:
            for i in range(len(unique_dates) - 1, 0, -1):
                d_start = unique_dates[i-1]
                d_end = unique_dates[i]
                
                period_label = f"{d_start.strftime('%Y/%m/%d')}<br>～ {d_end.strftime('%Y/%m/%d')}"
                period_keys.append(period_label)
                
                if not mode_bt_df.empty:
                    df_end_snap = mode_bt_df[mode_bt_df['_SNAPSHOT_DATE'] == d_end]
                    df_start_snap = mode_bt_df[mode_bt_df['_SNAPSHOT_DATE'] == d_start]
                elif not mode_filtered_ship_df.empty:
                    df_end_snap = mode_filtered_ship_df[mode_filtered_ship_df['_SNAPSHOT_DATE'] == d_end]
                    df_start_snap = mode_filtered_ship_df[mode_filtered_ship_df['_SNAPSHOT_DATE'] == d_start]
                else:
                    df_end_snap, df_start_snap = pd.DataFrame(), pd.DataFrame()
                
                if not df_end_snap.empty and not df_start_snap.empty:
                    metrics = calc_period_diff_metrics(df_end_snap, df_start_snap)
                else:
                    metrics = calc_metrics_from_row(pd.DataFrame())
                
                matrix_columns[period_label] = metrics
                graph_periods.append({
                    "label": f"{d_start.strftime('%m/%d')}~{d_end.strftime('%m/%d')}",
                    "win_rate": metrics["win_rate"],
                    "avg_damage": metrics["avg_damage"],
                    "avg_xp": metrics["avg_xp"],
                    "order": i
                })

        # 行表示の定義インジケーター
        row_indicators = [
            ("戦闘", "battles", "{:,}"), ("勝率", "win_rate", "{:.2f}%"),
            ("生還", "survived_rate", "{:.2f}%"), ("与ダメージ", "avg_damage", "{:,.0f}"),
            ("キル/デス比", "kd", "{:.2f}"), ("艦船撃沈", "avg_frags", "{:.2f}"),
            ("取得経験値", "avg_xp", "{:,.0f}")
        ]

        # 📋 HTMLを用いた画像完全再現テーブルの出力
        html_table = '<div class="matrix-scroll-wrapper"><table class="matrix-table"><thead><tr>'
        html_table += '<th class="sticky-indicator">各種データ</th>'
        html_table += '<th class="sticky-lifetime">全期間</th>'
        
        for p_key in period_keys:
            html_table += f'<th>{p_key}</th>'
        html_table += '</tr></thead><tbody>'
        
        for label, key, fmt in row_indicators:
            html_table += f'<tr><td class="sticky-indicator">{label}</td>'
            lt_val = matrix_columns["全期間"][key]
            if lt_val is not None:
                html_table += f'<td class="sticky-lifetime">{fmt.format(lt_val)}</td>'
            else:
                html_table += '<td class="sticky-lifetime empty-cell">-</td>'
            
            for p_key in period_keys:
                p_val = matrix_columns[p_key][key]
                if p_val is not None and pd.notna(p_val):
                    html_table += f'<td>{fmt.format(p_val)}</td>'
                else:
                    html_table += '<td class="empty-cell">-</td>'
            html_table += '</tr>'
            
        html_table += '</tbody></table></div>'
        st.markdown(html_table, unsafe_allow_html=True)

        # ------------------------------------------
        # 📈 📊 新機能: 総合戦績グラフィカルアナリティクス
        # ------------------------------------------
        st.markdown('<div class="chart-section-title">📊 期間別トレンド・アナリティクス</div>', unsafe_allow_html=True)
        
        # グラフ用データフレーム生成（時系列順に並び替え）
        g_df = pd.DataFrame(graph_periods).sort_values(by="order").dropna(subset=["win_rate"])
        
        if not g_df.empty:
            cg1, cg2 = st.columns(2)
            
            # 1. 勝率の推移（折れ線グラフ）
            with cg1:
                fig_win = px.line(g_df, x="label", y="win_rate", markers=True, text=g_df["win_rate"].apply(lambda x: f"{x:.1f}%"),
                                  title="【勝率】の期間推移トレンド", labels={"label": "期間", "win_rate": "勝率 (%)"})
                fig_win.update_traces(line_color="#00f2fe", marker=dict(size=8, color="#ffffff"), textposition="top center")
                fig_win.update_layout(template="plotly_dark", paper_bgcolor="#070d14", plot_bgcolor="#070d14", yaxis=dict(gridcolor="#1e293b"))
                st.plotly_chart(fig_win, use_container_width=True)
                
            # 2. 平均ダメージ & 平均経験値（2軸/並列バーチャート）
            with cg2:
                fig_dmg_xp = go.Figure()
                fig_dmg_xp.add_trace(go.Bar(x=g_df["label"], y=g_df["avg_damage"], name="平均ダメージ", marker_color="#38bdf8", yaxis="y"))
                fig_dmg_xp.add_trace(go.Bar(x=g_df["label"], y=g_df["avg_xp"], name="平均経験値", marker_color="#fbbf24", yaxis="y2"))
                fig_dmg_xp.update_layout(
                    title="【平均ダメージ】&【平均経験値】トレンド",
                    template="plotly_dark", paper_bgcolor="#070d14", plot_bgcolor="#070d14",
                    xaxis=dict(title="期間"),
                    yaxis=dict(title="平均与ダメージ", gridcolor="#1e293b", color="#38bdf8"),
                    yaxis2=dict(title="平均経験値", side="right", overlaying="y", color="#fbbf24"),
                    bgroupmode="group", legend=dict(x=0.01, y=0.99)
                )
                st.plotly_chart(fig_dmg_xp, use_container_width=True)
        else:
            st.info("期間別の遷移グラフを描画するための十分な差分データがありません。")

        # 3. 国籍・艦種別の戦闘数シェア（円グラフ） & レーダーチャート
        st.markdown('<div class="chart-section-title">🚢 国籍・艦種配分シェア & 戦闘能力レーダー</div>', unsafe_allow_html=True)
        
        if not mode_filtered_ship_df.empty:
            # 最新スナップショットの艦艇データを利用
            l_ships = mode_filtered_ship_df[mode_filtered_ship_df['_SNAPSHOT_DATE'] == mode_filtered_ship_df['_SNAPSHOT_DATE'].max()]
            
            c1, c2, c3 = st.columns(3)
            
            # A. 国籍別円グラフ
            with c1:
                nat_share = l_ships.groupby("_NATION")["BATTLES_COUNT"].sum().reset_index()
                fig_pie_nat = px.pie(nat_share, values="BATTLES_COUNT", names="_NATION", hole=0.4, title="国籍別 戦闘数シェア",
                                     color_discrete_sequence=px.colors.radial.Sunset_r)
                fig_pie_nat.update_layout(template="plotly_dark", paper_bgcolor="#070d14")
                st.plotly_chart(fig_pie_nat, use_container_width=True)
                
            # B. 艦種別円グラフ
            with c2:
                typ_share = l_ships.groupby("_SHIP_TYPE")["BATTLES_COUNT"].sum().reset_index()
                fig_pie_typ = px.pie(typ_share, values="BATTLES_COUNT", names="_SHIP_TYPE", hole=0.4, title="艦種別 戦闘数シェア",
                                     color_discrete_sequence=px.colors.radial.Neon)
                fig_pie_typ.update_layout(template="plotly_dark", paper_bgcolor="#070d14")
                st.plotly_chart(fig_pie_typ, use_container_width=True)
                
            # C. レーダーチャート（戦闘能力評価）
            with c3:
                if global_kpi["battles"] is not None:
                    # 全期間の数値を基準とした相対最大スケール値の算出(上限設定による綺麗に変形するレーダー)
                    r_metrics = ["勝率", "生存率", "与ダメージ", "K/D比", "撃沈数", "経験値"]
                    r_values = [
                        min(100.0, global_kpi["win_rate"] * 1.5) if global_kpi["win_rate"] else 0,
                        min(100.0, global_kpi["survived_rate"] * 1.5) if global_kpi["survived_rate"] else 0,
                        min(150000.0, global_kpi["avg_damage"]) if global_kpi["avg_damage"] else 0,
                        min(5.0, global_kpi["kd"]) if global_kpi["kd"] else 0,
                        min(3.0, global_kpi["avg_frags"] * 2) if global_kpi["avg_frags"] else 0,
                        min(3000.0, global_kpi["avg_xp"]) if global_kpi["avg_xp"] else 0
                    ]
                    # 表示用に実数値を成形
                    r_text = [
                        f"{global_kpi['win_rate']:.1f}%", f"{global_kpi['survived_rate']:.1f}%",
                        f"{int(global_kpi['avg_damage']):,}", f"{global_kpi['kd']:.2f}",
                        f"{global_kpi['avg_frags']:.2f}", f"{int(global_kpi['avg_xp']):,}"
                    ]
                    
                    fig_radar = go.Figure()
                    fig_radar.add_trace(go.Scatterpolar(
                        r=r_values, theta=r_metrics, fill='toself', name='全期間総合',
                        fillcolor='rgba(0, 242, 254, 0.2)', line=dict(color='#00f2fe', width=2),
                        text=r_text, hoverinfo="text+theta"
                    ))
                    fig_radar.update_layout(
                        polar=dict(radialaxis=dict(visible=False), gridshape='polygon'),
                        title="戦闘能力レーダーチャート", template="plotly_dark", paper_bgcolor="#070d14"
                    )
                    st.plotly_chart(fig_radar, use_container_width=True)
                else:
                    st.info("レーダーチャートを構成するデータが不足しています。")
        else:
            st.info("シェア分析を行うための艦艇別詳細スナップショットが存在しません。")

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
        else:
            st.info("選択されたモードにデータがありません。")

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
        else:
            st.info("選択されたモードにデータがありません。")

    # ------------------------------------------
    # Tab 4: 艦艇別詳細データ
    # ------------------------------------------
    with t_ship:
        if not mode_filtered_ship_df.empty:
            l_ships = mode_filtered_ship_df[mode_filtered_ship_df['_SNAPSHOT_DATE'] == mode_filtered_ship_df['_SNAPSHOT_DATE'].max()].copy()
            c_f1, c_f2 = st.columns(2)
            s_nat = c_f1.selectbox("国家で絞り込む", ["すべて"] + list(l_ships['_NATION'].unique()))
            s_typ = c_f2.selectbox("艦種で絞り込む", ["すべて"] + list(l_ships['_SHIP_TYPE'].unique()))
            
            query_df = l_ships.copy()
            if s_nat != "すべて": query_df = query_df[query_df['_NATION'] == s_nat]
            if s_typ != "すべて": query_df = query_df[query_df['_SHIP_TYPE'] == s_typ]
            
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
                sdf = pd.DataFrame(records_list).sort_values(by="戦闘数", ascending=False)
                st.write(sdf.to_html(escape=False, index=False), unsafe_allow_html=True)
        else:
            st.info("選択されたモードに艦艇データがありません。")

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
                ("最高撃沈数", "MAX_FRAGS"), ("最大メイン砲命中", "MAX_MAIN_HIT")
            ]
            for label, col in best_fields:
                if col in l_acc.columns and pd.notna(l_acc[col].iloc[0]):
                    b_records.append({"項目": label, "記録": f"{int(l_acc[col].iloc[0]):,}"})
            if b_records:
                st.dataframe(pd.DataFrame(b_records), width='stretch', hide_index=True)
        else:
            st.info("自己ベストデータが確認できません。")

    # ------------------------------------------
    # Tab 6: クランデータ
    # ------------------------------------------
    with t_clan:
        clan_df = data["clans"]
        if not clan_df.empty:
            l_clan = clan_df[clan_df['_SNAPSHOT_DATE'] == clan_df['_SNAPSHOT_DATE'].max()]
            st.dataframe(l_clan.T, width='stretch')
        else:
            st.info("クランデータ（Clans.csv）がアップロードデータ内にありません。")

if __name__ == '__main__':
    main()
