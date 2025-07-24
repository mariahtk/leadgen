import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import st_folium
from datetime import datetime

# Load Excel data once
@st.cache_data(show_spinner=False)
def load_excel_data():
    # Read Excel with headers on row 10 (index 9)
    df = pd.read_excel("City.xlsx", header=9)
    df['Centre_lower'] = df['Centre'].str.lower()
    return df

city_excel_df = load_excel_data()

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
def get_canadian_city_data(city_name):
    dummy_data = {
        "Toronto": {"population": 2930000, "median_income": 40000},
        "Montreal": {"population": 1780000, "median_income": 35000},
        "Vancouver": {"population": 675000, "median_income": 45000},
        "Calgary": {"population": 1239000, "median_income": 47000},
        "Ottawa": {"population": 994000, "median_income": 42000},
    }
    for key in dummy_data:
        if key.lower() in city_name.lower():
            return dummy_data[key]['population'], dummy_data[key]['median_income']
    return None, None

@st.cache_data(show_spinner=False)
def get_us_population_year(year, state_fips, city_name):
    url = (
        f"https://api.census.gov/data/{year}/acs/acs5?"
        f"get=NAME,B01003_001E&for=place:*&in=state:{state_fips}"
    )
    response = requests.get(url)
    if response.status_code != 200:
        return None
    data = response.json()
    df = pd.DataFrame(data[1:], columns=data[0])
    city_row = df[df['NAME'].str.contains(city_name, case=False)]
    if not city_row.empty:
        try:
            population = int(city_row.iloc[0]['B01003_001E'])
            return population
        except:
            return None
    return None

def calculate_population_growth(city_name, state_fips=None, country="US", years_forward=5):
    if country == "US" and state_fips:
        pop_2010 = get_us_population_year(2010, state_fips, city_name)
        pop_2021 = get_us_population_year(2021, state_fips, city_name)
        if pop_2010 and pop_2021 and pop_2010 > 0:
            years_past = 2021 - 2010
            annual_growth_rate = (pop_2021 / pop_2010) ** (1 / years_past) - 1
            projected_growth = (1 + annual_growth_rate) ** years_forward - 1
            return projected_growth
        else:
            return 0
    elif country == "CA":
        historic_total_growth = 0.08
        historic_years = 10
        annual_growth_rate = (1 + historic_total_growth) ** (1 / historic_years) - 1
        projected_growth = (1 + annual_growth_rate) ** years_forward - 1
        return projected_growth
    return 0

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
def get_transit_stops_osm(lat, lon, radius=10000):
    overpass_url = "http://overpass-api.de/api/interpreter"
    query = f"""
    [out:json];
    (
      node["public_transport"="platform"](around:{radius},{lat},{lon});
      node["highway"="bus_stop"](around:{radius},{lat},{lon});
      node["railway"="station"](around:{radius},{lat},{lon});
      node["railway"="tram_stop"](around:{radius},{lat},{lon});
      node["railway"="subway_entrance"](around:{radius},{lat},{lon});
    );
    out count;
    """
    response = requests.post(overpass_url, data={'data': query})
    if response.status_code != 200:
        return None
    data = response.json()
    count = len(data.get('elements', []))
    return count

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

# Sidebar for weights including new ones for SQM Occupancy and Efficiency
st.sidebar.header("Adjust Scoring Weights")
weight_population = st.sidebar.slider("Population Weight", 0.0, 5.0, 1.0, 0.1)
weight_growth = st.sidebar.slider("Population Growth Weight", 0.0, 5.0, 1.0, 0.1)
weight_coworking = st.sidebar.slider("Competition (Coworking Spaces) Weight", 0.0, 5.0, 1.0, 0.1)
weight_transit = st.sidebar.slider("Transit Accessibility Weight", 0.0, 5.0, 1.0, 0.1)
weight_price = st.sidebar.slider("Commercial Price Weight", 0.0, 5.0, 1.0, 0.1)
weight_occupancy = st.sidebar.slider("SQM Occupancy Weight", 0.0, 5.0, 1.0, 0.1)
weight_efficiency = st.sidebar.slider("Efficiency Weight", 0.0, 5.0, 1.0, 0.1)

st.title("North America Co-Working Priority Rankings")

st.markdown("""
Enter one or more city names (comma separated), e.g. Austin, TX, Toronto, ON, New York, NY.
""")

city_inputs = st.text_area("Enter cities:", "Austin, TX\nToronto, ON\nNew York, NY")

cities = [c.strip() for c in city_inputs.split('\n') if c.strip()]
results = []

map_center = [39.8283, -98.5795]  # Center of USA for initial map

m = folium.Map(location=map_center, zoom_start=4)
markers_group = folium.FeatureGroup(name="Coworking Spaces")
transit_group = folium.FeatureGroup(name="Transit Stops")

