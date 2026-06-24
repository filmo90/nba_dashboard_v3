import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
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
        st.error(f"Errore connessione Database: {e}")
        return pd.DataFrame()

@st.cache_data
def carica_storico_regressione():
    try:
        # Carica il file di regressione storica se presente nel workspace
        df_hist = pd.read_csv("report_analisi_regressione_avanzata.csv")
        return df_hist[df_hist['Giocatore'].notna()]
    except:
        return pd.DataFrame()

# Esecuzione caricamento
df_nba = carica_boxscores()
df_storico = carica_storico_regressione()

if df_nba.empty:
    st.error("❌ Impossibile procedere senza dati. Verifica il database.")
    st.stop()

# Adattamento nomi colonne (se minuscole/maiuscole differiscono dal crawler)
if 'Player' in df_nba.columns:
    df_nba = df_nba.rename(columns={'Player': 'PLAYER_NAME'})

# ==========================================
# 🎛️ BARRA LATERALE: PANNELLO DI CONTROLLO ALGORITMO
# ==========================================
st.sidebar.title("🎮 Algoritmo NBA")

# 1. Selezione Metrica
metrica = st.sidebar.radio(
    "Seleziona Metrica Target:",
    ["PTS", "TRB", "AST", "3P", "PRA", "PA", "PR", "RA"],
    index=0,
    horizontal=True
)

# 2. Selezione Ordinamento
ordine = st.sidebar.selectbox(
    "Ordina i giocatori per:",
    ["Media Decrescente", "Deviazione Standard (Volatilità)", "Streak Attuale"]
)

# 3. Filtri Avanzati di Condizione (Streak)
st.sidebar.subheader("🎯 Filtri Predittivi")
filtro_bounce = st.sidebar.checkbox("🚨 Ultime 3 sotto media (Bounce-Back)")
filtro_streak_neg = st.sidebar.checkbox("💀 Ultime 6 sotto media (Streak Critica)")

# 4. Ricerca Testuale
ricerca_giocatore = st.sidebar.text_input("🔍 Cerca Giocatore specifico:")

# ==========================================
# 🧮 MOTORE MATEMATICO (COMPUTE STATS)
# ==========================================
def calcola_metriche_avanzate(df, metrica_scelta):
    giocatori_processati = []
    
    # Raggruppiamo per giocatore
    for giocatore, group in df.groupby('PLAYER_NAME'):
        # Ordiniamo dal match più vecchio al più recente per calcolare le strisce temporali
        group = group.sort_values('Date', ascending=True).reset_index(drop=True)
        
        # Calcolo dinamico della metrica combinata richiesta
        if metrica_scelta == "PRA": values = group['PTS'] + group['TRB'] + group['AST']
        elif metrica_scelta == "PA": values = group['PTS'] + group['AST']
        elif metrica_scelta == "PR": values = group['PTS'] + group['TRB']
        elif metrica_scelta == "RA": values = group['TRB'] + group['AST']
        else: values = pd.to_numeric(group[metrica_scelta], errors='coerce').fillna(0)
        
        mean_val = values.mean()
        
        # Sbarramenti minimi dell'algoritmo originario per eliminare i giocatori irrilevanti
        if metrica_scelta == "PTS" and mean_val < 8: continue
        if metrica_scelta == "TRB" and mean_val < 5: continue
        if metrica_scelta == "AST" and mean_val < 5: continue
        if metrica_scelta == "3P"  and mean_val < 1.5: continue
        if metrica_scelta == "PRA" and mean_val < 18: continue
        if metrica_scelta == "PA"  and mean_val < 12: continue
        if metrica_scelta == "PR"  and mean_val < 12: continue
        if metrica_scelta == "RA"  and mean_val < 10: continue
        
        std_val = values.std() if len(values) > 1 else 0
        
        # Calcolo dell'Indice di Efficienza Medio: (FG% + 3P% + FT%) / 3
        # Gestiamo le stringhe o percentuali pulendo i dati
        fg = pd.to_numeric(group['FG%'], errors='coerce').fillna(0).mean()
        tp_pct = pd.to_numeric(group['3P%'], errors='coerce').fillna(0).mean()
        ft = pd.to_numeric(group['FT%'], errors='coerce').fillna(0).mean()
        efficienza_media = (fg + tp_pct + ft) / 3
        
        # Analisi delle Strisce (Streak) partendo dall'ultima partita indietro
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
                
        # Condizioni specifiche sui filtri di striscia richiesti
        last_3 = val_list[-3:] if len(val_list) >= 3 else []
        last_6 = val_list[-6:] if len(val_list) >= 6 else []
        
        is_last3_below = len(last3) == 3 and all(x < mean_val for x in last3)
        is_last6_below = len(last6) == 6 and all(x < mean_val for x in last6)
        
        # Costruzione del record statistico finale del giocatore
        giocatori_processati.append({
            'Giocatore': giocatore,
            'Team': group['Team'].iloc[-1],
            'Media': mean_val,
            'DevStd': std_val,
            'Streak': streak,
            'TipoStreak': "SOPRA" if ultimo_sopra else "SOTTO",
            'Last3Below': is_last3_below,
            'Last6Below': is_last6_below,
            'Efficienza': efficienza_media,
            'DatiCompleti': group,
            'ValoriMetrica': values
        })
        
    return pd.DataFrame(giocatori_processati)

