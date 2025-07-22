import streamlit as st
import requests
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

ATTOM_API_KEY = "7b9f39f8722159b30ca61f77279e829d"
HUNTER_API_KEY = "c95429706ea4eb1569e52e390a3913113a18fab0"

@st.cache_data(show_spinner=False)
def lookup_property(address, city, state, postalcode):
    url = "https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/address"
    headers = {"apikey": ATTOM_API_KEY}
    params = {
        "address1": address,
        "city": city,
        "state": state,
        "postalcode": postalcode,
        "page": 1,
        "pagesize": 1
    }

    st.write(f"Request URL: {url}")
    st.write(f"Params: {params}")

    try:
        response = requests.get(url, headers=headers, params=params)
        st.write(f"Response status code: {response.status_code}")
        response.raise_for_status()
        data = response.json()
        st.write("Full response JSON:")
        st.json(data)

        properties = data.get("property", [])
        if properties:
            return properties[0]
        else:
            st.warning("No properties found in response.")
            return None
    except Exception as e:
        st.error(f"ATTOM API Error: {e}")
        if response is not None:
            try:
                st.write("Error response content:")
                st.json(response.json())
            except Exception:
                st.write(response.text)
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
    return owner_name.replace(" ", "").lower() + ".com"

def main():
    st.title("🏢 Commercial Real Estate Finder")
    st.write("Search for a property and find nearby commercial properties + owner contact info.")

    with st.form("property_form"):
        address = st.text_input("Street Address", "142 W 57th Street")
        city = st.text_input("City", "New York")
        state = st.text_input("State (2-letter code)", "NY")
        postalcode = st.text_input("ZIP Code", "10019")
        submitted = st.form_submit_button("Search")

    if submitted:
        if not all([address, city, state, postalcode]):
            st.warning("Please fill in all fields.")
            return

        data = lookup_property(address, city, state, postalcode)
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
