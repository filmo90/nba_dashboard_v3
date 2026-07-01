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

# Sincronizzazione colonne Minuti se presenti con nomi diversi
if 'MIN' in df_nba.columns and 'MP' not in df_nba.columns:
    df_nba['MP'] = df_nba['MIN']

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

# 2. FILTRO SQUADRE
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

# 5. BARRA DI RICERCA GIOCATORI
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
    
    # Funzione di supporto per pulire i minuti se salvati come stringhe "MM:SS"
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
        
        # Calcolo Media e Deviazione Standard dei Minuti Giocati (MP)
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

        # --- PREPARAZIONE DATI GRAFICO E PULIZIA COLONNE TOOLTIP ---
        df_match = row['DatiCompleti'].copy()
        
        if metrica == "PRA": df_match['Grafico_Val'] = df_match['PTS'] + df_match['TRB'] + df_match['AST']
        elif metrica == "PA": df_match['Grafico_Val'] = df_match['PTS'] + df_match['AST']
        elif metrica == "PR": df_match['Grafico_Val'] = df_match['PTS'] + df_match['TRB']
        elif metrica == "RA": df_match['Grafico_Val'] = df_match['TRB'] + df_match['AST']
        else: df_match['Grafico_Val'] = pd.to_numeric(df_match[metrica], errors='coerce').fillna(0)
        
        df_match['Colore'] = np.where(df_match['Grafico_Val'] >= row['Media'], 'Sopra Media', 'Sotto Media')
        
        # Pulizia minuti specifica per la visualizzazione grafica
        def _pulisci_mp_grafico(x):
            if pd.isna(x): return 0.0
            s = str(x).strip()
            if ':' in s:
                try:
                    p = s.split(':')
                    return float(p[0]) + float(p[1]) / 60.0
                except: return 0.0
            try: return float(s)
            except: return 0.0
        
        df_match['MP_Numerico'] = df_match['MP'].apply(_pulisci_mp_grafico) if 'MP' in df_match.columns else 0.0
        
        # Sanificazione e conversione per i Tooltip
        for c in ['FG', 'FGA', '3P', '3PA', 'FT', 'FTA']:
            if c in df_match.columns:
                df_match[c] = pd.to_numeric(df_match[c], errors='coerce').fillna(0).astype(int)
        
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
            
        df_match['Data'] = df_match['Date'].dt.strftime('%Y-%m-%d')
        
        # ==========================================
        # 📈 COSTRUZIONE GRAFICO AVANZATO DOPPIO ASSE Y
        # ==========================================
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        # Asse Y Sinistro: Istogramma Metrica Selezionata
        fig.add_trace(
            go.Bar(
                x=df_match['Data'],
                y=df_match['Grafico_Val'],
                name=f"Valore {metrica}",
                marker_color=df_match['Colore'].map({'Sopra Media': '#3498db', 'Sotto Media': '#9b59b6'}).tolist(),
                text=df_match['Grafico_Val'].round(1),
                textposition='auto',
                customdata=np.stack((
                    df_match['MP'],
                    df_match['🎯 Tiri da 2 (Segnati/Tentati)'],
                    df_match['🏀 Tiri da 3 (Segnati/Tentati)'],
                    df_match['🟨 Tiri Liberi (Segnati/Tentati)']
                ), axis=-1),
                hovertemplate=(
                    "<b>Data:</b> %{x}<br>" +
                    f"<b>{metrica}:</b> %{{y}}<br>" +
                    "<b>⏱️ MP originali:</b> %{customdata[0]}<br>" +
                    "<b>🎯 Tiri da 2:</b> %{customdata[1]}<br>" +
                    "<b>🏀 Tiri da 3:</b> %{customdata[2]}<br>" +
                    "<b>🟨 Tiri Liberi:</b> %{customdata[3]}<extra></extra>"
                )
            ),
            secondary_y=False
        )
        
        # Asse Y Destro: Linea Minuti Giocati
        fig.add_trace(
            go.Scatter(
                x=df_match['Data'],
                y=df_match['MP_Numerico'],
                name="Minuti Giocati",
                mode="lines+markers",
                line=dict(color="#e67e22", width=3),
                marker=dict(size=8, symbol="circle"),
                hovertemplate="<b>Data:</b> %{x}<br><b>⏱️ Minuti:</b> %{y:.1f} min<extra></extra>"
            ),
            secondary_y=True
        )
        
        # Linea Orizzontale Media Stagionale Metrica Target
        fig.add_hline(
            y=row['Media'], 
            line_dash="dash", 
            line_color="#2c3e50", 
            annotation_text=f"Media {metrica}",
            secondary_y=False
        )
        
        # Configurazione Layout Grafico
        fig.update_layout(
            title=f"Trend {metrica} & Minuti Giocati di {row['Giocatore']}",
            height=360, 
            margin=dict(l=20, r=20, t=40, b=20),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1)
        )
        
        fig.update_yaxes(title_text=f"Valore {metrica}", secondary_y=False)
        fig.update_yaxes(title_text="⏱️ Minuti Giocati (Scala Destra)", secondary_y=True)
        
        st.plotly_chart(fig, use_container_width=True)
        st.divider()
