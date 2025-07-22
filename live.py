import streamlit as st
import requests
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

ATTOM_API_KEY = "7b9f39f8722159b30ca61f77279e829d"
HUNTER_API_KEY = "c95429706ea4eb1569e52e390a3913113a18fab0"

def geocode_location(location):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": location,
        "format": "json",
        "limit": 1
    }
    try:
        response = requests.get(url, params=params, headers={"User-Agent": "lead-gen-app"})
        response.raise_for_status()
        results = response.json()
        if results:
            lat = float(results[0]["lat"])
            lon = float(results[0]["lon"])
            return lat, lon
        else:
            st.error("Location not found via geocoding.")
            return None, None
    except Exception as e:
        st.error(f"Geocoding error: {e}")
        return None, None

@st.cache_data(show_spinner=False)
def get_nearby_cre(lat, lon):
    url = "https://api.gateway.attomdata.com/propertyapi/v1.0.0/area/geo/point"
    headers = {"apikey": ATTOM_API_KEY}
    params = {
        "latitude": lat,
        "longitude": lon,
        "radius": 1,  # radius in miles or km (check ATTOM docs)
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
    st.title("🏢 CRE Nearby Properties Finder")
    st.write("Type any location (address, city, zip) to find nearby commercial properties.")

    location = st.text_input("Enter Location (address, city, or zip)", "New York, NY")
    if st.button("Search Nearby CRE"):
        lat, lon = geocode_location(location)
        if lat is None or lon is None:
            return

        st.write(f"Coordinates: {lat}, {lon}")

        properties = get_nearby_cre(lat, lon)
        if not properties:
            st.warning("No nearby commercial properties found.")
            return

        m = folium.Map(location=[lat, lon], zoom_start=15)
        marker_cluster = MarkerCluster()
        marker_cluster.add_to(m)

        # Your search point marker
        folium.Marker([lat, lon], tooltip="Search Location", icon=folium.Icon(color='blue')).add_to(marker_cluster)

        for prop in properties:
            try:
                plat = prop["location"]["latitude"]
                plon = prop["location"]["longitude"]
                owner = prop.get("owner", {}).get("owner1", "Unknown Owner")
                folium.Marker(
                    [plat, plon],
                    tooltip=f"{prop['address']['line1']} - Owner: {owner}",
                    icon=folium.Icon(color='green', icon="building")
                ).add_to(marker_cluster)
            except Exception:
                continue

        st_folium(m, width=700)

        st.subheader("Owner Contacts")
        for prop in properties:
            owner = prop.get("owner", {}).get("owner1", "Unknown Owner")
            domain = extract_domain_from_owner(owner)
            email = get_email_from_hunter(domain)
            st.write(f"**{prop['address']['line1']}**")
            st.write(f"Owner: {owner}")
            st.write(f"Domain: {domain}")
            st.write(f"Email: {email}")
            st.write("---")

if __name__ == "__main__":
    main()
