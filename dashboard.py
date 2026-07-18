import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.graph_objects as go
from sqlalchemy import create_engine

# ==========================================
# ⚙️ CONFIGURAZIONE PAGINA
# ==========================================
st.set_page_config(page_title="📊 NBA Advanced Analytics & Bounce-Back", page_icon="🏀", layout="wide")

DB_URL = st.secrets["DB_URL"]

# ==========================================
# 📥 CARICAMENTO DATI (DB CLOUD + FILE STORICO)
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

# Esecuzione caricamento
df_nba = carica_boxscores()
df_storico = carica_storico_regressione()
df_infortuni, err_infortuni = carica_infortuni()
df_schedule, err_schedule = carica_calendario()

if df_nba.empty:
    st.error("❌ Impossibile procedere senza dati. Verifica il database.")
    st.stop()

# Uniformiamo il nome della colonna Player se necessario
if 'Player' in df_nba.columns:
    df_nba = df_nba.rename(columns={'Player': 'PLAYER_NAME'})

# Sincronizzazione colonne Minuti se presenti con nomi diversi
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

# Logica per estrarre le squadre di domani
if filtro_domani:
    if err_schedule:
        st.sidebar.error(f"❌ Errore caricamento calendario: {err_schedule}")
    elif not df_schedule.empty:
        # Calcola la data di domani
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
                st.sidebar.warning("Nomi colonne 'Home'/'Away' non trovati nella tabella schedule.")
        else:
            st.sidebar.warning("Nessuna partita in programma per domani.")
            lista_squadre = []
    else:
        st.sidebar.warning("Nessun dato sul calendario di domani trovato.")
        lista_squadre = []

# 3. FILTRO SQUADRE
squadre_selezionate = st.sidebar.multiselect(
    "🏀 Filtra per Squadra:",
    options=lista_squadre,
    default=lista_squadre
)

# 4. WIDGET INFORTUNI
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
        
        # 🐞 DEBUG VISIVO: Mostra cosa sta cercando di incrociare Streamlit
        with st.sidebar.expander("🛠️ Debug Nomi Squadre (Perché non vedo giocatori?)"):
            st.warning("Se sai che ci sono infortunati, i nomi qui sotto non combaciano:")
            st.write("**Le tue squadre selezionate:**", squadre_pulite[:5])
            if col_team:
                st.write("**Le squadre scritte nel DB Infortuni:**", df_infortuni[col_team].unique().tolist()[:5])
            st.info("Assicurati che i nomi coincidano (es. LAL vs Los Angeles Lakers)")
            
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
    st.sidebar.info("Tabella infortuni vuota o non configurata.")
# 5. Selezione Ordinamento
ordine = st.sidebar.selectbox(
    "Ordina i giocatori per:",
    ["Media Decrescente", "Deviazione Standard (Volatilità)", "Streak Attuale"]
)

# 6. Filtri Avanzati di Condizione (Streak)
st.sidebar.subheader("🎯 Filtri Predittivi")
filtro_bounce = st.sidebar.checkbox("🚨 Ultime 3 sotto media (Bounce-Back)")
filtro_streak_neg = st.sidebar.checkbox("💀 Ultime 6 sotto media (Streak Critica)")

# 7. BARRA DI RICERCA GIOCATORI
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
                parti = s.split(':')
                return float(parti[0]) + float(parti[1]) / 60.0
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
        
        if 'MP' in group.columns:
            mp_cleaned = group['MP'].apply(_pulisci_mp)
        else:
            mp_cleaned = pd.Series([0.0] * len(group))
        
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
            sopra = v >= mean_val
            if sopra == ultimo_sopra:
                streak += 1
            else:
                break
                
        last3 = val_list[-3:] if len(val_list) >= 3 else []
        last6 = val_list[-6:] if len(val_list) >= 6 else []
        
        is_last3_below = len(last3) == 3 and all(x < mean_val for x in last3)
        is_last6_below = len(last6) == 6 and all(x < mean_val for x in last6)
        
        giocatori_processati.append({
            'Giocatore': giocatore,
            'Team': group['Team'].iloc[-1],
            'Media': mean_val,
            'DevStd': std_val,
            'Media_Minuti': mean_mp,
            'DevStd_Minuti': std_mp,
            'Streak': streak,
            'TipoStreak': "SOPRA" if ultimo_sopra else "SOTTO",
            'Last3Below': is_last3_below,
            'Last6Below': is_last6_below,
            'Efficienza': efficienza_media,
            'DatiCompleti': group,
            'ValoriMetrica': values
        })
        
    return pd.DataFrame(giocatori_processati)

