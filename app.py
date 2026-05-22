import io, os, re, zipfile
from datetime import datetime, date
import pandas as pd
import streamlit as st

st.set_page_config(page_title="WoWsL Intel", layout="wide", initial_sidebar_state="expanded")

# 極限までシンプルにしたミリタリーフラットデザインCSS
st.markdown("""
<style>
    .stApp { background-color: #0b131e; color: #d1d5db; font-family: sans-serif; }
    section[data-testid="stSidebar"] { background-color: #070d14 !important; border-right: 1px solid #1e293b; }
    .matrix-container { margin: 10px 0 25px 0; overflow-x: auto; border: 1px solid #2d3748; border-radius: 3px; }
    .flat-table { width: 100%; border-collapse: collapse; background-color: #0f172a; font-size: 0.9rem; text-align: left; }
    .flat-table th { background-color: #1e293b; color: #94a3b8; font-weight: 600; padding: 10px 14px; border-bottom: 2px solid #334155; }
    .flat-table td { padding: 10px 14px; border-bottom: 1px solid #1e293b; color: #e2e8f0; }
    .flat-table tr:hover td { background-color: #1e293b; }
    .idx-name { font-weight: 500; color: #94a3b8 !important; background-color: #131c2e; width: 20%; border-right: 1px solid #1e293b; }
    .val-lt { font-weight: 600; color: #ffffff; }
    .mode-txt { font-size: 0.85rem; color: #94a3b8; margin-bottom: 4px; font-weight: 500; }
</style>
""", unsafe_allow_html=True)

CSV_MAP = {"WOWSL_Battle_Types_Statistics.csv": "bt", "WOWSL_Ship_Statistics_By_Type.csv": "ship", "WOWSL_Account_Statistics.csv": "acc"}
NAT_MAP = {"ja":"日本","us":"アメリカ","ge":"ドイツ","uk":"イギリス","ru":"ソ連","fr":"フランス","it":"イタリア"}
TYP_MAP = {"b":"戦艦","c":"巡洋艦","d":"駆逐艦","a":"空母"}

def parse_ship(name: str):
    if not isinstance(name, str) or len(name) < 4: return "その他", "その他"
    p = name[1:4].lower()
    return NAT_MAP.get(p[0:2], "その他"), TYP_MAP.get(p[2], "その他")

# ZIP解凍 & タイムスタンプ自動解析
def load_zips(files):
    dfs = {k: [] for k in CSV_MAP.values()}
    for f in files:
        try:
            with zipfile.ZipFile(io.BytesIO(f.read())) as z:
                dt = None
                for p in z.namelist():
                    base = os.path.basename(p)
                    if base in CSV_MAP:
                        k = CSV_MAP[base]
                        try: content = z.open(p).read().decode('utf-8')
                        except: content = z.open(p).read().decode('shift_jis')
                        df = pd.read_csv(io.StringIO(content))
                        if not df.empty:
                            df.columns = [c.strip().upper() for c in df.columns]
                            if k == "acc" and 'UPDATED_AT' in df.columns:
                                val = str(df['UPDATED_AT'].iloc[0]).strip()
                                if val.isdigit(): dt = datetime.fromtimestamp(float(val)).date()
                            dfs[k].append((df, dt))
                # 日付が取れなければファイル名から
                if not dt:
                    m = re.findall(r'\d{8}', f.name)
                    dt = datetime.strptime(m[0], '%Y%m%d').date() if m else date.today()
                for k in dfs.keys():
                    for item in dfs[k]:
                        if item[1] is None: item[0]['_DATE'] = pd.to_datetime(dt)
                        else: item[0]['_DATE'] = pd.to_datetime(item[1])
        except: pass
    
    res = {}
    for k, v in dfs.items():
        if v:
            c = pd.concat([x[0] for x in v], ignore_index=True).sort_values('_DATE')
            sub = ['_DATE', 'TYPE'] if k=='bt' else (['_DATE','VEHICLE_NAME','TYPE'] if k=='ship' else ['_DATE'])
            res[k] = c.drop_duplicates(subset=sub, keep='last').reset_index(drop=True)
        else: res[k] = pd.DataFrame()
    return res

def calc_kpi(df):
    if df.empty: return {"b":0,"w":0,"s":0,"d":0,"k":0}
    b = float(df['BATTLES_COUNT'].sum() if 'BATTLES_COUNT' in df.columns else 0)
    w = float(df['WINS'].sum() if 'WINS' in df.columns else 0)
    s = float(df['SURVIVED'].sum() if 'SURVIVED' in df.columns else 0)
    d = float(df['DAMAGE_DEALT'].sum() if 'DAMAGE_DEALT' in df.columns else 0)
    f = float(df['FRAGS'].sum() if 'FRAGS' in df.columns else 0)
    return {"b":int(b),"w":w/b*100 if b>0 else 0,"s":s/b*100 if b>0 else 0,"d":d/b if b>0 else 0,"k":f/(b-s) if (b-s)>0 else f}

