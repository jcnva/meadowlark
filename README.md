# Meadowlark

## Overview

Meadowlark is an interactive media mapper to help you find your next target species using observation data from the Macaulay Library. It parses high-quality checklists with media and comments, and presents recency and location data in a more accessible way than a regular eBird search. Use it to quickly find answers to questions like:

"Where has this bird been photographed most recently and reliably?"

"Is it worth chasing for photos, or is a scope required?"

"What time of year should I go?"

and

"Just give me the coordinates!"

## Features

1. **Data Upload & Validation**
   - Accepts CSV files exported from Macaulay Library.
   - Multiple files are accepted as long as all files contain data for **only one species**.

2. **Interactive Map**
   - **Color-coded markers and clusters** based on checklist recency:
     - 🔴 ≤7 days
     - 🟠 8–30 days
     - 🟢 31–90 days
     - 🔵 \>90 days
   - **Marker Icons** for highlighting comments and media types:
     - 🧭 Comment with Coordinates
     - 💬 Comment
     - 📷 Photo
     - 📹 Video
     - 🔊 Audio
   - **Tooltips and Popups**
     - Instantly view checklist details with a mouse hover or click. 
   - **Marker Filters**
     - Filter the locations shown on the map based on the checklist recency.
     - Filter by media type: Photo 📷, Video 📹, or Audio 🔊.
     - Show only checklists with Comments 💬, or Comments with Coordinates 🧭. 

3. **Activity by Location Table**
   - Displays localities sorted by most recent checklist. Can also be sorted by Checklist count.
   - Select a row or multiple rows to zoom in on the map.

4. **Analytics Charts**
   - **Observation History:** Shows checklist submissions over time.
   - **Seasonal Activity:** Displays birding activity across the year, combining multiple years.

## How to Prepare an Input File

1. Sign into eBird*
2. Visit the Macaulay Library. (http://media.ebird.org or http://search.macaulaylibrary.org)
3. Search for a species
4. Apply any desired filters such as Location, Date, etc. (**Highly recommend** sorting by **Date: Newest First**)
5. Click the 'Export' button at the upper right of the page to download the CSV file
6. Upload to Meadowlark

\* Being signed into eBird allows retrieval of up to 10,000 rows. Otherwise, it is limited to 30.

## Demo

https://github.com/user-attachments/assets/8911e950-02de-4867-918e-7dba438cc94e