max_occupancy = city_excel_df['SQM Occupancy'].max() if 'SQM Occupancy' in city_excel_df.columns else 1
max_efficiency = city_excel_df['Efficiency'].max() if 'Efficiency' in city_excel_df.columns else 1

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
        growth = calculate_population_growth(city_name, fips, country="US", years_forward=5)
    else:
        pop, income = get_canadian_city_data(city_name)
        growth = calculate_population_growth(city_name, country="CA", years_forward=5)

    coworking_count, coworking_places = get_coworking_osm(lat, lon)
    if coworking_count is None:
        coworking_count = 0
        coworking_places = []

    transit_count = get_transit_stops_osm(lat, lon)
    if transit_count is None:
        transit_count = 0

    avg_price = None
    if "ATTOM_API_KEY" in globals() and ATTOM_API_KEY and state_prov:
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

    centre_key = city_input.lower()
    match_row = city_excel_df[city_excel_df['Centre_lower'] == centre_key]
    if not match_row.empty:
        occupancy = float(match_row.iloc[0]['SQM Occupancy']) if 'SQM Occupancy' in match_row.columns else 0
        efficiency = float(match_row.iloc[0]['Efficiency']) if 'Efficiency' in match_row.columns else 0
    else:
        occupancy = 0
        efficiency = 0

    norm_pop = pop if pop else 1
    norm_growth = growth if growth else 0
    norm_coworking = coworking_count if coworking_count > 0 else 1
    norm_transit = transit_count if transit_count > 0 else 1
    norm_price = avg_price if avg_price and avg_price > 0 else 1_000_000
    norm_occupancy = occupancy / max_occupancy if max_occupancy > 0 else 0
    norm_efficiency = efficiency / max_efficiency if max_efficiency > 0 else 0

    score = (
        weight_population * norm_pop +
        weight_growth * norm_growth * norm_pop +
        weight_transit * norm_transit -
        weight_coworking * norm_coworking -
        weight_price * norm_price / 1_000_000 +
        weight_occupancy * norm_occupancy +
        weight_efficiency * norm_efficiency
    )

    results.append({
        "City": city_input,
        "Population": pop,
        "Population Growth": growth,
        "MedianIncome": income,
        "CoworkingSpaces": coworking_count,
        "TransitStops": transit_count,
        "AvgCommercialPrice": avg_price,
        "SQM Occupancy": occupancy,
        "Efficiency": efficiency,
        "Score": score,
        "Latitude": lat,
        "Longitude": lon,
        "CoworkingPlaces": coworking_places
    })

    popup_text = (
        f"<b>{city_input}</b><br>"
        f"Population: {pop if pop else 'N/A'}<br>"
        f"Population Growth (projected 5yr): {growth:.2%}<br>"
        f"Median Income: ${income if income else 'N/A'}<br>"
        f"Coworking Spaces: {coworking_count}<br>"
        f"Transit Stops: {transit_count}<br>"
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

    folium.CircleMarker(
        location=[lat, lon],
        radius=7,
        color='green',
        fill=True,
        fill_opacity=0.5,
        popup=f"Transit stops: {transit_count}"
    ).add_to(transit_group)

markers_group.add_to(m)
transit_group.add_to(m)
folium.LayerControl().add_to(m)

st.header("Map of Cities, Coworking Spaces & Transit Stops")
st_data = st_folium(m, width=700, height=500)

df_results = pd.DataFrame(results)
df_results_sorted = df_results.sort_values(by="Score", ascending=False)

st.header("City Rankings")

cols = st.columns(10)
headers = ["City", "Population", "Population Growth (5yr projected)", "Median Income", "Coworking Spaces", "Transit Stops", "Avg Commercial Price", "SQM Occupancy", "Efficiency", "Score"]
for col, header in zip(cols, headers):
    col.write(f"**{header}**")

for i, row in df_results_sorted.iterrows():
    c1, c2, c3, c4, c5, c6, c7, c8, c9, c10 = st.columns(10)
    c1.write(row['City'])
    c2.write(f"{row['Population']:,}" if pd.notnull(row['Population']) else "N/A")
    c3.write(f"{row['Population Growth']:.2%}" if pd.notnull(row['Population Growth']) else "N/A")
    c4.write(f"${row['MedianIncome']:,}" if pd.notnull(row['MedianIncome']) else "N/A")
    c5.write(row['CoworkingSpaces'])
    c6.write(row['TransitStops'])
    c7.write(f"${row['AvgCommercialPrice']:,.0f}" if pd.notnull(row['AvgCommercialPrice']) else "N/A")
    c8.write(f"{row['SQM Occupancy']:.2f}" if pd.notnull(row['SQM Occupancy']) else "N/A")
    c9.write(f"{row['Efficiency']:.2f}" if pd.notnull(row['Efficiency']) else "N/A")
    c10.write(f"{row['Score']:,.2f}")

st.markdown("""
---
**Notes:**
- Population growth is projected over next 5 years for both US and Canadian cities.
- Transit stops data comes from OpenStreetMap around city center.
- Adjust scoring weights in the sidebar to tailor prioritization to company strategy.
- Map shows city locations, coworking spaces (blue), and transit stops (green).
- SQM Occupancy and Efficiency data are loaded from City.xlsx and included in scoring.
""")

# --- Hide Streamlit Toolbar Buttons ---
hide_streamlit_style = """
    <style>
    [data-testid="stToolbar"] {visibility: hidden; height: 0%; position: fixed;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)