# Elaborazione dati
df_elaborato = calcola_metriche_avanzate(df_nba, metrica, squadre_selezionate)

# ==========================================
# 👁️ APPLICAZIONE FILTRI DA INTERFACCIA
# ==========================================
if not df_elaborato.empty:
    if filtro_bounce:
        df_elaborato = df_elaborato[df_elaborato['Last3Below'] == True]
    if filtro_streak_neg:
        df_elaborato = df_elaborato[df_elaborato['Last6Below'] == True]
        
    if ricerca_giocatore:
        df_elaborato = df_elaborato[df_elaborato['Giocatore'].str.lower().str.contains(ricerca_giocatore.lower(), na=False)]

    if ordine == "Media Decrescente":
        df_elaborato = df_elaborato.sort_values('Media', ascending=False)
    elif ordine == "Deviazione Standard (Volatilità)":
        df_elaborato = df_elaborato.sort_values('DevStd', ascending=False)
    elif ordine == "Streak Attuale":
        df_elaborato = df_elaborato.sort_values('Streak', ascending=False)

# ==========================================
# ⚙️ GESTIONE PAGINAZIONE DINAMICA
# ==========================================
if "limite_giocatori" not in st.session_state:
    st.session_state.limite_giocatori = 20

totale_giocatori_disponibili = len(df_elaborato) if not df_elaborato.empty else 0

# ==========================================
# 🖥️ COSTRUZIONE GRAFICA
# ==========================================
st.title("📊 NBA Player Analytics & Historical Bounce-Back")
st.markdown(f"Configurazione Attuale: Analisi predittiva focalizzata su **{metrica}**")

if df_elaborato.empty:
    st.warning("⚠️ Nessun giocatore soddisfa i criteri, i filtri di striscia o i filtri squadra impostati.")