# Elaborazione dati tramite il motore interno
df_elaborato = calcola_metriche_avanzate(df_nba, metrica)

# ==========================================
# 👁️ APPLICAZIONE FILTRI SELEZIONATI DA INTERFACCIA
# ==========================================
if not df_elaborato.empty:
    if filtro_bounce:
        df_elaborato = df_elaborato[df_elaborato['Last3Below'] == True]
    if filtro_streak_neg:
        df_elaborato = df_elaborato[df_elaborato['Last6Below'] == True]
    if ricerca_giocatore:
        df_elaborato = df_elaborato[df_elaborato['Giocatore'].str.lower().contains(ricerca_giocatore.lower())]

    # Gestione ordinamento dinamico
    if ordine == "Media Decrescente":
        df_elaborato = df_elaborato.sort_values('Media', ascending=False)
    elif ordine == "Deviazione Standard (Volatilità)":
        df_elaborato = df_elaborato.sort_values('DevStd', ascending=False)
    elif ordine == "Streak Attuale":
        df_elaborato = df_elaborato.sort_values('Streak', ascending=False)

# ==========================================
# 🖥️ COSTRUZIONE DELLA GRAFICA INTERATTIVA
# ==========================================
st.title("📊 NBA Player Analytics & Historical Bounce-Back")
st.markdown(f"Configurazione Attuale: Analisi predittiva focalizzata su **{metrica}**")

if df_elaborato.empty:
    st.warning("Nessun giocatore soddisfa i criteri o i filtri di striscia impostati al momento.")
else:
    # Mostriamo i primi 10 giocatori risultanti per non intasare lo smartphone
    top_giocatori = df_elaborato.head(10)
    
    for _, row in top_giocatori.iterrows():
        # Creazione del pannello per ciascun giocatore (Stile Card)
        badge_streak = "🔴 SOTTO" if row['TipoStreak'] == "SOTTO" else "🟢 SOPRA"
        
        # Controllo stringa statistiche addizionali triple
        extra_info = ""
        if metrica == "3P" and '3PA' in row['DatiCompleti'].columns:
            media_attentati = pd.to_numeric(row['DatiCompleti']['3PA'], errors='coerce').mean()
            extra_info = f" | Media Tentati: {media_attentati:.1f}"

        st.subheader(f"👤 {row['Giocatore']} ({row['Team']})")
        st.markdown(
            f"**Media Stagione:** `{row['Media']:.1f}` | **Dev.Std:** `{row['DevStd']:.2f}` | "
            f"**Striscia Corrente:** `{row['Streak']} partite` {badge_streak} la media"
            f" | **Efficienza Tiro:** `{row['Efficienza']:.2f}`{extra_info}"
        )
        
        # 📚 INTEGRAZIONE INFRASTRUTTURA STORICA (BOUNCE BACK ALERT)
        if not df_storico.empty:
            storico_giocatore = df_storico[(df_storico['Giocatore'] == row['Giocatore']) & (df_storico['Metrica'] == metrica)]
            if not storico_giocatore.empty:
                # Estraiamo il tempo medio di recupero calcolato dal tuo script di regressione
                recupero = storico_giocatore['Partite_per_Recupero'].iloc[0]
                
                if row['Last3Below']:
                    st.error(
                        f"⚠️ **BOUNCE-BACK ALERT STORICO:** Il modello 2020-25 indica che dopo questa striscia "
                        f"il giocatore impiega mediamente **{recupero} partite** per rompere il trend negativo. Occhio alle quote."
                    )
                else:
                    st.info(f"📋 *Riferimento Storico 2020-25:* Tempo medio stimato di reazione per questo scenario: {recupero} match.")

        # 📈 GRAFICO A BARRE INTERATTIVO CON SOGLIA DI MEDIA
        # Prepariamo i dati cronologici per il grafico
        df_match = row['DatiCompleti'].copy()
        
        # Calcoliamo dinamicamente il valore del singolo match per il grafico
        if metrica == "PRA": df_match['Grafico_Val'] = df_match['PTS'] + df_match['TRB'] + df_match['AST']
        elif metrica == "PA": df_match['Grafico_Val'] = df_match['PTS'] + df_match['AST']
        elif metrica == "PR": df_match['Grafico_Val'] = df_match['PTS'] + df_match['TRB']
        elif metrica == "RA": df_match['Grafico_Val'] = df_match['TRB'] + df_match['AST']
        else: df_match['Grafico_Val'] = pd.to_numeric(df_match[metrica], errors='coerce').fillna(0)
        
        # Generiamo colori differenziati in base al rendimento del singolo match rispetto alla media
        df_match['Colore'] = np.where(df_match['Grafico_Val'] >= row['Media'], 'Sopra Media', 'Sotto Media')
        
        fig = px.bar(
            df_match,
            x='Date',
            y='Grafico_Val',
            color='Colore',
            color_discrete_map={'Sopra Media': '#3498db', 'Sotto Media': '#9b59b6'},
            text_auto=True,
            title=f"Trend Prestazioni Recenti di {row['Giocatore']}"
        )
        
        # Linea orizzontale della media matematica
        fig.add_hline(y=row['Media'], line_dash="dash", line_color="#2c3e50", annotation_text="Media Stagione")
        fig.update_layout(height=300, margin=dict(l=20, r=20, t=40, b=20), showlegend=False)
        
        st.plotly_chart(fig, use_container_width=True)
        st.divider()
