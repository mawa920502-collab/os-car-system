import streamlit as st
import pandas as pd
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import webbrowser
import re
from urllib.parse import quote_plus
import time
import shutil

CSV_PATH = "baza.csv"

# ✅ BACKUP DANYCH
def backup_data():
    if os.path.exists(CSV_PATH):
        backup_name = f"backup_baza_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        shutil.copy2(CSV_PATH, backup_name)
        return backup_name
    return None

# ⚡ OPTYMALIZACJA - cache dla danych
@st.cache_data(ttl=300)
def load_data():
    if not os.path.exists(CSV_PATH):
        return pd.DataFrame(columns=["id", "tytul", "cena", "link", "opis", "status", "notatka", "dodano"])
    df = pd.read_csv(CSV_PATH, dtype=str)
    # ✅ USUWANIE 'nan' Z PUSTYCH PÓL
    df = df.replace('nan', '').fillna('')
    return df

# ⚡ OPTYMALIZACJA - szybszy zapis
def save_data(df):
    # ✅ USUWANIE 'nan' PRZED ZAPISEM
    df = df.replace('nan', '').fillna('')
    df.to_csv(CSV_PATH, index=False, encoding="utf-8")
    # ✅ TWORZENIE BACKUPU PRZY KAŻDYM ZAPISIE
    backup_name = backup_data()
    if backup_name:
        st.toast(f"📂 Backup utworzony: {backup_name}", icon="✅")
    load_data.clear()

def save_field(idx, key, column):
    value = st.session_state.get(key, "")
    current_df = load_data()
    current_df.at[idx, column] = value
    save_data(current_df)

def extract_ids_and_links(html):
    soup = BeautifulSoup(html, "html.parser")
    links = soup.select("a[href*='sprzedajemy.pl/'][href*='nr']")
    ids, urls = [], []
    for link in links:
        href = link.get("href", "")
        if "nr" in href:
            offer_id = href.split("-")[-1].replace("nr", "")
            clean = href.replace("httpshttps", "https").replace("https//", "https://").replace("https://sprzedajemy.plhttps://", "https://sprzedajemy.pl/")
            full_url = "https://sprzedajemy.pl" + href if not href.startswith("https") else clean
            ids.append(offer_id)
            urls.append(full_url)
    return ids, urls

def analyze_search(base):
    headers = {"User-Agent": "Mozilla/5.0"}
    url_title = f"https://oscar.sprzedajemy.pl/szukaj?schm2=ls&catCode=6bea9f&inp_text%5Bv%5D={base}&inp_category_id=2&inp_location_id=1"
    url_id = f"{url_title}&inp_text%5Bn%5D=1"

    # ⚡ DODAJ TIMEOUT - szybsze błędy
    try:
        html_title = requests.get(url_title, headers=headers, timeout=8).text
        html_id = requests.get(url_id, headers=headers, timeout=8).text
    except requests.exceptions.Timeout:
        return {"ids_title": [], "urls_title": [], "ids_id": [], "urls_id": [], "url_title": url_title, "url_id": url_id}
    except Exception as e:
        st.error(f"Błąd połączenia: {e}")
        return {"ids_title": [], "urls_title": [], "ids_id": [], "urls_id": [], "url_title": url_title, "url_id": url_id}
    
    ids_title, urls_title = extract_ids_and_links(html_title)
    ids_id, urls_id = extract_ids_and_links(html_id)

    return {
        "ids_title": ids_title,
        "urls_title": urls_title,
        "ids_id": ids_id,
        "urls_id": urls_id,
        "url_title": url_title,
        "url_id": url_id
    }

def szukaj_allegro_parts_skoda(fraza):
    try:
        encoded_fraza = quote_plus(fraza)
        allegro_url = f"https://allegro.pl/uzytkownik/PARTS_SKODA?string={encoded_fraza}"
        
        return {
            "link": allegro_url,
            "fraza": fraza,
            "platforma": "Allegro",
            "seller": "CZĘŚCI_SKODA"
        }
        
    except Exception as e:
        st.error(f"Błąd Allegro: {str(e)}")
        return None

