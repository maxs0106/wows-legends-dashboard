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

    /* 📊 総合戦績表：横スクロール・列固定 */
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
        min-width: 160px;
        max-width: 160px;
        width: 160px;
        box-sizing: border-box;
    }
    .matrix-table th.sticky-indicator, .matrix-table td.sticky-indicator {
        position: sticky;
        left: 0;
        background-color: #0f172a !important;
        z-index: 10;
        text-align: left;
        min-width: 180px;
        border-right: 2px solid #00f2fe;
    }
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
</style>
"""
st.markdown(CSS_STYLE, unsafe_allow_html=True)

# ==========================================
# 2. マッピング定義
# ==========================================
CSV_MAPPING = {
    "WOWSL_Game_Sessions.csv":"game_sessions",
    "Clans.csv": "clans",
    "WOWSL_Account_Statistics.csv": "account_stats",
    "WOWSL_Battle_Types_Statistics.csv": "battle_types",
    "WOWSL_Ship_Statistics_By_Type.csv": "ship_stats",
    "Account_Info.csv":"account_info"   
}

IMAGE_NATION_MAP = {
    "a": "アメリカ",
    "j": "日本",
    "b": "イギリス",
    "g": "ドイツ",
    "f": "フランス",
    "r": "ソ連",
    "i": "イタリア",
    "w": "ヨーロッパ",
    "z": "パンアジア",
    "e": "パンヨーロッパ",
    "u": "イギリス連邦",
    "h": "オランダ",
    "n": "オランダ",
    "s": "スペイン",
    "v": "パンアメリカ"
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

# 🌟 ご指定いただいた国家の絶対的な表示順
NATION_ORDER = [
    "アメリカ", "日本", "イギリス", "ドイツ", "フランス", "ソ連", 
    "イタリア", "ヨーロッパ", "パンアジア", "パンヨーロッパ", "パンアメリカ", "オランダ", "スペイン"
]

# ==========================================
# 3. データ処理エンジン（関数群）
# ==========================================
def load_ship_reference():
    # ship_id.csv を読み込み
    df = pd.read_csv("ship_id.csv")
    # id をキー、(名前, Tier) を値とした辞書を作成
    return dict(zip(df['id'], zip(df['name'], df['Tier'])))
    
def parse_ship_id(vehicle_name: str, ship_map: Dict[str, Tuple[str, str]]) -> Tuple[str, str, str, str]:
    # 1. 艦名とティアの取得
    if vehicle_name in ship_map:
        display_name, tier = ship_map[vehicle_name]
    else:
        display_name = vehicle_name # 見つからない場合はそのまま
        tier = "その他"            # ティアはその他

    # 2. 国籍と艦種の判定（既存ロジック）
    low_name = vehicle_name.lower().strip()
    nation, ship_class = "その他", "その他"
    
    if low_name.startswith('p') and len(low_name) >= 4:
        n_code = low_name[1]
        c_code = low_name[3] if low_name[2] == 's' else low_name[2]
        nation = IMAGE_NATION_MAP.get(n_code, "その他")
        ship_class = IMAGE_CLASS_MAP.get(c_code, "その他")
    
    return nation, ship_class, str(tier), display_name

def get_snapshot_date(df: pd.DataFrame, file_name: str) -> datetime:
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
        
        # クランの場合は日付での重複排除を行わない（または別の条件にする）
        if key == 'clans':
            # 日付での排除をせず、全データを保持する
            merged[key] = df_concat.drop_duplicates().reset_index(drop=True)
        else:
            # 他のデータはこれまで通り日付で排除
            df_concat['_SNAPSHOT_DATE'] = pd.to_datetime(df_concat['_SNAPSHOT_DATE'])
            id_cols = ['_SNAPSHOT_DATE']
            if key == 'battle_types': id_cols.append('TYPE')
            if key == 'ship_stats': id_cols.extend(['VEHICLE_NAME', 'TYPE'])
            merged[key] = df_concat.drop_duplicates(subset=id_cols, keep='last')
            
    return merged

def calc_metrics_from_row(df: pd.DataFrame) -> Dict[str, Any]:
    if df.empty or 'BATTLES_COUNT' not in df.columns or df['BATTLES_COUNT'].sum() <= 0:
        return {"battles": None, "win_rate": None, "survived_rate": None, "avg_damage": None, "kd": None, "avg_frags": None, "avg_xp": None}
    b = float(df['BATTLES_COUNT'].sum())
    d = b - float(df['SURVIVED'].sum() if 'SURVIVED' in df.columns else 0)
    return {
        "battles": int(b), "win_rate": (float(df['WINS'].sum()) / b * 100),
        "survived_rate": (float(df['SURVIVED'].sum() if 'SURVIVED' in df.columns else 0) / b * 100),
        "avg_damage": (float(df['DAMAGE_DEALT'].sum() if 'DAMAGE_DEALT' in df.columns else 0) / b),
        "kd": (float(df['FRAGS'].sum() if 'FRAGS' in df.columns else 0) / (1.0 if d <= 0 else d)),
        "avg_frags": (float(df['FRAGS'].sum() if 'FRAGS' in df.columns else 0) / b),
        "avg_xp": (float(df['ORIGINAL_EXP'].sum() if 'EXP' in df.columns else 0) / b)
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
            all_dates.extend(df['_SNAPSHOT_DATE'].dropna().unique().tolist())
    
    if not all_dates:
        st.error("有効な日付データを含むCSVファイルが見つかりません。")
        return
        
    unique_dates = sorted(list(set(pd.to_datetime(all_dates))))

    # 1. 最初にCSVを読み込んで辞書を作成（load_ship_reference関数を使用）
    ship_name_map = load_ship_reference()

    ship_df = data["ship_stats"]
    if not ship_df.empty:
        # 2. lambdaを使って、辞書(ship_name_map)を関数に渡すように変更
        parsed_meta = ship_df['VEHICLE_NAME'].apply(lambda x: parse_ship_id(x, ship_name_map))
        
        # 3. 結果をデータフレームに格納
        ship_df['_NATION'] = [x[0] for x in parsed_meta]
        ship_df['_SHIP_TYPE'] = [x[1] for x in parsed_meta]
        ship_df['_ESTIMATED_TIER'] = [x[2] for x in parsed_meta]
        ship_df['_CLEAN_NAME'] = [x[3] for x in parsed_meta]
        data["ship_stats"] = ship_df

    # ⚓ プレイヤー名・クラン名の堅牢な抽出
    clan_tag, p_name = None, "プレイヤーデータ"
    
    if not data["account_info"].empty:
        l_info = data["account_info"].iloc[-1]
        if 'NICKNAME' in l_info.index and pd.notna(l_info['NICKNAME']): p_name = str(l_info['NICKNAME'])
        
    if p_name == "プレイヤーデータ" and not data["account_stats"].empty:
        l_stats = data["account_stats"].iloc[-1]
        for name_col in ['NICKNAME', 'PLAYER_NAME', 'NAME', 'ACCOUNT_NAME']:
            if name_col in l_stats.index and pd.notna(l_stats[name_col]):
                p_name = str(l_stats[name_col])
                break
                
    # 💡 最新の CREATED_AT に基づき、CLAN_NAME からタグを抽出
    if not data["clans"].empty and 'CREATED_AT' in data["clans"].columns:
        # 1. CREATED_AT でソートして最新の1行を取得
        clan_df = data["clans"].copy()
        clan_df['CREATED_AT'] = pd.to_datetime(clan_df['CREATED_AT'], errors='coerce')
        latest_clan_df = clan_df.sort_values(by='CREATED_AT').dropna(subset=['CREATED_AT']).iloc[-1:]
        
        if not latest_clan_df.empty:
            l_clan = latest_clan_df.iloc[0]
            
            # 2. 優先的に CLAN_NAME 列をチェックし、タグを探す
            # CLAN_NAME に [TAG] のような形式が含まれていることを想定
            target_cols = ['CLAN_NAME', 'CLAN_TAG', 'TAG'] # 念のためタグ系列も探索
            
            for col in target_cols:
                if col in l_clan.index and pd.notna(l_clan[col]):
                    val_str = str(l_clan[col]).strip()
                    
                    # カッコが含まれている場合は中身を抽出 (例: [ABC] -> ABC)
                    if "[" in val_str and "]" in val_str:
                        import re
                        match = re.search(r'\[(.*?)\]', val_str)
                        if match:
                            val_str = match.group(1)
                    
                    # 2～5文字の英数字をタグとして採用
                    if 2 <= len(val_str) <= 20 and val_str.isalnum():
                        clan_tag = val_str
                        break

    player_display_string = f"【{clan_tag}】{p_name}" if clan_tag else p_name

    header_html = f"""
    <div class="game-header-container">
        <div class="game-title">WOWSL Legends Dashboard</div>
        <div class="player-clan-info">
            {player_display_string}
        </div>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)

    t_summary, t_nation, t_type, t_ship, t_best, t_clan = st.tabs([
        "総合戦績 (マトリクス)", "国家別分析", "艦種別分析", "艦艇別詳細", "自己ベスト", "クランデータ"
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

        # STEP2: 部隊形式選択
        st.markdown('<div class="mode-selection-header">■ STEP2: 部隊形式選択</div>', unsafe_allow_html=True)
        
        # モードによってボタンの数を切り替える
        if current_mode in ["クラン戦", "軍記"]:
            team_options = ["総合"]
        else:
            team_options = ["総合", "ソロ", "2人分隊", "3人分隊"]
        
        if 'sel_team' not in st.session_state or st.session_state.sel_team not in team_options:
            st.session_state.sel_team = "総合"
            
        t_cols = st.columns(4) # 常に4列構成にすることで幅を固定
        for idx, t_name in enumerate(team_options):
            with t_cols[idx]:
                if st.button(t_name, key=f"btn_t_{t_name}", use_container_width=True, type="primary" if st.session_state.sel_team == t_name else "secondary"):
                    st.session_state.sel_team = t_name
                    st.rerun()

        # データ抽出ロジック
        if st.session_state.sel_team == "総合":
            target_type_codes = [tid for tid, meta in BATTLE_TYPE_MAP.items() if meta["mode"] == current_mode]
            mode_bt_df = bt_df[bt_df['TYPE'].isin(target_type_codes)] if not bt_df.empty else pd.DataFrame()
            mode_filtered_ship_df = ship_df[ship_df['TYPE'].isin(target_type_codes)] if not ship_df.empty else pd.DataFrame()
        else:
            target_type_code = next((tid for tid, meta in BATTLE_TYPE_MAP.items() 
                                     if meta["mode"] == current_mode and meta["team"] == st.session_state.sel_team), None)
            mode_bt_df = bt_df[bt_df['TYPE'] == target_type_code] if not bt_df.empty and target_type_code else pd.DataFrame()
            mode_filtered_ship_df = ship_df[ship_df['TYPE'] == target_type_code] if not ship_df.empty and target_type_code else pd.DataFrame()

        
        matrix_columns = {}
        if not mode_bt_df.empty:
            global_kpi = calc_metrics_from_row(mode_bt_df[mode_bt_df['_SNAPSHOT_DATE'] == mode_bt_df['_SNAPSHOT_DATE'].max()])
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

        # 📈 推移トレンド
        st.markdown('<div class="chart-section-title">📈 通常戦（総合データ）日程別推移トレンド</div>', unsafe_allow_html=True)
        normal_total_bt = bt_df[bt_df['TYPE'] == 1] if not bt_df.empty else pd.DataFrame()
        trend_records = []
        if not normal_total_bt.empty:
            for d in unique_dates:
                snap_df = normal_total_bt[normal_total_bt['_SNAPSHOT_DATE'] == d]
                if not snap_df.empty:
                    kpi = calc_metrics_from_row(snap_df)
                    if kpi["battles"] is not None:
                        trend_records.append({
                            "日付": d.strftime('%Y/%m/%d'), "勝率": round(kpi["win_rate"], 2),
                            "平均ダメージ": round(kpi["avg_damage"], 0), "平均経験値": round(kpi["avg_xp"], 0)
                        })
                        
        trend_df = pd.DataFrame(trend_records)
        if not trend_df.empty:
            lc1, lc2, lc3 = st.columns(3)
            with lc1:
                f_win = px.line(trend_df, x="日付", y="勝率", markers=True, text=[f"{v}%" for v in trend_df["勝率"]], title="通常戦 勝率推移")
                f_win.update_traces(line_color="#00f2fe", marker=dict(size=7), textposition="top center")
                f_win.update_layout(template="plotly_dark", paper_bgcolor="#070d14", plot_bgcolor="#070d14", yaxis=dict(title="勝率 (%)", gridcolor="#1e293b"))
                st.plotly_chart(f_win, use_container_width=True)
            with lc2:
                f_dmg = px.line(trend_df, x="日付", y="平均ダメージ", markers=True, text=[f"{int(v):,}" for v in trend_df["平均ダメージ"]], title="通常戦 平均ダメージ推移")
                f_dmg.update_traces(line_color="#38bdf8", marker=dict(size=7), textposition="top center")
                f_dmg.update_layout(template="plotly_dark", paper_bgcolor="#070d14", plot_bgcolor="#070d14", yaxis=dict(title="平均ダメージ", gridcolor="#1e293b"))
                st.plotly_chart(f_dmg, use_container_width=True)
            with lc3:
                f_xp = px.line(trend_df, x="日付", y="平均経験値", markers=True, text=[f"{int(v):,}" for v in trend_df["平均経験値"]], title="通常戦 平均経験値推移")
                f_xp.update_traces(line_color="#fbbf24", marker=dict(size=7), textposition="top center")
                f_xp.update_layout(template="plotly_dark", paper_bgcolor="#070d14", plot_bgcolor="#070d14", yaxis=dict(title="平均経験値", gridcolor="#1e293b"))
                st.plotly_chart(f_xp, use_container_width=True)

        # 📊 国家・艦種戦闘数分布
        st.markdown('<div class="chart-section-title">📊 通常戦（総合データ）国籍・艦種戦闘数分布</div>', unsafe_allow_html=True)
        normal_ship_df = ship_df[ship_df['TYPE'] == 1] if not ship_df.empty else pd.DataFrame()
        
        if not normal_ship_df.empty:
            l_date = normal_ship_df['_SNAPSHOT_DATE'].max()
            l_ships_latest = normal_ship_df[normal_ship_df['_SNAPSHOT_DATE'] == l_date]
            sc1, sc2 = st.columns(2)
            
            with sc1:
                nat_data = l_ships_latest.groupby("_NATION")["BATTLES_COUNT"].sum().reset_index()
                # 🌟 ご指定いただいた国家順に完全固定してソート
                nat_data["_NATION"] = pd.Categorical(nat_data["_NATION"], categories=NATION_ORDER, ordered=True)
                nat_data = nat_data.dropna(subset=["_NATION"]).sort_values(by="_NATION", ascending=False)
                
                f_nat_bar = px.bar(nat_data, x="BATTLES_COUNT", y="_NATION", orientation='h', text="BATTLES_COUNT",
                                   title="国家別戦闘数分布 (通常戦)", labels={"BATTLES_COUNT":"戦闘数", "_NATION":"国家"})
                f_nat_bar.update_traces(marker_color="#00f2fe", texttemplate='%{text:,} 戦', textposition='outside', marker_line=dict(width=1, color='#ffffff'))
                f_nat_bar.update_layout(template="plotly_dark", paper_bgcolor="#070d14", plot_bgcolor="#070d14", xaxis=dict(gridcolor="#1e293b", title="総戦闘数"), yaxis=dict(title=""))
                st.plotly_chart(f_nat_bar, use_container_width=True)
                
            with sc2:
                typ_data = l_ships_latest.groupby("_SHIP_TYPE")["BATTLES_COUNT"].sum().reset_index().sort_values(by="BATTLES_COUNT", ascending=True)
                f_typ_bar = px.bar(typ_data, x="BATTLES_COUNT", y="_SHIP_TYPE", orientation='h', text="BATTLES_COUNT",
                                   title="艦種別戦闘数分布 (通常戦)", labels={"BATTLES_COUNT":"戦闘数", "_SHIP_TYPE":"艦種"})
                f_typ_bar.update_traces(marker_color="#38bdf8", texttemplate='%{text:,} 戦', textposition='outside', marker_line=dict(width=1, color='#ffffff'))
                f_typ_bar.update_layout(template="plotly_dark", paper_bgcolor="#070d14", plot_bgcolor="#070d14", xaxis=dict(gridcolor="#1e293b", title="総戦闘数"), yaxis=dict(title=""))
                st.plotly_chart(f_typ_bar, use_container_width=True)

    # ------------------------------------------
    # Tab 2: 国家別分析 (指定順)
    # ------------------------------------------
    with t_nation:
        if not mode_filtered_ship_df.empty:
            l_ships = mode_filtered_ship_df[mode_filtered_ship_df['_SNAPSHOT_DATE'] == mode_filtered_ship_df['_SNAPSHOT_DATE'].max()]
            nat_records = []
            for n in NATION_ORDER:
                sub_df = l_ships[l_ships['_NATION'] == n]
                if not sub_df.empty:
                    kpi = calc_metrics_from_row(sub_df)
                    if kpi["battles"] is not None:
                        nat_records.append({"国家": n, "戦闘数": kpi["battles"], "勝率": f'{kpi["win_rate"]:.2f}%', "平均与ダメ": int(kpi["avg_damage"])})
            if nat_records: st.dataframe(pd.DataFrame(nat_records), width='stretch', hide_index=True)
        else: st.info("データがありません。")

    # ------------------------------------------
    # Tab 3: 艦種別分析
    # ------------------------------------------
    with t_type:
        if not mode_filtered_ship_df.empty:
            l_ships = mode_filtered_ship_df[mode_filtered_ship_df['_SNAPSHOT_DATE'] == mode_filtered_ship_df['_SNAPSHOT_DATE'].max()]
            typ_records = [{"艦種": t, "戦闘数": calc_metrics_from_row(l_ships[l_ships['_SHIP_TYPE'] == t])["battles"], "勝率": f'{calc_metrics_from_row(l_ships[l_ships['_SHIP_TYPE'] == t])["win_rate"]:.2f}%', "平均与ダメ": int(calc_metrics_from_row(l_ships[l_ships['_SHIP_TYPE'] == t])["avg_damage"])} for t in l_ships['_SHIP_TYPE'].unique() if calc_metrics_from_row(l_ships[l_ships['_SHIP_TYPE'] == t])["battles"] is not None]
            if typ_records: st.dataframe(pd.DataFrame(typ_records).sort_values("戦闘数", ascending=False), width='stretch', hide_index=True)
        else: st.info("データがありません。")

    # ------------------------------------------
    # Tab 4: 艦艇別詳細 (指定順)
    # ------------------------------------------
    with t_ship:
        if not mode_filtered_ship_df.empty:
            l_ships = mode_filtered_ship_df[mode_filtered_ship_df['_SNAPSHOT_DATE'] == mode_filtered_ship_df['_SNAPSHOT_DATE'].max()].copy()
            c_f1, c_f2 = st.columns(2)
            
            # 🌟 セレクトボックスの国家選択肢も指定順でソート
            available_nations = [n for n in NATION_ORDER if n in l_ships['_NATION'].unique()]
            s_nat = c_f1.selectbox("国家で絞り込む", ["すべて"] + available_nations)
            s_typ = c_f2.selectbox("艦種で絞り込む", ["すべて"] + list(l_ships['_SHIP_TYPE'].unique()))
            
            mask = pd.Series(True, index=l_ships.index)
            if s_nat != "すべて": mask = mask & (l_ships['_NATION'] == s_nat)
            if s_typ != "すべて": mask = mask & (l_ships['_SHIP_TYPE'] == s_typ)
            query_df = l_ships[mask]
            
            records_list = [{"艦艇名": f'<span class="game-ship-name">{r["_CLEAN_NAME"]}</span>', "国家": r['_NATION'], "艦種": r['_SHIP_TYPE'], "戦闘数": r['BATTLES_COUNT'], "勝率": f"{(r['WINS']/r['BATTLES_COUNT']*100):.2f}%", "平均与ダメ": int(r['DAMAGE_DEALT']/r['BATTLES_COUNT'])} for _, r in query_df.iterrows() if r['BATTLES_COUNT'] > 0]
            if records_list: 
                st.write(pd.DataFrame(records_list).sort_values(by="戦闘数", ascending=False).to_html(escape=False, index=False), unsafe_allow_html=True)
            else: st.info("該当する艦艇データがありません。")
        else: st.info("データがありません。")

    # ------------------------------------------
    # Tab 5: 自己ベスト (柔軟な部分一致スキャン版)
    # ------------------------------------------
    with t_best:
        acc_df = data["account_stats"]
        if not acc_df.empty:
            # 💡 キー名のズレに対応する柔軟なマッピング
            search_rules = [
                ("最高与ダメージ", ["DAMAGE_DEALT", "DAMAGE", "MAX_DAMAGE"]),
                ("最高経験値", ["MAX_EXP", "EXP", "MAXIMUM_EXP"]),
                ("最高撃沈数", ["MAX_FRAGS", "FRAGS", "KILLS"]),
                ("最大メイン砲命中", ["MAX_MAIN_HIT", "MAIN_HIT", "MAIN_BATTERY"])
            ]
            
            b_records = []
            for label, potential_cols in search_rules:
                matched_col = None
                # 完全一致または部分一致するカラムを探す
                for c in acc_df.columns:
                    if any(p in c for p in potential_cols):
                        matched_col = c
                        break
                
                if matched_col:
                    # 強制的に数値化して最大値をスキャン
                    series_num = pd.to_numeric(acc_df[matched_col], errors='coerce').dropna()
                    if not series_num.empty:
                        b_records.append({"項目": label, "記録": f"{int(series_num.max()):,}"})
                        
            if b_records: 
                st.dataframe(pd.DataFrame(b_records), width='stretch', hide_index=True)
            else:
                st.warning("項目データの抽出に失敗しました。CSVのカラム名が変更されている可能性があります。")
        else: 
            st.info("自己ベストデータ（account_stats）が確認できません。")

    # ------------------------------------------
    # Tab 6: クランデータ
    # ------------------------------------------
    with t_clan:
        clan_df = data["clans"]
        if not clan_df.empty: st.dataframe(clan_df[clan_df['_SNAPSHOT_DATE'] == clan_df['_SNAPSHOT_DATE'].max()].T, width='stretch')
        else: st.info("クランデータ（Clans.csv）がありません。")

if __name__ == '__main__':
    main()
