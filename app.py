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
# 1. ページ初期設定 & カスタムミニマルCSS
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
    
    /* 📋 【表デザイン】イラスト排除・極限までシンプルなシック・グリッド */
    .simple-matrix-container {
        margin: 10px 0 25px 0;
        overflow-x: auto;
        border: 1px solid #2d3748;
        border-radius: 3px;
    }
    .simple-table {
        width: 100%;
        border-collapse: collapse;
        background-color: #0f172a;
        font-size: 0.9rem;
        text-align: left;
    }
    .simple-table th {
        background-color: #1e293b;
        color: #94a3b8;
        font-weight: 600;
        padding: 10px 14px;
        border-bottom: 2px solid #334155;
        font-size: 0.85rem;
        letter-spacing: 0.5px;
    }
    .simple-table td {
        padding: 10px 14px;
        border-bottom: 1px solid #1e293b;
        color: #e2e8f0;
    }
    .simple-table tr:last-child td {
        border-bottom: none;
    }
    .simple-table tr:hover td {
        background-color: #1e293b;
    }
    .simple-indicator-name {
        font-weight: 500;
        color: #94a3b8 !important;
        background-color: #131c2e;
        width: 22%;
        border-right: 1px solid #1e293b;
    }
    .simple-value-lifetime {
        font-weight: 600;
        color: #ffffff;
    }
    .simple-value-period {
        color: #cbd5e1;
    }
    
    /* 調整用小文字テキスト */
    .mode-label-text {
        font-size: 0.85rem;
        color: #94a3b8;
        margin-bottom: 4px;
        font-weight: 500;
    }
