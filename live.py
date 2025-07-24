import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import st_folium
from datetime import datetime
import openpyxl


# --- API KEYS (HARDCODE HERE) ---
ATTOM_API_KEY = "7b9f39f8722159b30ca61f77279e829d"  # Replace with your ATTOM key

# --- Load Excel data (headers start at row 10) ---
@st.cache_data(show_spinner=False)
def load_excel_data():
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
            return int(city_row.iloc[0]['B01003_001E'])
        except:
            return None
    return None

def calculate_population_growth(city_name, state_fips=None, country="US", years_forward=5):
    if country == "US" and state_fips:
        pop_2010 = get_us_population_year(2010, state_fips, city_name)
        pop_2021 = get_us_population_year(2021, state_fips, city_name)
        if pop_2010 and pop_2021 and pop_2010 > 0:
            annual_growth_rate = (pop_2021 / pop_2010) ** (1 / (2021 - 2010)) - 1
            return (1 + annual_growth_rate) ** years_forward - 1
        else:
            return 0
    elif country == "CA":
        historic_total_growth = 0.08
        annual_growth_rate = (1 + historic_total_growth) ** (1 / 10) - 1
        return (1 + annual_growth_rate) ** years_forward - 1
    return 0

@st.cache_data(show_spinner=False)
def geocode_city(city_name):
    url = f"https://nominatim.openstreetmap.org/search"
    params = {'q': city_name, 'format': 'json', 'limit': 1}
    response = requests.get(url, params=params, headers={'User-Agent': 'coworking-location-app'})
    if response.status_code != 200:
        return None, None
    data = response.json()
    if len(data) == 0:
        return None, None
    return float(data[0]['lat']), float(data[0]['lon'])

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
        return 0, []
    data = response.json()
    return len(data.get('elements', [])), data.get('elements', [])

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
    out;
    """
    response = requests.post(overpass_url, data={'data': query})
    if response.status_code != 200:
        return 0
    return len(response.json().get('elements', []))


# --- Sidebar weights ---
st.sidebar.header("Adjust Scoring Weights")
weight_population = st.sidebar.slider("Population Weight", 0.0, 5.0, 1.0, 0.1)
weight_growth = st.sidebar.slider("Population Growth Weight", 0.0, 5.0, 1.0, 0.1)
weight_coworking = st.sidebar.slider("Competition (Coworking Spaces) Weight", 0.0, 5.0, 1.0, 0.1)
weight_transit = st.sidebar.slider("Transit Accessibility Weight", 0.0, 5.0, 1.0, 0.1)
weight_price = st.sidebar.slider("Commercial Price Weight", 0.0, 5.0, 1.0, 0.1)
weight_occupancy = st.sidebar.slider("SQM Occupancy Weight", 0.0, 5.0, 1.0, 0.1)
weight_efficiency = st.sidebar.slider("Efficiency Weight", 0.0, 5.0, 1.0, 0.1)
weight_cbitda = st.sidebar.slider("CBITDA Weight", 0.0, 5.0, 1.0, 0.1)

st.title("North America Co-Working Priority Rankings")
st.markdown("Enter one or more city names (comma separated), e.g. `Austin, TX`, `Toronto, ON`, `New York, NY`.")
city_inputs = st.text_area("Enter cities:", "Austin, TX\nToronto, ON\nNew York, NY")
cities = [c.strip() for c in city_inputs.split('\n') if c.strip()]
results = []

# --- For normalization ---
max_occupancy = city_excel_df['SQM Occupancy'].max() if 'SQM Occupancy' in city_excel_df.columns else 1
max_efficiency = city_excel_df['Efficiency'].max() if 'Efficiency' in city_excel_df.columns else 1
max_cbitda = city_excel_df['CBITDA'].max() if 'CBITDA' in city_excel_df.columns else 1

# --- Map ---
m = folium.Map(location=[39.8283, -98.5795], zoom_start=4)
markers_group, transit_group = folium.FeatureGroup(name="Coworking Spaces"), folium.FeatureGroup(name="Transit Stops")

for city_input in cities:
    city_name, state_prov = city_input.split(',', 1) if ',' in city_input else (city_input, "")
    lat, lon = geocode_city(city_input)
    if not lat or not lon:
        st.warning(f"Could not find coordinates for {city_input}")
        continue

    # --- Population & income ---
    if state_prov.strip().upper() in us_state_fips:
        fips = us_state_fips[state_prov.strip().upper()]
        pop, income = get_us_city_data(fips, city_name)
        growth = calculate_population_growth(city_name, fips, "US", 5)
    else:
        pop, income = get_canadian_city_data(city_name)
        growth = calculate_population_growth(city_name, country="CA", years_forward=5)

    coworking_count, coworking_places = get_coworking_osm(lat, lon)
    transit_count = get_transit_stops_osm(lat, lon)

    # --- No ATTOM Price Lookup ---
    avg_price = None

    # --- Match Excel Row ---
    match_row = city_excel_df[city_excel_df['Centre_lower'] == city_input.lower()]
    occupancy = float(match_row.iloc[0]['SQM Occupancy']) if not match_row.empty else 0
    efficiency = float(match_row.iloc[0]['Efficiency']) if not match_row.empty else 0
    cbitda = float(match_row.iloc[0]['CBITDA']) if not match_row.empty else 0

    # --- Normalize & Score ---
    norm_occupancy = occupancy / max_occupancy
    norm_efficiency = efficiency / max_efficiency
    norm_cbitda = cbitda / max_cbitda
    norm_pop = pop or 1
    norm_growth = growth or 0
    norm_coworking = coworking_count or 1
    norm_transit = transit_count or 1
    norm_price = avg_price or 1_000_000

    score = (
        weight_population * norm_pop +
        weight_growth * norm_growth * norm_pop +
        weight_transit * norm_transit -
        weight_coworking * norm_coworking -
        weight_price * norm_price / 1_000_000 +
        weight_occupancy * norm_occupancy +
        weight_efficiency * norm_efficiency +
        weight_cbitda * norm_cbitda
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
        "CBITDA": cbitda,
        "Score": score,
        "Latitude": lat,
        "Longitude": lon,
        "CoworkingPlaces": coworking_places
    })

    folium.Marker([lat, lon], popup=f"<b>{city_input}</b>").add_to(m)
    for place in coworking_places[:20]:
        folium.CircleMarker(
            location=[place.get('lat') or place.get('center', {}).get('lat'),
                      place.get('lon') or place.get('center', {}).get('lon')],
            radius=5, color='blue', fill=True, fill_opacity=0.7,
            popup=place.get('tags', {}).get('name', 'Coworking Space')
        ).add_to(markers_group)

markers_group.add_to(m)
transit_group.add_to(m)
folium.LayerControl().add_to(m)
st.header("Map of Cities, Coworking Spaces & Transit Stops")
st_data = st_folium(m, width=700, height=500)

df_results = pd.DataFrame(results).sort_values(by="Score", ascending=False)

# --- Table ---
st.header("City Rankings")
headers = ["City", "Population", "Population Growth (5yr projected)", "Median Income", 
           "Coworking Spaces", "Transit Stops", "Avg Commercial Price", 
           "SQM Occupancy", "Efficiency", "CBITDA", "Score"]

cols = st.columns(len(headers))
for col, header in zip(cols, headers):
    col.write(f"**{header}**")

for _, row in df_results.iterrows():
    values = [row['City'],
              f"{row['Population']:,}" if pd.notnull(row['Population']) else "N/A",
              f"{row['Population Growth']:.2%}" if pd.notnull(row['Population Growth']) else "N/A",
              f"${row['MedianIncome']:,}" if pd.notnull(row['MedianIncome']) else "N/A",
              row['CoworkingSpaces'], row['TransitStops'],
              f"${row['AvgCommercialPrice']:,.0f}" if pd.notnull(row['AvgCommercialPrice']) else "N/A",
              f"{row['SQM Occupancy']:.2f}", f"{row['Efficiency']:.2f}", f"{row['CBITDA']:.2f}",
              f"{row['Score']:,.2f}"]
    st.columns(len(values))
    for col, val in zip(st.columns(len(values)), values):
        col.write(val)

# --- Hide Streamlit Toolbar ---
hide_streamlit_style = """
    <style>
    [data-testid="stToolbar"] {visibility: hidden; height: 0%; position: fixed;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)
