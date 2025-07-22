import streamlit as st
import requests
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from io import StringIO

ATTOM_API_KEY = "7b9f39f8722159b30ca61f77279e829d"
HUNTER_API_KEY = "c95429706ea4eb1569e52e390a3913113a18fab0"

def lookup_property_detail(street_number, street_name, city, state, postalcode):
    url = "https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/detail"
    headers = {"apikey": ATTOM_API_KEY}
    params = {
        "streetNumber": street_number,
        "streetName": street_name,
        "city": city,
        "state": state,
        "postalcode": postalcode,
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
        st.error(f"ATTOM API error: {e}")
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
        st.error(f"Hunter API error: {e}")
        return "N/A"

def extract_domain_from_owner(owner_name):
    clean_name = owner_name.replace(" ", "").replace(",", "").lower()
    return clean_name + ".com"

def main():
    st.title("🏢 CRE Property Detail & Lead Enrichment")

    st.write("Enter the property address components:")

    street_number = st.text_input("Street Number", "142")
    street_name = st.text_input("Street Name", "W 57th St")
    city = st.text_input("City", "New York")
    state = st.text_input("State", "NY")
    postalcode = st.text_input("Postal Code", "10019")

    if st.button("Lookup Property"):
        if not all([street_number, street_name, city, state, postalcode]):
            st.warning("Please fill in all address fields.")
            return

        prop = lookup_property_detail(street_number, street_name, city, state, postalcode)
        if prop is None:
            st.error("No property found.")
            return

        owner_name = prop.get("owner", {}).get("owner1", "Unknown Owner")
        domain = extract_domain_from_owner(owner_name)
        email = get_email_from_hunter(domain)

        st.subheader("Property Details")
        st.json(prop)

        lat = prop.get("location", {}).get("latitude")
        lon = prop.get("location", {}).get("longitude")

        if lat and lon:
            m = folium.Map(location=[lat, lon], zoom_start=16)
            MarkerCluster().add_to(m)
            folium.Marker([lat, lon], tooltip="Property Location", icon=folium.Icon(color='blue')).add_to(m)
            st_folium(m, width=700)
        else:
            st.info("No coordinates available for this property.")

        st.subheader("Owner Contact Info")
        st.write(f"Owner: {owner_name}")
        st.write(f"Guessed Domain: {domain}")
        st.write(f"Email from Hunter.io: {email}")

if __name__ == "__main__":
    main()