def search_multiple_platforms(query):
    results = {}
    
    base = query.strip().replace(" ", "+")
    sprzedajemy_result = analyze_search(base)
    results["sprzedajemy"] = sprzedajemy_result
    
    allegro_result = szukaj_allegro_parts_skoda(query)
    results["allegro"] = allegro_result
    
    return results

def get_best_offer_link(results, query):
    sprzedajemy_result = results["sprzedajemy"]
    allegro_result = results["allegro"]
    
    ids_title, urls_title = sprzedajemy_result["ids_title"], sprzedajemy_result["urls_title"]
    ids_id, urls_id = sprzedajemy_result["ids_id"], sprzedajemy_result["urls_id"]
    
    if len(ids_title) == 1:
        return urls_title[0], "Sprzedajemy.pl", f"Konkretna oferta: {query}"
    elif len(ids_id) == 1:
        return urls_id[0], "Sprzedajemy.pl", f"Konkretna oferta: {query}"
    elif len(ids_title) > 0 or len(ids_id) > 0:
        if len(ids_title) > len(ids_id):
            return sprzedajemy_result["url_title"], "Sprzedajemy.pl", f"Lista ofert: {query}"
        else:
            return sprzedajemy_result["url_id"], "Sprzedajemy.pl", f"Lista ofert: {query}"
    elif allegro_result and allegro_result["link"]:
        return allegro_result["link"], "Allegro", f"Wyszukiwanie Allegro: {query}"
    else:
        base = query.strip().replace(" ", "+")
        result = analyze_search(base)
        return result["url_title"], "Sprzedajemy.pl", f"Wyszukiwanie: {query}"

# 🌐 KONFIGURACJA
st.set_page_config(
    layout="wide", 
    page_title="OS-CAR - System Ofert", 
    page_icon="🚗"
)

