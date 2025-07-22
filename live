import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
import pandas as pd

# === API KEYS ===
ATTOM_API_KEY = "7b9f39f8722159b30ca61f77279e829d"
HUNTER_API_KEY = "c95429706ea4eb1569e52e390a3913113a18fab0"

# === Functions ===

def query_attom_property(address1, city, state):
    url = (
        "https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/detail"
        f"?address1={address1}&address2={city}&state={state}"
    )
    headers = {"apikey": ATTOM_API_KEY}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        return res.json()
    else:
        st.error(f"ATTOM API Error: {res.status_code} {res.text}")
        return None

def hunter_email_lookup(domain):
    url = f"https://api.hunter.io/v2/domain-search?domain={domain}&api_key={HUNTER_API_KEY}"
    res = requests.get(url)
    if res.status_code == 200:
        return res.json().get("data", {}).get("emails", [])
    return []

def plot_map(lat, lon, address):
    m = folium.Map(location=[lat, lon], zoom_start=16)
    folium.Marker([lat, lon], popup=address).add_to(m)
    return m

# === Streamlit UI ===

st.title("🏢 ATTOM Property Lookup with Owner Email Finder")

with st.form("property_form"):
    address1 = st.text_input("Address line 1 (e.g., 1600 Amphitheatre Pkwy)")
    city = st.text_input("City (e.g., Mountain View)")
    state = st.text_input("State (e.g., CA)")
    submitted = st.form_submit_button("Search Property")

if submitted:
    if not address1 or not city or not state:
        st.error("Please fill all address fields")
    else:
        data = query_attom_property(address1, city, state)
        if data and "property" in data and len(data["property"]["property"]) > 0:
            prop = data["property"]["property"][0]
            addr = prop.get("address", {})
            st.subheader("Property Details")
            st.write(f"**Address:** {addr.get('oneLine', 'N/A')}")
            st.write(f"**Property Type:** {prop.get('useCodeDesc', 'N/A')}")
            st.write(f"**Year Built:** {prop.get('yearBuilt', 'N/A')}")
            st.write(f"**Building SqFt:** {prop.get('buildingSize', {}).get('size', 'N/A')}")
            st.write(f"**Lot Size SqFt:** {prop.get('lotSize', {}).get('size', 'N/A')}")
            st.write(f"**Owner Name:** {prop.get('owner', {}).get('nameFull', 'N/A')}")

            lat = prop.get("location", {}).get("latitude")
            lon = prop.get("location", {}).get("longitude")
            if lat and lon:
                st.subheader("Property Location Map")
                m = plot_map(lat, lon, addr.get("oneLine", ""))
                st_folium(m, width=700)

            # Owner domain/email via Hunter.io if available
            owner_name = prop.get("owner", {}).get("nameFull", "")
            # You can add logic to extract domain from owner name or input manually
            st.subheader("Hunter.io Email Lookup (Enter owner domain)")
            owner_domain = st.text_input("Owner domain for Hunter.io lookup (e.g., example.com)")

            if owner_domain:
                emails = hunter_email_lookup(owner_domain)
                if emails:
                    df = pd.DataFrame(emails)
                    st.dataframe(df[['value', 'type', 'confidence']])
                else:
                    st.info("No emails found via Hunter.io.")
        else:
            st.error("Property not found or incomplete data.")
