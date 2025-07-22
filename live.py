import streamlit as st
import requests
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

# === API KEYS ===
ATTOM_API_KEY = "7b9f39f8722159b30ca61f77279e829d"
HUNTER_API_KEY = "c95429706ea4eb1569e52e390a3913113a18fab0"

@st.cache_data(show_spinner=False)
def get_property_info(address, state, zip_code):
    url = "https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/address"
    headers = {"apikey": ATTOM_API_KEY}
    params = {
        "address1": address,
        "postalcode": zip_code,
        "state": state
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        json_data = response.json()
        return json_data.get("property", [None])[0]
    except Exception as e:
        st.error(f"ATTOM API Error: {e}")
        return None

@st.cache_data(show_spinner=False)
def get_nearby_cre(lat, lon):
    url = "https://api.gateway.attomdata.com/propertyapi/v1.0.0/area/geo/point"
    headers = {"apikey": ATTOM_API_KEY}
    params = {
        "latitude": lat,
        "longitude": lon,
        "radius": 1,
        "propertytype": "COM"
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        json_data = response.json()
        return json_data.get("property", [])[:5]
    except Exception as e:
        st.error(f"ATTOM Nearby API Error: {e}")
        return []

def get_email_from_hunter(domain):
    url = f"https://api.hunter.io/v2/domain-search?domain={domain}&api_key={HUNTER_API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        emails = data.get("data", {}).get("emails", [])
        return emails[0]["value"] if emails else "N/A"
    except Exception as e:
        st.error(f"Hunter API Error: {e}")
        return "N/A"

def extract_domain_from_owner(owner_name):
    # Basic domain guesser — improve as needed
    return owner_name.replace(" ", "").lower() + ".com"

def main():
    st.title("🏢 Commercial Real Estate Finder")
    st.write("Search for a property and find nearby commercial properties + owner contact info.")

    with st.form("property_form"):
        address = st.text_input("Street Address", "1600 Amphitheatre Parkway")
        # city removed from form inputs since not used in ATTOM API call
        state = st.text_input("State (2-letter code)", "CA")
        zip_code = st.text_input("ZIP Code", "94043")
        submitted = st.form_submit_button("Search")

    if submitted:
        if not all([address, state, zip_code]):
            st.warning("Please fill in all fields.")
            return

        data = get_property_info(address, state, zip_code)
        if not data:
            st.error("No property found.")
            return

        lat = data.get("location", {}).get("latitude")
        lon = data.get("location", {}).get("longitude")
        if not lat or not lon:
            st.error("No location data found for this property.")
            return

        owner_name = data.get("owner", {}).get("owner1", "Unknown Owner")

        st.subheader("🔍 Property Information")
        st.json(data)

        st.subheader("📍 Map View with Nearby CRE")
        m = folium.Map(location=[lat, lon], zoom_start=15)
        marker_cluster = MarkerCluster()
        marker_cluster.add_to(m)

        folium.Marker([lat, lon], tooltip="Your Property", icon=folium.Icon(color='blue')).add_to(marker_cluster)

        nearby = get_nearby_cre(lat, lon)
        for prop in nearby:
            try:
                plat = prop["location"]["latitude"]
                plon = prop["location"]["longitude"]
                folium.Marker(
                    [plat, plon],
                    tooltip=prop["address"]["line1"],
                    icon=folium.Icon(color='green', icon="building")
                ).add_to(marker_cluster)
            except Exception:
                continue

        st_folium(m, width=700)

        st.subheader("📬 Owner Contact Info")
        domain = extract_domain_from_owner(owner_name)

        hunter_lookup = st.button("Look up Owner Email via Hunter.io")
        if hunter_lookup:
            email = get_email_from_hunter(domain)
            st.write(f"**Owner:** {owner_name}")
            st.write(f"**Guessed Domain:** {domain}")
            st.write(f"**Email (via Hunter.io):** {email}")

if __name__ == "__main__":
    main()
