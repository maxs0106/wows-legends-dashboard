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
    .stApp { background-color: #0b131e; color: #d1d5db; font-family: sans-serif; }
    section[data-testid="stSidebar"] { background-color: #070d14 !important; border-right: 1px solid #1e293b; }
    
    /* 表のデザイン：イラストを排除した極限までシンプルなグリッド */
    .matrix-container { margin: 10px 0 25px 0; overflow-x: auto; border: 1px solid #2d3748; border-radius: 3px; }
    .flat-table { width: 100%; border-collapse: collapse; background-color: #0f172a; font-size: 0.9rem; text-align: left; }
    .flat-table th { background-color: #1e293b; color: #94a3b8; font-weight: 600; padding: 10px 14px; border-bottom: 2px solid #334155; }
    .flat-table td { padding: 10px 14px; border-bottom: 1px solid #1e293b; color: #e2e8f0; }
    .flat-table tr:hover td { background-color: #1e293b; }
    .idx-name { font-weight: 500; color: #94a3b8 !important; background-color: #131c2e; width: 20%; border-right: 1px solid #1e293b; }
    .val-lt { font-weight: 600; color: #ffffff; }
    
    /* ボタン上のラベル用 */
    .mode-txt { font-size: 0.85rem; color: #94a3b8; margin-bottom: 4px; font-weight: 500; }
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
                temp_dfs = {}
                detected_date = None
                
                # 最初に対象のCSVを一通りスキャンしてデータ日付を特定する
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
                            
                            # 💡 【エラー修正解決】タイムスタンプがUNIX秒（数値）か文字列かを自動判別してパース
                            if key == "account_stats":
                                target_col = 'DOSSIER_UPDATED_AT' if 'DOSSIER_UPDATED_AT' in df.columns else ('UPDATED_AT' if 'UPDATED_AT' in df.columns else None)
                                if target_col:
                                    raw_val = str(df[target_col].iloc[0]).strip()
                                    if raw_val and raw_val != "nan":
                                        # 数値（UNIX時間）のみで構成されている場合
                                        if raw_val.isdigit() or (raw_val.replace('.', '', 1).isdigit() and '.' in raw_val):
                                            timestamp_sec = float(raw_val)
                                            detected_date = datetime.fromtimestamp(timestamp_sec).date()
                                        else:
                                            # 通常の YYYY-MM-DD 形式の場合
                                            if len(raw_val) >= 10:
                                                detected_date = datetime.strptime(raw_val[:10], '%Y-%m-%d').date()
                
                # もし内部から日付が取れなかった場合はファイル名から取得を試みる
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
                
                # 確定したスナップショット日付を付与して格納
                matched_count = 0
                for key, df in temp_dfs.items():
                    df['_SNAPSHOT_DATE'] = pd.to_datetime(detected_date)
                    all_data[key].append(df)
                    matched_count += 1
                            
                if matched_count > 0:
                    success_zips.append(f"{up_file.name} -> [確定日: {detected_date.strftime('%Y-%m-%d')}]")
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
        "battles": int(battles),
        "win_rate": (wins / battles * 100) if battles > 0 else 0.0,
        "survived_rate": (survived / battles * 100) if battles > 0 else 0.0,
        "avg_damage": (damage / battles) if battles > 0 else 0.0,
        "avg_frags": (frags / battles) if battles > 0 else 0.0,
        "avg_xp": (xp / battles) if battles > 0 else 0.0,
        "kd": (frags / deaths) if battles > 0 else 0.0
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
        "battles": int(max(0, battles)),
        "win_rate": max(0.0, min(100.0, (wins / battles * 100))) if battles > 0 else 0.0,
        "survived_rate": max(0.0, min(100.0, (survived / battles * 100))) if battles > 0 else 0.0,
        "avg_damage": max(0.0, damage / battles) if battles > 0 else 0.0,
        "avg_frags": max(0.0, frags / battles) if battles > 0 else 0.0,
        "avg_xp": max(0.0, xp / battles) if battles > 0 else 0.0,
        "kd": max(0.0, frags / deaths) if battles > 0 else 0.0
    }

# ==========================================
# 5. メインコントロール
# ==========================================
def main():
    st.title("⚓ WoWs Legends stats")
    st.markdown("`Fleet Intelligence Platform` | ⏱️ 期間設定: **内部データ自動解析マトリクス**")
    
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
                    公式からエクスポートした個人データのZIPアーカイブを複数まとめてサイドバーにドロップしてください。<br>内部の記録日を自動でマージ解析します。
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
        return

    with st.spinner("📦 CSV内部タイムスタンプからデータ基準日を逆引き解析中..."):
        raw_data, success_zips, errors = extract_zip_data(uploaded_files)
        data = merge_and_optimize(raw_data)
        
    with st.sidebar.expander("📊 解析メタデータ一覧", expanded=True):
        st.caption(f"読み込み成功履歴:")
        for sz in success_zips: st.caption(f"✅ {sz}")
        if errors:
            st.error("エラー一覧:")
            for e in errors: st.caption(e)

    # 動的にソートされた一意の日付を取得
    all_dates = []
    for df in data.values():
        if not df.empty and '_SNAPSHOT_DATE' in df.columns:
            all_dates.extend(df['_SNAPSHOT_DATE'].unique().tolist())
    unique_dates = sorted(list(set(pd.to_datetime(all_dates))))
    
    if unique_dates:
        st.sidebar.markdown("---")
        st.sidebar.markdown("📅 **自動検知したデータスナップショット一覧:**")
        for d in unique_dates:
            st.sidebar.markdown(f'<div class="date-badge">⏳ {d.strftime("%Y-%m-%d")}</div>', unsafe_allow_html=True)

    ship_df = data["ship_stats"]
    if not ship_df.empty:
        parsed_meta = ship_df['VEHICLE_NAME'].apply(parse_ship_id)
        ship_df['_NATION'] = [x[0] for x in parsed_meta]
        ship_df['_SHIP_TYPE'] = [x[1] for x in parsed_meta]
        ship_df['_ESTIMATED_TIER'] = [x[2] for x in parsed_meta]
        data["ship_stats"] = ship_df

    # 🕹️ 戦闘タイプ（モード）選択ボタン
    st.markdown('<div class="section-header">🕹️ 戦闘タイプ (BATTLE TYPE) 選択</div>', unsafe_allow_html=True)
    
    if 'selected_mode_code' not in st.session_state:
        st.session_state.selected_mode_code = 1
        
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
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
        if st.button("イベント戦 / アリーナ", use_container_width=True, type="primary" if st.session_state.selected_mode_code == 4 else "secondary"):
            st.session_state.selected_mode_code = 4
            st.rerun()

    selected_mode_code = st.session_state.selected_mode_code
    target_mode_str = BATTLE_TYPE_CODE_MAP.get(selected_mode_code, "通常戦")

    t_summary, t_mode, t_nation, t_ship, t_records, t_clan = st.tabs([
        "📈 期間マトリクス・総合戦績", "⚔️ 戦闘モード全体一覧", "🌍 国家・艦種", "🚢 艦艇別データ", "🏆 自己ベスト", "🛡️ クラン履歴"
    ])
    
    # ------------------------------------------
    # Tab 1: 総合戦績（マトリクス表）
    # ------------------------------------------
    with t_summary:
        st.markdown('<div class="mode-txt">戦闘タイプ選択</div>', unsafe_allow_html=True)
        if 'mode' not in st.session_state: st.session_state.mode = 1
        
        # 横並びの小さなボタンの配置
        c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1.2, 4])
        if c1.button("通常戦", use_container_width=True, type="primary" if st.session_state.mode==1 else "secondary"): st.session_state.mode=1; st.rerun()
        if c2.button("AI戦", use_container_width=True, type="primary" if st.session_state.mode==2 else "secondary"): st.session_state.mode=2; st.rerun()
        if c3.button("ランク戦", use_container_width=True, type="primary" if st.session_state.mode==3 else "secondary"): st.session_state.mode=3; st.rerun()
        if c4.button("イベント", use_container_width=True, type="primary" if st.session_state.mode==4 else "secondary"): st.session_state.mode=4; st.rerun()

        m = st.session_state.mode
        f_bt = data['bt'][data['bt']['TYPE']==m] if not data['bt'].empty else pd.DataFrame()
        f_sp = data['ship'][data['ship']['TYPE']==m] if not data['ship'].empty else pd.DataFrame()
        
        cols = {}
        # 全期間データの集計
        lt_df = f_bt if not f_bt.empty else f_sp
        cols["全期間"] = (calc_kpi(lt_df[lt_df['_DATE']==lt_df['_DATE'].max()]) if not lt_df.empty else calc_kpi(pd.DataFrame()), True)
        
        # 期間別差分の計算
        if len(dates) > 1:
            for i in range(len(dates)-1):
                d1, d2 = dates[i], dates[i+1]
                lbl = f"{pd.to_datetime(d1).strftime('%Y%m%d')}～{pd.to_datetime(d2).strftime('%Y%m%d')}"
                src = f_bt if not f_bt.empty else f_sp
                if not src.empty:
                    cols[lbl] = (calc_diff(src[src['_DATE']==d2], src[src['_DATE']==d1]), False)

        # イラスト（絵文字）を完全に排除した項目定義
        rows = [
            ("戦闘数", "b", "{:,}"),
            ("勝率", "w", "{:.2f}%"),
            ("生存率", "s", "{:.2f}%"),
            ("平均与ダメ", "d", "{:,.0f}"),
            ("K/D比", "k", "{:.2f}")
        ]
        
        # フラットなHTMLテーブルを生成
        html = '<div class="matrix-container"><table class="flat-table"><thead><tr><th>データ項目</th>'
        for k in cols.keys(): html += f'<th>{k}</th>'
        html += '</tr></thead><tbody>'
        for l, k, fmt in rows:
            html += f'<tr><td class="idx-name">{l}</td>'
            for c_lbl, (kpi, is_lt) in cols.items():
                html += f'<td class="{"val-lt" if is_lt else ""}" style="color:{"" if is_lt else "#cbd5e1"}">{fmt.format(kpi[k])}</td>'
            html += '</tr>'
        html += '</tbody></table></div>'
        st.markdown(html, unsafe_allow_html=True)

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
