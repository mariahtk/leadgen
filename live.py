import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import st_folium
from datetime import datetime
import re

# --- Load Excel data ---
@st.cache_data(show_spinner=False)
def load_excel_data():
    df = pd.read_excel("Map.xlsx", sheet_name="Map")
    df['Centre_lower'] = df['Centre'].str.lower()
    return df

map_excel_df = load_excel_data()

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
            return int(city_row.iloc[0]['B01003_001E']), int(city_row.iloc[0]['B19013_001E'])
        except:
            return None, None
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
            years_past = 2021 - 2010
            annual_growth_rate = (pop_2021 / pop_2010) ** (1 / years_past) - 1
            return (1 + annual_growth_rate) ** years_forward - 1
        return 0
    elif country == "CA":
        return (1 + (0.08)**(1/10)) ** years_forward - 1
    return 0

@st.cache_data(show_spinner=False)
def geocode_city(city_name):
    url = "https://nominatim.openstreetmap.org/search"
    params = {'q': city_name, 'format': 'json', 'limit': 1}
    response = requests.get(url, params=params, headers={'User-Agent': 'coworking-location-app'})
    if response.status_code != 200 or len(response.json()) == 0:
        return None, None
    data = response.json()[0]
    return float(data['lat']), float(data['lon'])

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
    r = requests.post(overpass_url, data={'data': query})
    if r.status_code != 200: return None, []
    return len(r.json().get('elements', [])), r.json().get('elements', [])

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
    r = requests.post(overpass_url, data={'data': query})
    if r.status_code != 200: return None
    return len(r.json().get('elements', []))

# --- Sidebar weights ---
st.sidebar.header("Adjust Scoring Weights")
weight_population = st.sidebar.slider("Population Weight", 0.0, 5.0, 1.0, 0.1)
weight_growth = st.sidebar.slider("Population Growth Weight", 0.0, 5.0, 1.0, 0.1)
weight_coworking = st.sidebar.slider("Competition (Coworking Spaces) Weight", 0.0, 5.0, 1.0, 0.1)
weight_transit = st.sidebar.slider("Transit Accessibility Weight", 0.0, 5.0, 1.0, 0.1)
weight_office_sqft = st.sidebar.slider("Office Inv. SQFT Weight", 0.0, 5.0, 1.0, 0.1)
weight_total_centre_sqft = st.sidebar.slider("Total centre SQFT Weight", 0.0, 5.0, 1.0, 0.1)
weight_efficiency = st.sidebar.slider("Efficiency Weight", 0.0, 5.0, 1.0, 0.1)
weight_occupancy = st.sidebar.slider("SQM Occupancy % Weight", 0.0, 5.0, 1.0, 0.1)
weight_cbitda = st.sidebar.slider("CBITDA Weight", 0.0, 5.0, 1.0, 0.1)

st.title("North America Co-Working Priority Rankings")
city_inputs = st.text_area("Enter cities:", "Austin, TX\nToronto, ON\nNew York, NY")
cities = [c.strip() for c in city_inputs.split('\n') if c.strip()]
results = []

map_center = [39.8283, -98.5795]
m = folium.Map(location=map_center, zoom_start=4)
markers_group = folium.FeatureGroup(name="Coworking Spaces")
transit_group = folium.FeatureGroup(name="Transit Stops")

# --- Max values ---
max_office_sqft = map_excel_df['Office Inv. SQFT'].max() or 1
max_total_centre_sqft = map_excel_df['Total centre SQFT'].max() or 1
max_efficiency = map_excel_df['Efficiency'].max() or 1
max_occupancy = map_excel_df['SQM Occupancy %'].max() or 1
max_cbitda = map_excel_df['CBITDA'].max() or 1

