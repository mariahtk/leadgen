import streamlit as st
import requests
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

# === API KEYS ===
ATTOM_API_KEY = "7b9f39f8722159b30ca61f77279e829d"
HUNTER_API_KEY = "c95429706ea4eb1569e52e390a3913113a18fab0"

# --- Helper Functions ---

def get_property_info(address, city, state, zip_code):
    url = f"https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/address"
    headers = {
        "apikey": ATTOM_API_KEY
    }
    params = {
        "address1": address,
        "address2": f"{city}, {state} {zip_code}"
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        st.error(f"ATTOM API Error: {response.status_code} - {response.text}")
        return None
    return response.json().get("property", [])[0]

def get_nearby_cre(lat, lon):
    url = f"https://api.gateway.attomdata.com/propertyapi/v1.0.0/area/geo/point"
    headers = {"apikey": ATTOM_API_KEY}
    params = {
        "latitude": lat,
        "longitude": lon,
        "radius": 1,
        "propertytype": "COM"
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        st.error(f"ATTOM Nearby API Error: {response.status_code} - {response.text}")
        return []
    return response.json().get("property", [])[:5]

def get_email_from_hunter(domain):
    url = f"https://api.hunter.io/v2/domain-search?domain={domain}&api_key={HUNTER_API_KEY}"
    response = requests.get(url)
    if response.status_code != 200:
        return "N/A"
    data = response.json()
    emails = data.get("data", {}).get("emails", [])
    return emails[0]["value"] if emails else "N/A"

def extract_domain_from_owner(owner_name):
    # Dummy domain parser (you could use Clearbit if allowed)
    return owner_name.replace(" ", "").lower() + ".com"

# --- Streamlit UI ---

st.title("🏢 Commercial Real Estate Finder")
st.write("Search for a property and find nearby commercial properties + owner contact info.")

with st.form("property_form"):
    address = st.text_input("Street Address", "1600 Amphitheatre Parkway")
    city = st.text_input("City", "Mountain View")
    state = st.text_input("State", "CA")
    zip_code = st.text_input("ZIP Code", "94043")
    submitted = st.form_submit_button("Search")

if submitted:
    data = get_property_info(address, city, state, zip_code)
    if not data:
        st.error("No property found.")
    else:
        lat = data["location"]["latitude"]
        lon = data["location"]["longitude"]
        owner_name = data.get("owner", {}).get("owner1", "Unknown Owner")

        st.subheader("🔍 Property Information")
        st.write(data)

        st.subheader("📍 Map View with Nearby CRE")
        m = folium.Map(location=[lat, lon], zoom_start=15)
        MarkerCluster().add_to(m)

        folium.Marker([lat, lon], tooltip="Your Property", icon=folium.Icon(color='blue')).add_to(m)
        nearby = get_nearby_cre(lat, lon)

        for prop in nearby:
            try:
                folium.Marker(
                    [prop["location"]["latitude"], prop["location"]["longitude"]],
                    tooltip=prop["address"]["line1"],
                    icon=folium.Icon(color='green', icon="building")
                ).add_to(m)
            except:
                continue

        st_folium(m, width=700)

        st.subheader("📬 Owner Contact Info")
        domain = extract_domain_from_owner(owner_name)
        email = get_email_from_hunter(domain)
        st.write(f"**Owner:** {owner_name}")
        st.write(f"**Guessed Domain:** {domain}")
        st.write(f"**Email (via Hunter.io):** {email}")
