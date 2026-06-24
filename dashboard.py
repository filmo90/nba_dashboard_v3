import streamlit as st
import pandas as pd
from sqlalchemy import create_engine

st.set_page_config(page_title="NBA Fantasy Dashboard", page_icon="🏀", layout="wide")

# PROTEZIONE: Carica l'URI dai segreti criptati di Streamlit, non in chiaro
DB_URL = st.secrets["DB_URL"]

@st.cache_data(ttl=1800) # Aggiorna la cache ogni 30 minuti
def carica_dati():
    engine = create_engine(DB_URL)
    return pd.read_sql("SELECT * FROM nba_boxscores ORDER BY \"Date\" DESC", engine)

st.title("🏀 NBA Player Props Dashboard")
st.markdown("Dati archiviati su Supabase e accessibili da qualsiasi dispositivo.")

with st.spinner("Connessione al database cloud..."):
    df_nba = carica_dati()

if not df_nba.empty:
    col1, col2, col3 = st.columns(3)
    col1.metric("Giornate Scansionate", df_nba['Date'].nunique())
    col2.metric("Giocatori Totali", df_nba['Player'].nunique())
    col3.metric("Record nel DB", len(df_nba))
    
    st.divider()
    st.subheader("Tabellino Generale Completo")
    st.dataframe(df_nba, use_container_width=True)
else:
    st.warning("Database vuoto o non raggiungibile.")