# 🎨 STYL - ZAKTUALIZOWANY
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 0.5rem;
        font-weight: bold;
        padding-top: 0.2rem;
    }
    .search-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        margin-bottom: 1.5rem;
    }
    .search-box h3 {
        color: white;
        margin-bottom: 1rem;
    }
    .stats-mini {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 0.5rem;
        border-radius: 8px;
        text-align: center;
        margin-bottom: 0.5rem;
        font-size: 0.8rem;
    }
    .stats-number {
        font-size: 1.2rem;
        font-weight: bold;
    }
    .stats-label {
        font-size: 0.7rem;
        opacity: 0.9;
    }
    .date-section {
        background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 0.8rem;
        font-family: 'Courier New', monospace;
    }
    .shipping-section {
        background-color: #f0f8f0;
        padding: 1rem;
        border-radius: 10px;
        border-left: 5px solid #28a745;
        margin-bottom: 0.8rem;
        border: 1px solid #28a745;
    }
    .secondary-box {
        background-color: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }
    .manual-box {
        background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        margin-bottom: 1rem;
    }
    .allegro-blue-button {
        background: linear-gradient(135deg, #2196F3 0%, #21CBF3 100%) !important;
        color: white !important;
        font-weight: bold !important;
        border: none !important;
    }
    .allegro-blue-button:hover {
        background: linear-gradient(135deg, #1976D2 0%, #00B0FF 100%) !important;
    }
    .compact-section {
        margin-bottom: 0.5rem;
    }
    .compact-button {
        margin-bottom: 0.3rem;
    }
    .sidebar-content {
        max-height: 85vh;
        overflow-y: auto;
        padding-right: 5px;
    }
    .sidebar-content::-webkit-scrollbar {
        width: 6px;
    }
    .sidebar-content::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 10px;
    }
    .sidebar-content::-webkit-scrollbar-thumb {
        background: #888;
        border-radius: 10px;
    }
    .sidebar-content::-webkit-scrollbar-thumb:hover {
        background: #555;
    }
    </style>
""", unsafe_allow_html=True)

# 🚗 NAGŁÓWEK
st.markdown('<div class="main-header">🚗 System OS-CAR</div>', unsafe_allow_html=True)

# INICJALIZACJA STANU - ODDZIELNE DLA WYSZUKIWARKI I RĘCZNEGO DODAWANIA
if 'search_query' not in st.session_state:
    st.session_state.search_query = ""
if 'last_query' not in st.session_state:
    st.session_state.last_query = ""
if 'link_opened' not in st.session_state:
    st.session_state.link_opened = False

# ODDZIELNE STANY DLA FORMULARZA RĘCZNEGO
if 'manual_id' not in st.session_state:
    st.session_state.manual_id = ""
if 'manual_link' not in st.session_state:
    st.session_state.manual_link = ""
if 'manual_note' not in st.session_state:
    st.session_state.manual_note = ""

df = load_data()

# 📊 SIDEBAR - ZOPTYMALIZOWANY I KOMPAKTOWY
with st.sidebar:
    st.markdown('<div class="sidebar-content">', unsafe_allow_html=True)
    
    # ✅ DATA I DZIEŃ TYGODNIA PO POLSKU (BEZ ZEGARKA)
    days_pl = {
        'Monday': 'Poniedziałek', 'Tuesday': 'Wtorek', 'Wednesday': 'Środa',
        'Thursday': 'Czwartek', 'Friday': 'Piątek', 'Saturday': 'Sobota', 'Sunday': 'Niedziela'
    }
    day_en = datetime.now().strftime("%A")
    day_pl = days_pl.get(day_en, day_en)
    current_date = datetime.now().strftime(f"%Y-%m-%d | {day_pl}")
    
    st.markdown(f"""
        <div class="date-section">
            <div style="font-size: 1.2rem; font-weight: bold;">{current_date}</div>
        </div>
    """, unsafe_allow_html=True)
    
    # ✅ SZYBKI DOSTĘP - NAJWAŻNIEJSZE NA GÓRZE
    st.markdown("### 🔗 Szybki Dostęp")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🏠 Sprzedajemy.pl", use_container_width=True, key="sprzedajemy_btn"):
            webbrowser.open_new_tab("https://oscar.sprzedajemy.pl/")
            st.success("Otwieram Sprzedajemy.pl...")
    with col2:
        if st.button("🛒 allegro.pl", use_container_width=True, key="allegro_btn"):
            webbrowser.open_new_tab("https://salescenter.allegro.com/my-assortment?limit=20&publication.status=ACTIVE&sellingMode.format=BUY_NOW&context.marketplace=allegro-pl")
            st.success("Otwieram Allegro...")
    
    if st.button("📋 Zamówienia allegro", use_container_width=True, key="zamowienia_btn"):
        webbrowser.open_new_tab("https://salescenter.allegro.com/orders")
        st.success("Otwieram zamówienia...")
    
    if st.button("📊 Ovoko", use_container_width=True, key="ovoko_btn"):
        webbrowser.open_new_tab("https://oscar.rrr.lt/v2")
        st.success("Otwieram Ovoko...")
    
    if st.button("🔧 Polcar", use_container_width=True, key="polcar_btn"):
        webbrowser.open_new_tab("https://catalog.polcar.com/polcar")
        st.success("Otwieram Polcar...")
    
    if st.button("🧾 Wystaw fakture", use_container_width=True, key="faktura_btn"):
        webbrowser.open_new_tab("https://kontakt-oscar.fakturownia.pl/")
        st.success("Otwieram fakturownię...")
    
    if st.button("📦 BaseLinker", use_container_width=True, key="baselinker_btn"):
        webbrowser.open_new_tab("https://panel-f.baselinker.com/index.php")
        st.success("Otwieram BaseLinker...")
    
    st.markdown("---")
    
    # ✅ WYSYŁKI - WYŻEJ
    st.markdown("### 🚚 Wysyłki")
    st.markdown('<div class="shipping-section">', unsafe_allow_html=True)
    
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        if st.button("📦 DHL", use_container_width=True, key="dhl_btn"):
            webbrowser.open_new_tab("https://dhl24.com.pl/pl/uzytkownik/zaloguj.html")
            st.success("Otwieram DHL...")
    with col_s2:
        if st.button("🚚 AmbroExpress", use_container_width=True, key="ambro_btn"):
            webbrowser.open_new_tab("https://ambro.opennet.pl/Default.aspx")
            st.success("Otwieram AmbroExpress...")
    
    col_s3, col_s4 = st.columns(2)
    with col_s3:
        if st.button("📮 BLpaczka", use_container_width=True, key="blpaczka_btn"):
            webbrowser.open_new_tab("https://blpaczka.com/panel")
            st.success("Otwieram BLpaczka...")
    with col_s4:
        if st.button("📦 Sendit", use_container_width=True, key="sendit_btn"):
            webbrowser.open_new_tab("https://panel.sendit.pl/logowanie")
            st.success("Otwieram Sendit...")
    
    col_s5, col_s6 = st.columns(2)
    with col_s5:
        if st.button("📦 Polkurier", use_container_width=True, key="polkurier_btn"):
            webbrowser.open_new_tab("https://www.polkurier.pl/logowanie")
            st.success("Otwieram Polkurier...")
    with col_s6:
        if st.button("🚛 CTL Group", use_container_width=True, key="ctl_btn"):
            webbrowser.open_new_tab("https://www.ctlgroup.pl/customers/login")
            st.success("Otwieram CTL Group...")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    if st.button("🔄 Odśwież Dane", use_container_width=True, key="refresh_btn"):
        load_data.clear()
        st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

# 🎯 GŁÓWNY INTERFEJS - PROPORCJE 60%/40%
col1, col2 = st.columns([1.5, 1])  # ✅ 60% WYSZUKIWARKA, 40% BAZA

# 🔍 PANEL WYSZUKIWANIA - 60%
with col1:
    st.markdown('<div class="search-box">', unsafe_allow_html=True)
    st.markdown("### 🔍 Wyszukiwarka Ofert")
    
    search_input = st.text_input(
        "**Wpisz nazwę części, numer OEM lub ID:**",
        placeholder="np: maska skoda octavia, 5J0853661, lusterko fabia...",
        key="search_input_widget"
    )
    
    if search_input.strip():
        st.session_state.search_query = search_input.strip()

    if st.session_state.search_query and st.session_state.search_query != st.session_state.last_query:
        st.session_state.link_opened = False
        st.session_state.last_query = st.session_state.search_query

    if st.session_state.search_query:
        with st.spinner("🔄 Szukam ofert..."):
            current_search_results = search_multiple_platforms(st.session_state.search_query)
        
        sprzedajemy_result = current_search_results["sprzedajemy"]
        ids_title, urls_title = sprzedajemy_result["ids_title"], sprzedajemy_result["urls_title"]
        ids_id, urls_id = sprzedajemy_result["ids_id"], sprzedajemy_result["urls_id"]

        st.markdown(f"#### 📋 Sprzedajemy.pl")
        st.markdown(f"**Znalezione oferty:** Tytuły ({len(ids_title)}) | Numery ({len(ids_id)})")
        
        link_to_open = None
        if not ids_title and not ids_id:
            st.warning("❌ Brak ofert dla podanej frazy")
        elif ids_title != ids_id:
            if len(ids_title) == 1:
                st.success("🎯 Znaleziono 1 ofertę")
                link_to_open = urls_title[0]
            elif len(ids_id) == 1:
                st.success("🎯 Znaleziono 1 ofertę po numerze")
                link_to_open = urls_id[0]
            elif len(ids_title) > len(ids_id):
                st.success("📖 Otwórz listę ofert z tytułów")
                link_to_open = sprzedajemy_result["url_title"]
            else:
                st.success("🔢 Otwórz listę ofert z numerów")
                link_to_open = sprzedajemy_result["url_id"]
        else:
            st.info(f"📊 Oferty znalezione: {ids_title[:3]}")
            link_to_open = sprzedajemy_result["url_title"]

        # ✅ PRZYCISK ZAMIAST AUTOMATYCZNEGO OTWIERANIA
        if link_to_open:
            if st.button("🌐 OTWÓRZ OFERTĘ SPRZEDAJEMY.PL", use_container_width=True, key=f"open_sprzedajemy_{int(time.time())}"):
                webbrowser.open_new_tab(link_to_open)
                st.success("✅ Otwieram ofertę...")

        allegro_result = current_search_results["allegro"]
        if allegro_result:
            st.markdown(f"#### 🛒 allegro.pl")
            st.markdown(f"**Gotowe wyszukiwanie:** Twoje oferty z filtrem")
            
            # ✅ PRZYCISK ALLEGRO
            if st.button("🚀 OTWÓRZ ALLEGRO", key="open_allegro", use_container_width=True):
                webbrowser.open_new_tab(allegro_result['link'])
                st.success("✅ Otwieram allegro.pl...")

    if st.session_state.search_query:
        if st.button("➕ DODAJ DO BAZY JAKO SPRZEDANE", 
                     use_container_width=True, 
                     type="primary",
                     key="add_offer_btn"):
            
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            
            with st.spinner("🔄 Sprawdzam oferty..."):
                fresh_results = search_multiple_platforms(st.session_state.search_query)
            
            if fresh_results:
                offer_url, platform, opis = get_best_offer_link(fresh_results, st.session_state.search_query)
                
                new_row = {
                    "id": f"{platform.lower().replace('.', '')}-{st.session_state.search_query}-{int(time.time())}",
                    "tytul": f"{st.session_state.search_query}",
                    "cena": "",
                    "link": offer_url,
                    "opis": opis,
                    "status": f"Sprzedana ({now})",
                    "notatka": "",
                    "dodano": now
                }
                current_df = load_data()
                new_df = pd.DataFrame([new_row])
                updated_df = pd.concat([current_df, new_df], ignore_index=True)
                save_data(updated_df)
                st.success(f"✅ Dodano jako sprzedane ({platform})!")
                st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 📤 DODAWANIE RĘCZNE
    st.markdown('<div class="manual-box">', unsafe_allow_html=True)
    st.markdown("### 📝 Dodaj ręcznie sprzedaną część")
    
    manual_id = st.text_input(
        "🏷️ **Numer oferty/części:**", 
        placeholder="np: 5J0853661, maska octavia...",
        key="manual_id_input",
        value=st.session_state.manual_id
    )
    
    manual_link = st.text_input(
        "🔗 **Link do oferty (opcjonalnie):**", 
        placeholder="https://...",
        key="manual_link_input",
        value=st.session_state.manual_link
    )
    
    manual_note = st.text_area(
        "📝 **Notatka (opcjonalnie):**", 
        placeholder="Dodatkowe informacje...", 
        height=80,
        key="manual_note_input",
        value=st.session_state.manual_note
    )
    
    if st.button("✅ DODAJ DO SPRZEDANYCH", 
                 use_container_width=True, 
                 type="primary",
                 key="manual_submit_btn"):
        
        if manual_id and manual_id.strip():
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            new_row = {
                "id": f"manual-{manual_id.strip()}-{int(time.time())}",
                "tytul": manual_id.strip(),
                "cena": "",
                "link": manual_link.strip() if manual_link else "",
                "opis": f"Ręcznie dodana oferta: {manual_id.strip()}",
                "status": f"Sprzedana ({now})",
                "notatka": manual_note.strip() if manual_note else "",
                "dodano": now
            }
            current_df = load_data()
            new_df = pd.DataFrame([new_row])
            updated_df = pd.concat([current_df, new_df], ignore_index=True)
            save_data(updated_df)
            
            st.session_state.manual_id = ""
            st.session_state.manual_link = ""
            st.session_state.manual_note = ""
            
            st.success("🎉 Oferta dodana do bazy sprzedanych!")
            time.sleep(0.5)
            st.rerun()
        else:
            st.error("❌ Wpisz numer oferty/części!")
    
    st.markdown('</div>', unsafe_allow_html=True)

# 📦 PANEL SPRZEDANYCH OFERT - 40% (LEPSZA CZYTELNOŚĆ)
with col2:
    # ✅ MINIMALNE STATYSTYKI NAD BAZĄ
    st.markdown("### 📦 Baza Sprzedanych Ofert")
    
    if not df.empty:
        col_stat1, col_stat2 = st.columns(2)
        with col_stat1:
            st.markdown(f"""
                <div class="stats-mini">
                    <div class="stats-number">{len(df)}</div>
                    <div class="stats-label">Łącznie ofert</div>
                </div>
            """, unsafe_allow_html=True)
        with col_stat2:
            # ✅ DODANA DOKŁADNA GODZINA OSTATNIEJ OFERTY
            last_added = df['dodano'].max()
            last_time = last_added[:16] if len(last_added) >= 16 else last_added
            st.markdown(f"""
                <div class="stats-mini">
                    <div class="stats-number">{last_time}</div>
                    <div class="stats-label">Ostatnia</div>
                </div>
            """, unsafe_allow_html=True)
    
    st.markdown('<div class="secondary-box">', unsafe_allow_html=True)
    
    if df.empty:
        st.info("📭 Brak ofert w bazie. Dodaj pierwszą ofertę używając formularza po lewej.")
    else:
        sort_option = st.selectbox("Sortuj:", ["Najnowsze", "Najstarsze", "Alfabetycznie"], key="sort_sold")
        
        filtered_df = df.copy()
        
        if sort_option == "Najnowsze":
            filtered_df = filtered_df.sort_values('dodano', ascending=False)
        elif sort_option == "Najstarsze":
            filtered_df = filtered_df.sort_values('dodano', ascending=True)
        else:
            filtered_df = filtered_df.sort_values('tytul', ascending=True)
        
        # ✅ KOMPAKTOWY WIDOK OFERT
        for idx, row in filtered_df.iterrows():
            platform = "Sprzedajemy.pl"
            if "allegro" in str(row["id"]).lower() or "allegro" in str(row["link"]).lower():
                platform = "Allegro"
            elif "sprzedajemy" in str(row["id"]).lower():
                platform = "Sprzedajemy.pl"
            elif "manual" in str(row["id"]).lower():
                platform = "Ręczna"
            
            # ✅ SKRÓCONY TYTUŁ DLA LEPSZEJ CZYTELNOŚCI
            short_title = row['tytul'][:35] + "..." if len(row['tytul']) > 35 else row['tytul']
            
            with st.expander(f"📦 {short_title} [{platform}]", expanded=False):
                col_info, col_actions = st.columns([3, 1])
                
                with col_info:
                    title_key = f"title_{idx}"
                    link_key = f"link_{idx}"
                    note_key = f"note_{idx}"
                    
                    st.text_input("**Numer oferty:**", value=row["tytul"], key=title_key, 
                                on_change=lambda i=idx, k=title_key: save_field(i, k, "tytul"))
                    
                    st.text_input("**Link do oferty:**", value=row["link"], key=link_key,
                                on_change=lambda i=idx, k=link_key: save_field(i, k, "link"))
                    
                    # ✅ PRZYCISK ZAMIAST LINK_BUTTON
                    if isinstance(row["link"], str) and row["link"].startswith("http"):
                        if st.button("🔗 OTWÓRZ OFERTĘ", key=f"open_offer_{idx}", use_container_width=True):
                            webbrowser.open_new_tab(row["link"])
                            st.success("Otwieram...")
                    else:
                        st.caption("🔗 Brak linku")
                    
                    st.text_area("**Notatka:**", value=row["notatka"], key=note_key, height=80,
                               on_change=lambda i=idx, k=note_key: save_field(i, k, "notatka"))
                    
                    st.caption(f"🕒 Dodano: {row['dodano']} | Platforma: {platform}")
                
                with col_actions:
                    st.write("")
                    if st.button("🗑️ Usuń", key=f"del_{idx}", use_container_width=True):
                        current_df = load_data()
                        updated_df = current_df.drop(idx).reset_index(drop=True)
                        save_data(updated_df)
                        st.success("🗑️ Oferta usunięta!")
                        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---")
st.markdown("""
    <div style='text-align: center; color: #666; font-size: 0.9rem;'>
        🚗 <b>System OS-CAR</b> | Proste • Skuteczne • Niezawodne
    </div>
""", unsafe_allow_html=True)