else:
    top_giocatori = df_elaborato.head(st.session_state.limite_giocatori)
    st.info(f"Visualizzati {len(top_giocatori)} giocatori su un totale di {totale_giocatori_disponibili} trovati.")
    
    # Pre-calcolo partite totali giocate da ciascuna squadra
    team_games_count = df_nba.groupby('Team')['Date'].nunique().to_dict()
    
    for _, row in top_giocatori.iterrows():
        badge_streak = "🔴 SOTTO" if row['TipoStreak'] == "SOTTO" else "🟢 SOPRA"
        
        extra_info = ""
        if metrica == "3P" and '3PA' in row['DatiCompleti'].columns:
            media_attentati = pd.to_numeric(row['DatiCompleti']['3PA'], errors='coerce').mean()
            extra_info = f" | Media Tentati: {media_attentati:.1f}"

        # CALCOLO PARTITE GIOCATE
        partite_giocate = len(row['DatiCompleti'])
        partite_totali_squadra = team_games_count.get(row['Team'], partite_giocate)

        st.subheader(f"👤 {row['Giocatore']} ({row['Team']}) — 🏟️ Partite: {partite_giocate}/{partite_totali_squadra}")
        st.markdown(
            f"**Media {metrica}:** `{row['Media']:.1f}` | **Dev.Std {metrica}:** `{row['DevStd']:.2f}` |\n"
            f"**Media Minuti (MP):** `{row['Media_Minuti']:.1f}` | **Dev.Std Minuti:** `{row['DevStd_Minuti']:.2f}` |\n"
            f"**Striscia Corrente:** `{row['Streak']} partite` {badge_streak} la media"
            f" | **Efficienza Tiro:** `{row['Efficienza']:.2f}`{extra_info}"
        )
        
        if not df_storico.empty:
            storico_giocatore = df_storico[(df_storico['Giocatore'] == row['Giocatore']) & (df_storico['Metrica'] == metrica)]
            if not storico_giocatore.empty:
                recupero = storico_giocatore['Partite_per_Recupero'].iloc[0]
                if row['Last3Below']:
                    st.error(
                        f"⚠️ **BOUNCE-BACK ALERT STORICO:** Il modello 2020-25 indica che dopo questa striscia "
                        f"il giocatore impiega mediamente **{recupero} partite** per rompere il trend negativo. Possibile Bounce-Back."
                    )
                else:
                    st.info(f"📋 *Riferimento Storico 2020-25:* Tempo medio stimato di reazione: {recupero} match.")

        # ==========================================
        # 📈 PREPARAZIONE DATI GRAFICO (CON GESTIONE BUCHI E ZERO)
        # ==========================================
        df_match = row['DatiCompleti'].copy()
        player_team = row['Team']
        
        # 1. Troviamo tutte le date cronologiche in cui la SQUADRA ha disputato un match
        tutte_date_squadra = sorted(df_nba[df_nba['Team'] == player_team]['Date'].unique())
        df_completo_squadra = pd.DataFrame({'Date': tutte_date_squadra})
        
        # 2. Allineiamo i dati del giocatore a quelli della squadra (Right Join su template vuoto)
        df_match = pd.merge(df_completo_squadra, df_match, on='Date', how='left')
        
        # 3. Identifichiamo se il giocatore era in campo
        df_match['Ha_Giocato'] = df_match['PLAYER_NAME'].notna()
        
        # 4. Calcoliamo la metrica target (mettiamo NaN se il giocatore non era a referto)
        if metrica == "PRA": 
            df_match['Grafico_Val'] = np.where(df_match['Ha_Giocato'], df_match['PTS'].fillna(0) + df_match['TRB'].fillna(0) + df_match['AST'].fillna(0), np.nan)
        elif metrica == "PA": 
            df_match['Grafico_Val'] = np.where(df_match['Ha_Giocato'], df_match['PTS'].fillna(0) + df_match['AST'].fillna(0), np.nan)
        elif metrica == "PR": 
            df_match['Grafico_Val'] = np.where(df_match['Ha_Giocato'], df_match['PTS'].fillna(0) + df_match['TRB'].fillna(0), np.nan)
        elif metrica == "RA": 
            df_match['Grafico_Val'] = np.where(df_match['Ha_Giocato'], df_match['TRB'].fillna(0) + df_match['AST'].fillna(0), np.nan)
        else: 
            df_match['Grafico_Val'] = np.where(df_match['Ha_Giocato'], pd.to_numeric(df_match[metrica], errors='coerce').fillna(0), np.nan)
        
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
        
        # Minuti a NaN se non ha giocato, così la linea dei minuti si rompe (buco nel grafico)
        df_match['MP_Numerico'] = np.where(
            df_match['Ha_Giocato'], 
            df_match['MP'].apply(_pulisci_mp_grafico), 
            np.nan
        )
        
        # Sanificazione colonne per i Tooltip
        for c in ['FG', 'FGA', '3P', '3PA', 'FT', 'FTA']:
            if c in df_match.columns:
                df_match[c] = pd.to_numeric(df_match[c], errors='coerce').fillna(0).astype(int)
        
        # Campi descrittivi intelligenti
        df_match['🎯 Tiri da 2'] = np.where(
            df_match['Ha_Giocato'],
            (df_match['FG'] - df_match['3P']).astype(str) + " / " + (df_match['FGA'] - df_match['3PA']).astype(str),
            "N/D (DNP - Assente)"
        )
        df_match['🏀 Tiri da 3'] = np.where(
            df_match['Ha_Giocato'],
            df_match['3P'].astype(str) + " / " + df_match['3PA'].astype(str),
            "N/D (DNP - Assente)"
        )
        df_match['🟨 Tiri Liberi'] = np.where(
            df_match['Ha_Giocato'],
            df_match['FT'].astype(str) + " / " + df_match['FTA'].astype(str),
            "N/D (DNP - Assente)"
        )
        
        df_match['Stato_Giocatore'] = np.where(df_match['Ha_Giocato'], "GIOCATO", "ASSENTE / DNP")
        df_match['MP_Originale_Str'] = np.where(df_match['Ha_Giocato'], df_match['MP'].astype(str), "0")
        df_match['Data'] = df_match['Date'].dt.strftime('%Y-%m-%d')
        
        # Generazione scritte sopra le barre: se ha giocato mostriamo il numero (anche se è 0), se DNP lasciamo vuoto
        bar_text_list = []
        for _, r in df_match.iterrows():
            if r['Ha_Giocato']:
                val = r['Grafico_Val']
                if pd.isna(val):
                    bar_text_list.append("0")
                else:
                    if val == int(val):
                        bar_text_list.append(str(int(val)))
                    else:
                        bar_text_list.append(f"{val:.1f}")
            else:
                bar_text_list.append("") # Stringa vuota per indicare il buco della partita saltata
        
        # ==========================================
        # 📈 DISEGNO GRAFICO AVANZATO
        # ==========================================
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        # Asse Y Sinistro: Istogramma Metrica Target
        fig.add_trace(
            go.Bar(
                x=df_match['Data'],
                y=df_match['Grafico_Val'],
                name=f"Valore {metrica}",
                marker_color=df_match.apply(
                    lambda r: '#3498db' if r['Ha_Giocato'] and r['Colore'] == 'Sopra Media' 
                    else ('#9b59b6' if r['Ha_Giocato'] else 'rgba(0,0,0,0)'), axis=1
                ).tolist(),
                text=bar_text_list,
                textposition='auto',
                customdata=np.stack((
                    df_match['MP_Originale_Str'], 
                    df_match['🎯 Tiri da 2'], 
                    df_match['🏀 Tiri da 3'], 
                    df_match['🟨 Tiri Liberi'],
                    df_match['Stato_Giocatore']
                ), axis=-1),
                hovertemplate=(
                    "<b>Data:</b> %{x}<br>" +
                    "<b>Stato nel Match:</b> %{customdata[4]}<br>" +
                    f"<b>{metrica}:</b> %{{y}}<br>" +
                    "<b>⏱️ MP:</b> %{customdata[0]}<br>" +
                    "<b>🎯 Tiri da 2:</b> %{customdata[1]}<br>" +
                    "<b>🏀 Tiri da 3:</b> %{customdata[2]}<br>" +
                    "<b>🟨 Tiri Liberi:</b> %{customdata[3]}<extra></extra>"
                )
            ),
            secondary_y=False
        )
        
        # Asse Y Destro: Linea Minuti Giocati (Non unisce i buchi se connectgaps=False)
        fig.add_trace(
            go.Scatter(
                x=df_match['Data'],
                y=df_match['MP_Numerico'],
                name="Minuti Giocati",
                mode="lines+markers",
                line=dict(color="#e67e22", width=3),
                marker=dict(size=8, symbol="circle"),
                connectgaps=False, # <-- Molto Importante: interrompe la linea se il giocatore salta il match!
                hovertemplate="<b>Data:</b> %{x}<br><b>⏱️ Minuti:</b> %{y:.1f} min<extra></extra>"
            ),
            secondary_y=True
        )
        
        # Linea Media
        fig.add_hline(
            y=row['Media'], 
            line_dash="dash", 
            line_color="#2c3e50", 
            annotation_text=f"Media {metrica}",
            secondary_y=False
        )
        
        fig.update_layout(
            title=f"Trend {metrica} & Minuti Giocati di {row['Giocatore']}",
            height=360, 
            margin=dict(l=20, r=20, t=40, b=20),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1)
        )
        
        # Impostiamo l'asse X come categorico per allineare correttamente le partite consecutive
        fig.update_xaxes(type='category')
        
        fig.update_yaxes(title_text=f"Valore {metrica}", secondary_y=False)
        fig.update_yaxes(title_text="⏱️ Minuti Giocati (Scala Destra)", secondary_y=True)
        
        st.plotly_chart(fig, use_container_width=True)
        st.divider()

    # ==========================================
    # 🔄 PULSANTE DINAMICO "MOSTRA ALTRI"
    # ==========================================
    if totale_giocatori_disponibili > st.session_state.limite_giocatori:
        st.write("")
        col_button, _ = st.columns([1, 3])
        with col_button:
            if st.button("➡ Mostra Altri 20 Giocatori", use_container_width=True):
                st.session_state.limite_giocatori += 20
                st.rerun()
