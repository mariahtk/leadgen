import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import st_folium

# --- Config ---
canada_csv_path = "canada_cities.csv"

# --- API KEYS (HARDCODE HERE) ---
ATTOM_API_KEY = "7b9f39f8722159b30ca61f77279e829d"  # Replace with your ATTOM key

us_state_fips = {
    'AL': '01', 'AK': '02', 'AZ': '04', 'AR': '05', 'CA': '06',
    'CO': '08', 'CT': '09', 'DE': '10', 'FL': '12', 'GA': '13',
    'HI': '15', 'ID': '16', 'IL': '17', 'IN': '18', 'IA': '19',
    'KS': '20', 'KY': '21', 'LA': '22', 'ME': '23', 'MD': '24',
    'MA': '25', 'MI': '26', 'MN': '27', 'MS': '28', 'MO': '29',
    'MT': '30', 'NE': '31', 'NV': '32', 'NH': '33', 'NJ': '34',
    'NM': '35', 'NY': '36', 'NC': '37', 'ND': '38', 'OH': '39',
    'OK': '40', 'OR': '41', 'PA': '42', 'RI': '44', 'SC': '45',
    'SD': '46', 'TN': '47', 'TX': '48', 'UT': '49', 'VT': '50',
    'VA': '51', 'WA': '53', 'WV': '54', 'WI': '55', 'WY': '56'
}

@st.cache_data(show_spinner=False)
def load_canadian_data(path):
    df = pd.read_csv(path)
    df = df.rename(columns={
        'Geographic Name': 'City',
        'Population': 'Population',
        'Median income': 'MedianIncome'
    })
    return df

@st.cache_data(show_spinner=False)
def get_us_city_data(state_fips, city_name):
    url = (
        f"https://api.census.gov/data/2021/acs/acs5?"
        f"get=NAME,B01003_001E,B19013_001E&for=place:*&in=state:{state_fips}"
    )
    response = requests.get(url)
    if response.status_code != 200:
        return None, None
    data = response.json()
    df = pd.DataFrame(data[1:], columns=data[0])
    city_row = df[df['NAME'].str.contains(city_name, case=False)]
    if not city_row.empty:
        try:
            population = int(city_row.iloc[0]['B01003_001E'])
            median_income = int(city_row.iloc[0]['B19013_001E'])
            return population, median_income
        except:
            return None, None
    else:
        return None, None

@st.cache_data(show_spinner=False)
def get_coworking_osm(lat, lon, radius=10000):
    overpass_url = "http://overpass-api.de/api/interpreter"
    query = f"""
    [out:json];
    (
      node["office"="coworking"](around:{radius},{lat},{lon});
      way["office"="coworking"](around:{radius},{lat},{lon});
      relation["office"="coworking"](around:{radius},{lat},{lon});
    );
    out;
    """
    response = requests.post(overpass_url, data={'data': query})
    if response.status_code != 200:
        return None, []
    data = response.json()
    elements = data.get('elements', [])
    return len(elements), elements

@st.cache_data(show_spinner=False)
def geocode_city(city_name):
    url = f"https://nominatim.openstreetmap.org/search"
    params = {
        'q': city_name,
        'format': 'json',
        'limit': 1
    }
    response = requests.get(url, params=params, headers={'User-Agent': 'coworking-location-app'})
    if response.status_code != 200:
        return None, None
    data = response.json()
    if len(data) == 0:
        return None, None
    lat = float(data[0]['lat'])
    lon = float(data[0]['lon'])
    return lat, lon

