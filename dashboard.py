import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.graph_objects as go
from sqlalchemy import create_engine
import datetime

# ==========================================
# ⚙️ CONFIGURAZIONE PAGINA E DATABASE
# ==========================================
st.set_page_config(page_title="📊 NBA Advanced Analytics & Bounce-Back", page_icon="🏀", layout="wide")

# Assicurati di avere il tuo URL impostato nei secrets di Streamlit
DB_URL = st.secrets["DB_URL"]

# ==========================================
# 📥 CARICAMENTO DATI (CACHE)
# ==========================================
@st.cache_data(ttl=600)
def carica_boxscores():
    try:
        engine = create_engine(DB_URL)
        with engine.connect() as connection:
            df = pd.read_sql("SELECT * FROM nba_boxscores ORDER BY \"Date\" DESC", connection)
            df['Date'] = pd.to_datetime(df['Date'])
        return df
    except Exception as e:
        st.error(f"Errore connessione Database (Boxscores): {e}")
        return pd.DataFrame()

@st.cache_data
def carica_storico_regressione():
    try:
        df_hist = pd.read_csv("report_analisi_regressione_avanzata.csv")
        return df_hist[df_hist['Giocatore'].notna()]
    except:
        return pd.DataFrame()

@st.cache_data(ttl=600)
def carica_infortuni():
    try:
        engine = create_engine(DB_URL)
        with engine.connect() as connection:
            df = pd.read_sql("SELECT * FROM infortuni", connection)
        return df, None
    except Exception as e:
        return pd.DataFrame(), str(e)

@st.cache_data(ttl=600)
def carica_calendario():
    try:
        engine = create_engine(DB_URL)
        with engine.connect() as connection:
            df = pd.read_sql("SELECT * FROM schedule", connection)
            if not df.empty and 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'])
        return df, None
    except Exception as e:
        return pd.DataFrame(), str(e)

@st.cache_data(ttl=600)
def carica_quote():
    try:
        engine = create_engine(DB_URL)
        with engine.connect() as connection:
            df = pd.read_sql("SELECT * FROM quote_giocatori", connection)
        return df, None
    except Exception as e:
        return pd.DataFrame(), str(e)

# Esecuzione caricamento
df_nba = carica_boxscores()
df_storico = carica_storico_regressione()
df_infortuni, err_infortuni = carica_infortuni()
df_schedule, err_schedule = carica_calendario()
df_quote, err_quote = carica_quote()

if df_nba.empty:
    st.error("❌ Impossibile procedere senza dati. Verifica il database dei boxscores.")
    st.stop()

# Uniformiamo i nomi colonna principali
if 'Player' in df_nba.columns:
    df_nba = df_nba.rename(columns={'Player': 'PLAYER_NAME'})
if 'MIN' in df_nba.columns and 'MP' not in df_nba.columns:
    df_nba['MP'] = df_nba['MIN']

# ==========================================
# 🎛️ BARRA LATERALE: PANNELLO DI CONTROLLO
# ==========================================
st.sidebar.title("🎮 Algoritmo NBA")

# 1. Selezione Metrica
metrica = st.sidebar.radio(
    "Seleziona Metrica Target:",
    ["PTS", "TRB", "AST", "3P", "PRA", "PA", "PR", "RA"],
    index=0,
    horizontal=True
)

st.sidebar.markdown("---")

# 2. FILTRO CALENDARIO DI DOMANI
st.sidebar.subheader("📅 Filtro Calendario")
filtro_domani = st.sidebar.checkbox("Mostra solo le squadre che giocano DOMANI")

lista_squadre = sorted(df_nba['Team'].unique().tolist())

# Logica squadre di domani
if filtro_domani:
    if err_schedule:
        st.sidebar.error(f"❌ Errore caricamento calendario: {err_schedule}")
    elif not df_schedule.empty:
        domani = pd.Timestamp.today().normalize() + pd.Timedelta(days=1)
        sched_domani = df_schedule[df_schedule['Date'].dt.date == domani.date()]
        
        if not sched_domani.empty:
            col_casa = 'Home' if 'Home' in sched_domani.columns else ('HomeTeam' if 'HomeTeam' in sched_domani.columns else None)
            col_trasferta = 'Away' if 'Away' in sched_domani.columns else ('AwayTeam' if 'AwayTeam' in sched_domani.columns else None)
            
            if col_casa and col_trasferta:
                try:
                    squadre_domani = set(sched_domani[col_casa].tolist() + sched_domani[col_trasferta].tolist())
                    lista_squadre = [s for s in lista_squadre if s in squadre_domani]
                except Exception as e:
                    st.sidebar.warning(f"Errore nel parsing delle squadre: {e}")
        else:
            st.sidebar.warning("Nessuna partita in programma per domani.")
            lista_squadre = []
    else:
        lista_squadre = []

