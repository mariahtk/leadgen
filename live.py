import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
import pandas as pd

# === API KEYS ===
ATTOM_API_KEY = "7b9f39f8722159b30ca61f77279e829d"
HUNTER_API_KEY = "c95429706ea4eb1569e52e390a3913113a18fab0"


# --- Streamlit UI ---
st.title("🏙️ Commercial Property Lead Generator")
address = st.text_input("Enter Address (e.g., 123 Main St)")
city = st.text_input("City")
state = st.text_input("State (e.g., NY)")
postalcode = st.text_input("ZIP Code")

if st.button("🔍 Search Property"):
    if not (address and city and state and postalcode):
        st.warning("Please fill all fields.")
    else:
        with st.spinner("Fetching data from ATTOM..."):
            attom_url = f"https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/detail"
            headers = {"apikey": ATTOM_API_KEY}
            params = {
                "address1": address,
                "city": city,
                "state": state.upper(),
                "postalcode": postalcode
            }

            response = requests.get(attom_url, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                try:
                    prop = data['property'][0]
                    owner = prop.get("owner", {})
                    location = prop.get("location", {})
                    st.subheader("🏡 Property Details")
                    st.write(f"**Owner Name:** {owner.get('owner1', 'N/A')}")
                    st.write(f"**Mailing Address:** {owner.get('mailingaddr', 'N/A')}")
                    st.write(f"**City, State, ZIP:** {owner.get('mailingcity', '')}, {owner.get('mailingstate', '')} {owner.get('mailingzip', '')}")

                    # Map
                    lat, lon = location.get("latitude"), location.get("longitude")
                    if lat and lon:
                        m = folium.Map(location=[lat, lon], zoom_start=16)
                        MarkerCluster().add_to(m)
                        folium.Marker([lat, lon], tooltip="Property Location").add_to(m)
                        st_folium(m, width=700)

                    # Hunter.io Lookup
                    with st.spinner("Looking up owner email (Hunter.io)..."):
                        domain = st.text_input("Company Domain (for Hunter.io email guess)")
                        if domain:
                            hunter_url = f"https://api.hunter.io/v2/domain-search?domain={domain}&api_key={HUNTER_API_KEY}"
                            r = requests.get(hunter_url)
                            if r.status_code == 200:
                                emails = r.json().get("data", {}).get("emails", [])
                                if emails:
                                    st.subheader("📧 Found Emails")
                                    for email in emails[:3]:
                                        st.write(f"{email['value']} ({email['position']})")
                                else:
                                    st.info("No emails found.")
                            else:
                                st.error("Hunter API error.")
                except Exception as e:
                    st.error(f"Error parsing ATTOM response: {e}")
            else:
                st.error(f"ATTOM API Error {response.status_code}: {response.text}")
