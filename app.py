import io
import os
import re
from datetime import datetime, date, timedelta
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
    .kpi-card {
        background: rgba(10, 25, 47, 0.65);
        border: 1px solid rgba(0, 242, 254, 0.25);
        border-radius: 8px;
        padding: 18px;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4), inset 0 0 12px rgba(0, 242, 254, 0.05);
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
        margin-bottom: 12px;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        border-color: rgba(0, 242, 254, 0.7);
        box-shadow: 0 6px 25px rgba(0, 242, 254, 0.25);
    }
    .kpi-title {
        font-size: 0.8rem;
        color: #00f2fe;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        margin-bottom: 6px;
    }
    .kpi-value {
        font-size: 1.65rem;
        font-weight: 700;
        color: #ffffff;
        text-shadow: 0 0 8px rgba(0, 242, 254, 0.4);
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
        elif key == "ship_stats" and 'VEHICLE_NAME' in df_concat.columns:
            df_concat = df_concat.drop_duplicates(subset=['_SNAPSHOT_DATE', 'VEHICLE_NAME'], keep='last')
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

# ==========================================
# 5. UIプレゼンテーション層
# ==========================================
def render_kpi_block(metrics: Dict[str, Any]):
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="kpi-card"><div class="kpi-title">⚔️ 総戦闘数</div><div class="kpi-value">{metrics["battles"]:,}</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="kpi-card"><div class="kpi-title">🏆 総合勝率</div><div class="kpi-value">{metrics["win_rate"]:.2f}%</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="kpi-card"><div class="kpi-title">🛡️ 生存率</div><div class="kpi-value">{metrics["survived_rate"]:.2f}%</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="kpi-card"><div class="kpi-title">💀 K/D 比</div><div class="kpi-value">{metrics["kd"]:.2f}</div></div>', unsafe_allow_html=True)

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        st.markdown(f'<div class="kpi-card"><div class="kpi-title">💥 平均与ダメージ</div><div class="kpi-value">{metrics["avg_damage"]:,.0f}</div></div>', unsafe_allow_html=True)
    with c6:
        st.markdown(f'<div class="kpi-card"><div class="kpi-title">🎯 平均撃沈数</div><div class="kpi-value">{metrics["avg_frags"]:.2f}</div></div>', unsafe_allow_html=True)
    with c7:
        st.markdown(f'<div class="kpi-card"><div class="kpi-title">⭐ 平均取得経験値</div><div class="kpi-value">{metrics["avg_xp"]:,.0f}</div></div>', unsafe_allow_html=True)
    with c8:
        st.markdown(f'<div class="kpi-card"><div class="kpi-title">⚓ 平均戦闘ティア</div><div class="kpi-value">{metrics["avg_tier"]:.1f}</div></div>', unsafe_allow_html=True)

# ==========================================
# 6. メインコントロール
# ==========================================
def main():
    st.title("⚓ WoWs Legends 高級戦績ダッシュボード")
    st.markdown("`Production-Ready Data Platform`")
    
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
                    World of Warships: Legends公式サイトからダウンロードした個人データエクスポートのZIPアーカイブをそのままサイドバーにドラッグ＆ドロップしてください。
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

    ship_df = data["ship_stats"]
    if not ship_df.empty:
        parsed_meta = ship_df['VEHICLE_NAME'].apply(parse_ship_id)
        ship_df['_NATION'] = [x[0] for x in parsed_meta]
        ship_df['_SHIP_TYPE'] = [x[1] for x in parsed_meta]
        ship_df['_ESTIMATED_TIER'] = [x[2] for x in parsed_meta]
        data["ship_stats"] = ship_df

    all_dates = []
    for df in data.values():
        if not df.empty and '_SNAPSHOT_DATE' in df.columns:
            all_dates.extend(df['_SNAPSHOT_DATE'].tolist())
            
    min_d, max_d = (min(all_dates).date(), max(all_dates).date()) if all_dates else (date.today(), date.today())
    
    st.sidebar.markdown("---")
    st.sidebar.header("⏱️ 分析対象期間")
    preset = st.sidebar.selectbox("期間プリセット", ["全期間", "今日", "7日間", "30日間", "90日間", "カスタム"])
    
    start_d, end_d = min_d, max_d
    if preset == "今日": start_d = max_d
    elif preset == "7日間": start_d = max(min_d, max_d - timedelta(days=7))
    elif preset == "30日間": start_d = max(min_d, max_d - timedelta(days=30))
    elif preset == "90日間": start_d = max(min_d, max_d - timedelta(days=90))
    elif preset == "カスタム":
        c_d1, c_d2 = st.sidebar.columns(2)
        start_d = c_d1.date_input("開始", min_d, min_value=min_d, max_value=max_d)
        end_d = c_d2.date_input("終了", max_d, min_value=min_d, max_value=max_d)

    st.sidebar.info(f"📅 スコープ: {start_d} 〜 {end_d}")

    t_summary, t_mode, t_nation, t_ship, t_records, t_clan = st.tabs([
        "📈 総合戦績・推移", "⚔️ 戦闘モード", "🌍 国家・艦種", "🚢 艦艇別データ", "🏆 自己ベスト", "🛡️ クラン履歴"
    ])

    # ------------------------------------------
    # Tab 1: 総合戦績・推移
    # ------------------------------------------
    with t_summary:
        st.markdown('<div class="section-header">🏆 指定期間の総合パフォーマンス</div>', unsafe_allow_html=True)
        
        if not ship_df.empty:
            f_ship = ship_df[(ship_df['_SNAPSHOT_DATE'].dt.date >= start_d) & (ship_df['_SNAPSHOT_DATE'].dt.date <= end_d)]
            
            if not f_ship.empty:
                max_date_in_f = f_ship['_SNAPSHOT_DATE'].max()
                min_date_in_f = f_ship['_SNAPSHOT_DATE'].min()
                
                df_max_snap = f_ship[f_ship['_SNAPSHOT_DATE'] == max_date_in_f]
                df_min_snap = f_ship[f_ship['_SNAPSHOT_DATE'] == min_date_in_f]
                
                if max_date_in_f == min_date_in_f or len(f_ship['_SNAPSHOT_DATE'].unique()) == 1:
                    global_kpi = calc_metrics_from_row(df_max_snap)
                else:
                    v_max = df_max_snap.set_index('VEHICLE_NAME')
                    v_min = df_min_snap.set_index('VEHICLE_NAME')
                    
                    common_ships = v_max.index.intersection(v_min.index)
                    diff_rows = []
                    for s in common_ships:
                        r_max = v_max.loc[s]
                        r_min = v_min.loc[s]
                        diff_rows.append({
                            'BATTLES_COUNT': max(0, r_max['BATTLES_COUNT'] - r_min['BATTLES_COUNT']),
                            'WINS': max(0, r_max['WINS'] - r_min['WINS']),
                            'SURVIVED': max(0, r_max['SURVIVED'] - r_min['SURVIVED']),
                            'DAMAGE_DEALT': max(0, r_max['DAMAGE_DEALT'] - r_min['DAMAGE_DEALT']),
                            'FRAGS': max(0, r_max['FRAGS'] - r_min['FRAGS']),
                            'EXP': max(0, r_max['EXP'] - r_min['EXP']),
                            '_ESTIMATED_TIER': r_max['_ESTIMATED_TIER']
                        })
                    new_ships = v_max.index.difference(v_min.index)
                    for s in new_ships:
                        r_max = v_max.loc[s]
                        diff_rows.append({
                            'BATTLES_COUNT': r_max['BATTLES_COUNT'], 'WINS': r_max['WINS'],
                            'SURVIVED': r_max['SURVIVED'], 'DAMAGE_DEALT': r_max['DAMAGE_DEALT'],
                            'FRAGS': r_max['FRAGS'], 'EXP': r_max['EXP'], '_ESTIMATED_TIER': r_max['_ESTIMATED_TIER']
                        })
                        
                    if diff_rows:
                        global_kpi = calc_metrics_from_row(pd.DataFrame(diff_rows))
                    else:
                        global_kpi = calc_metrics_from_row(df_max_snap)
                        
                render_kpi_block(global_kpi)
            else:
                st.info("選択された期間のデータスナップショットがありません。")
        else:
            acc_df = data["account_stats"]
            if not acc_df.empty:
                render_kpi_block(calc_metrics_from_row(acc_df))
            else:
                st.warning("戦績計算に必要なCSVファイルが不足しています。")

        st.markdown('<div class="section-header">📈 パフォーマンス成長トレンド (時系列推移)</div>', unsafe_allow_html=True)
        if not ship_df.empty and len(ship_df['_SNAPSHOT_DATE'].unique()) > 1:
            trend_data = []
            for d, group in ship_df.groupby('_SNAPSHOT_DATE'):
                metrics_d = calc_metrics_from_row(group)
                metrics_d['date'] = d
                trend_data.append(metrics_d)
                
            td_df = pd.DataFrame(trend_data)
            
            metric_selector = st.selectbox(
                "可視化インジケーターの変更", 
                ["win_rate", "avg_damage", "avg_xp", "kd", "survived_rate"],
                format_func=lambda x: {"win_rate":"勝率 (%)", "avg_damage":"平均与ダメージ", "avg_xp":"平均取得経験値", "kd":"K/D 比", "survived_rate":"生存率 (%)"}[x]
            )
            
            fig = px.line(td_df, x='date', y=metric_selector, markers=True, color_discrete_sequence=['#00f2fe'])
            fig.update_layout(
                template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(10,25,47,0.4)',
                xaxis_title="記録日", yaxis_title=metric_selector, hovermode="x unified"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("💡 異なる日付のZIPファイルを2つ以上読み込ませることで、自動的に時系列推移グラフが生成されます。")

    # ------------------------------------------
    # Tab 2: 戦闘モード別分析
    # ------------------------------------------
    with t_mode:
        st.markdown('<div class="section-header">⚔️ 戦闘モード別スタッツ</div>', unsafe_allow_html=True)
        bt_df = data["battle_types"]
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
                        "戦闘モード": r["モード"],
                        "戦闘数": int(r["battles"]),
                        "勝率": f"{r['win_rate']:.2f}%",
                        "生存率": f"{r['survived_rate']:.2f}%",
                        "K/D": f"{r['kd']:.2f}",
                        "平均与ダメージ": f"{int(r['avg_damage']):,}"
                    })
                st.dataframe(pd.DataFrame(disp_rows), use_container_width=True, hide_index=True)
                
                # ─── グラフ描画の完全安全化 ───
                if not ma_df.empty and ma_df["battles"].sum() > 0:
                    # すべてのモードで勝率データが0、またはデータ数が極端に少ない場合のクラッシュ防止
                    if (ma_df["win_rate"] == 0).all() or len(ma_df) <= 1:
                        fig_m = px.bar(ma_df, x="モード", y="battles", title="モード別出撃割合")
                    else:
                        fig_m = px.bar(ma_df, x="モード", y="battles", color="win_rate", color_continuous_scale="cool", title="モード別出撃割合")
                    
                    fig_m.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(10,25,47,0.4)')
                    st.plotly_chart(fig_m, use_container_width=True)
                else:
                    st.info("📊 グラフを表示するための戦闘データ（差分）がありません。全期間を選択するか、複数日分のZIPをアップロードしてください。")
            else:
                st.info("対応する戦闘モード別データが見つかりません。")
        else:
            st.info("WOWSL_Battle_Types_Statistics.csv が見つかりません。")

    # ------------------------------------------
    # Tab 3: 国家・艦種分析
    # ------------------------------------------
    with t_nation:
        st.markdown('<div class="section-header">🌍 国家別 × 艦種別 ポートフォリオ可視化</div>', unsafe_allow_html=True)
        if not ship_df.empty:
            latest_s = ship_df[ship_df['_SNAPSHOT_DATE'] == ship_df['_SNAPSHOT_DATE'].max()]
            
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                st.subheader("艦種別出撃パイチャート")
                t_sum = latest_s.groupby('_SHIP_TYPE').sum(numeric_only=True).reset_index()
                fig_t = px.pie(t_sum, values='BATTLES_COUNT', names='_SHIP_TYPE', hole=0.4, color_discrete_sequence=px.colors.sequential.Electric)
                fig_t.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_t, use_container_width=True)
                
            with col_g2:
                st.subheader("国家別戦闘数ランキング")
                n_sum = latest_s.groupby('_NATION').sum(numeric_only=True).reset_index().sort_values(by='BATTLES_COUNT', ascending=False)
                fig_n = px.bar(n_sum, x='_NATION', y='BATTLES_COUNT', color='BATTLES_COUNT', color_continuous_scale='Electric')
                fig_n.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_n, use_container_width=True)
        else:
            st.info("艦種別マッピングを構成するデータがありません。")

    # ------------------------------------------
    # Tab 4: 艦艇別データ
    # ------------------------------------------
    with t_ship:
        st.markdown('<div class="section-header">🚢 艦艇マスタデータ・検索・ソートマトリクス</div>', unsafe_allow_html=True)
        if not ship_df.empty:
            l_ships = ship_df[ship_df['_SNAPSHOT_DATE'] == ship_df['_SNAPSHOT_DATE'].max()].copy()
            
            c_f1, c_f2, c_f3 = st.columns(3)
            with c_f1:
                nat_opt = ["すべて"] + list(l_ships['_NATION'].unique())
                s_nat = c_f1.selectbox("国家フィルタ", nat_opt)
            with c_f2:
                typ_opt = ["すべて"] + list(l_ships['_SHIP_TYPE'].unique())
                s_typ = c_f2.selectbox("艦種フィルタ", typ_opt)
            with c_f3:
                tier_opt = ["すべて"] + sorted([int(x) for x in l_ships['_ESTIMATED_TIER'].unique()])
                s_tier = c_f3.selectbox("ティアフィルタ", tier_opt)
                
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
                    "K/D": round(row_kpi["kd"], 2), "生存率": f"{row_kpi['survived_rate']:.2f}%", "平均経験値": int(row_kpi["avg_xp"])
                })
                
            if records_list:
                st.dataframe(pd.DataFrame(records_list).sort_values(by="戦闘数", ascending=False), use_container_width=True, hide_index=True)
            else:
                st.info("条件に一致する艦艇データがありません。")

    # ------------------------------------------
    # Tab 5: 自己ベスト
    # ------------------------------------------
    with t_records:
        st.markdown('<div class="section-header">🔥 記録：パーソナル最高スコア</div>', unsafe_allow_html=True)
        if not ship_df.empty:
            l_ships = ship_df[ship_df['_SNAPSHOT_DATE'] == ship_df['_SNAPSHOT_DATE'].max()]
            
            records_map = {
                "MAX_DAMAGE_DEALT": "💥 1試合最大与ダメージ",
                "MAX_FRAGS": "💀 1試合最大撃沈数",
                "MAX_EXP": "⭐ 1試合最大取得経験値",
                "MAX_PLANES_KILLED": "✈️ 1試合最大航空機撃墜数"
            }
            
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
                            f"""
                            <div style="background: rgba(0, 242, 254, 0.04); border: 1px solid rgba(0, 242, 254, 0.3); border-radius: 8px; padding: 20px; margin-bottom: 15px;">
                                <div style="color: #00f2fe; font-size: 0.85rem; font-weight: 600; text-transform: uppercase;">{label}</div>
                                <div style="font-size: 2.2rem; font-weight: 700; color: #ffffff; margin: 8px 0;">{best_row[col_col]:,.0f}</div>
                                <div style="font-size: 0.85rem; color: #94a3b8;">
                                    使用艦艇: <span style="color: #ffffff; font-weight: 600;">{best_row['VEHICLE_NAME']}</span>
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
        else:
            st.info("最高記録算出可能なデータセットがありません。")

    # ------------------------------------------
    # Tab 6: クラン履歴
    # ------------------------------------------
    with t_clan:
        st.markdown('<div class="section-header">🛡️ クランアクション・所属タイムライン</div>', unsafe_allow_html=True)
        clan_df = data["clans"]
        if not clan_df.empty:
            time_col = 'CREATED_AT' if 'CREATED_AT' in clan_df.columns else '_SNAPSHOT_DATE'
            clan_df[time_col] = pd.to_datetime(clan_df[time_col])
            clan_sorted = clan_df.sort_values(by=time_col, ascending=False)
            
            for _, row in clan_sorted.iterrows():
                op = str(row.get('OPERATION_NAME', 'unknown')).lower()
                c_tag = row.get('CLAN_NAME', 'クラン')
                role = row.get('ROLE_NAME', '-')
                t_stamp = row[time_col].strftime('%Y-%m-%d %H:%M')
                
                if "join" in op:
                    border_color = "#10b981"
                    badge_text = f"🟢 クラン [{c_tag}] に加入しました (初期役職: {role})"
                elif "leave" in op:
                    border_color = "#ef4444"
                    badge_text = f"🔴 クラン [{c_tag}] から脱退、または除名されました"
                elif "role" in op:
                    border_color = "#f59e0b"
                    badge_text = f"🟡 クラン [{c_tag}] 内での役職変更: 役職名 -> {role}"
                else:
                    border_color = "#3b82f6"
                    badge_text = f"🔷 クランアクションイベント: {op}"
                    
                st.markdown(
                    f"""
                    <div style="border-left: 4px solid {border_color}; background: rgba(255,255,255,0.02); padding: 12px 16px; margin-bottom: 10px; border-radius: 0 6px 6px 0;">
                        <span style="font-size: 0.8rem; color: #94a3b8; font-family: monospace;">[{t_stamp}]</span><br>
                        <span style="font-weight: 500; color: #f8fafc;">{badge_text}</span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        else:
            st.info("クランのアクションデータ(Clans.csv)が存在しないか空です。")

if __name__ == '__main__':
    main()
