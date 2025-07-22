import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import st_folium
from datetime import datetime


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
def get_us_city_data(state_fips, city_name):
    # Get 2021 ACS data for population and income
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
    # Using Statistics Canada API (CANSIM tables via their Open Data Portal)
    # We'll fetch the latest population and median income estimates for CMA/CA
    # The API structure is not standardized, so using example pre-aggregated endpoint:
    # To keep it simple, here’s a static example of population & income by city name
    # In production, you’d build a full scraper or dataset parser.
    # For demo: using city_name mapping to dummy data or simple API call simulation

    # Dummy fallback data (replace with real API logic or dataset download)
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

def calculate_population_growth(city_name, state_fips):
    pop_2010 = get_us_population_year(2010, state_fips, city_name)
    pop_2021 = get_us_population_year(2021, state_fips, city_name)
    if pop_2010 and pop_2021 and pop_2010 > 0:
        growth = (pop_2021 - pop_2010) / pop_2010
        return growth
    else:
        return 0  # If no data, assume 0 growth

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

# Sidebar for weights
st.sidebar.header("Adjust Scoring Weights")
weight_population = st.sidebar.slider("Population Weight", 0.0, 5.0, 1.0, 0.1)
weight_growth = st.sidebar.slider("Population Growth Weight", 0.0, 5.0, 1.0, 0.1)
weight_coworking = st.sidebar.slider("Competition (Coworking Spaces) Weight", 0.0, 5.0, 1.0, 0.1)
weight_transit = st.sidebar.slider("Transit Accessibility Weight", 0.0, 5.0, 1.0, 0.1)
weight_price = st.sidebar.slider("Commercial Price Weight", 0.0, 5.0, 1.0, 0.1)

st.title("North America Coworking Space Location Finder")

st.markdown("""
Enter one or more city names (comma separated), e.g. `Austin, TX`, `Toronto, ON`, `New York, NY`.
""")

city_inputs = st.text_area("Enter cities:", "Austin, TX\nToronto, ON\nNew York, NY")

cities = [c.strip() for c in city_inputs.split('\n') if c.strip()]
results = []

map_center = [39.8283, -98.5795]  # Center of USA for initial map

m = folium.Map(location=map_center, zoom_start=4)
markers_group = folium.FeatureGroup(name="Coworking Spaces")
transit_group = folium.FeatureGroup(name="Transit Stops")

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

    # Get population and income
    if state_prov.upper() in us_state_fips:
        fips = us_state_fips[state_prov.upper()]
        pop, income = get_us_city_data(fips, city_name)
        growth = calculate_population_growth(city_name, fips)
    else:
        pop, income = get_canadian_city_data(city_name)
        growth = 0  # Canadian growth not implemented here

    # Coworking spaces count
    coworking_count, coworking_places = get_coworking_osm(lat, lon)
    if coworking_count is None:
        coworking_count = 0
        coworking_places = []

    # Transit stops count
    transit_count = get_transit_stops_osm(lat, lon)
    if transit_count is None:
        transit_count = 0

    # ATTOM commercial price
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

    # Normalize metrics (avoid zero division)
    norm_pop = pop if pop else 1
    norm_growth = growth if growth else 0
    norm_coworking = coworking_count if coworking_count > 0 else 1
    norm_transit = transit_count if transit_count > 0 else 1
    norm_price = avg_price if avg_price and avg_price > 0 else 1_000_000

    # Composite score (higher population, growth, transit positive; more coworking & price negative)
    score = (
        weight_population * norm_pop +
        weight_growth * norm_growth * norm_pop +  # growth weighted by population
        weight_transit * norm_transit -
        weight_coworking * norm_coworking -
        weight_price * norm_price / 1_000_000  # scale price down
    )

    results.append({
        "City": city_input,
        "Population": pop,
        "Population Growth": growth,
        "MedianIncome": income,
        "CoworkingSpaces": coworking_count,
        "TransitStops": transit_count,
        "AvgCommercialPrice": avg_price,
        "Score": score,
        "Latitude": lat,
        "Longitude": lon,
        "CoworkingPlaces": coworking_places
    })

    # Add city marker
    popup_text = (
        f"<b>{city_input}</b><br>"
        f"Population: {pop if pop else 'N/A'}<br>"
        f"Population Growth: {growth:.2%}<br>"
        f"Median Income: ${income if income else 'N/A'}<br>"
        f"Coworking Spaces: {coworking_count}<br>"
        f"Transit Stops: {transit_count}<br>"
        f"Avg Commercial Price: ${avg_price:,.0f}" if avg_price else "N/A"
    )
    folium.Marker([lat, lon], popup=popup_text).add_to(m)

    # Coworking spaces markers (limit 20)
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

    # Transit stops markers - to avoid overload, just mark city center with transit count
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

# Results leaderboard
df_results = pd.DataFrame(results)
df_results_sorted = df_results.sort_values(by="Score", ascending=False)

st.header("City Rankings")

cols = st.columns(8)
headers = ["City", "Population", "Population Growth", "Median Income", "Coworking Spaces", "Transit Stops", "Avg Commercial Price", "Score"]
for col, header in zip(cols, headers):
    col.write(f"**{header}**")

for i, row in df_results_sorted.iterrows():
    c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(8)
    c1.write(row['City'])
    c2.write(f"{row['Population']:,}" if pd.notnull(row['Population']) else "N/A")
    c3.write(f"{row['Population Growth']:.2%}" if pd.notnull(row['Population Growth']) else "N/A")
    c4.write(f"${row['MedianIncome']:,}" if pd.notnull(row['MedianIncome']) else "N/A")
    c5.write(row['CoworkingSpaces'])
    c6.write(row['TransitStops'])
    c7.write(f"${row['AvgCommercialPrice']:,.0f}" if pd.notnull(row['AvgCommercialPrice']) else "N/A")
    c8.write(f"{row['Score']:,.2f}")

st.markdown("""
---
**Notes:**
- Population growth is calculated only for US cities (2010→2021).
- Transit stops data comes from OpenStreetMap around city center.
- Adjust scoring weights in the sidebar to tailor prioritization to company strategy.
- Map shows city locations, coworking spaces (blue), and transit stops (green).
""")