</style>
"""
st.markdown(CSS_STYLE, unsafe_allow_html=True)

# ==========================================
# 2. 定数定義 & マッピング定義
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

# ==========================================
# 3. 解析エンジン
# ==========================================
SHIP_TYPE_LETTER_MAP = {
    "b": "戦艦", "c": "巡洋艦", "d": "駆逐艦", "a": "空母"
}

BATTLE_TYPE_CODE_MAP = {
    1: "通常戦", 2: "AI戦", 3: "ランク戦", 4: "イベント戦"
}

def parse_ship_id(vehicle_name: str) -> Tuple[str, str, int]:
    if not isinstance(vehicle_name, str) or len(vehicle_name) < 4:
        return "その他", "その他", 0
        
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
        
    return nation, ship_type, tier

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
        
        if key == "account_stats":
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
        return {"battles": 0, "win_rate": 0.0, "survived_rate": 0.0, "avg_damage": 0.0, "avg_frags": 0.0, "avg_xp": 0.0, "kd": 0.0}
    battles = float(df['BATTLES_COUNT'].sum() if 'BATTLES_COUNT' in df.columns else 0)
    wins = float(df['WINS'].sum() if 'WINS' in df.columns else 0)
    survived = float(df['SURVIVED'].sum() if 'SURVIVED' in df.columns else 0)
    damage = float(df['DAMAGE_DEALT'].sum() if 'DAMAGE_DEALT' in df.columns else 0)
    frags = float(df['FRAGS'].sum() if 'FRAGS' in df.columns else 0)
    xp = float(df['EXP'].sum() if 'EXP' in df.columns else 0)
    deaths = battles - survived
    if deaths <= 0: deaths = 1.0

    return {
        "battles": int(battles), "win_rate": (wins / battles * 100) if battles > 0 else 0.0,
        "survived_rate": (survived / battles * 100) if battles > 0 else 0.0,
        "avg_damage": (damage / battles) if battles > 0 else 0.0,
        "avg_frags": (frags / battles) if battles > 0 else 0.0,
        "avg_xp": (xp / battles) if battles > 0 else 0.0, "kd": (frags / deaths) if battles > 0 else 0.0
    }

def calc_period_diff_metrics(df_new: pd.DataFrame, df_old: pd.DataFrame) -> Dict[str, Any]:
    battles = float(df_new['BATTLES_COUNT'].sum() - df_old['BATTLES_COUNT'].sum())
    if battles <= 0:
        return {"battles": 0, "win_rate": 0.0, "survived_rate": 0.0, "avg_damage": 0.0, "avg_frags": 0.0, "avg_xp": 0.0, "kd": 0.0}
    wins = float(df_new['WINS'].sum() - df_old['WINS'].sum())
    survived = float(df_new['SURVIVED'].sum() - df_old['SURVIVED'].sum())
    damage = float(df_new['DAMAGE_DEALT'].sum() - df_old['DAMAGE_DEALT'].sum())
    frags = float(df_new['FRAGS'].sum() - df_old['FRAGS'].sum())
    xp = float(df_new['EXP'].sum() - df_old['EXP'].sum())
    deaths = battles - survived
    if deaths <= 0: deaths = 1.0

    return {
        "battles": int(max(0, battles)), "win_rate": max(0.0, min(100.0, (wins / battles * 100))) if battles > 0 else 0.0,
        "survived_rate": max(0.0, min(100.0, (survived / battles * 100))) if battles > 0 else 0.0,
        "avg_damage": max(0.0, damage / battles) if battles > 0 else 0.0,
        "avg_frags": max(0.0, frags / battles) if battles > 0 else 0.0,
        "avg_xp": max(0.0, xp / battles) if battles > 0 else 0.0, "kd": max(0.0, frags / deaths) if battles > 0 else 0.0
    }

# ==========================================
# 5. アプリケーションメインルーチン
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
    unique_dates = sorted(list(set(pd.to_datetime(all_dates))))

    ship_df = data["ship_stats"]
    if not ship_df.empty:
        parsed_meta = ship_df['VEHICLE_NAME'].apply(parse_ship_id)
        ship_df['_NATION'] = [x[0] for x in parsed_meta]
        ship_df['_SHIP_TYPE'] = [x[1] for x in parsed_meta]
        ship_df['_ESTIMATED_TIER'] = [x[2] for x in parsed_meta]
        data["ship_stats"] = ship_df

    t_summary, t_ship = st.tabs(["総合戦績 (マトリクス)", "艦艇別詳細データ"])

    # ------------------------------------------
    # Tab 1: 総合戦績（マトリクス表）
    # ------------------------------------------
    with t_summary:
        st.markdown('<div class="mode-label-text">戦闘タイプ選択</div>', unsafe_allow_html=True)
        
        if 'selected_mode_code' not in st.session_state:
            st.session_state.selected_mode_code = 1
            
        m_col1, m_col2, m_col3, m_col4, m_blank = st.columns([1.2, 1.2, 1.2, 1.5, 4])
        with m_col1:
            if st.button("通常戦 (PvP)", use_container_width=True, type="primary" if st.session_state.selected_mode_code == 1 else "secondary"):
                st.session_state.selected_mode_code = 1
                st.rerun()
        with m_col2:
            if st.button("AI戦 (PvE)", use_container_width=True, type="primary" if st.session_state.selected_mode_code == 2 else "secondary"):
                st.session_state.selected_mode_code = 2
                st.rerun()
        with m_col3:
            if st.button("ランク戦", use_container_width=True, type="primary" if st.session_state.selected_mode_code == 3 else "secondary"):
                st.session_state.selected_mode_code = 3
                st.rerun()
        with m_col4:
            if st.button("イベント / アリーナ", use_container_width=True, type="primary" if st.session_state.selected_mode_code == 4 else "secondary"):
                st.session_state.selected_mode_code = 4
                st.rerun()

        selected_mode_code = st.session_state.selected_mode_code
        
        bt_df = data["battle_types"]
        mode_bt_df = bt_df[bt_df['TYPE'] == selected_mode_code] if not bt_df.empty else pd.DataFrame()
        mode_filtered_ship_df = ship_df[ship_df['TYPE'] == selected_mode_code] if not ship_df.empty else pd.DataFrame()
        
        matrix_columns = {}
        
        # 1. 全期間
        if not mode_bt_df.empty:
            latest_snap_date = mode_bt_df['_SNAPSHOT_DATE'].max()
            latest_row = mode_bt_df[mode_bt_df['_SNAPSHOT_DATE'] == latest_snap_date]
            global_kpi = calc_metrics_from_row(latest_row)
        elif not mode_filtered_ship_df.empty:
            latest_snap_date = mode_filtered_ship_df['_SNAPSHOT_DATE'].max()
            latest_row = mode_filtered_ship_df[mode_filtered_ship_df['_SNAPSHOT_DATE'] == latest_snap_date]
            global_kpi = calc_metrics_from_row(latest_row)
        else:
            global_kpi = calc_metrics_from_row(pd.DataFrame())
            
        matrix_columns["全期間"] = (global_kpi, True)
        
        # 2. 期間別差分
        if len(unique_dates) > 1:
            for i in range(len(unique_dates) - 1):
                d_start = unique_dates[i]
                d_end = unique_dates[i+1]
                period_label = f"{d_start.strftime('%Y%m%d')}～{d_end.strftime('%Y%m%d')}"
                
                if not mode_bt_df.empty:
                    df_end_snap = mode_bt_df[mode_bt_df['_SNAPSHOT_DATE'] == d_end]
                    df_start_snap = mode_bt_df[mode_bt_df['_SNAPSHOT_DATE'] == d_start]
                elif not mode_filtered_ship_df.empty:
                    df_end_snap = mode_filtered_ship_df[mode_filtered_ship_df['_SNAPSHOT_DATE'] == d_end]
                    df_start_snap = mode_filtered_ship_df[mode_filtered_ship_df['_SNAPSHOT_DATE'] == d_start]
                else:
                    df_end_snap, df_start_snap = pd.DataFrame(), pd.DataFrame()
                
                if not df_end_snap.empty and not df_start_snap.empty:
                    period_kpi = calc_period_diff_metrics(df_end_snap, df_start_snap)
                else:
                    period_kpi = calc_metrics_from_row(pd.DataFrame())
                    
                matrix_columns[period_label] = (period_kpi, False)

        row_indicators = [
            ("戦闘数", "battles", "{:,}"),
            ("勝率", "win_rate", "{:.2f}%"),
            ("生存率", "survived_rate", "{:.2f}%"),
            ("平均与ダメージ", "avg_damage", "{:,.0f}"),
            ("K/D比", "kd", "{:.2f}"),
            ("平均撃沈数", "avg_frags", "{:.2f}"),
            ("平均経験値", "avg_xp", "{:,.0f}")
        ]
        
        html_table = '<div class="simple-matrix-container"><table class="simple-table"><thead><tr>'
        html_table += '<th>各種データ</th>'
        for col_name in matrix_columns.keys():
            html_table += f'<th>{col_name}</th>'
        html_table += '</tr></thead><tbody>'
        
        for label, key, fmt in row_indicators:
            html_table += f'<tr><td class="simple-indicator-name">{label}</td>'
            for col_name, (kpi, is_lifetime) in matrix_columns.items():
                val = kpi[key]
                formatted_val = fmt.format(val)
                cell_class = "simple-value-lifetime" if is_lifetime else "simple-value-period"
                html_table += f'<td class="{cell_class}">{formatted_val}</td>'
            html_table += '</tr>'
            
        html_table += '</tbody></table></div>'
        st.markdown(html_table, unsafe_allow_html=True)

    # ------------------------------------------
    # Tab 2: 艦艇別データ
    # ------------------------------------------
    with t_ship:
        if not mode_filtered_ship_df.empty:
            l_ships = mode_filtered_ship_df[mode_filtered_ship_df['_SNAPSHOT_DATE'] == mode_filtered_ship_df['_SNAPSHOT_DATE'].max()].copy()
            c_f1, c_f2 = st.columns(2)
            s_nat = c_f1.selectbox("国家", ["すべて"] + list(l_ships['_NATION'].unique()))
            s_typ = c_f2.selectbox("艦種", ["すべて"] + list(l_ships['_SHIP_TYPE'].unique()))
            
            query_df = l_ships.copy()
            if s_nat != "すべて": query_df = query_df[query_df['_NATION'] == s_nat]
            if s_typ != "すべて": query_df = query_df[query_df['_SHIP_TYPE'] == s_typ]
            
            records_list = []
            for _, row in query_df.iterrows():
                row_kpi = calc_metrics_from_row(pd.DataFrame([row]))
                records_list.append({
                    "艦艇名": row['VEHICLE_NAME'], "国家": row['_NATION'], "艦種": row['_SHIP_TYPE'],
                    "戦闘数": row_kpi["battles"], "勝率": f"{row_kpi['win_rate']:.2f}%", "平均与ダメ": int(row_kpi["avg_damage"])
                })
            if records_list:
                st.dataframe(pd.DataFrame(records_list).sort_values(by="戦闘数", ascending=False), width='stretch', hide_index=True)

if __name__ == '__main__':
    main()
