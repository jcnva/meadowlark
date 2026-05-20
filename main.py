import streamlit as st
import pandas as pd
import numpy as np
import folium
import altair as alt
import re
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster, Fullscreen
from datetime import datetime

# --- Help Text ---
txt_file = """
Upload your Macaulay Library Catalog File here.

1. Sign into eBird*
2. Visit the Macaulay Library using the above link. (http://media.ebird.org or http://search.macaulaylibrary.org)
3. Search for a species
4. Apply any desired filters such as Location, Date, etc. (Highly recommend sorting by Date: Newest First)
5. Click the 'Export' button at the upper right of the page to download the CSV file.
6. Upload the CSV file here.

\\* Being signed into eBird allows retrieval of up to 10,000 rows. Otherwise, it is limited to ~ 30.
"""

txt_table = """
This table displays all localities sorted by their most recent checklist.
It can be also be sorted by total checklist count.
Selecting the checkbox to the left of a row will zoom into that locality on the map
as well as update the charts to reflect only that locality. Multiple rows can be selected.
"""

txt_chart1 = (
    'Shows how many checklists were submitted over time, letting you track '
    'long-term trends in bird observations.'
)
txt_chart2 = (
    'Shows birding activity by time of year, combining multiple years to '
    'reveal seasonal patterns such as migration or breeding peaks.'
)

# --- Global Regex Patterns ---
DECIMAL_PATTERN = re.compile(
    r"[-+]?\d{1,3}\.\d+[,\s]+[-+]?\d{1,3}\.\d+",
    re.VERBOSE,
)

DMS_PATTERN = re.compile(
    r"\d{1,3}[°º]\s*\d{1,2}['′]?\s*\d{1,2}(?:\.\d+)?[\"″]?\s*[NSEW]",
    re.VERBOSE | re.IGNORECASE,
)

DDM_PATTERN = re.compile(
    r"\d{1,3}[°º]\s*\d{1,2}\.\d+['′]?\s*[NSEW]",
    re.VERBOSE | re.IGNORECASE,
)

UTM_PATTERN = re.compile(
    r"\b(?:[1-9]|[1-5]\d|60)\s*[C-X]\s+\d{6}\s+\d{7}\b",
    re.IGNORECASE,
)

GOOGLE_MAPS_PATTERN = re.compile(
    r"https?://(?:maps\.app\.goo\.gl|(?:\w+\.)?google\.com/maps|maps\.google\.com)",
    re.IGNORECASE,
)

APPLE_MAPS_PATTERN = re.compile(
    r"https?://maps\.apple\.com",
    re.IGNORECASE,
)

PLUS_CODE_PATTERN = re.compile(
    r"\b[23456789CFGHJMPQRVWX]{4,8}\+[23456789CFGHJMPQRVWX]{2,}\b",
    re.IGNORECASE,
)

W3W_PATTERN = re.compile(
    r"(?:/{3}|https?://w3w\.co/)[A-Za-z]+\.[A-Za-z]+\.[A-Za-z]+",
    re.IGNORECASE,
)

