import streamlit as st
import pandas as pd
import folium
import altair as alt
import re
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster, Fullscreen
from datetime import datetime

# --- Help Text ---
txt_file = """
Upload your Macaulay Library Catalog File here.

1. Log into eBird*
2. Visit the Macaulay Library using the above link. (http://media.ebird.org or http://search.macaulaylibrary.org)
3. Search for a species
4. Apply any desired filters such as Location, Date, etc. (Highly recommend sorting by Date: Newest First)
5. Click the 'Export' button at the upper right of the page to download the CSV file.
6. Upload the CSV file here.

\\* Being logged into eBird allows retrieval of up to 10,000 rows. Otherwise, it is limited to whatever is displayed on the page.
"""

txt_table = """
This table displays the greater of EITHER:

a) All localities with a checklist within the past 7 days, OR
b) The most recent 14 localities with a checklist

To zoom into a specific locality on the map, select the checkbox to the left of it.
"""

txt_chart1 = (
    'Shows how many checklists were submitted over time, letting you track '
    'long-term trends in bird observations.'
)
txt_chart2 = (
    'Shows birding activity by time of year, combining multiple years to '
    'reveal seasonal patterns such as migration or breeding peaks.'
)


# --- Marker Recency ---
def get_marker_recency(checklist_date):
    days_old = (pd.Timestamp.now().normalize() - checklist_date.normalize()).days
    if days_old <= 7:
        return {"marker_color": "red", "cluster_color": "#e74c3c", "priority": 4}
    elif days_old <= 30:
        return {"marker_color": "orange", "cluster_color": "#f39c12", "priority": 3}
    elif days_old <= 90:
        return {"marker_color": "green", "cluster_color": "#27ae60", "priority": 2}
    else:
        return {"marker_color": "blue", "cluster_color": "#3498db", "priority": 1}

# --- Function for detecting coordinate strings ---
def contains_coordinates(text):

    if pd.isna(text):
        return False

    text = str(text)

    # Decimal degrees
    decimal_pattern = re.compile(
        r"""
        [-+]?\d{1,3}\.\d+
        [,\s]+
        [-+]?\d{1,3}\.\d+
        """,
        re.VERBOSE,
    )

    # Degrees / minutes / seconds
    dms_pattern = re.compile(
        r"""
        \d{1,3}[°º]
        \s*\d{1,2}['′]?
        \s*\d{1,2}(?:\.\d+)?["″]?
        \s*[NSEW]
        """,
        re.VERBOSE | re.IGNORECASE,
    )

    return bool(
        decimal_pattern.search(text)
        or dms_pattern.search(text)
    )

# --- Page Config ---
st.set_page_config(
    page_title="Meadowlark",
    page_icon="meadowlark.png",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'about': '**v1.0.0**\n\nhttps://github.com/jcnva/meadowlark\n\nCopyright © 2026 Jonathan Casanova'
    }
)
st.logo(image='meadowlark.png', size='large')


# --- 1. Data Loading & Cleaning ---
@st.cache_data
def load_data(files):
    dataframes = []

    for file in files:
        df = pd.read_csv(
            file,
            dtype={
                'ML Catalog Number': str,
                'Format': str,
                'Common Name': str,
                'Latitude': float,
                'Longitude': float,
                'eBird Checklist ID': str,
                'Observation Details': str,
            },
            parse_dates=['Date']
        )
        dataframes.append(df)

    df = pd.concat(dataframes, ignore_index=True)

    # Normalize species names by removing subspecies names in parentheses
    normalized_species = (
        df['Common Name']
        .str.replace(r'\s*\(.*?\)', '', regex=True)
        .str.strip()
    )

    # Ensure only one species is present
    species = normalized_species.unique()
    if len(species) > 1:
        raise ValueError(f"Uploaded CSV contains multiple species: {species}")

    # Remove rows without coordinates
    df = df[df['Latitude'].notna() & df['Longitude'].notna()]

    # Convert Date column to datetime
    df['Date_obj'] = df['Date']

    # Sanitize backticks to prevent JavaScript crashes
    df['Locality'] = df['Locality'].str.replace('`', "'")
    df['Observation Details'] = df['Observation Details'].str.replace('`', "'")

    # Remove duplicate catalog assets across files
    df = df.drop_duplicates(subset=["ML Catalog Number"])

    # Extract unique checklists
    df_unique = (
        df
        .sort_values(
            by=['Date_obj', 'Time', 'eBird Checklist ID', 'Average Community Rating'],
            ascending=[True, True, True, False]
        )
        .drop_duplicates(subset=['eBird Checklist ID'])
    )

    # Precompute marker info without storing dicts
    recency_info = df_unique['Date_obj'].apply(get_marker_recency)

    df_unique['marker_color'] = recency_info.apply(lambda x: x['marker_color'])
    df_unique['cluster_color'] = recency_info.apply(lambda x: x['cluster_color'])
    df_unique['priority'] = recency_info.apply(lambda x: x['priority'])
    df_unique['Date'] = df_unique['Date_obj'].dt.strftime('%Y-%m-%d')

    return df, df_unique


