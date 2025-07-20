import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
from folium.plugins import Fullscreen, MeasureControl
import matplotlib.pyplot as plt
import seaborn as sns
from pymongo import MongoClient
import os

# Streamlit page configuration
st.set_page_config(page_title="Flight Route Analysis", layout="wide")

# Title and description
st.title("✈️ Global Flight Route Analysis")
st.markdown("""
Flight Route Analysis app presents an analysis of the busiest passenger flight routes scraped from Wikipedia. 
Explore the data, visualize passenger trends, and interact with a global map of the top routes.
""")

# Function to load data from MongoDB or CSV
@st.cache_data
def load_data():
    try:
        # Attempt to connect to MongoDB
        client = MongoClient("mongodb://localhost:27017/")
        db = client["flight_routes_db"]
        collection = db["flight_routess"]
        data = pd.DataFrame(list(collection.find()))
        client.close()
        st.success("Data loaded from MongoDB")
        return data
    except Exception as e:
        st.warning(f"Could not connect to MongoDB: {e}")
        # Fallback to CSV if available
        if os.path.exists("busist_flight.csv.csv"):
            data = pd.read_csv("busist_flight.csv.csv")
            st.success("Data loaded from CSV")
            return data
        else:
            st.error("No data source available. Please ensure MongoDB is running or provide a CSV file.")
            return None

# Load data
df = load_data()