# 3. FILTRO SQUADRE
squadre_selezionate = st.sidebar.multiselect(
    "🏀 Filtra per Squadra:",
    options=lista_squadre,
    default=lista_squadre
)

# 4. WIDGET INFORTUNI AVANZATO
st.sidebar.markdown("---")
st.sidebar.subheader("🚑 Report Infortuni")

if err_infortuni:
    st.sidebar.error(f"⚠️ Errore caricamento database:\n`{err_infortuni}`")
elif not df_infortuni.empty:
    col_team = 'Team' if 'Team' in df_infortuni.columns else ('squadra' if 'squadra' in df_infortuni.columns else None)
    
    if col_team:
        # 🧹 PULIZIA: Rimuove spazi invisibili e rende tutto maiuscolo per evitare mismatch
        df_infortuni[col_team] = df_infortuni[col_team].astype(str).str.strip().str.upper()
        squadre_pulite = [str(s).strip().upper() for s in squadre_selezionate]
        
        # Filtriamo gli infortuni
        df_inf_filtrati = df_infortuni[df_infortuni[col_team].isin(squadre_pulite)]
    else:
        df_inf_filtrati = df_infortuni

    if df_inf_filtrati.empty:
        st.sidebar.success("✅ Nessun infortunio per le squadre selezionate.")
        # 🐞 DEBUG VISIVO
        with st.sidebar.expander("🛠️ Debug Nomi Squadre"):
            st.warning("Se sai che ci sono infortunati, i nomi qui sotto non combaciano:")
            st.write("**Tue squadre:**", squadre_pulite[:5])
            if col_team:
                st.write("**DB Infortuni:**", df_infortuni[col_team].unique().tolist()[:5])
    else:
        with st.sidebar.expander("Vedi dettagli infortunati", expanded=True):
            for _, row in df_inf_filtrati.iterrows():
                nome = row.get('Giocatore', row.get('Player', row.get('player_name', 'Sconosciuto')))
                status = str(row.get('Status', row.get('stato', ''))).upper()
                dettagli = row.get('Dettagli', row.get('descrizione', ''))
                
                icona = "🔴" if status in ["OUT", "FUORI"] else "🟡" if status in ["QUESTIONABLE", "IN DUBBIO", "DAY-TO-DAY"] else "⚪"
                st.markdown(f"{icona} **{nome}**")
                if dettagli: 
                    st.caption(f"Stato: {status} | Info: {dettagli}")
                else: 
                    st.caption(f"Stato: {status}")
else:
    st.sidebar.info("Tabella infortuni vuota.")

st.sidebar.markdown("---")

# 5. Ordinamento e Filtri
ordine = st.sidebar.selectbox(
    "Ordina i giocatori per:",
    ["Media Decrescente", "Deviazione Standard (Volatilità)", "Streak Attuale"]
)

st.sidebar.subheader("🎯 Filtri Predittivi")
filtro_bounce = st.sidebar.checkbox("🚨 Ultime 3 sotto media (Bounce-Back)")
filtro_streak_neg = st.sidebar.checkbox("💀 Ultime 6 sotto media (Streak Critica)")

ricerca_giocatore = st.sidebar.text_input("🔍 Cerca Giocatore specifico:")