# --- Sidebar ---
with st.sidebar:
    st.title("Meadowlark")
    st.link_button("Open Macaulay Library", "https://search.macaulaylibrary.org")
    uploaded_files = st.file_uploader("Upload your ML Catalog CSV file", type=["csv"], help=txt_file,accept_multiple_files=True)

if uploaded_files:
    try:
        df_full, df_unique = load_data(uploaded_files)
    except ValueError as e:
        st.error(str(e))
        st.stop()

    # Metrics
    st.sidebar.metric("Total Media Assets", len(df_full))
    st.sidebar.metric("Unique Checklists", len(df_unique))
    st.header(df_full['Common Name'].iloc[0], anchor=False)

    # --- Recent Observations ---
    list_col, map_col = st.columns([1, 1])
    with list_col:
        st.subheader("Recent Activity by Location", help=txt_table, anchor=False)

        now = pd.Timestamp.now().normalize()

        df_recent = (
            df_unique
            .groupby('Locality', as_index=False)
            .agg(
                Checklists=('eBird Checklist ID', 'nunique'),
                Newest_Checklist=('Date_obj', 'max')
            )
            .sort_values(by='Newest_Checklist', ascending=False)
            .head(14)
        )

        df_week = (
            df_unique[df_unique['Date_obj'] >= (now - pd.Timedelta(days=7))]
            .groupby('Locality', as_index=False)
            .agg(
                Checklists=('eBird Checklist ID', 'nunique'),
                Newest_Checklist=('Date_obj', 'max')
            )
            .sort_values(by='Newest_Checklist', ascending=False)
        )

        df_display = df_week if len(df_week) > len(df_recent) else df_recent

        if not df_display.empty:
            df_display['Date'] = df_display['Newest_Checklist'].dt.strftime('%Y-%m-%d')
        else:
            st.warning("No checklists to display for the selected data.")

        table_event = st.dataframe(
            df_display[['Date', 'Locality', 'Checklists']],
            hide_index=True,
            height=527,
            selection_mode="single-row",
            on_select="rerun"
        )

        selected_locality = None
        if table_event.selection.rows:
            selected_idx = table_event.selection.rows[0]
            selected_locality = df_display.iloc[selected_idx]['Locality']

    # --- Analytics Charts ---
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.subheader("Observation History", help=txt_chart1, anchor=False)

        timeline_data = (
            df_unique.groupby(df_unique['Date_obj'].dt.date)['eBird Checklist ID']
            .nunique()
            .reset_index()
        )
        timeline_data.columns = ['Date', 'Checklists']

        history_chart = alt.Chart(timeline_data).mark_bar(color="#2E86C1").encode(
            x=alt.X('Date:T', title=None),
            y=alt.Y('Checklists:Q', title='Checklists', axis=alt.Axis(format='d')),
            tooltip=['Date:T', 'Checklists:Q']
        ).properties(height=250).interactive(bind_y=False)
        st.altair_chart(history_chart, width='stretch')

    with chart_col2:
        st.subheader("Seasonal Activity", help=txt_chart2, anchor=False)

        # Map dates to a fixed year to show seasonal patterns
        def map_to_seasonal_calendar(dt):
            return dt.replace(year=2000)

        df_unique['Seasonal_Date'] = df_unique['Date_obj'].apply(map_to_seasonal_calendar)
        counts = df_unique.groupby('Seasonal_Date')['eBird Checklist ID'].nunique()
        calendar_index = pd.date_range(start="2000-01-01", end="2000-12-31")
        seasonal_series = counts.reindex(calendar_index, fill_value=0)
        seasonal_df = pd.DataFrame({"Date": seasonal_series.index, "Checklists": seasonal_series.values})

        seasonal_chart = alt.Chart(seasonal_df).mark_bar(
            color="#28B463",
        ).encode(
            x=alt.X(
                'Date:T',
                axis=alt.Axis(
                    format='%b',
                    tickCount='month',
                    grid=True,
                    gridColor='#E5E8E8',
                    labelAngle=0,
                    title='Annual Cycle (January – December)'
                ),
                scale=alt.Scale(domain=[calendar_index.min(), calendar_index.max()], nice=False)
            ),
            y=alt.Y('Checklists:Q', title='Checklists', axis=alt.Axis(format='d')),
            tooltip=[
                alt.Tooltip('Date:T', format='%B %d', title='Date'),
                alt.Tooltip('Checklists:Q', title='Checklists')
            ]
        ).properties(height=250).interactive(bind_y=False)

        st.altair_chart(seasonal_chart, width='stretch')

    # --- Map ---
    with map_col:
        def render_map(data, selected_locality=None):
            if selected_locality:
                data = data[data['Locality'] == selected_locality]

            m = folium.Map()

            Fullscreen().add_to(m)

            icon_create_function = """
            function(cluster) {
                var markers = cluster.getAllChildMarkers();
                var highestPriority = 0;
                var clusterColor = 'blue';

                markers.forEach(function(marker) {
                    var priority = marker.options.priority || 1;
                    var color = marker.options.markerColor || 'blue';
                    if (priority > highestPriority) {
                        highestPriority = priority;
                        clusterColor = color;
                    }
                });

                return L.divIcon({
                    html: `<div style="
                        background-color:${clusterColor};
                        width:40px;
                        height:40px;
                        border-radius:50%;
                        display:flex;
                        align-items:center;
                        justify-content:center;
                        color:white;
                        font-weight:bold;
                        box-shadow:0 0 6px rgba(0,0,0,0.35);
                        ">${cluster.getChildCount()}</div>`,
                    className: 'marker-cluster-custom',
                    iconSize: [40, 40]
                });
            }
            """

            marker_cluster = MarkerCluster(icon_create_function=icon_create_function).add_to(m)
            folium.FitOverlays().add_to(m)

            for _, row in data.iterrows():
                # Only generate thumbnail if Format is Photo
                if row.get('Format') == "Photo":
                    catalog_id = row['ML Catalog Number']
                    thumbnail_url = f"https://cdn.download.ams.birds.cornell.edu/api/v2/asset/{catalog_id}/160"
                else:
                    thumbnail_url = None

                checklist_url = f"https://ebird.org/checklist/{row['eBird Checklist ID']}"
                observation_details = ""

                if pd.notna(row['Observation Details']):
                    observation_details = f"""
                    <b>Observation Details:</b>
                    {row['Observation Details']}<br>
                    """
                    if contains_coordinates(
                        row['Observation Details']
                    ):
                        icon = 'compass'
                    else:
                        icon = 'comment'
                elif row['Format'] == 'Photo':
                    icon = 'camera'
                elif row['Format'] == 'Video':
                    icon = 'video-camera'
                elif row['Format'] == 'Audio':
                    icon = 'volume-high'
                else:
                    icon = ''
                popup_html = f"""
                <div style="font-family: sans-serif; font-size: 12px;">
                    {"<img src='" + thumbnail_url + "' style='width: 160px; border-radius: 8px; margin-bottom: 8px;' ><br>" if thumbnail_url else ""}
                    <b style="font-size: 14px;">{row['Common Name']}</b><br>
                    <b>Locality:</b> {row['Locality']}<br>
                    <b>Date:</b> {row['Date']}<br>
                    {observation_details}
                    <a href="{checklist_url}" target="_blank" style="color: #2E86C1; font-weight: bold;">
                        {row['eBird Checklist ID']}
                    </a>
                </div>
                """
                tooltip_html = f"""
                <div style="font-family: sans-serif; font-size: 12px; width: 160px; white-space: normal">
                    {"<img src='" + thumbnail_url + "' style='width: 160px; border-radius: 8px; margin-bottom: 8px;' ><br>" if thumbnail_url else ""}
                    <b style="font-size: 14px;">{row['Common Name']}</b><br>
                    <b>Locality:</b> {row['Locality']}<br>
                    <b>Date:</b> {row['Date']}<br>
                </div>
                """

                folium.Marker(
                    location=[row['Latitude'], row['Longitude']],
                    popup=folium.Popup(popup_html, max_width=160),
                    tooltip=tooltip_html,
                    icon=folium.Icon(color=row['marker_color'], icon=icon, prefix="fa"),
                    priority=row['priority'],
                    markerColor=row['cluster_color']
                ).add_to(marker_cluster)

            return m

        # --- Map Legend ---
        legend_html = """
        <div style="display:flex; gap:15px; margin-bottom:10px;">
            <div style="background-color:#e74c3c; width:20px; height:20px; display:inline-block;"></div> ≤ 7 days
            <div style="background-color:#f39c12; width:20px; height:20px; display:inline-block;"></div> 8–30 days
            <div style="background-color:#27ae60; width:20px; height:20px; display:inline-block;"></div> 31–90 days
            <div style="background-color:#3498db; width:20px; height:20px; display:inline-block;"></div> > 90 days
        </div>
        """

        st.markdown(legend_html, unsafe_allow_html=True)

        # Render the map
        with st.spinner("Rendering map..."):
            st_folium(
                render_map(df_unique, selected_locality),
                width="100%",
                height=550,
                key="bird_map_v14",
                returned_objects=[]
            )

else:
    st.sidebar.info("Waiting for CSV file upload...")
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.image("meadowlark.png")
