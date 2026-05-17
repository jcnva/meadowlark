# Meadowlark

## Overview

Meadowlark is a Streamlit-based application designed for single-species study and analysis using observation data from the Macaulay Library. Users can upload CSV files exported from the Macaulay Library Catalog to investigate the distribution, seasonality, recency, and historical activity of an individual species through interactive maps, linked media, checklist exploration, and analytical visualizations.

## Features

1. **Data Upload & Validation**
   - Accepts CSV files exported from Macaulay Library.
   - Multiple files are accepted so long as all files contain data for **only one species**.

2. **Recent Observations Table**
   - Displays the most recent localities with checklists OR all localities with checklists within the last 7 days.
   - Allows selecting a locality to zoom in on the map.

3. **Interactive Map**
   - Uses **Folium** for interactive map visualization.
   - **Color-coded markers and clusters** based on checklist recency:
     - ≤7 days: <span style="color:red">Red</span>
     - 8–30 days: <span style="color:orange">Orange</span>
     - 31–90 days: <span style="color:green">Green</span>
     - \>90 days: <span style="color:blue">Blue</span>

   - **Marker Icons** for comments and media types:

     <img src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/7.x/svgs/solid/compass.svg" width="15" height="15"> Comment with Coordinates

     <img src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/7.x/svgs/solid/comment.svg" width="15" height="15"> Comment

     <img src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/7.x/svgs/solid/camera.svg" width="15" height="15"> Photo

     <img src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/7.x/svgs/solid/video-camera.svg" width="15" height="15"> Video

     <img src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/7.x/svgs/solid/volume-high.svg" width="15" height="15"> Audio   

4. **Analytics Charts**
   - **Observation History:** Shows checklist submissions over time.
   - **Seasonal Activity:** Displays birding activity across the year, combining multiple years.

## How to Prepare an Input File

1. Log into eBird*
2. Visit the Macaulay Library. (http://media.ebird.org or http://search.macaulaylibrary.org)
3. Search for a species
4. Apply any desired filters such as Location, Date, etc. (**Highly recommend** sorting by **Date: Newest First**)
5. Click the 'Export' button at the upper right of the page to download the CSV file
6. Upload to Meadowlark

\* Being logged into eBird allows retrieval of up to 10,000 rows. Otherwise, it is limited to whatever is displayed on the page.

## Demo

https://github.com/user-attachments/assets/8911e950-02de-4867-918e-7dba438cc94e
