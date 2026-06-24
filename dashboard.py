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

# Uniformiamo il nome della colonna Player se necessario
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

# 2. FILTRO SQUADRE (Multiselect - Attivo di default su tutte come nel file HTML)
lista_squadre = sorted(df_nba['Team'].unique().tolist())
squadre_selezionate = st.sidebar.multiselect(
    "🏀 Filtra per Squadra:",
    options=lista_squadre,
    default=lista_squadre
)

# 3. Selezione Ordinamento
ordine = st.sidebar.selectbox(
    "Ordina i giocatori per:",
    ["Media Decrescente", "Deviazione Standard (Volatilità)", "Streak Attuale"]
)

# 4. Filtri Avanzati di Condizione (Streak)
st.sidebar.subheader("🎯 Filtri Predittivi")
filtro_bounce = st.sidebar.checkbox("🚨 Ultime 3 sotto media (Bounce-Back)")
filtro_streak_neg = st.sidebar.checkbox("💀 Ultime 6 sotto media (Streak Critica)")

# 5. BARRA DI RICERCA GIOCATORI (Corretta)
ricerca_giocatore = st.sidebar.text_input("🔍 Cerca Giocatore specifico:")

# ==========================================
# 🧮 MOTORE MATEMATICO (COMPUTE STATS)
# ==========================================
def calcola_metriche_avanzate(df, metrica_scelta, team_filter):
    giocatori_processati = []
    
    # Applichiamo subito il filtro sulle squadre selezionate
    df_filtrato_team = df[df['Team'].isin(team_filter)]
    
    if df_filtrato_team.empty:
        return pd.DataFrame()
    
    for giocatore, group in df_filtrato_team.groupby('PLAYER_NAME'):
        group = group.sort_values('Date', ascending=True).reset_index(drop=True)
        
        if metrica_scelta == "PRA": values = group['PTS'] + group['TRB'] + group['AST']
        elif metrica_scelta == "PA": values = group['PTS'] + group['AST']
        elif metrica_scelta == "PR": values = group['PTS'] + group['TRB']
        elif metrica_scelta == "RA": values = group['TRB'] + group['AST']
        else: values = pd.to_numeric(group[metrica_scelta], errors='coerce').fillna(0)
        
        mean_val = values.mean()
        
        # Sbarramenti minimi dell'algoritmo originario
        if metrica_scelta == "PTS" and mean_val < 8: continue
        if metrica_scelta == "TRB" and mean_val < 5: continue
        if metrica_scelta == "AST" and mean_val < 5: continue
        if metrica_scelta == "3P"  and mean_val < 1.5: continue
        if metrica_scelta == "PRA" and mean_val < 18: continue
        if metrica_scelta == "PA"  and mean_val < 12: continue
        if metrica_scelta == "PR"  and mean_val < 12: continue
        if metrica_scelta == "RA"  and mean_val < 10: continue
        
        std_val = values.std() if len(values) > 1 else 0
        
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
        
    # FIX BARRA DI RICERCA GIOCATORE (Aggiunto il secondo modificatore .str)
    if ricerca_giocatore:
        df_elaborato = df_elaborato[df_elaborato['Giocatore'].str.lower().str.contains(ricerca_giocatore.lower(), na=False)]

    if ordine == "Media Decrescente":
        df_elaborato = df_elaborato.sort_values('Media', ascending=False)
    elif ordine == "Deviazione Standard (Volatilità)":
        df_elaborato = df_elaborato.sort_values('DevStd', ascending=False)
    elif ordine == "Streak Attuale":
        df_elaborato = df_elaborato.sort_values('Streak', ascending=False)

# ==========================================
# 🖥️ COSTRUZIONE GRAFICA
# ==========================================
st.title("📊 NBA Player Analytics & Historical Bounce-Back")
st.markdown(f"Configurazione Attuale: Analisi predittiva focalizzata su **{metrica}**")

if df_elaborato.empty:
    st.warning("⚠️ Nessun giocatore soddisfa i criteri, i filtri di striscia o i filtri squadra impostati.")
