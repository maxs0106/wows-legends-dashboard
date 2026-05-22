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
# 1. ページ初期設定 & UI/UXカスタムCSS
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
        background: radial-gradient(circle at 50% 15%, #0a192f 0%, #020c1b 100%);
        color: #e2e8f0;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    section[data-testid="stSidebar"] {
        background-color: rgba(2, 12, 27, 0.85) !important;
        backdrop-filter: blur(12px);
        border-right: 1px solid rgba(0, 242, 254, 0.2);
    }
    .section-header {
        border-left: 4px solid #00f2fe;
        padding-left: 12px;
        margin-top: 24px;
        margin-bottom: 16px;
        color: #ffffff;
        font-weight: 600;
        font-size: 1.2rem;
    }
    .date-badge {
        background: rgba(0, 242, 254, 0.1);
        border: 1px solid #00f2fe;
        color: #00f2fe;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        display: inline-block;
        margin-bottom: 5px;
    }
    .empty-state {
        background: rgba(10, 25, 47, 0.4);
        border: 2px dashed rgba(0, 242, 254, 0.25);
        border-radius: 12px;
        padding: 60px 20px;
        text-align: center;
        margin: 40px auto;
        max-width: 750px;
    }
    .empty-icon {
        font-size: 4.5rem;
        color: rgba(0, 242, 254, 0.3);
        margin-bottom: 15px;
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

SHIP_TYPE_LETTER_MAP = {
    "b": "戦艦", "c": "巡洋艦", "d": "駆逐艦", "a": "空母"
}

BATTLE_TYPE_CODE_MAP = {
    1: "通常戦", 2: "AI戦", 3: "ランク戦", 4: "イベント戦"
}

# ==========================================
# 3. 解析エンジン
# ==========================================
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
                matched_count = 0
                
                snapshot_date = date.today()
                date_matches = re.findall(r'\d{4}-\d{2}-\d{2}', up_file.name)
                if date_matches:
                    snapshot_date = datetime.strptime(date_matches[0], '%Y-%m-%d').date()
                else:
                    # ファイル名に日付がない場合は、内部のCSVの最終更新日時等から推測
                    snapshot_date = date.today()
                
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
                            df['_SNAPSHOT_DATE'] = pd.to_datetime(snapshot_date)
                            all_data[key].append(df)
                            matched_count += 1
                            
                if matched_count > 0:
                    success_zips.append(f"{up_file.name} ({matched_count}個のCSVを検出)")
                else:
                    errors.append(f"{up_file.name}: 有効なWoWsLファイル構造が見つかりません。")
        except Exception as e:
            errors.append(f"{up_file.name}の処理エラー: {str(e)}")
            
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
        elif key == "clans":
            df_concat = df_concat.drop_duplicates(keep='first')
            
        merged[key] = df_concat
    return merged

# ==========================================
# 4. アナリティクス計算関数
# ==========================================
def calc_metrics_from_row(df: pd.DataFrame) -> Dict[str, Any]:
    if df.empty:
        return {"battles": 0, "win_rate": 0.0, "survived_rate": 0.0, "avg_damage": 0.0, "avg_frags": 0.0, "avg_xp": 0.0, "kd": 0.0, "avg_tier": 5.0}
    
    battles = float(df['BATTLES_COUNT'].sum() if 'BATTLES_COUNT' in df.columns else 0)
    wins = float(df['WINS'].sum() if 'WINS' in df.columns else 0)
    survived = float(df['SURVIVED'].sum() if 'SURVIVED' in df.columns else 0)
    damage = float(df['DAMAGE_DEALT'].sum() if 'DAMAGE_DEALT' in df.columns else 0)
    frags = float(df['FRAGS'].sum() if 'FRAGS' in df.columns else 0)
    xp = float(df['EXP'].sum() if 'EXP' in df.columns else 0)
    
    deaths = battles - survived
    if deaths <= 0: deaths = 1.0
    
    avg_tier = 5.0
    if '_ESTIMATED_TIER' in df.columns and battles > 0:
        avg_tier = float((df['_ESTIMATED_TIER'] * df['BATTLES_COUNT']).sum() / battles)

    return {
        "battles": int(battles),
        "win_rate": (wins / battles * 100) if battles > 0 else 0.0,
        "survived_rate": (survived / battles * 100) if battles > 0 else 0.0,
        "avg_damage": (damage / battles) if battles > 0 else 0.0,
        "avg_frags": (frags / battles) if battles > 0 else 0.0,
        "avg_xp": (xp / battles) if battles > 0 else 0.0,
        "kd": (frags / deaths) if battles > 0 else 0.0,
        "avg_tier": avg_tier
    }

# 指定された新旧データ行から「期間内の純粋な差分戦績」を算出する関数
def calc_period_diff_metrics(df_new: pd.DataFrame, df_old: pd.DataFrame) -> Dict[str, Any]:
    battles = float(df_new['BATTLES_COUNT'].sum() - df_old['BATTLES_COUNT'].sum())
    if battles <= 0:
        return {"battles": 0, "win_rate": 0.0, "survived_rate": 0.0, "avg_damage": 0.0, "avg_frags": 0.0, "avg_xp": 0.0, "kd": 0.0, "avg_tier": 5.0}
        
    wins = float(df_new['WINS'].sum() - df_old['WINS'].sum())
    survived = float(df_new['SURVIVED'].sum() - df_old['SURVIVED'].sum())
    damage = float(df_new['DAMAGE_DEALT'].sum() - df_old['DAMAGE_DEALT'].sum())
    frags = float(df_new['FRAGS'].sum() - df_old['FRAGS'].sum())
    xp = float(df_new['EXP'].sum() - df_old['EXP'].sum())
    
    deaths = battles - survived
    if deaths <= 0: deaths = 1.0
    
    avg_tier = 5.0
    if '_ESTIMATED_TIER' in df_new.columns and 'BATTLES_COUNT' in df_new.columns:
        # 新しい側の推定Tierを基準に割り当て
        avg_tier = float((df_new['_ESTIMATED_TIER'] * df_new['BATTLES_COUNT']).sum() / df_new['BATTLES_COUNT'].sum()) if df_new['BATTLES_COUNT'].sum() > 0 else 5.0

    return {
        "battles": int(max(0, battles)),
        "win_rate": max(0.0, min(100.0, (wins / battles * 100))) if battles > 0 else 0.0,
        "survived_rate": max(0.0, min(100.0, (survived / battles * 100))) if battles > 0 else 0.0,
        "avg_damage": max(0.0, damage / battles) if battles > 0 else 0.0,
        "avg_frags": max(0.0, frags / battles) if battles > 0 else 0.0,
        "avg_xp": max(0.0, xp / battles) if battles > 0 else 0.0,
        "kd": max(0.0, frags / deaths) if battles > 0 else 0.0,
        "avg_tier": avg_tier
    }

# ==========================================
# 6. メインコントロール
# ==========================================
def main():
    st.title("⚓ WoWs Legends 高級戦績ダッシュボード")
    st.markdown("`Fleet Intelligence Platform` | ⏱️ 期間設定: **ファイル自動解析（全期間 ＆ 各期間の差分表示）**")
    
    st.sidebar.header("📁 データインポート")
    uploaded_files = st.sidebar.file_uploader(
        "ZIPデータダンプの投入 (複数可)", 
        type="zip", 
        accept_multiple_files=True
    )
    
    if not uploaded_files:
        st.markdown(
            """
            <div class="empty-state">
                <div class="empty-icon">⚓</div>
                <h3>データダンプが読み込まれていません</h3>
                <p style="color: #94a3b8; max-width: 550px; margin: 0 auto 20px auto;">
                    World of Warships: Legends公式サイトからダウンロードした個人データエクスポートのZIPアーカイブを複数まとめてサイドバーにドラッグ＆ドロップしてください。
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
        return

    with st.spinner("📦 データマイニング及びメタ解析を実行中..."):
        raw_data, success_zips, errors = extract_zip_data(uploaded_files)
        data = merge_and_optimize(raw_data)
        
    with st.sidebar.expander("📊 解析メタデータ一覧", expanded=False):
        st.caption(f"読み込み成功ZIP: {len(success_zips)}件")
        if errors:
            st.error("エラー一覧:")
            for e in errors: st.caption(e)

    # 💡 ファイルから検出されたすべての日付をソートして抽出
    all_dates = []
    for df in data.values():
        if not df.empty and '_SNAPSHOT_DATE' in df.columns:
            all_dates.extend(df['_SNAPSHOT_DATE'].unique().tolist())
    
    # 重複を排除して昇順にソート
    unique_dates = sorted(list(set(pd.to_datetime(all_dates))))
    
    if unique_dates:
        st.sidebar.markdown("---")
        st.sidebar.markdown("📅 **検出されたスナップショット基準日:**")
        for d in unique_dates:
            st.sidebar.markdown(f'<div class="date-badge">⏱️ {d.strftime("%Y-%m-%d")}</div>', unsafe_allow_html=True)

    ship_df = data["ship_stats"]
    if not ship_df.empty:
        parsed_meta = ship_df['VEHICLE_NAME'].apply(parse_ship_id)
        ship_df['_NATION'] = [x[0] for x in parsed_meta]
        ship_df['_SHIP_TYPE'] = [x[1] for x in parsed_meta]
        ship_df['_ESTIMATED_TIER'] = [x[2] for x in parsed_meta]
        data["ship_stats"] = ship_df

    # 🕹️ 【ご要望】戦闘タイプ（モード）選択を画像のUI仕様へ変更
    st.markdown('<div class="section-header">🕹️ 戦闘タイプ (BATTLE TYPE) 選択</div>', unsafe_allow_html=True)
    
    if 'selected_mode_code' not in st.session_state:
        st.session_state.selected_mode_code = 1 # デフォルトは通常戦
        
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    
    with m_col1:
        is_active = "👉 " if st.session_state.selected_mode_code == 1 else ""
        if st.button(f"{is_active}通常戦 (PvP)", use_container_width=True, type="primary" if st.session_state.selected_mode_code == 1 else "secondary"):
            st.session_state.selected_mode_code = 1
            st.rerun()
            
    with m_col2:
        is_active = "👉 " if st.session_state.selected_mode_code == 2 else ""
        if st.button(f"{is_active}AI戦 (PvE)", use_container_width=True, type="primary" if st.session_state.selected_mode_code == 2 else "secondary"):
            st.session_state.selected_mode_code = 2
            st.rerun()
            
    with m_col3:
        is_active = "👉 " if st.session_state.selected_mode_code == 3 else ""
        if st.button(f"{is_active}ランク戦", use_container_width=True, type="primary" if st.session_state.selected_mode_code == 3 else "secondary"):
            st.session_state.selected_mode_code = 3
            st.rerun()
            
    with m_col4:
        is_active = "👉 " if st.session_state.selected_mode_code == 4 else ""
        if st.button(f"{is_active}イベント戦 / アリーナ", use_container_width=True, type="primary" if st.session_state.selected_mode_code == 4 else "secondary"):
            st.session_state.selected_mode_code = 4
            st.rerun()

    selected_mode_code = st.session_state.selected_mode_code
    target_mode_str = BATTLE_TYPE_CODE_MAP.get(selected_mode_code, "通常戦")

    t_summary, t_mode, t_nation, t_ship, t_records, t_clan = st.tabs([
        "📈 期間マトリクス・総合戦績", "⚔️ 戦闘モード全体一覧", "🌍 国家・艦種", "🚢 艦艇別データ", "🏆 自己ベスト", "🛡️ クラン履歴"
    ])

    # ------------------------------------------
    # Tab 1: 総合戦績（期間マトリクス表）
    # ------------------------------------------
    with t_summary:
        st.markdown(f'<div class="section-header">🏆 期間別マトリクス・スタッツ表 ({target_mode_str})</div>', unsafe_allow_html=True)
        
        # 該当戦闘モードのデータ抽出
        bt_df = data["battle_types"]
        mode_bt_df = bt_df[bt_df['TYPE'] == selected_mode_code] if not bt_df.empty else pd.DataFrame()
        mode_filtered_ship_df = ship_df[ship_df['TYPE'] == selected_mode_code] if not ship_df.empty else pd.DataFrame()
        
        # マトリクスに格納するコラム辞書を定義
        matrix_columns = {}
        
        # 1️⃣ 【全期間】最新ファイルの生涯データを計算
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
            
        matrix_columns["全期間 (Lifetime)"] = global_kpi
        
        # 2️⃣ 【各CSVの期間別（差分）】日付が複数ある場合に動的に列を生成
        if len(unique_dates) > 1:
            # 日付を逆順にして、新しい期間から順に表示されるようにループを構成
            for i in range(len(unique_dates) - 1, 0, -1):
                d_end = unique_dates[i]
                d_start = unique_dates[i-1]
                
                period_label = f"{d_start.strftime('%Y%m%d')} 〜 {d_end.strftime('%Y%m%d')}"
                
                # それぞれの日付のデータを抽出
                if not mode_bt_df.empty:
                    df_end_snap = mode_bt_df[mode_bt_df['_SNAPSHOT_DATE'] == d_end]
                    df_start_snap = mode_bt_df[mode_bt_df['_SNAPSHOT_DATE'] == d_start]
                elif not mode_filtered_ship_df.empty:
                    df_end_snap = mode_filtered_ship_df[mode_filtered_ship_df['_SNAPSHOT_DATE'] == d_end]
                    df_start_snap = mode_filtered_ship_df[mode_filtered_ship_df['_SNAPSHOT_DATE'] == d_start]
                else:
                    df_end_snap, df_start_snap = pd.DataFrame(), pd.DataFrame()
                
                # 差分計算
                if not df_end_snap.empty and not df_start_snap.empty:
                    period_kpi = calc_period_diff_metrics(df_end_snap, df_start_snap)
                else:
                    period_kpi = calc_metrics_from_row(pd.DataFrame())
                    
                matrix_columns[period_label] = period_kpi

        # 💡 【重要】一つの戦闘タイプを一つの表に統合（縦軸に各種データ、横軸に期間）
        row_names = [
            "⚔️ 総戦闘数", 
            "🏆 総合勝率", 
            "🛡️ 生存率", 
            "💥 平均与ダメージ", 
            "💀 K/D 比", 
            "🎯 平均撃沈数", 
            "⭐ 平均取得経験値"
        ]
        
        table_data = {col_name: [] for col_name in matrix_columns.keys()}
        
        for col_name, kpi in matrix_columns.items():
            table_data[col_name].append(f"{kpi['battles']:,} 戦")
            table_data[col_name].append(f"{kpi['win_rate']:.2f} %")
            table_data[col_name].append(f"{kpi['survived_rate']:.2f} %")
            table_data[col_name].append(f"{int(kpi['avg_damage']):,} ダメージ")
            table_data[col_name].append(f"{kpi['kd']:.2f}")
            table_data[col_name].append(f"{kpi['avg_frags']:.2f} 隻")
            table_data[col_name].append(f"{int(kpi['avg_xp']):,}")
            
        matrix_df = pd.DataFrame(table_data, index=row_names)
        
        # 表示用のインデックス列名を設定
        matrix_df.index.name = "戦績インジケーター"
        st.dataframe(matrix_df, width='stretch')

        # 📈 可視化トレンド表示
        if not mode_filtered_ship_df.empty and len(mode_filtered_ship_df['_SNAPSHOT_DATE'].unique()) > 1:
            st.markdown(f'<div class="section-header">📈 パフォーマンス成長トレンド (時系列履歴グラフ)</div>', unsafe_allow_html=True)
            trend_data = []
            for d, group in mode_filtered_ship_df.groupby('_SNAPSHOT_DATE'):
                metrics_d = calc_metrics_from_row(group)
                metrics_d['date'] = d
                trend_data.append(metrics_d)
                
            td_df = pd.DataFrame(trend_data)
            metric_selector = st.selectbox(
                "表示する指標を変更", 
                ["win_rate", "avg_damage", "avg_xp", "kd"],
                format_func=lambda x: {"win_rate":"勝率 (%)", "avg_damage":"平均与ダメージ", "avg_xp":"平均取得経験値", "kd":"K/D 比"}[x]
            )
            fig = px.line(td_df, x='date', y=metric_selector, markers=True, color_discrete_sequence=['#00f2fe'])
            fig.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(10,25,47,0.4)')
            st.plotly_chart(fig, width='stretch')

    # ------------------------------------------
    # Tab 2: 戦闘モード別全体一覧
    # ------------------------------------------
    with t_mode:
        st.markdown('<div class="section-header">⚔️ 全戦闘モードのスタッツ一覧</div>', unsafe_allow_html=True)
        if not bt_df.empty:
            bt_latest = bt_df[bt_df['_SNAPSHOT_DATE'] == bt_df['_SNAPSHOT_DATE'].max()]
            mode_analytics = []
            for code, name in BATTLE_TYPE_CODE_MAP.items():
                m_row = bt_latest[bt_latest['TYPE'].astype(str) == str(code)]
                if not m_row.empty:
                    m_kpi = calc_metrics_from_row(m_row)
                    m_kpi['モード'] = name
                    mode_analytics.append(m_kpi)
                    
            if mode_analytics:
                ma_df = pd.DataFrame(mode_analytics)
                disp_rows = []
                for _, r in ma_df.iterrows():
                    disp_rows.append({
                        "戦闘モード": r["モード"], "戦闘数": int(r["battles"]), "勝率": f"{r['win_rate']:.2f}%",
                        "生存率": f"{r['survived_rate']:.2f}%", "K/D": f"{r['kd']:.2f}", "平均与ダメージ": f"{int(r['avg_damage']):,}"
                    })
                st.dataframe(pd.DataFrame(disp_rows), width='stretch', hide_index=True)
        else:
            st.info("WOWSL_Battle_Types_Statistics.csv が見つかりません。")

    # ------------------------------------------
    # Tab 3: 国家・艦種分析
    # ------------------------------------------
    with t_nation:
        st.markdown(f'<div class="section-header">🌍 国家別 × 艦種別 分析 ({target_mode_str})</div>', unsafe_allow_html=True)
        if not mode_filtered_ship_df.empty:
            latest_s = mode_filtered_ship_df[mode_filtered_ship_df['_SNAPSHOT_DATE'] == mode_filtered_ship_df['_SNAPSHOT_DATE'].max()]
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                st.subheader("艦種別出撃パイチャート")
                t_sum = latest_s.groupby('_SHIP_TYPE').sum(numeric_only=True).reset_index()
                fig_t = px.pie(t_sum, values='BATTLES_COUNT', names='_SHIP_TYPE', hole=0.4, color_discrete_sequence=px.colors.sequential.Electric)
                fig_t.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_t, width='stretch')
            with col_g2:
                st.subheader("国家別戦闘数ランキング")
                n_sum = latest_s.groupby('_NATION').sum(numeric_only=True).reset_index().sort_values(by='BATTLES_COUNT', ascending=False)
                fig_n = px.bar(n_sum, x='_NATION', y='BATTLES_COUNT', color='BATTLES_COUNT', color_continuous_scale='electric')
                fig_n.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_n, width='stretch')

    # ------------------------------------------
    # Tab 4: 艦艇別データ
    # ------------------------------------------
    with t_ship:
        st.markdown(f'<div class="section-header">🚢 艦艇マスタデータ・ソートマトリクス ({target_mode_str})</div>', unsafe_allow_html=True)
        if not mode_filtered_ship_df.empty:
            l_ships = mode_filtered_ship_df[mode_filtered_ship_df['_SNAPSHOT_DATE'] == mode_filtered_ship_df['_SNAPSHOT_DATE'].max()].copy()
            c_f1, c_f2, c_f3 = st.columns(3)
            s_nat = c_f1.selectbox("国家フィルタ", ["すべて"] + list(l_ships['_NATION'].unique()))
            s_typ = c_f2.selectbox("艦種フィルタ", ["すべて"] + list(l_ships['_SHIP_TYPE'].unique()))
            s_tier = c_f3.selectbox("ティアフィルタ", ["すべて"] + sorted([int(x) for x in l_ships['_ESTIMATED_TIER'].unique()]))
            
            search_str = st.text_input("🔍 艦艇識別名でのリアルタイムクイック検索", "")
            query_df = l_ships.copy()
            if s_nat != "すべて": query_df = query_df[query_df['_NATION'] == s_nat]
            if s_typ != "すべて": query_df = query_df[query_df['_SHIP_TYPE'] == s_typ]
            if s_tier != "すべて": query_df = query_df[query_df['_ESTIMATED_TIER'] == int(s_tier)]
            if search_str: query_df = query_df[query_df['VEHICLE_NAME'].str.contains(search_str, case=False, na=False)]
            
            records_list = []
            for _, row in query_df.iterrows():
                row_kpi = calc_metrics_from_row(pd.DataFrame([row]))
                records_list.append({
                    "艦艇識別名": row['VEHICLE_NAME'], "国家": row['_NATION'], "艦種": row['_SHIP_TYPE'], "推定Tier": row['_ESTIMATED_TIER'],
                    "戦闘数": row_kpi["battles"], "勝率": f"{row_kpi['win_rate']:.2f}%", "平均与ダメ": int(row_kpi["avg_damage"]),
                    "K/D": round(row_kpi["kd"], 2), "生存率": f"{row_kpi['survived_rate']:.2f}%"
                })
            if records_list:
                st.dataframe(pd.DataFrame(records_list).sort_values(by="戦闘数", ascending=False), width='stretch', hide_index=True)

    # ------------------------------------------
    # Tab 5: 自己ベスト
    # ------------------------------------------
    with t_records:
        st.markdown(f'<div class="section-header">🔥 記録：パーソナル最高スコア ({target_mode_str})</div>', unsafe_allow_html=True)
        if not mode_filtered_ship_df.empty:
            l_ships = mode_filtered_ship_df[mode_filtered_ship_df['_SNAPSHOT_DATE'] == mode_filtered_ship_df['_SNAPSHOT_DATE'].max()]
            records_map = {"MAX_DAMAGE_DEALT": "💥 最大与ダメージ", "MAX_FRAGS": "💀 最大撃沈数", "MAX_EXP": "⭐ 最大取得経験値"}
            cx1, cx2 = st.columns(2)
            toggle = True
            for col_col, label in records_map.items():
                if col_col in l_ships.columns and not l_ships[col_col].dropna().empty:
                    idx = l_ships[col_col].idxmax()
                    best_row = l_ships.loc[idx]
                    target_c = cx1 if toggle else cx2
                    toggle = not toggle
                    with target_c:
                        st.markdown(
                            f'<div style="background: rgba(0, 242, 254, 0.04); border: 1px solid rgba(0, 242, 254, 0.3); border-radius: 8px; padding: 20px; margin-bottom: 15px;">'
                            f'<div style="color: #00f2fe; font-size: 0.85rem; font-weight: 600;">{label}</div>'
                            f'<div style="font-size: 2.2rem; font-weight: 700; color: #ffffff; margin: 8px 0;">{best_row[col_col]:,.0f}</div>'
                            f'<div style="font-size: 0.85rem; color: #94a3b8;">使用艦艇: <span style="color: #ffffff;">{best_row["VEHICLE_NAME"]}</span></div>'
                            f'</div>', unsafe_allow_html=True
                        )

    # ------------------------------------------
    # Tab 6: クラン履歴
    # ------------------------------------------
    with t_clan:
        st.markdown('<div class="section-header">🛡️ クランアクション・所属タイムライン</div>', unsafe_allow_html=True)
        clan_df = data["clans"]
        if not clan_df.empty:
            time_col = 'CREATED_AT' if 'CREATED_AT' in clan_df.columns else '_SNAPSHOT_DATE'
            clan_df[time_col] = pd.to_datetime(clan_df[time_col])
            for _, row in clan_df.sort_values(by=time_col, ascending=False).iterrows():
                op = str(row.get('OPERATION_NAME', 'unknown')).lower()
                c_tag = row.get('CLAN_NAME', 'クラン')
                t_stamp = row[time_col].strftime('%Y-%m-%d %H:%M')
                badge_text = f"🔷 アクション: {op} [{c_tag}]"
                if "join" in op: badge_text = f"🟢 クラン [{c_tag}] に加入しました"
                elif "leave" in op: badge_text = f"🔴 クラン [{c_tag}] から脱退しました"
                st.markdown(f'<div style="border-left: 4px solid #3b82f6; background: rgba(255,255,255,0.02); padding: 12px; margin-bottom: 10px;">[{t_stamp}] {badge_text}</div>', unsafe_allow_html=True)

if __name__ == '__main__':
    main()