def get_attom_commercial_properties(city, state, attom_api_key, page=1):
    url = "https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/detail"
    headers = {"apikey": attom_api_key}
    address = f"{city}, {state}"
    params = {
        "address1": address,
        "pagesize": 10,
        "page": page,
        "propertytype": "commercial"
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        return None

# Sidebar: Scoring weights
st.sidebar.header("Adjust Scoring Weights")
weight_population = st.sidebar.slider("Population Weight", 0.0, 5.0, 1.0, 0.1)
weight_coworking = st.sidebar.slider("Competition (Coworking Spaces) Weight", 0.0, 5.0, 1.0, 0.1)
weight_price = st.sidebar.slider("Commercial Price Weight", 0.0, 5.0, 1.0, 0.1)

st.title("North America Coworking Space Location Finder")

st.markdown("""
Enter one or more city names (comma separated), e.g. `Austin, TX`, `Toronto, ON`, `New York, NY`.
""")

city_inputs = st.text_area("Enter cities:", "Austin, TX\nToronto, ON\nNew York, NY")

df_canada = None
if canada_csv_path:
    try:
        df_canada = load_canadian_data(canada_csv_path)
    except Exception as e:
        st.sidebar.error(f"Error loading Canada CSV: {e}")

cities = [c.strip() for c in city_inputs.split('\n') if c.strip()]
results = []

map_center = [39.8283, -98.5795]  # Center of USA for initial map

m = folium.Map(location=map_center, zoom_start=4)
markers_group = folium.FeatureGroup(name="Coworking Spaces")

for city_input in cities:
    if ',' in city_input:
        city_name, state_prov = [x.strip() for x in city_input.split(',', 1)]
    else:
        city_name = city_input
        state_prov = ""

    lat, lon = geocode_city(city_input)
    if lat is None or lon is None:
        st.warning(f"Could not find coordinates for {city_input}")
        continue

    if state_prov.upper() in us_state_fips:
        fips = us_state_fips[state_prov.upper()]
        pop, income = get_us_city_data(fips, city_name)
    else:
        if df_canada is not None:
            row = df_canada[df_canada['City'].str.contains(city_name, case=False)]
            if not row.empty:
                pop = int(row['Population'].values[0])
                income = int(row['MedianIncome'].values[0])
            else:
                pop, income = None, None
                st.warning(f"Population/Income data not found in Canada dataset for {city_input}")
        else:
            pop, income = None, None

    coworking_count, coworking_places = get_coworking_osm(lat, lon)
    if coworking_count is None:
        coworking_count = 0
        coworking_places = []

    avg_price = None
    if ATTOM_API_KEY and state_prov:
        attom_data = get_attom_commercial_properties(city_name, state_prov, ATTOM_API_KEY)
        prices = []
        if attom_data:
            properties = attom_data.get('property', [])
            for prop in properties:
                try:
                    price_info = prop.get('property', {}).get('lastSale', {}).get('price')
                    if price_info:
                        prices.append(float(price_info))
                except:
                    pass
            if prices:
                avg_price = sum(prices) / len(prices)

    norm_pop = pop if pop else 1
    norm_coworking = coworking_count if coworking_count > 0 else 1
    norm_price = avg_price if avg_price and avg_price > 0 else 1_000_000

    score = (weight_population * norm_pop) / (weight_coworking * norm_coworking) / (weight_price * norm_price)

    results.append({
        "City": city_input,
        "Population": pop,
        "MedianIncome": income,
        "CoworkingSpaces": coworking_count,
        "AvgCommercialPrice": avg_price,
        "Score": score,
        "Latitude": lat,
        "Longitude": lon,
        "CoworkingPlaces": coworking_places
    })

    popup_text = (
        f"<b>{city_input}</b><br>"
        f"Population: {pop if pop else 'N/A'}<br>"
        f"Median Income: ${income if income else 'N/A'}<br>"
        f"Coworking Spaces: {coworking_count}<br>"
        f"Avg Commercial Price: ${avg_price:,.0f}" if avg_price else "N/A"
    )
    folium.Marker([lat, lon], popup=popup_text).add_to(m)

    for place in coworking_places[:20]:
        c_lat = place.get('lat') or place.get('center', {}).get('lat')
        c_lon = place.get('lon') or place.get('center', {}).get('lon')
        name = place.get('tags', {}).get('name', 'Coworking Space')
        if c_lat and c_lon:
            folium.CircleMarker(
                location=[c_lat, c_lon],
                radius=5,
                color='blue',
                fill=True,
                fill_opacity=0.7,
                popup=name
            ).add_to(markers_group)

markers_group.add_to(m)
folium.LayerControl().add_to(m)

st.header("Map of Cities and Coworking Spaces")
st_data = st_folium(m, width=700, height=500)

df_results = pd.DataFrame(results)
df_results_sorted = df_results.sort_values(by="Score", ascending=False)

st.header("City Rankings")

cols = st.columns(6)
headers = ["City", "Population", "Median Income", "Coworking Spaces", "Avg Commercial Price", "Score"]
for col, header in zip(cols, headers):
    col.write(f"**{header}**")

for i, row in df_results_sorted.iterrows():
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.write(row['City'])
    c2.write(f"{row['Population']:,}" if pd.notnull(row['Population']) else "N/A")
    c3.write(f"${row['MedianIncome']:,}" if pd.notnull(row['MedianIncome']) else "N/A")
    c4.write(row['CoworkingSpaces'])
    c5.write(f"${row['AvgCommercialPrice']:,.0f}" if pd.notnull(row['AvgCommercialPrice']) else "N/A")
    c6.write(f"{row['Score']:,.2f}")

st.markdown("""
---
**Notes:**

- Hardcoded your ATTOM API key at the top of the script.
- Adjust scoring weights on the sidebar.
- Map shows coworking spaces and city centers.
""")