def find_city_metrics(city_input):
    # Parse user input
    if ',' in city_input:
        city_name, province = [x.strip().lower() for x in city_input.split(',', 1)]
    else:
        city_name, province = city_input.lower(), ""

    # Match from Centre column
    matches = map_excel_df[
        map_excel_df['Centre_lower'].str.contains(province) &
        map_excel_df['Centre_lower'].str.contains(city_name)
    ]
    if matches.empty:
        return 0,0,0,0,0

    office_sqft = matches['Office Inv. SQFT'].sum()
    total_centre_sqft = matches['Total centre SQFT'].sum()
    efficiency = matches['Efficiency'].mean()
    occupancy = matches['SQM Occupancy %'].mean()
    cbitda = matches['CBITDA'].sum()
    return office_sqft, total_centre_sqft, efficiency, occupancy, cbitda

for city_input in cities:
    lat, lon = geocode_city(city_input)
    if lat is None or lon is None:
        st.warning(f"Could not find coordinates for {city_input}")
        continue

    if ',' in city_input and city_input.split(',')[1].strip().upper() in us_state_fips:
        fips = us_state_fips[city_input.split(',')[1].strip().upper()]
        pop, income = get_us_city_data(fips, city_input.split(',')[0].strip())
        growth = calculate_population_growth(city_input.split(',')[0].strip(), fips, "US", 5)
    else:
        pop, income = get_canadian_city_data(city_input)
        growth = calculate_population_growth(city_input, country="CA", years_forward=5)

    coworking_count, coworking_places = get_coworking_osm(lat, lon)
    transit_count = get_transit_stops_osm(lat, lon) or 0

    office_sqft, total_centre_sqft, efficiency, occupancy, cbitda = find_city_metrics(city_input)

    # Normalize
    norm_pop = pop if pop else 1
    norm_growth = growth if growth else 0
    norm_coworking = coworking_count if coworking_count > 0 else 1
    norm_transit = transit_count if transit_count > 0 else 1
    norm_office_sqft = office_sqft / max_office_sqft
    norm_total_centre_sqft = total_centre_sqft / max_total_centre_sqft
    norm_efficiency = efficiency / max_efficiency
    norm_occupancy = occupancy / max_occupancy
    norm_cbitda = cbitda / max_cbitda

    score = (
        weight_population * norm_pop +
        weight_growth * norm_growth * norm_pop +
        weight_transit * norm_transit -
        weight_coworking * norm_coworking +
        weight_office_sqft * norm_office_sqft +
        weight_total_centre_sqft * norm_total_centre_sqft +
        weight_efficiency * norm_efficiency +
        weight_occupancy * norm_occupancy +
        weight_cbitda * norm_cbitda
    )

    results.append({
        "City": city_input,
        "Population": pop,
        "Population Growth": growth,
        "MedianIncome": income,
        "CoworkingSpaces": coworking_count,
        "TransitStops": transit_count,
        "Office Inv. SQFT": office_sqft,
        "Total centre SQFT": total_centre_sqft,
        "Efficiency": efficiency,
        "SQM Occupancy %": occupancy,
        "CBITDA": cbitda,
        "Score": score
    })

    folium.Marker([lat, lon], popup=f"<b>{city_input}</b>").add_to(m)
    for place in coworking_places[:20]:
        c_lat = place.get('lat') or place.get('center', {}).get('lat')
        c_lon = place.get('lon') or place.get('center', {}).get('lon')
        if c_lat and c_lon:
            folium.CircleMarker(location=[c_lat, c_lon], radius=5, color='blue',
                                fill=True, fill_opacity=0.7).add_to(markers_group)
    folium.CircleMarker(location=[lat, lon], radius=7, color='green',
                        fill=True, fill_opacity=0.5).add_to(transit_group)

markers_group.add_to(m)
transit_group.add_to(m)
folium.LayerControl().add_to(m)

st.header("Map of Cities, Coworking Spaces & Transit Stops")
st_folium(m, width=700, height=500)

df_results = pd.DataFrame(results).sort_values(by="Score", ascending=False)
st.header("City Rankings")
st.dataframe(df_results)

st.markdown("""
---
**Notes:**
- Population growth is projected over next 5 years.
- Transit stops data comes from OpenStreetMap.
- Aggregated centre data (sum or avg where applicable).
""")
st.markdown("<style>[data-testid='stToolbar'] {visibility: hidden; height: 0%; position: fixed;}</style>", unsafe_allow_html=True)