if df is not None:
    # Remove '_id' column from MongoDB if present
    if '_id' in df.columns:
        df = df.drop(columns=['_id'])

    # Sidebar for filters
    st.sidebar.header("Filter Options")
    year_options = sorted(df["Year"].unique())
    selected_year = st.sidebar.multiselect("Select Year(s)", year_options, default=year_options)
    route_type_options = df["Type"].unique()
    selected_type = st.sidebar.multiselect("Select Route Type(s)", route_type_options, default=route_type_options)

    # Filter DataFrame
    filtered_df = df[df["Year"].isin(selected_year) & df["Type"].isin(selected_type)]

    # Key Metrics
    st.header("Key Metrics")
    col1, col2, col3 = st.columns(3)
    total_passengers = filtered_df["Passengers"].sum()
    total_routes = len(filtered_df)
    top_country = filtered_df.groupby("From_Country")["Passengers"].sum().idxmax()
    col1.metric("Total Passengers", f"{total_passengers:,}")
    col2.metric("Total Routes", total_routes)
    col3.metric("Top Origin Country", top_country)

    # Data Table
    st.header("Flight Routes Data")
    st.dataframe(filtered_df, use_container_width=True)

    # Define a custom color palette
    custom_palette = ['#22223b', '#4a4e69', '#9a8c98', '#c9ada7', '#f2e9e4']


    # Passenger Trends by Year
    st.header("Passenger Trends by Year")
    yearly_passengers = filtered_df.groupby("Year")["Passengers"].sum().reset_index()
    fig, ax = plt.subplots()
    
    sns.lineplot(data=yearly_passengers, x="Year", y="Passengers", marker="o", ax=ax, color=custom_palette[0],)
    plt.title(
        "Total Passenger Numbers Over Time", 
        fontsize=20, 
        color="#22223b", 
        weight="bold", 
        pad=20  
    )  
    ax.set_ylabel("Passengers (Millions)",fontsize=14, color="#4a4e69", labelpad=10)
    ax.set_xlabel("Year",fontsize=14, color="#4a4e69", labelpad=10)
    sns.set_style("whitegrid", {"axes.facecolor": "#f2e9e4","grid.color": "#c9ada7","grid.linestyle": "--"})
    st.pyplot(fig)

    # Top Departure Countries by Route Type
    st.header("Top 5 Departure Countries by Route Type")
    try:
        top_departure_countries = filtered_df.groupby(["From_Country", "Type"])["Passengers"].sum().unstack().fillna(0)
        top_departure_countries["Total"] = top_departure_countries.sum(axis=1)
        top_departure_countries = top_departure_countries.sort_values("Total", ascending=False).head(5).drop(columns="Total")
        custom_colors = ['#4a4e69', '#9a8c98']
        plt.figure(figsize=(10, 6))
        top_departure_countries.plot(
            kind="bar",
            color=custom_colors
        )
        plt.title(
            "Top 5 Departure Countries by Route Type",
            fontsize=18,
            color="#22223b",
            weight="bold",
            pad=20
        )
        plt.xlabel("Country", fontsize=14, color="#4a4e69", labelpad=10)
        plt.ylabel("Total Passengers (in millions)", fontsize=14, color="#4a4e69", labelpad=10)
        plt.xticks(fontsize=12, color="#9a8c98", rotation=45, ha="right")
        plt.yticks(fontsize=12, color="#9a8c98")
        plt.legend(
            title="Route Type",
            title_fontsize=12,
            fontsize=10,
            loc="upper right",
            frameon=False
        )
        plt.tight_layout()
        st.pyplot(plt)
    except Exception as e:
        st.error(f"Error rendering departure countries chart: {e}")

    # Top 10 Busiest Routes
    st.header("Top 10 Busiest Routes")
    route_data = filtered_df.groupby(["Route", "From", "To", "From_Lat", "From_Lon", "To_Lat", "To_Lon"])["Passengers"].sum().reset_index()
    top_routes = route_data.sort_values("Passengers", ascending=False).head(10)
    st.table(top_routes[["Route", "Passengers"]])

    # Interactive Map
    st.header("Interactive Flight Routes Map")
    try:
        m = folium.Map(location=[20, 0], zoom_start=2, tiles="CartoDB positron")
        routes_group = folium.FeatureGroup(name="Flight Routes")
        markers_group = folium.FeatureGroup(name="Airport Markers")

        # Add Palestine marker
        palestine_center = [31.5, 34.5]
        folium.Marker(
            location=palestine_center,
            tooltip="Palestine - Center of the region",
            popup=folium.Popup(
                html="""
                <div style="text-align: center;">
                    <div style="font-size: 18pt; font-weight: bold; font-style: italic; color: #800000;">
                        🇵🇸 Palestine
                    </div>
                </div>
                """,
                max_width=250
            ),
            icon=folium.DivIcon(
                html="""
                <div style="
                    padding: 5px 10px;
                    font-size: 16pt;
                    font-weight: bold;
                    font-style: italic;
                    color: #bc4749;
                    text-align: center;">
                    Palestine
                </div>
                """
            )
        ).add_to(m)

        # Add routes and markers
        for _, row in top_routes.iterrows():
            start = (row["From_Lat"], row["From_Lon"])
            end = (row["To_Lat"], row["To_Lon"])
            passenger_count = row["Passengers"]
            line_weight = 2 + passenger_count / max(top_routes["Passengers"]) * 5 if not top_routes["Passengers"].empty else 2
            folium.CircleMarker(
                location=start,
                radius=6,
                color="green",
                fill=True,
                fill_color="green",
                tooltip=f"Departure: {row['From']}",
                popup=folium.Popup(f"""
                <b>Departure:</b> {row['From']}<br>
                <b>Latitude:</b> {row['From_Lat']}<br>
                <b>Longitude:</b> {row['From_Lon']}
                """, max_width=250)
            ).add_to(markers_group)
            folium.CircleMarker(
                location=end,
                radius=6,
                color="red",
                fill=True,
                fill_color="red",
                tooltip=f"Destination: {row['To']}",
                popup=folium.Popup(f"""
                <b>Destination:</b> {row['To']}<br>
                <b>Latitude:</b> {row['To_Lat']}<br>
                <b>Longitude:</b> {row['To_Lon']}
                """, max_width=250)
            ).add_to(markers_group)
            folium.PolyLine(
                locations=[start, end],
                color="gray",
                weight=line_weight,
                popup=folium.Popup(f"""
                <b>Route:</b> {row['Route']}<br>
                <b>Passengers:</b> {row['Passengers']:,}
                """, max_width=300)
            ).add_to(routes_group)
            mid_lat = (row["From_Lat"] + row["To_Lat"]) / 2
            mid_lon = (row["From_Lon"] + row["To_Lon"]) / 2
            folium.Marker(
                location=[mid_lat, mid_lon],
                icon=folium.Icon(icon="plane", prefix="fa", color="blue"),
                tooltip=f"Midpoint of {row['Route']}",
                popup=folium.Popup(f"""
                <b>Midpoint of Route:</b> {row['Route']}
                """, max_width=250)
            ).add_to(routes_group)

        routes_group.add_to(m)
        markers_group.add_to(m)
        folium.LayerControl().add_to(m)
        m.add_child(MeasureControl(primary_length_unit='kilometers'))
        Fullscreen().add_to(m)
        legend_html = '''
        <div style="position: fixed;
                    bottom: 50px; left: 50px; width: 250px; height: 140px;
                    background-color: white; z-index:1000; font-size:14px;
                    border:2px solid grey; padding: 10px;">
            <b>Legend</b><br>
            <div style="display: flex; align-items: center;">
                <div style="width: 10px; height: 10px; background-color: green; margin-right: 8px;"></div> Departure
            </div>
            <div style="display: flex; align-items: center;">
                <div style="width: 10px; height: 10px; background-color: red; margin-right: 8px;"></div> Destination
            </div>
            <div style="display: flex; align-items: center;">
                <div style="width: 10px; height: 10px; background-color: gray; margin-right: 8px;"></div> Route (Thickness = Traffic)
            </div>
            <div style="display: flex; align-items: center;">
                <div style="width: 10px; height: 10px; background-color: blue; margin-right: 8px;"></div> Midpoint
            </div>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
        m.fit_bounds(routes_group.get_bounds())
        folium_static(m, width=1200, height=600)
    except Exception as e:
        st.error(f"Error rendering map: {e}")
else:
    st.error("Unable to load data for visualization.")