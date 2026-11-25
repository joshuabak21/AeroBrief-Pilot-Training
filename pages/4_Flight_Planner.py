"""Educational route, performance and weather comparison page."""
import math
import altair as alt
import pandas as pd
import requests
import streamlit as st
from aviation_data import AIRPORTS, get_forecast, extract_forecast, wind_components
from site_theme import apply_theme, safety_note

st.set_page_config(page_title='AeroBrief | Flight Planner', page_icon='✈️', layout='wide')
apply_theme()
st.title('Flight Planning & Performance')
st.write('Explore direct airport routes, cruise estimates and forecast conditions for training.')
safety_note()

@st.cache_data(ttl=900)
def load_weather(lat, lon):
    return get_forecast(lat, lon)

def distance_nm(a, b):
    lat1, lat2 = math.radians(a['lat']), math.radians(b['lat'])
    dlat = lat2 - lat1
    dlon = math.radians(b['lon'] - a['lon'])
    h = math.sin(dlat / 2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon / 2)**2
    return 3440.065 * 2 * math.asin(math.sqrt(min(1, max(0, h))))

st.subheader('01 / Route planning')
left, right = st.columns(2)
with left:
    departure = st.selectbox('Departure airport', list(AIRPORTS))
with right:
    arrival = st.selectbox('Destination airport', list(AIRPORTS), index=len(AIRPORTS)-1)
a, b = AIRPORTS[departure], AIRPORTS[arrival]
if departure == arrival:
    st.warning('Choose different airports to explore a route.')
else:
    import pydeck as pdk
    route = [[a['lon'], a['lat']], [b['lon'], b['lat']]]
    points = [{'name': departure, 'position': route[0]}, {'name': arrival, 'position': route[1]}]
    st.pydeck_chart(pdk.Deck(layers=[
        pdk.Layer('GreatCircleLayer', [{'source': route[0], 'target': route[1]}], get_source_position='source', get_target_position='target', get_source_color=[98,213,212], get_target_color=[98,213,212], get_width=4),
        pdk.Layer('ScatterplotLayer', points, get_position='position', get_fill_color=[98,213,212], get_radius=18000, pickable=True),
        pdk.Layer('TextLayer', points, get_position='position', get_text='name', get_size=13, get_color=[230,240,250], get_pixel_offset=[0,-20])],
        initial_view_state=pdk.ViewState(latitude=(a['lat']+b['lat'])/2, longitude=(a['lon']+b['lon'])/2, zoom=3.3), tooltip={'text':'{name}'}))
    st.caption('Direct great-circle illustration, not an operational route.')
    st.subheader('02 / Cruise performance')
    c1, c2 = st.columns(2)
    with c1:
        speed = st.slider('Assumed groundspeed (kt)', 60, 300, 120, 5)
    with c2:
        fuel = st.slider('Cruise fuel burn (US gal/hour)', 4.0, 30.0, 9.0, 0.5)
    distance = distance_nm(a,b)
    duration = distance/speed
    minutes = round(duration*60)
    c1,c2,c3 = st.columns(3)
    c1.metric('Direct distance', f'{distance:.1f} NM')
    c2.metric('Cruise time', f'{minutes//60}h {minutes%60}m')
    c3.metric('Cruise fuel', f'{duration*fuel:.1f} gal')
    st.caption('Excludes reserves, taxi, climb, descent, routing and changes in groundspeed.')
    st.subheader('03 / Airport weather comparison')
    hours = st.slider('Forecast hours at each airport', 6, 48, 24, 6)
    frames = []
    for label, place in [(departure,a),(arrival,b)]:
        try:
            payload = load_weather(place['lat'],place['lon'])
            rows = extract_forecast(payload, hours=hours)
            frame = pd.DataFrame(rows)
            frame['Airport'] = label
            frame['Forecast hour'] = range(len(frame))
            frames.append(frame)
            st.caption(f"{label}: forecast starts {rows[0]['Local time']} ({payload.get('timezone','local time')})")
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            st.warning(f'Forecast unavailable for {label}.')
    if frames:
        data = pd.concat(frames, ignore_index=True)
        for field in ['Wind (kt)', 'Visibility (sm)', 'Rain chance (%)']:
            chart = alt.Chart(data).mark_line(point=True).encode(x=alt.X('Forecast hour:Q', title='Hours from first forecast'), y=alt.Y(field+':Q'), color='Airport:N', tooltip=['Airport:N','Local time:T',field+':Q']).properties(height=220)
            st.altair_chart(chart, use_container_width=True)
        st.caption('Hours are relative to each airport’s first available forecast, not necessarily identical UTC timestamps or estimated arrival conditions.')
        st.subheader('04 / Personal weather limits')
        c1,c2 = st.columns(2)
        with c1:
            max_wind = st.slider('Maximum surface wind (kt)', 5, 40, 15)
        with c2:
            min_vis = st.slider('Minimum visibility (sm)', 1, 10, 5)
        def compare(row):
            if pd.isna(row['Wind (kt)']) or pd.isna(row['Visibility (sm)']):
                return 'Missing data'
            return 'Within selected limits' if row['Wind (kt)'] <= max_wind and row['Visibility (sm)'] >= min_vis else 'Outside selected limits'
        data['Comparison'] = data.apply(compare, axis=1)
        st.dataframe(data[['Airport','Local time','Wind (kt)','Visibility (sm)','Comparison']], hide_index=True, use_container_width=True)
        st.caption('Only compares two user-selected criteria; does not assess flight safety or legality.')

st.subheader('05 / Runway wind simulator')
c1,c2,c3 = st.columns(3)
with c1:
    heading = st.slider('Runway true heading (°)',0,359,90)
with c2:
    direction = st.slider('Wind from true direction (°)',0,359,130)
with c3:
    wind = st.slider('Simulated wind speed (kt)',0,40,20)
head, cross = wind_components(wind,direction,heading)
c1,c2 = st.columns(2)
c1.metric('Headwind' if head >= 0 else 'Tailwind', f'{abs(head):.1f} kt')
c2.metric('Crosswind magnitude', f'{cross:.1f} kt')
# A compass diagram: runway rotates with heading; arrow points inward from wind source.
st.markdown(f'''<svg viewBox="0 0 320 250" width="100%" style="max-width:420px;display:block;margin:auto" xmlns="http://www.w3.org/2000/svg">
<circle cx="160" cy="125" r="98" fill="none" stroke="#658399" stroke-dasharray="4 5"/>
<g fill="#b5c7d7" font-size="13" text-anchor="middle"><text x="160" y="18">N</text><text x="275" y="130">E</text><text x="160" y="241">S</text><text x="45" y="130">W</text></g>
<g transform="translate(160 125) rotate({heading})"><rect x="-17" y="-80" width="34" height="160" rx="3" fill="#475569"/><line x1="0" y1="-74" x2="0" y2="74" stroke="white" stroke-dasharray="9 7"/><path d="M0 -35 L-8 -20 L8 -20 Z" fill="white"/></g>
<g transform="translate(160 125) rotate({direction})" stroke="#62d5d4" stroke-width="4" fill="none"><path d="M0 -95 L0 -12 M-8 -25 L0 -12 L8 -25"/></g></svg>''', unsafe_allow_html=True)
st.caption('Arrow shows wind flowing from its source toward the runway. Both angles use true north.')
