import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import st_folium
from datetime import datetime

# Load Excel data once
@st.cache_data(show_spinner=False)
def load_excel_data():
    # Read from Map.xlsx -> Map sheet
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
    return len(data.get('elements', []))

# Sidebar weights for scoring
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

st.markdown("Enter one or more city names (one per line), e.g. Austin, TX\nToronto, ON\nNew York, NY.")

city_inputs = st.text_area("Enter cities:", "Austin, TX\nToronto, ON\nNew York, NY")
cities = [c.strip() for c in city_inputs.split('\n') if c.strip()]

# First pass: Collect raw data for all cities
raw_results = []

for city_input in cities:
    if ',' in city_input:
        city_name, state_prov = [x.strip() for x in city_input.split(',', 1)]
    else:
        city_name, state_prov = city_input, ""

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
        coworking_count, coworking_places = 0, []

    transit_count = get_transit_stops_osm(lat, lon) or 0

    # Match centres that contain the city_name and state in 'Centre_lower'
    # Example centre: "5001_BC, Vancouver - Spaces Green Lamp"
    # We'll check if "vancouver" and "bc" are substrings inside the centre string (case insensitive)
    city_name_lower = city_name.lower()
    state_prov_lower = state_prov.lower()
    matching_centres = map_excel_df[
        map_excel_df['Centre_lower'].apply(lambda x: city_name_lower in x and state_prov_lower in x)
    ]

    # Sum or average the metrics over matching centres
    if not matching_centres.empty:
        office_sqft = matching_centres['Office Inv. SQFT'].sum()
        total_centre_sqft = matching_centres['Total centre SQFT'].sum()
        efficiency = matching_centres['Efficiency'].mean()
        occupancy = matching_centres['SQM Occupancy %'].mean()
        cbitda = matching_centres['CBITDA'].sum()
    else:
        office_sqft = total_centre_sqft = efficiency = occupancy = cbitda = 0

    raw_results.append({
        "City": city_input,
        "Population": pop if pop else 0,
        "Population Growth": growth if growth else 0,
        "MedianIncome": income if income else 0,
        "CoworkingSpaces": coworking_count,
        "TransitStops": transit_count,
        "Office Inv. SQFT": office_sqft,
        "Total centre SQFT": total_centre_sqft,
        "Efficiency": efficiency,
        "SQM Occupancy %": occupancy,
        "CBITDA": cbitda,
        "Latitude": lat,
        "Longitude": lon,
        "CoworkingPlaces": coworking_places
    })

# Compute max values for normalization from all raw data
max_pop = max([r["Population"] for r in raw_results] + [1])
max_growth = max([r["Population Growth"] for r in raw_results] + [1])
max_coworking = max([r["CoworkingSpaces"] for r in raw_results] + [1])
max_transit = max([r["TransitStops"] for r in raw_results] + [1])
max_office_sqft = max([r["Office Inv. SQFT"] for r in raw_results] + [1])
max_total_centre_sqft = max([r["Total centre SQFT"] for r in raw_results] + [1])
max_efficiency = max([r["Efficiency"] for r in raw_results] + [1])
max_occupancy = max([r["SQM Occupancy %"] for r in raw_results] + [1])
max_cbitda = max([r["CBITDA"] for r in raw_results] + [1])

# Second pass: Normalize, score and prepare final results
results = []

for r in raw_results:
    norm_pop = r["Population"] / max_pop if max_pop > 0 else 0
    norm_growth = r["Population Growth"] / max_growth if max_growth > 0 else 0
    norm_coworking = r["CoworkingSpaces"] / max_coworking if max_coworking > 0 else 0
    norm_transit = r["TransitStops"] / max_transit if max_transit > 0 else 0
    norm_office_sqft = r["Office Inv. SQFT"] / max_office_sqft if max_office_sqft > 0 else 0
    norm_total_centre_sqft = r["Total centre SQFT"] / max_total_centre_sqft if max_total_centre_sqft > 0 else 0
    norm_efficiency = r["Efficiency"] / max_efficiency if max_efficiency > 0 else 0
    norm_occupancy = r["SQM Occupancy %"] / max_occupancy if max_occupancy > 0 else 0
    norm_cbitda = r["CBITDA"] / max_cbitda if max_cbitda > 0 else 0

    # Score calculation: higher coworking spaces means more competition so subtract its weighted value
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

    r["Score"] = score
    r["Normalized Population"] = norm_pop
    r["Normalized Growth"] = norm_growth
    r["Normalized Coworking"] = norm_coworking
    r["Normalized Transit"] = norm_transit
    results.append(r)

