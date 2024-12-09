# Import libraries
import pandas as pd
import os
from dash import Dash, dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go

# Load data
folder_path = '/data'
df_ContainerActivities = pd.read_csv(os.path.join(folder_path, 'modified_data/ContainerActivities_coordinates.csv'))
df_ContainerActivities['LOCATION_ID'] = df_ContainerActivities['LOCATION_ID'].astype(str)

# Ensure RECORDED_AT is in datetime format
df_ContainerActivities['RECORDED_AT'] = pd.to_datetime(df_ContainerActivities['RECORDED_AT'])

# Drop rows where DISTANCE > 100m
df_ContainerActivities = df_ContainerActivities[df_ContainerActivities['DISTANCE'] <= 100]

# Calculate average distance per location
average_distances = (
    df_ContainerActivities.groupby('LOCATION_ID')['DISTANCE']
    .mean()
    .reset_index()
    .rename(columns={'DISTANCE': 'AVERAGE_DISTANCE'})
)

# Merge average distances back into the main DataFrame for display purposes
df_ContainerActivities = pd.merge(df_ContainerActivities, average_distances, on='LOCATION_ID', how='left')

# Initialize the Dash app
app = Dash(__name__)

# Get a list of unique location IDs for the dropdown
unique_locations = df_ContainerActivities['LOCATION_ID'].unique()

# Layout of the Dash app
app.layout = html.Div([
    html.H1("Location Movement Visualization", style={'textAlign': 'center'}),
    dcc.Dropdown(
        id='location-dropdown',
        options=[{'label': f'Location {location_id}', 'value': location_id} for location_id in unique_locations],
        placeholder='Select a Location',
        style={'width': '50%', 'margin': '0 auto'}
    ),
    html.Div([
        dcc.Graph(id='location-map', style={'display': 'inline-block', 'width': '49%'}),
        dcc.Graph(id='distance-time-plot', style={'display': 'inline-block', 'width': '49%'})
    ])
])


# Callback to update the graphs based on selected location
@app.callback(
    [Output('location-map', 'figure'),
     Output('distance-time-plot', 'figure')],
    [Input('location-dropdown', 'value')]
)
def update_graphs(selected_location):
    print(f"Selected Location: {selected_location}")

    if not selected_location:
        return (
            go.Figure(layout={"title": "No location selected."}),
            go.Figure(layout={"title": "No data to display."})
        )

    # Filter data for the selected location
    location_data = df_ContainerActivities[df_ContainerActivities['LOCATION_ID'] == selected_location]
    if location_data.empty:
        return (
            go.Figure(layout={"title": f"No data available for location {selected_location}"}),
            go.Figure(layout={"title": "No data to display."})
        )

    # Map figure
    map_fig = go.Figure()

    # Add starting point
    if not pd.isna(location_data['GEO_LAT'].iloc[0]) and not pd.isna(location_data['GEO_LON'].iloc[0]):
        map_fig.add_trace(go.Scattergeo(
            lon=[location_data['GEO_LON'].iloc[0]],
            lat=[location_data['GEO_LAT'].iloc[0]],
            mode='markers',
            marker=dict(size=15, color='red', symbol='star'),
            name='Starting Point'
        ))

    # Add activity points with hover info
    map_fig.add_trace(go.Scattergeo(
        lon=location_data['LONGITUDE'],
        lat=location_data['LATITUDE'],
        mode='markers',  # Only markers
        marker=dict(size=7, color='blue'),
        text=[f"Date: {row['RECORDED_AT']}<br>Distance: {row['DISTANCE']} m<br>Avg Distance: {row['AVERAGE_DISTANCE']:.2f} m"
              for _, row in location_data.iterrows()],
        hoverinfo='text',
        name='Activity Points'
    ))

    # Configure the layout to auto-zoom to points
    map_fig.update_layout(
        title=f"Location {selected_location} - Movement Plot",
        geo=dict(
            showland=True,
            landcolor="lightgray",
            showcountries=True,
            countrycolor="white",
            resolution=50,
            projection_type='mercator',
            fitbounds="locations"
        ),
        width=600,
        height=800
    )

    # Distance-Time Plot
    time_fig = go.Figure()

    # Add line plot for distance over time (line chart)
    time_fig.add_trace(go.Scatter(
        x=location_data['RECORDED_AT'],
        y=location_data['DISTANCE'],
        mode='lines+markers',
        line=dict(color='blue'),
        marker=dict(size=7),
        name='Distance Over Time'
    ))

    # Add horizontal line for average distance
    avg_distance = location_data['AVERAGE_DISTANCE'].iloc[0]
    time_fig.add_trace(go.Scatter(
        x=[location_data['RECORDED_AT'].min(), location_data['RECORDED_AT'].max()],
        y=[avg_distance, avg_distance],
        mode='lines',
        line=dict(color='red', dash='dash'),
        name=f'Average Distance: {avg_distance:.2f} m'
    ))

    time_fig.update_layout(
        title=f"Location {selected_location} - Distance Over Time",
        xaxis_title="Time (RECORDED_AT)",
        yaxis_title="Distance (m)",
        width=600,
        height=800
    )

    return map_fig, time_fig

# Run the app
app.run_server(debug=True, port=8090)