def contains_coordinates(text):
    if pd.isna(text):
        return False
    text = str(text)
    return bool(
        DECIMAL_PATTERN.search(text)
        or DMS_PATTERN.search(text)
        or DDM_PATTERN.search(text)
        or UTM_PATTERN.search(text)
        or GOOGLE_MAPS_PATTERN.search(text)
        or APPLE_MAPS_PATTERN.search(text)
        or PLUS_CODE_PATTERN.search(text)
        or W3W_PATTERN.search(text)
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

    def get_format_emojis(formats):
        f_set = set(formats.dropna())
        return (
            ("📷 " if "Photo" in f_set else "") +
            ("📹 " if "Video" in f_set else "") +
            ("🔊 " if "Audio" in f_set else "")
        ).strip()

    # Robust grouping key: Fall back to ML Catalog Number if Checklist ID is NaN
    group_key = df['eBird Checklist ID'].fillna(df['ML Catalog Number'])
    df['Media_Emojis'] = df.groupby(group_key)['Format'].transform(get_format_emojis)
    df_nan = df[df['eBird Checklist ID'].isna()]

    # CRITICAL FIX: Standard drop_duplicates would throw away all but the first NaN row.
    # We separate them, drop duplicates on valid IDs, and combine them back.
    df_nan = df[df['eBird Checklist ID'].isna()]
    df_valid = df[df['eBird Checklist ID'].notna()].drop_duplicates(subset=['eBird Checklist ID'])
    df_unique = pd.concat([df_valid, df_nan], ignore_index=True)
    df_unique = df_unique.sort_values(
            by=['Date_obj', 'Time', 'eBird Checklist ID', 'Average Community Rating'],
            ascending=[True, True, True, False]
    )

    # Vectorize marker categorization
    now = pd.Timestamp.now().normalize()
    days_old = (now - df_unique['Date_obj'].dt.normalize()).dt.days

    conditions = [
        (days_old <= 7),
        (days_old <= 30),
        (days_old <= 90)
    ]

    df_unique['marker_color'] = np.select(conditions, ['red', 'orange', 'green'], default='blue')
    df_unique['cluster_color'] = np.select(conditions, ['#e74c3c', '#f39c12', '#27ae60'], default='#3498db')
    df_unique['priority'] = np.select(conditions, [4, 3, 2], default=1)
    df_unique['Date'] = df_unique['Date_obj'].dt.strftime('%Y-%m-%d')
    
    # Map Checkbox Optimization: Pre-tag rows with their icon_group
    def determine_icon_group(row):
        if pd.notna(row['Observation Details']) and str(row['Observation Details']).strip() != "":
            if contains_coordinates(row['Observation Details']):
                return 'compass'
            return 'comment'
        return 'media_or_blank'

    df_unique['icon_group'] = df_unique.apply(determine_icon_group, axis=1)

    # Cache df_display by moving it inside load_data
    df_display = (
        df_unique
        .groupby('Locality', as_index=False)
        .agg(
            Checklists=('eBird Checklist ID', 'nunique'),
            Newest_Checklist=('Date_obj', 'max')
        )
        .sort_values(by='Newest_Checklist', ascending=False)
        .reset_index(drop=True)
    )

    if not df_display.empty:
        df_display['Date'] = df_display['Newest_Checklist'].dt.strftime('%Y-%m-%d')

    return df, df_unique, df_display


# --- Sidebar Setup ---
with st.sidebar:
    st.title("Meadowlark")
    st.link_button("🔎︎ Macaulay Library", "https://search.macaulaylibrary.org/catalog?sort=obs_date_desc")
    uploaded_files = st.file_uploader("Upload your ML Catalog CSV file", type=["csv"], help=txt_file, accept_multiple_files=True)

if uploaded_files:
    try:
        df_full, df_unique, df_display = load_data(uploaded_files)
        now = pd.Timestamp.now().normalize()

        # Define hierarchy options and weight map for "up-only" comparison
        recency_options = ["Past 7 Days", "Past 30 Days", "Past 90 Days", "All Time"]
        recency_weights = {opt: i for i, opt in enumerate(recency_options)}
        
        # Helper to convert days old to slider category
        def get_recency_category(days):
            if days <= 7: return "Past 7 Days"
            if days <= 30: return "Past 30 Days"
            if days <= 90: return "Past 90 Days"
            return "All Time"

        # --- 2. Calculate Table Data & Handle Global Reset ---
        current_file_signature = tuple(sorted(f.name for f in uploaded_files))
        
        if "uploaded_signature" not in st.session_state or st.session_state.uploaded_signature != current_file_signature:
            st.session_state.uploaded_signature = current_file_signature
            st.session_state.prev_selection = []
            if "loc_table" in st.session_state:
                del st.session_state["loc_table"]

            # Initialize map recency from newest observation in whole dataset
            newest_global = df_unique['Date_obj'].max()
            global_days_old = (now - newest_global.normalize()).days
            st.session_state.map_recency = get_recency_category(global_days_old)

        # --- 3. Read Selection State (Before rendering UI) ---
        current_selection = []
        if "loc_table" in st.session_state:
            current_selection = st.session_state.loc_table.get("selection", {}).get("rows", [])

        if "prev_selection" not in st.session_state:
            st.session_state.prev_selection = []

        selection_changed = current_selection != st.session_state.prev_selection
        st.session_state.prev_selection = current_selection

        selected_localities = []
        if current_selection:
            selected_localities = df_display.iloc[current_selection]["Locality"].tolist()

        if selected_localities:
            df_filtered = df_unique[df_unique["Locality"].isin(selected_localities)]

            # If the selection changed, conditionally expand the slider window UP
            if selection_changed:
                # Find the oldest date among the currently selected table rows
                oldest_selected_date = df_display.iloc[current_selection]['Newest_Checklist'].min()
                days_old = (now - oldest_selected_date.normalize()).days
                required_recency = get_recency_category(days_old)
                current_recency = st.session_state.get("map_recency", "Past 7 Days")
                
                # Only adjust the target index up, never down.
                if recency_weights[required_recency] > recency_weights[current_recency]:
                    st.session_state.map_recency = required_recency

        else:
            df_filtered = df_unique

    except ValueError as e:
        st.error(str(e))
        st.stop()

    # --- 4. Render Metrics ---
    st.sidebar.metric("Total Media Assets", len(df_full))
    st.sidebar.metric("Unique Checklists", len(df_unique))

# --- 5. Main Content Area ---
    st.header(df_full['Common Name'].iloc[0], anchor=False)

    map_col, list_col = st.columns([1, 1])
    with list_col:
        st.subheader("Activity by Location", help=txt_table, anchor=False)

        if not df_display.empty:
            
            df_display['Days_Old'] = (now - df_display['Newest_Checklist'].dt.normalize()).dt.days
            
            def style_table(df):
                colors = np.select(
                    [df_display['Days_Old'] <= 7, df_display['Days_Old'] <= 30, df_display['Days_Old'] <= 90],
                    ['background-color: #e74c3c99', 'background-color: #f39c1299', 'background-color: #27ae6099'],
                    default='background-color: #3498db99'
                )
                return pd.DataFrame([[c]*len(df.columns) for c in colors], index=df.index, columns=df.columns)

            styled_df = (
                df_display[['Date', 'Checklists', 'Locality']]
                .style.apply(style_table, axis=None)
            )

            st.dataframe(
                styled_df,
                hide_index=True,
                height=555,
                selection_mode="multi-row",
                on_select="rerun",
                key="loc_table",
                column_config={
                    "Date": st.column_config.Column(
                        "Date",
                        width="small",
                        required=True
                    ),
                    "Checklists": st.column_config.Column(
                        "Checklists",
                        width="small",
                        required=True
                    ),
                    "Locality": st.column_config.Column(
                        "Locality", 
                        width="large"
                    )
                },
                width='stretch'
            )
        else:
            st.warning("No checklists to display for the selected data.")

    # --- Analytics Charts ---
    chart_col1, chart_col2 = st.columns(2)

    with chart_col2:
        st.subheader("Observation History", help=txt_chart1, anchor=False)

        timeline_data = (
            df_filtered.groupby(df_unique['Date_obj'].dt.date)['eBird Checklist ID']
            .nunique()
            .reset_index()
        )
        timeline_data.columns = ['Date', 'Checklists']

        min_year = timeline_data['Date'].min().year
        max_year = timeline_data['Date'].max().year

        if min_year == max_year:
            year_title = f"Year ({min_year})"
        else:
            year_title = f"Years ({min_year}–{max_year})"

        history_chart = alt.Chart(timeline_data).mark_bar(color="#2E86C1").encode(
            x=alt.X(
                "Date:T",
                axis=alt.Axis(
                    format="%Y",
                    tickCount="year",
                    grid=True,
                    gridColor="#E5E8E8",
                    labelAngle=0,
                    title=year_title,
                ),
            ),
            y=alt.Y('Checklists:Q', title='Checklists', axis=alt.Axis(format='d')),
            tooltip=['Date:T', 'Checklists:Q']
        ).properties(height=250).interactive(bind_y=False)

        st.altair_chart(history_chart, width='stretch')

    with chart_col1:
        st.subheader("Seasonal Activity", help=txt_chart2, anchor=False)

        def map_to_seasonal_calendar(dt):
            return dt.replace(year=2000)

        df_filtered['Seasonal_Date'] = df_unique['Date_obj'].apply(map_to_seasonal_calendar)
        counts = df_filtered.groupby('Seasonal_Date')['eBird Checklist ID'].nunique()
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
        
        # Initialize session state for the unified multi-select pill group
        if "map_filters_pill" not in st.session_state:
            st.session_state.map_filters_pill = []

        # Read active states directly out of the list
        show_compass = "🧭" in st.session_state.map_filters_pill
        show_comments = "💬" in st.session_state.map_filters_pill

        # Pill Slider Auto-Expand Logic
        prev_filters = st.session_state.get("prev_map_filters_pill", [])
        compass_toggled_on = show_compass and ("🧭" not in prev_filters)
        comments_toggled_on = show_comments and ("💬" not in prev_filters)
        
        cb_subset = None
        if compass_toggled_on:
            cb_subset = df_filtered[df_filtered['icon_group'] == 'compass']
        elif comments_toggled_on:
            cb_subset = df_filtered[df_filtered['icon_group'].isin(['comment', 'compass'])]
            
        if cb_subset is not None and not cb_subset.empty:
            newest_cb_date = cb_subset['Date_obj'].max()
            days_old_cb = (now - newest_cb_date.normalize()).days
            required_recency_cb = get_recency_category(days_old_cb)
            
            current_recency = st.session_state.get("map_recency", "Past 7 Days")
            if recency_weights[required_recency_cb] > recency_weights[current_recency]:
                st.session_state.map_recency = required_recency_cb

        # Keep state updated for the next rerun comparison
        st.session_state.prev_map_filters_pill = st.session_state.map_filters_pill

        # --- Map Controls ---
        ctrl_col1, ctrl_col2 = st.columns([5, 2], vertical_alignment="bottom")
        
        with ctrl_col1:
            st.select_slider(
                "Show Checklists by Recency",
                options=recency_options,
                key="map_recency",
                label_visibility="collapsed",
                help="Filter the locations shown on the map based on the checklist recency"
            )
            
        with ctrl_col2:
            st.pills(
                "Filters",
                options=["💬", "🧭"],
                selection_mode="multi",
                key="map_filters_pill",
                label_visibility="collapsed",
                help="💬: Show only checklists with comments | 🧭: Show only checklists with coordinates in comments "
            )

        # A. Apply Slider Filter for Map bounds
        if st.session_state.map_recency == "Past 7 Days":
            df_map = df_filtered[df_filtered['Date_obj'] >= (now - pd.Timedelta(days=7))].copy()
        elif st.session_state.map_recency == "Past 30 Days":
            df_map = df_filtered[df_filtered['Date_obj'] >= (now - pd.Timedelta(days=30))].copy()
        elif st.session_state.map_recency == "Past 90 Days":
            df_map = df_filtered[df_filtered['Date_obj'] >= (now - pd.Timedelta(days=90))].copy()
        else:
            df_map = df_filtered.copy()
            
        # B. Robust Cascading Content Type Filters
        if not df_map.empty:
            if "🧭" in st.session_state.map_filters_pill:
                # Top priority: If compass is active, filter strictly to compass rows.
                # Deselecting 'comments' keeps this condition true, so the map won't alter or reset.
                df_map = df_map[df_map['icon_group'] == 'compass']
            elif "💬" in st.session_state.map_filters_pill:
                # Lower priority: Only comments is active, show both comments and compass rows.
                df_map = df_map[df_map['icon_group'].isin(['comment', 'compass'])]
            # Default: If nothing is selected, df_map passes through unchanged (displays all rows).
            
        def render_map(data):

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

            clean_df = data.rename(columns=lambda x: x.replace(' ', '_'))
            
            for row in clean_df.itertuples():
                catalog_id = getattr(row, 'ML_Catalog_Number', '')
                format_type = getattr(row, 'Format', '')
                
                popup_media_html = ""
                tooltip_media_html = ""
                
                time_str = str(int(float(row.Time))).zfill(4)
                formatted_time = f"{time_str[:-2]}:{time_str[-2:]}"

                if pd.notna(catalog_id) and str(catalog_id).strip():
                    thumbnail_url = f"https://cdn.download.ams.birds.cornell.edu/api/v2/asset/{catalog_id}"
                    
                    if format_type == "Photo":
                        popup_media_html = f"<img src='{thumbnail_url}/160' style='width: 160px; border-radius: 8px; margin-bottom: 8px;' ><br>"
                        tooltip_media_html = popup_media_html
                        
                    elif format_type == "Audio":
                        popup_media_html = f"<audio controls style='width: 160px; height: 32px; margin-bottom: 8px;'><source src='{thumbnail_url}/mp3'>Your browser does not support audio.</audio><br>"
                    elif format_type == "Video":
                        popup_media_html = f"<video controls poster='{thumbnail_url}/mp4/1280' style='width: 160px; border-radius: 8px; margin-bottom: 8px;'><source src='{thumbnail_url}/mp4/1280'>Your browser does not support video.</video><br>"
                        tooltip_media_html = f"<img src='{thumbnail_url}/160' style='width: 160px; border-radius: 8px; margin-bottom: 8px;' ><br>"

                if pd.notna(row.eBird_Checklist_ID):
                    cl_url = f"https://ebird.org/checklist/{row.eBird_Checklist_ID}"
                    cl_txt = row.eBird_Checklist_ID
                else:
                    cl_url = f"https://macaulaylibrary.org/asset/{row.ML_Catalog_Number}"
                    cl_txt = f"ML{row.ML_Catalog_Number}"

                observation_details = ""

                if pd.notna(row.Observation_Details):
                    observation_details = f"""
                    <b>Observation Details:</b>
                    {row.Observation_Details}<br>
                    """
                    
                if row.icon_group == 'compass':
                    icon = 'compass'
                elif row.icon_group == 'comment':
                    icon = 'comment'
                elif format_type == 'Photo':
                    icon = 'camera'
                elif format_type == 'Video':
                    icon = 'video-camera'
                elif format_type == 'Audio':
                    icon = 'volume-high'
                else:
                    icon = ''
                    
                popup_html = f"""
                <div style="font-family: sans-serif; font-size: 12px;">
                    {popup_media_html}
                    <b style="font-size: 14px;">{row.Common_Name}</b><br>
                    <b>Locality:</b> {row.Locality}<br>
                    <b>Date:</b> {row.Date}<br>
                    <b>Time:</b> {formatted_time}<br>
                    {observation_details}
                    {row.Media_Emojis}<br>
                    <a href="{cl_url}" target="_blank" style="color: #2E86C1; font-weight: bold;">
                        {cl_txt}
                    </a>
                </div>
                """
                
                tooltip_html = f"""
                <div style="font-family: sans-serif; font-size: 12px; width: 160px; white-space: normal">
                    {tooltip_media_html}
                    <b style="font-size: 14px;">{row.Common_Name}</b><br>
                    <b>Locality:</b> {row.Locality}<br>
                    <b>Date:</b> {row.Date}<br>
                    <b>Time:</b> {formatted_time}<br>
                    {row.Media_Emojis}
                </div>
                """

                folium.Marker(
                    location=[row.Latitude, row.Longitude],
                    popup=folium.Popup(popup_html, max_width=160),
                    tooltip=tooltip_html,
                    icon=folium.Icon(color=row.marker_color, icon=icon, prefix="fa"),
                    priority=row.priority,
                    markerColor=row.cluster_color
                ).add_to(marker_cluster)

            return m

        # Map Legend
        legend_html = """
        <div style="display:flex; gap:15px; margin-bottom:10px;">
        🔴 ≤7 days
        🟠 8–30 days
        🟢 31–90 days
        🔵 >90 days
        </div>
        """
        st.markdown(legend_html, unsafe_allow_html=True)

        with st.spinner("Rendering map..."):
            st_folium(
                render_map(df_map), 
                width="100%",
                height=525,
                key="bird_map_v14",
                returned_objects=[]
            )

else:
    st.sidebar.info("Waiting for CSV file upload...")
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.image("meadowlark.png")