else:
    top_giocatori = df_elaborato.head(10)
    
    for _, row in top_giocatori.iterrows():
        badge_streak = "🔴 SOTTO" if row['TipoStreak'] == "SOTTO" else "🟢 SOPRA"
        
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

        # --- PREPARAZIONE DATI GRAFICO E PULIZIA COLONNE TOOLTIP ---
        df_match = row['DatiCompleti'].copy()
        
        if metrica == "PRA": df_match['Grafico_Val'] = df_match['PTS'] + df_match['TRB'] + df_match['AST']
        elif metrica == "PA": df_match['Grafico_Val'] = df_match['PTS'] + df_match['AST']
        elif metrica == "PR": df_match['Grafico_Val'] = df_match['PTS'] + df_match['TRB']
        elif metrica == "RA": df_match['Grafico_Val'] = df_match['TRB'] + df_match['AST']
        else: df_match['Grafico_Val'] = pd.to_numeric(df_match[metrica], errors='coerce').fillna(0)
        
        df_match['Colore'] = np.where(df_match['Grafico_Val'] >= row['Media'], 'Sopra Media', 'Sotto Media')
        
        # Sanificazione e conversione in stringa pulita "Segnati/Tentati" per i Tooltip
        for c in ['FG', 'FGA', '3P', '3PA', 'FT', 'FTA']:
            if c in df_match.columns:
                df_match[c] = pd.to_numeric(df_match[c], errors='coerce').fillna(0).astype(int)
        
        # Calcolo matematico dei tiri da 2 punti per sottrazione (FG - 3P)
        if 'FG' in df_match.columns and '3P' in df_match.columns:
            df_match['🎯 Tiri da 2 (Segnati/Tentati)'] = (df_match['FG'] - df_match['3P']).astype(str) + " / " + (df_match['FGA'] - df_match['3PA']).astype(str)
        else:
            df_match['🎯 Tiri da 2 (Segnati/Tentati)'] = "n/d"
            
        if '3P' in df_match.columns and '3PA' in df_match.columns:
            df_match['🏀 Tiri da 3 (Segnati/Tentati)'] = df_match['3P'].astype(str) + " / " + df_match['3PA'].astype(str)
        else:
            df_match['🏀 Tiri da 3 (Segnati/Tentati)'] = "n/d"
            
        if 'FT' in df_match.columns and 'FTA' in df_match.columns:
            df_match['🟨 Tiri Liberi (Segnati/Tentati)'] = df_match['FT'].astype(str) + " / " + df_match['FTA'].astype(str)
        else:
            df_match['🟨 Tiri Liberi (Segnati/Tentati)'] = "n/d"
            
        # Formattazione data per asse X grafica
        df_match['Data'] = df_match['Date'].dt.strftime('%Y-%m-%d')
        
        # Generazione Grafico Potenziato con Hover Data customizzato
        fig = px.bar(
            df_match,
            x='Data',
            y='Grafico_Val',
            color='Colore',
            color_discrete_map={'Sopra Media': '#3498db', 'Sotto Media': '#9b59b6'},
            text_auto=True,
            hover_data={
                'Data': True,
                'Grafico_Val': True,
                'MP': True,
                '🎯 Tiri da 2 (Segnati/Tentati)': True,
                '🏀 Tiri da 3 (Segnati/Tentati)': True,
                '🟨 Tiri Liberi (Segnati/Tentati)': True,
                'Colore': False # Nascondiamo l'etichetta del colore interna
            },
            labels={
                'Grafico_Val': f'Valore {metrica}',
                'MP': '⏱️ Minuti Giocati'
            },
            title=f"Trend Prestazioni Recenti di {row['Giocatore']}"
        )
        
        fig.add_hline(y=row['Media'], line_dash="dash", line_color="#2c3e50", annotation_text="Media Stagione")
        fig.update_layout(height=320, margin=dict(l=20, r=20, t=40, b=20), showlegend=False)
        
        st.plotly_chart(fig, use_container_width=True)
        st.divider()