# ==========================================
# 🧮 MOTORE MATEMATICO (COMPUTE STATS)
# ==========================================
def calcola_metriche_avanzate(df, metrica_scelta, team_filter):
    giocatori_processati = []
    df_filtrato_team = df[df['Team'].isin(team_filter)]
    if df_filtrato_team.empty:
        return pd.DataFrame()
    
    def _pulisci_mp(x):
        if pd.isna(x): return 0.0
        s = str(x).strip()
        if ':' in s:
            try:
                p = s.split(':')
                return float(p[0]) + float(p[1]) / 60.0
            except: return 0.0
        try: return float(s)
        except: return 0.0

    for giocatore, group in df_filtrato_team.groupby('PLAYER_NAME'):
        group = group.sort_values('Date', ascending=True).reset_index(drop=True)
        
        if metrica_scelta == "PRA": values = group['PTS'] + group['TRB'] + group['AST']
        elif metrica_scelta == "PA": values = group['PTS'] + group['AST']
        elif metrica_scelta == "PR": values = group['PTS'] + group['TRB']
        elif metrica_scelta == "RA": values = group['TRB'] + group['AST']
        else: values = pd.to_numeric(group[metrica_scelta], errors='coerce').fillna(0)
        
        mean_val = values.mean()
        
        # Sbarramenti minimi
        if metrica_scelta == "PTS" and mean_val < 8: continue
        if metrica_scelta == "TRB" and mean_val < 5: continue
        if metrica_scelta == "AST" and mean_val < 5: continue
        if metrica_scelta == "3P"  and mean_val < 1.5: continue
        if metrica_scelta == "PRA" and mean_val < 18: continue
        if metrica_scelta == "PA"  and mean_val < 12: continue
        if metrica_scelta == "PR"  and mean_val < 12: continue
        if metrica_scelta == "RA"  and mean_val < 10: continue
        
        std_val = values.std() if len(values) > 1 else 0
        mp_cleaned = group['MP'].apply(_pulisci_mp) if 'MP' in group.columns else pd.Series([0.0]*len(group))
        
        mean_mp = mp_cleaned.mean()
        std_mp = mp_cleaned.std() if len(mp_cleaned) > 1 else 0.0
        
        fg = pd.to_numeric(group['FG%'], errors='coerce').fillna(0).mean()
        tp_pct = pd.to_numeric(group['3P%'], errors='coerce').fillna(0).mean()
        ft = pd.to_numeric(group['FT%'], errors='coerce').fillna(0).mean()
        efficienza_media = (fg + tp_pct + ft) / 3
        
        val_list = list(values)
        if len(val_list) == 0: continue
        
        ultimo_sopra = val_list[-1] >= mean_val
        streak = 0
        for v in reversed(val_list):
            if (v >= mean_val) == ultimo_sopra:
                streak += 1
            else:
                break
                
        last3 = val_list[-3:] if len(val_list) >= 3 else []
        last6 = val_list[-6:] if len(val_list) >= 6 else []
        
        giocatori_processati.append({
            'Giocatore': giocatore,
            'Team': group['Team'].iloc[-1],
            'Media': mean_val,
            'DevStd': std_val,
            'Media_Minuti': mean_mp,
            'DevStd_Minuti': std_mp,
            'Streak': streak,
            'TipoStreak': "SOPRA" if ultimo_sopra else "SOTTO",
            'Last3Below': len(last3) == 3 and all(x < mean_val for x in last3),
            'Last6Below': len(last6) == 6 and all(x < mean_val for x in last6),
            'Efficienza': efficienza_media,
            'DatiCompleti': group,
        })
        
    return pd.DataFrame(giocatori_processati)

df_elaborato = calcola_metriche_avanzate(df_nba, metrica, squadre_selezionate)

# Applicazione Filtri
if not df_elaborato.empty:
    if filtro_bounce: df_elaborato = df_elaborato[df_elaborato['Last3Below'] == True]
    if filtro_streak_neg: df_elaborato = df_elaborato[df_elaborato['Last6Below'] == True]
    if ricerca_giocatore: df_elaborato = df_elaborato[df_elaborato['Giocatore'].str.lower().str.contains(ricerca_giocatore.lower(), na=False)]

    if ordine == "Media Decrescente": df_elaborato = df_elaborato.sort_values('Media', ascending=False)
    elif ordine == "Deviazione Standard (Volatilità)": df_elaborato = df_elaborato.sort_values('DevStd', ascending=False)
    elif ordine == "Streak Attuale": df_elaborato = df_elaborato.sort_values('Streak', ascending=False)

# Paginazione
if "limite_giocatori" not in st.session_state:
    st.session_state.limite_giocatori = 20
totale_giocatori_disponibili = len(df_elaborato) if not df_elaborato.empty else 0

# ==========================================
# 🖥️ COSTRUZIONE GRAFICA FRONTEND
# ==========================================
st.title("📊 NBA Player Analytics & Historical Bounce-Back")
st.markdown(f"Configurazione Attuale: Analisi predittiva focalizzata su **{metrica}**")

if df_elaborato.empty:
    st.warning("⚠️ Nessun giocatore soddisfa i criteri impostati.")
