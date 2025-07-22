import streamlit as st
import requests
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from io import StringIO

ATTOM_API_KEY = "7b9f39f8722159b30ca61f77279e829d"
HUNTER_API_KEY = "c95429706ea4eb1569e52e390a3913113a18fab0"

def test_attom_api():
    url = "https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/detail"
    headers = {
        "apikey": ATTOM_API_KEY
    }
    params = {
        "address1": "142 W 57th Street",
        "city": "New York",
        "state": "NY",
        "postalcode": "10019",
        "page": 1,
        "pagesize": 1
    }

    response = requests.get(url, headers=headers, params=params)
    print(f"Status Code: {response.status_code}")
    print(f"Response Content:\n{response.text}")

if __name__ == "__main__":
    test_attom_api()


def lookup_property_detail(address):
    url = "https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/detail"
    headers = {"apikey": ATTOM_API_KEY}
    # Expecting full address string; we split for ATTOM params if possible
    # Here we try a naive split: street address + city/state/zip parsing would improve this
    # For demo, we send full address as address1 and leave city/state/postalcode blank
    params = {
        "address1": address,
        "page": 1,
        "pagesize": 1
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        props = data.get("property", [])
        if props:
            return props[0]
        else:
            return None
    except Exception as e:
        st.error(f"ATTOM API error for address '{address}': {e}")
        return None

def get_email_from_hunter(domain):
    url = f"https://api.hunter.io/v2/domain-search?domain={domain}&api_key={HUNTER_API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        emails = data.get("data", {}).get("emails", [])
        return emails[0]["value"] if emails else "N/A"
    except Exception as e:
        st.error(f"Hunter API error for domain '{domain}': {e}")
        return "N/A"

def extract_domain_from_owner(owner_name):
    # Simple domain guess, could be improved
    clean_name = owner_name.replace(" ", "").replace(",", "").lower()
    return clean_name + ".com"

def main():
    st.title("📋 CRE Lead Enrichment Tool")
    st.write("""
        Enter one or more full property addresses (one per line).
        The app will fetch property details from ATTOM and try to find owner emails using Hunter.io.
    """)

    addresses_text = st.text_area("Property Addresses", height=150, placeholder="e.g.\n142 W 57th Street, New York, NY 10019\n1600 Amphitheatre Parkway, Mountain View, CA 94043")
    if st.button("Enrich Leads"):
        addresses = [a.strip() for a in addresses_text.split("\n") if a.strip()]
        if not addresses:
            st.warning("Please enter at least one address.")
            return

        results = []
        map_center = None

        m = folium.Map(location=[39.5, -98.35], zoom_start=4)  # US center default
        marker_cluster = MarkerCluster().add_to(m)

        for addr in addresses:
            prop = lookup_property_detail(addr)
            if prop is None:
                st.warning(f"No data found for address: {addr}")
                continue

            lat = prop.get("location", {}).get("latitude")
            lon = prop.get("location", {}).get("longitude")
            owner_name = prop.get("owner", {}).get("owner1", "Unknown Owner")
            domain = extract_domain_from_owner(owner_name)
            email = get_email_from_hunter(domain)

            results.append({
                "Address": addr,
                "Owner": owner_name,
                "Domain": domain,
                "Email": email,
                "Latitude": lat,
                "Longitude": lon,
                "Property Type": prop.get("summary", {}).get("usecode", "N/A"),
                "Building Sqft": prop.get("summary", {}).get("buildingSqFt", "N/A"),
                "Year Built": prop.get("summary", {}).get("yearBuilt", "N/A"),
            })

            if lat and lon:
                if map_center is None:
                    map_center = [lat, lon]
                    m.location = map_center
                    m.zoom_start = 15

                folium.Marker(
                    [lat, lon],
                    tooltip=f"{addr}\nOwner: {owner_name}\nEmail: {email}",
                    icon=folium.Icon(color="green", icon="building")
                ).add_to(marker_cluster)

        if results:
            df = pd.DataFrame(results)
            st.subheader("Lead Enrichment Results")
            st.dataframe(df)

            st.subheader("Property Locations Map")
            st_folium(m, width=700)

            csv_buffer = StringIO()
            df.to_csv(csv_buffer, index=False)
            st.download_button(
                label="Download Results CSV",
                data=csv_buffer.getvalue(),
                file_name="cre_leads_enriched.csv",
                mime="text/csv"
            )
        else:
            st.error("No valid property data found for any address.")

if __name__ == "__main__":
    main()