def calc_diff(n, o):
    b = float(n['BATTLES_COUNT'].sum() - o['BATTLES_COUNT'].sum())
    if b <= 0: return {"b":0,"w":0,"s":0,"d":0,"k":0}
    w = float(n['WINS'].sum() - o['WINS'].sum())
    s = float(n['SURVIVED'].sum() - o['SURVIVED'].sum())
    d = float(n['DAMAGE_DEALT'].sum() - o['DAMAGE_DEALT'].sum())
    f = float(n['FRAGS'].sum() - o['FRAGS'].sum())
    return {"b":int(max(0,b)),"w":max(0.0,w/b*100),"s":max(0.0,s/b*100),"d":max(0.0,d/b),"k":max(0.0,f/(b-s)) if (b-s)>0 else f}

def main():
    st.sidebar.header("データインポート")
    up = st.sidebar.file_uploader("ZIP投入", type="zip", accept_multiple_files=True)
    if not up:
        st.info("サイドバーからZIPファイルをアップロードしてください。")
        return

    data = load_zips(up)
    dates = sorted(list(set(data['bt']['_DATE'].unique().tolist()))) if not data['bt'].empty else []
    
    if not data['ship'].empty:
        meta = data['ship']['VEHICLE_NAME'].apply(parse_ship)
        data['ship']['_NAT'] = [x[0] for x in meta]
        data['ship']['_TYP'] = [x[1] for x in meta]

    t_sum, t_det = st.tabs(["総合戦績", "艦艇別データ"])

    with t_sum:
        st.markdown('<div class="mode-txt">戦闘タイプ選択</div>', unsafe_allow_html=True)
        if 'mode' not in st.session_state: st.session_state.mode = 1
        
        c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1.2, 4])
        if c1.button("通常戦", use_container_width=True, type="primary" if st.session_state.mode==1 else "secondary"): st.session_state.mode=1; st.rerun()
        if c2.button("AI戦", use_container_width=True, type="primary" if st.session_state.mode==2 else "secondary"): st.session_state.mode=2; st.rerun()
        if c3.button("ランク戦", use_container_width=True, type="primary" if st.session_state.mode==3 else "secondary"): st.session_state.mode=3; st.rerun()
        if c4.button("イベント", use_container_width=True, type="primary" if st.session_state.mode==4 else "secondary"): st.session_state.mode=4; st.rerun()

        m = st.session_state.mode
        f_bt = data['bt'][data['bt']['TYPE']==m] if not data['bt'].empty else pd.DataFrame()
        f_sp = data['ship'][data['ship']['TYPE']==m] if not data['ship'].empty else pd.DataFrame()
        
        cols = {}
        # 全期間
        lt_df = f_bt if not f_bt.empty else f_sp
        cols["全期間"] = (calc_kpi(lt_df[lt_df['_DATE']==lt_df['_DATE'].max()]) if not lt_df.empty else calc_kpi(pd.DataFrame()), True)
        
        # 期間別
        if len(dates) > 1:
            for i in range(len(dates)-1):
                d1, d2 = dates[i], dates[i+1]
                lbl = f"{pd.to_datetime(d1).strftime('%Y%m%d')}～{pd.to_datetime(d2).strftime('%Y%m%d')}"
                src = f_bt if not f_bt.empty else f_sp
                if not src.empty:
                    cols[lbl] = (calc_diff(src[src['_DATE']==d2], src[src['_DATE']==d1]), False)

        rows = [("戦闘数","b","{:,}"),("勝率","w","{:.2f}%"),("生存率","s","{:.2f}%"),("平均与ダメ","d","{:,.0f}"),("K/D比","k","{:.2f}")]
        
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

    with t_det:
        if not f_sp.empty:
            l_sp = f_sp[f_sp['_DATE']==f_sp['_DATE'].max()]
            cc1, cc2 = st.columns(2)
            sn = cc1.selectbox("国家", ["すべて"] + list(l_sp['_NAT'].unique()))
            st_ = cc2.selectbox("艦種", ["すべて"] + list(l_sp['_TYP'].unique()))
            q = l_sp.copy()
            if sn != "すべて": q = q[q['_NAT'] == sn]
            if st_ != "すべて": q = q[q['_TYP'] == st_]
            res = [{"艦艇名":r['VEHICLE_NAME'],"国家":r['_NAT'],"艦種":r['_TYP'],"戦闘数":int(r['BATTLES_COUNT']),"勝率":f"{r['WINS']/r['BATTLES_COUNT']*100:.1f}%"} for _,r in q.iterrows() if r['BATTLES_COUNT']>0]
            if res: st.dataframe(pd.DataFrame(res).sort_values("戦闘数", ascending=False), width='stretch', hide_index=True)

if __name__ == '__main__':
    main()