else:
    top_giocatori = df_elaborato.head(st.session_state.limite_giocatori)
    st.info(f"Visualizzati {len(top_giocatori)} giocatori su un totale di {totale_giocatori_disponibili} trovati.")
    
    team_games_count = df_nba.groupby('Team')['Date'].nunique().to_dict()
    
    for _, row in top_giocatori.iterrows():
        badge_streak = "🔴 SOTTO" if row['TipoStreak'] == "SOTTO" else "🟢 SOPRA"
        extra_info = f" | Media Tentati 3P: {pd.to_numeric(row['DatiCompleti']['3PA'], errors='coerce').mean():.1f}" if metrica == "3P" and '3PA' in row['DatiCompleti'].columns else ""

        partite_giocate = len(row['DatiCompleti'])
        partite_totali_squadra = team_games_count.get(row['Team'], partite_giocate)

        st.subheader(f"👤 {row['Giocatore']} ({row['Team']}) — 🏟️ Partite: {partite_giocate}/{partite_totali_squadra}")
        st.markdown(
            f"**Media {metrica}:** `{row['Media']:.1f}` | **Dev.Std {metrica}:** `{row['DevStd']:.2f}` |\n"
            f"**Media Minuti (MP):** `{row['Media_Minuti']:.1f}` | **Dev.Std Minuti:** `{row['DevStd_Minuti']:.2f}` |\n"
            f"**Striscia Corrente:** `{row['Streak']} partite` {badge_streak} la media"
            f" | **Efficienza Tiro:** `{row['Efficienza']:.2f}`{extra_info}"
        )
        
        # 🎰 INTEGRAZIONE QUOTE BOOKMAKER
        if not df_quote.empty:
            quota_giocatore = df_quote[(df_quote['Giocatore'] == row['Giocatore']) & (df_quote['Metrica'] == metrica)]
            if not quota_giocatore.empty:
                linea = quota_giocatore['Linea'].iloc[0]
                q_over = quota_giocatore.get('Quota_Over', pd.Series([0])).iloc[0]
                q_under = quota_giocatore.get('Quota_Under', pd.Series([0])).iloc[0]
                
                scarto = row['Media'] - linea
                alert_valore = "🔥 **VALORE:** Media superiore alla Linea!" if scarto > 1.5 else ("🧊 **VALORE:** Media inferiore alla Linea!" if scarto < -1.5 else "")

                st.info(
                    f"🎰 **LINEA BOOKMAKER ({metrica}):** `{linea}` | "
                    f"📈 **Over:** `{q_over}` | 📉 **Under:** `{q_under}`  {alert_valore}"
                )

        if not df_storico.empty:
            storico_giocatore = df_storico[(df_storico['Giocatore'] == row['Giocatore']) & (df_storico['Metrica'] == metrica)]
            if not storico_giocatore.empty:
                recupero = storico_giocatore['Partite_per_Recupero'].iloc[0]
                if row['Last3Below']:
                    st.error(f"⚠️ **BOUNCE-BACK ALERT STORICO:** Il modello indica che il giocatore impiega mediamente **{recupero} partite** per rompere il trend negativo. Possibile Bounce-Back.")
                else:
                    st.caption(f"📋 Riferimento Storico: Tempo medio stimato di reazione {recupero} match.")

        # ==========================================
        # 📈 PREPARAZIONE DATI GRAFICO 
        # ==========================================
        df_match = row['DatiCompleti'].copy()
        tutte_date_squadra = sorted(df_nba[df_nba['Team'] == row['Team']]['Date'].unique())
        df_completo_squadra = pd.DataFrame({'Date': tutte_date_squadra})
        
        df_match = pd.merge(df_completo_squadra, df_match, on='Date', how='left')
        df_match['Ha_Giocato'] = df_match['PLAYER_NAME'].notna()
        
        if metrica == "PRA": df_match['Grafico_Val'] = np.where(df_match['Ha_Giocato'], df_match['PTS'].fillna(0) + df_match['TRB'].fillna(0) + df_match['AST'].fillna(0), np.nan)
        elif metrica == "PA": df_match['Grafico_Val'] = np.where(df_match['Ha_Giocato'], df_match['PTS'].fillna(0) + df_match['AST'].fillna(0), np.nan)
        elif metrica == "PR": df_match['Grafico_Val'] = np.where(df_match['Ha_Giocato'], df_match['PTS'].fillna(0) + df_match['TRB'].fillna(0), np.nan)
        elif metrica == "RA": df_match['Grafico_Val'] = np.where(df_match['Ha_Giocato'], df_match['TRB'].fillna(0) + df_match['AST'].fillna(0), np.nan)
        else: df_match['Grafico_Val'] = np.where(df_match['Ha_Giocato'], pd.to_numeric(df_match[metrica], errors='coerce').fillna(0), np.nan)
        
        df_match['Colore'] = np.where(df_match['Grafico_Val'] >= row['Media'], 'Sopra Media', 'Sotto Media')
        
        def _pulisci_mp_grafico(x):
            if pd.isna(x): return np.nan
            s = str(x).strip()
            if ':' in s:
                try:
                    p = s.split(':')
                    return float(p[0]) + float(p[1]) / 60.0
                except: return np.nan
            try: return float(s)
            except: return np.nan
        
        df_match['MP_Numerico'] = np.where(df_match['Ha_Giocato'], df_match['MP'].apply(_pulisci_mp_grafico), np.nan)
        
        for c in ['FG', 'FGA', '3P', '3PA', 'FT', 'FTA']:
            if c in df_match.columns:
                df_match[c] = pd.to_numeric(df_match[c], errors='coerce').fillna(0).astype(int)
        
        df_match['🎯 Tiri da 2'] = np.where(df_match['Ha_Giocato'], (df_match['FG'] - df_match['3P']).astype(str) + " / " + (df_match['FGA'] - df_match['3PA']).astype(str), "N/D (DNP)")
        df_match['🏀 Tiri da 3'] = np.where(df_match['Ha_Giocato'], df_match['3P'].astype(str) + " / " + df_match['3PA'].astype(str), "N/D (DNP)")
        df_match['🟨 Tiri Liberi'] = np.where(df_match['Ha_Giocato'], df_match['FT'].astype(str) + " / " + df_match['FTA'].astype(str), "N/D (DNP)")
        df_match['Stato_Giocatore'] = np.where(df_match['Ha_Giocato'], "GIOCATO", "ASSENTE / DNP")
        df_match['MP_Originale_Str'] = np.where(df_match['Ha_Giocato'], df_match['MP'].astype(str), "0")
        df_match['Data'] = df_match['Date'].dt.strftime('%Y-%m-%d')
        
        bar_text_list = []
        for _, r in df_match.iterrows():
            if r['Ha_Giocato']:
                val = r['Grafico_Val']
                bar_text_list.append("0" if pd.isna(val) else (str(int(val)) if val == int(val) else f"{val:.1f}"))
            else:
                bar_text_list.append("")
        
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        fig.add_trace(go.Bar(
            x=df_match['Data'], y=df_match['Grafico_Val'], name=f"Valore {metrica}",
            marker_color=df_match.apply(lambda r: '#3498db' if r['Ha_Giocato'] and r['Colore'] == 'Sopra Media' else ('#9b59b6' if r['Ha_Giocato'] else 'rgba(0,0,0,0)'), axis=1).tolist(),
            text=bar_text_list, textposition='auto',
            customdata=np.stack((df_match['MP_Originale_Str'], df_match['🎯 Tiri da 2'], df_match['🏀 Tiri da 3'], df_match['🟨 Tiri Liberi'], df_match['Stato_Giocatore']), axis=-1),
            hovertemplate="<b>Data:</b> %{x}<br><b>Stato:</b> %{customdata[4]}<br>f<b>%{metrica}:</b> %{y}<br><b>⏱️ MP:</b> %{customdata[0]}<br><b>🎯 da 2:</b> %{customdata[1]}<br><b>🏀 da 3:</b> %{customdata[2]}<br><b>🟨 TL:</b> %{customdata[3]}<extra></extra>"
        ), secondary_y=False)
        
        fig.add_trace(go.Scatter(
            x=df_match['Data'], y=df_match['MP_Numerico'], name="Minuti Giocati",
            mode="lines+markers", line=dict(color="#e67e22", width=3), marker=dict(size=8, symbol="circle"),
            connectgaps=False, 
            hovertemplate="<b>Data:</b> %{x}<br><b>⏱️ Minuti:</b> %{y:.1f} min<extra></extra>"
        ), secondary_y=True)
        
        fig.add_hline(y=row['Media'], line_dash="dash", line_color="#2c3e50", annotation_text=f"Media {metrica}", secondary_y=False)
        
        fig.update_layout(title=f"Trend {metrica} & Minuti Giocati di {row['Giocatore']}", height=360, margin=dict(l=20, r=20, t=40, b=20), showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1))
        fig.update_xaxes(type='category')
        fig.update_yaxes(title_text=f"Valore {metrica}", secondary_y=False)
        fig.update_yaxes(title_text="⏱️ Minuti Giocati (Scala Destra)", secondary_y=True)
        
        st.plotly_chart(fig, use_container_width=True)
        st.divider()

    # Mostra Altri
    if totale_giocatori_disponibili > st.session_state.limite_giocatori:
        col_button, _ = st.columns([1, 3])
        with col_button:
            if st.button("➡ Mostra Altri 20 Giocatori", use_container_width=True):
                st.session_state.limite_giocatori += 20
                st.rerun()