# Map creation
map_center = [39.8283, -98.5795]
m = folium.Map(location=map_center, zoom_start=4)
markers_group = folium.FeatureGroup(name="Coworking Spaces")
transit_group = folium.FeatureGroup(name="Transit Stops")

for r in results:
    popup_text = (
        f"<b>{r['City']}</b><br>"
        f"Population: {r['Population']:,}<br>"
        f"Population Growth (projected 5yr): {r['Population Growth']:.2%}<br>"
        f"Median Income: ${r['MedianIncome']:,}<br>"
        f"Coworking Spaces: {r['CoworkingSpaces']}<br>"
        f"Transit Stops: {r['TransitStops']}<br>"
        f"Office Inv. SQFT: {r['Office Inv. SQFT']:,}<br>"
        f"Total centre SQFT: {r['Total centre SQFT']:,}<br>"
        f"Efficiency: {r['Efficiency']:.2f}<br>"
        f"SQM Occupancy %: {r['SQM Occupancy %']:.2f}<br>"
        f"CBITDA: {r['CBITDA']:,}<br>"
        f"<b>Score: {r['Score']:.3f}</b>"
    )
    folium.Marker([r['Latitude'], r['Longitude']], popup=popup_text).add_to(m)

    # Show coworking places in blue circles (up to 20)
    for place in r['CoworkingPlaces'][:20]:
        c_lat = place.get('lat') or place.get('center', {}).get('lat')
        c_lon = place.get('lon') or place.get('center', {}).get('lon')
        name = place.get('tags', {}).get('name', 'Coworking Space')
        if c_lat and c_lon:
            folium.CircleMarker(
                location=[c_lat, c_lon], radius=5, color='blue',
                fill=True, fill_opacity=0.7, popup=name
            ).add_to(markers_group)

    folium.CircleMarker(
        location=[r['Latitude'], r['Longitude']], radius=7, color='green',
        fill=True, fill_opacity=0.5,
        popup=f"Transit stops: {r['TransitStops']}"
    ).add_to(transit_group)

markers_group.add_to(m)
transit_group.add_to(m)
folium.LayerControl().add_to(m)

st.header("Map of Cities, Coworking Spaces & Transit Stops")
st_folium(m, width=700, height=500)

df_results = pd.DataFrame(results).sort_values(by="Score", ascending=False)

st.header("City Rankings")
st.dataframe(df_results[[
    "City", "Population", "Population Growth", "MedianIncome",
    "CoworkingSpaces", "TransitStops",
    "Office Inv. SQFT", "Total centre SQFT", "Efficiency",
    "SQM Occupancy %", "CBITDA", "Score"
]])

st.markdown(
    """
---
**Notes:**

- Population growth is projected over the next 5 years for both US and Canadian cities.  
- Transit stops data is retrieved from OpenStreetMap around city centers.  
- Adjust scoring weights in the sidebar to prioritize metrics according to your strategy.  
- The score for each city is calculated as a weighted sum of normalized metrics, including population, growth, transit accessibility, office space, efficiency, occupancy, financials (CBITDA), and competition (coworking spaces).  
- Competition (number of coworking spaces) negatively impacts the score, while other metrics positively contribute.  
- The map displays city locations, coworking spaces (blue markers), and transit stops (green markers).  
"""
)

# Hide Streamlit toolbar
st.markdown("<style>[data-testid='stToolbar'] {visibility: hidden; height: 0%; position: fixed;}</style>", unsafe_allow_html=True)
