import plotly.graph_objects as go
import numpy as np
import rasterio.transform
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon
import pandas as pd
import trimesh
import overturemaps
from shapely import wkb
from shapely.geometry import LineString
import osmnx as ox
from rasterio import warp, enums
import rasterio
from rasterio import mask
import os
# Matplotlib and display are not strictly needed for the API function to return a Plotly figure
# from bmi_topography import Topography # Topography needs to be imported here if it's not global
from bmi_topography import Topography # Ensure Topography is available

def generate_3d_model(api_key: str, target_place: str) -> str:
    """
    Generates an interactive 3D visualization of terrain, road network, and buildings
    for a specified target place using OpenTopography DEM, OSMnx for roads/buildings,
    and Overture Maps for building heights.

    Args:
        api_key (str): Your OpenTopography API key.
        target_place (str): The name of the municipality or area to visualize (e.g., "Nesøya, Asker, Norway").

    Returns:
        str: A JSON string representation of a Plotly Figure object containing the 3D visualization.
    """
    print(f"Starting 3D visualization generation for: {target_place}")

    # --- 1. User Defined Parameters (within function scope) ---
    # ROOT_PATH = Path.cwd() # define the root path
    API_KEY = api_key
    TARGET_PLACE = target_place
    DEM_DATASET = 'COP30'
    # Generate unique filenames for temporary files to avoid conflicts
    safe_place_name = TARGET_PLACE.replace(' ', '_').replace(',', '')
    OUTPUT_DEM_FILENAME = f'{safe_place_name}_dem.tif'
    # The GeoJSON files are kept for consistency with previous steps, but can be removed
    # or kept in memory for an API if preferred.
    # OUTPUT_BUILDINGS_GEOJSON = f'/tmp/{safe_place_name}_buildings_with_heights.geojson'
    # OUTPUT_ROADS_GEOJSON = f'/tmp/{safe_place_name}_road_network_3d.geojson'

    # --- 2. Calculate Precise Bounding Box using OSMnx ---
    print(f"1. Fetching boundary for '{TARGET_PLACE}' from OpenStreetMap...")
    try:
        gdf_place_boundary = ox.geocode_to_gdf(TARGET_PLACE)
        west, south, east, north = gdf_place_boundary.total_bounds
        OSLO_BOUNDS = (west, south, east, north)
        print(f"   ✅ OSM Boundary found.")
    except Exception as e:
        print(f"   ❌ Error fetching boundary for '{TARGET_PLACE}'. Using a default fallback bounding box.")
        OSLO_BOUNDS = (10.0, 59.5, 11.5, 60.5) # Fallback to a rough box around Oslo if OSMnx fails
        print(f"   Fallback Bounding Box used: W:{OSLO_BOUNDS[0]}, S:{OSLO_BOUNDS[1]}, E:{OSLO_BOUNDS[2]}, N:{OSLO_BOUNDS[3]}")
        print(f"   Error details: {e}")
        return go.Figure().add_annotation(text=f"Could not fetch boundary for {TARGET_PLACE}.", showarrow=False).to_json()

    # --- 3. Set API Key as Environment Variable ---
    os.environ['OPENTOPOGRAPHY_API_KEY'] = API_KEY

    # --- 4. Initialize and Fetch DEM Data ---
    print(f"\n2. Starting download of {DEM_DATASET} for {TARGET_PLACE}...")
    try:
        topo = Topography(
            dem_type=DEM_DATASET,
            south=OSLO_BOUNDS[1],
            north=OSLO_BOUNDS[3],
            west=OSLO_BOUNDS[0],
            east=OSLO_BOUNDS[2],
            output_format='GTiff'
        )
        output_path = topo.fetch()
        os.rename(output_path, OUTPUT_DEM_FILENAME)
        print(f"\n✅ Download complete! Temporary file saved as: {OUTPUT_DEM_FILENAME}")
    except Exception as e:
        print(f"\n❌ An error occurred during DEM download. Please ensure your API key is correct and valid.")
        print(f"Error details: {e}")
        return go.Figure().add_annotation(text=f"DEM download failed for {TARGET_PLACE}. Error: {e}", showarrow=False).to_json()

    # --- 5. Clip DEM to Municipality Boundary ---
    print(f"Opening DEM file '{OUTPUT_DEM_FILENAME}'...")
    try:
        with rasterio.open(OUTPUT_DEM_FILENAME) as src:
            # Use the already fetched gdf_place_boundary
            geometries = [geom for geom in gdf_place_boundary.geometry.values]
            data_masked, transform_masked = mask.mask(src, geometries, crop=True)
        print("DEM successfully clipped to boundary.")
    except Exception as e:
        print(f"Error clipping DEM: {e}")
        if os.path.exists(OUTPUT_DEM_FILENAME): os.remove(OUTPUT_DEM_FILENAME)
        return go.Figure().add_annotation(text=f"DEM clipping failed for {TARGET_PLACE}. Error: {e}", showarrow=False).to_json()


    # --- 6. Reproject DEM to EPSG:3857 ---
    print("Reprojecting masked DEM to EPSG:3857 (Web Mercator)...")
    data_reprojected_3d = np.array([]) # Initialize with empty array
    transform_reprojected_3d = None
    try:
        with rasterio.open(OUTPUT_DEM_FILENAME) as src_original:
            src_crs_original = src_original.crs
            data_reprojected_3d, transform_reprojected_3d = warp.reproject(
                source=data_masked,
                src_crs=src_crs_original,
                src_transform=transform_masked,
                dst_crs='EPSG:3857',
                resampling=enums.Resampling.bilinear,
                num_threads=4
            )
        data_reprojected_3d = data_reprojected_3d.squeeze()
        nodata_value = src_original.nodata if src_original.nodata is not None else 0.0
        data_reprojected_3d[data_reprojected_3d == nodata_value] = np.nan
        print("Reprojection complete. Nodata values set to np.nan.")
    except Exception as e:
        print(f"Error reprojecting DEM: {e}")
        if os.path.exists(OUTPUT_DEM_FILENAME): os.remove(OUTPUT_DEM_FILENAME)
        return go.Figure().add_annotation(text=f"DEM reprojecting failed for {TARGET_PLACE}. Error: {e}", showarrow=False).to_json()

    # Helper function to get elevation from DEM at a given coordinate
    def get_elevation(x, y, dem_data, dem_transform):
        """Safely retrieves elevation from DEM at given (x, y) coordinates."""
        if dem_transform is None or dem_data.size == 0: # Check if DEM data/transform is valid
            return np.nan
        row, col = rasterio.transform.rowcol(dem_transform, x, y)
        if 0 <= row < dem_data.shape[0] and 0 <= col < dem_data.shape[1]:
            elevation = dem_data[row, col]
            if np.isnan(elevation) or elevation == 0.0: # Assuming 0 is also nodata for areas outside mask
                return np.nan
            return elevation
        return np.nan # Return NaN if coordinate is out of bounds


    #-------6.5 save terrain data as obj file ------------
    print("Generating OBJ file from DEM data...")

    output_obj_filename = 'terrain.obj'
    '''
    # Dimensions of the reprojected data
    rows, cols = data_reprojected_3d.shape

    # Generate X and Y coordinate grids
    _cols, _rows = np.meshgrid(np.arange(cols), np.arange(rows))
    xs, ys = rasterio.transform.xy(transform_reprojected_3d, _rows, _cols)
    X = np.array(xs)
    Y = np.array(ys)
    '''

    #--define X, Y--
    # 1. Extract height and width of the data
    height, width = data_reprojected_3d.shape

    # 2. Calculate the extent of the reprojected data
    x_min_3d, y_min_3d, x_max_3d, y_max_3d = rasterio.transform.array_bounds(height, width, transform_reprojected_3d)

    # 3. Create 1D arrays for X and Y coordinates
    # X-coordinates should be ordered from West to East by default from linspace
    x = np.linspace(x_min_3d, x_max_3d, width)
    # Y-coordinates need to be inverted to go from North (top) to South (bottom) for Plotly's surface plot
    y = np.linspace(y_min_3d, y_max_3d, height)
    y = y[::-1] # Invert the array for correct North-South orientation

    # 4. Generate 2D meshgrid arrays
    X, Y = np.meshgrid(x, y)
    #--define X, Y--


    # Open the OBJ file for writing
    with open(output_obj_filename, 'w') as f:
        f.write("# OBJ file generated from DEM data\n")
        f.write("o TerrainMesh\n") # Object name

    # Iterate through the data to create vertices
        vertices = []
        vertex_idx_map = np.zeros(data_reprojected_3d.shape, dtype=int)
        vertex_count = 0

    # Dimensions of the reprojected data
        rows, cols = data_reprojected_3d.shape

        for r in range(rows):
            for c in range(cols):
                z = data_reprojected_3d[r, c]
                if not np.isnan(z):
                    x_val = X[r, c] # Already in Web Mercator
                    y_val = Y[r, c] # Already in Web Mercator
                # Write vertex to file
                    f.write(f"v {x_val:.4f} {y_val:.4f} {z:.4f}\n")
                    vertex_count += 1
                    vertex_idx_map[r, c] = vertex_count # Store 1-based index
                else:
                    vertex_idx_map[r, c] = 0 # Mark as invalid

    # Iterate through the data to create faces (two triangles per grid cell)
        for r in range(rows - 1):
            for c in range(cols - 1):
            # Get 1-based indices for the four corners of the grid cell
                v1 = vertex_idx_map[r, c]
                v2 = vertex_idx_map[r, c + 1]
                v3 = vertex_idx_map[r + 1, c + 1]
                v4 = vertex_idx_map[r + 1, c]

            # Check if all vertices for a triangle are valid (non-zero index)
            # Triangle 1: (v1, v2, v3)
                if v1 != 0 and v2 != 0 and v3 != 0:
                    f.write(f"f {v1} {v2} {v3}\n")

            # Triangle 2: (v1, v3, v4)
                if v1 != 0 and v3 != 0 and v4 != 0:
                    f.write(f"f {v1} {v3} {v4}\n")

    print(f"OBJ file '{output_obj_filename}' created successfully with {vertex_count} vertices.")


    #--------6.5 save terrain to obj file------------

    # --- 7. Download and Process Road Network ---

    #'''
    #ALLOWED_HIGHWAY_REGEX = ".*"
    #custom_filter = f'"highway"~"{ALLOWED_HIGHWAY_REGEX}"'
    #G_oslo = ox.graph_from_place(place_name, custom_filter=f'[{custom_filter}]', retain_all=False, simplify=True)
    #'''

    print("Downloading road network...")
    gdf_roads_3d = gpd.GeoDataFrame() # Initialize empty GeoDataFrame
    ALLOWED_HIGHWAY_REGEX = ".*"
    custom_filter = f'"highway"~"{ALLOWED_HIGHWAY_REGEX}"'
    try:
        G_place = ox.graph_from_place(TARGET_PLACE, custom_filter=f'[{custom_filter}]', retain_all=False, simplify=True)
        _, gdf_edges_place = ox.graph_to_gdfs(G_place)
        gdf_edges_reprojected = gdf_edges_place.to_crs('EPSG:3857')

        road_segments_3d = []
        for idx, row in gdf_edges_reprojected.iterrows():
            geometry = row['geometry']
            if geometry.geom_type == 'LineString':
                coords_3d = []
                for x_coord, y_coord in geometry.coords:
                    elevation = get_elevation(x_coord, y_coord, data_reprojected_3d, transform_reprojected_3d)
                    coords_3d.append((x_coord, y_coord, elevation))
                road_segments_3d.append({
                    'geometry_3d': LineString(coords_3d),
                    'highway': row.get('highway'), 'name': row.get('name'),
                    'length': row.get('length'), 'osmid': row.get('osmid')
                })
        gdf_roads_3d = gpd.GeoDataFrame(road_segments_3d, geometry='geometry_3d', crs='EPSG:3857')
        print(f"Successfully processed {len(gdf_roads_3d)} 3D road segments.")
    except Exception as e:
        print(f"Error processing road network: {e}")
        # Continue, roads might be missing but other layers can still be drawn



    # ------7.5 Add power lines available from OSM --------------

    OUTPUT_GEOJSON_FILE = "power_lines.geojson"

    print(f"Querying power line data for '{TARGET_PLACE}' from OpenStreetMap...")
    # Define the tags for power lines. OSMnx uses tag-based querying.
    # For power lines, common tags include 'power=line' or 'power=cable'.
    # We'll query for 'power' objects with 'line' or 'cable' value.
    tags = {"power": ["line", "cable", "minor_line", "major_line"]}

    # Get the power lines within the specified place boundary
    No_powerline_symbol = 1
    try:
        gdf_power_lines = ox.features_from_place(TARGET_PLACE, tags)
    except Exception as e:
        No_powerline_symbol = 0
        print(f"Error processing power lines: {e}")

    #print('1111111111111')
    gdf_powerline_3d = gpd.GeoDataFrame() # Initialize empty GeoDataFrame
    if No_powerline_symbol == 0:
        print(f"No power lines found for '{TARGET_PLACE}'. No GeoJSON file will be saved and no visualization will be generated.")
        # Ensure any previous file is removed if no lines found now
        if os.path.exists(OUTPUT_GEOJSON_FILE):
            os.remove(OUTPUT_GEOJSON_FILE)
    else:
        print(f"Found {len(gdf_power_lines)} power line features.")
        print(f"Saving power line information to '{OUTPUT_GEOJSON_FILE}'...")

        gdf_boundary = ox.geocode_to_gdf(TARGET_PLACE)

        gdf_power_lines = gdf_power_lines.to_crs(gdf_boundary.crs)
        gdf_power_lines_clipped = gpd.clip(gdf_power_lines, gdf_boundary)

        # Save the GeoDataFrame to a GeoJSON file
        gdf_power_lines_clipped.to_file(OUTPUT_GEOJSON_FILE, driver="GeoJSON")

        #print('22222222222222')

        #boundary_filename = "boundary.geojson"
        #gdf_boundary.to_file(boundary_filename, driver="GeoJSON")

        print("Power line data saved successfully.")
        #print("First 5 rows of the GeoDataFrame:")
        #print(gdf_power_lines.head())
        #print(f"Power lines found for '{TARGET_PLACE}'. Proceeding to visualization in the next cell.")


        # process power grids and make them in 3D

        print("Downloading power grids...")
        gdf_powerline_3d = gpd.GeoDataFrame() # Initialize empty GeoDataFrame
        #ALLOWED_HIGHWAY_REGEX = ".*"
        #custom_filter = f'"highway"~"{ALLOWED_HIGHWAY_REGEX}"'
        try:
        #G_place = ox.graph_from_place(TARGET_PLACE, custom_filter=f'[{custom_filter}]', retain_all=False, simplify=True)
        #_, gdf_edges_place = ox.graph_to_gdfs(G_place)
            gdf_power_lines_clipped = gdf_power_lines_clipped.to_crs('EPSG:3857')

            powerline_segments_3d = []
            for idx, row in gdf_power_lines_clipped.iterrows():
                geometry = row['geometry']
                if geometry.geom_type == 'LineString':
                    coords_3d = []
                    for x_coord, y_coord in geometry.coords:
                        elevation = get_elevation(x_coord, y_coord, data_reprojected_3d, transform_reprojected_3d)
                        coords_3d.append((x_coord, y_coord, elevation))
                    powerline_segments_3d.append({
                        'geometry_3d': LineString(coords_3d),
                        #'highway': row.get('highway'), 'name': row.get('name'),
                        'osmid': row.get('osmid')#, 'length': row.get('length')
                    })
            gdf_powerline_3d = gpd.GeoDataFrame(powerline_segments_3d, geometry='geometry_3d', crs='EPSG:3857')
            print(f"Successfully processed {len(gdf_powerline_3d)} 3D power line segments.")
        except Exception as e:
            print(f"Error processing power lines: {e}")
        # Continue, roads might be missing but other layers can still be drawn


    # ------7.5 Add power lines available from OSM --------------




    # --- 8. Download and Process Building Data ---
    print("Extracting building footprints and fetching Overture data...")
    buildings_reprojected_for_mesh = gpd.GeoDataFrame() # Initialize empty GeoDataFrame
    try:
        tags = {"building": True}
        gdf_buildings_footprints = ox.features_from_place(TARGET_PLACE, tags)
        if gdf_buildings_footprints.crs != "EPSG:4326":
            gdf_buildings_footprints = gdf_buildings_footprints.to_crs("EPSG:4326")

        bbox_buildings = tuple(gdf_buildings_footprints.total_bounds)
        overture_gdf = gpd.GeoDataFrame()
        table_iter = overturemaps.record_batch_reader("building", bbox=bbox_buildings, release="2026-02-18.0") # 2026-02-18.0, 2025-11-19.0
        for batch in table_iter:
            batch_df = batch.to_pandas()
            if 'geometry' in batch_df.columns and not batch_df['geometry'].empty:
                if batch_df['geometry'].apply(lambda x: isinstance(x, bytes)).any():
                    batch_df['geometry'] = batch_df['geometry'].apply(wkb.loads)
            batch_gdf = gpd.GeoDataFrame(batch_df, geometry='geometry', crs="EPSG:4326")
            overture_gdf = pd.concat([overture_gdf, batch_gdf], ignore_index=True)
        overture_gdf = overture_gdf.reset_index(drop=True)

        overture_join_df = overture_gdf[['geometry', 'height', 'num_floors']].copy()
        overture_join_df.rename(columns={'height': 'overture_height', 'num_floors': 'overture_floors'}, inplace=True)

        buildings_with_heights = gpd.sjoin(gdf_buildings_footprints, overture_join_df, how="left", predicate="intersects")
        if 'overture_height' not in buildings_with_heights.columns:
            buildings_with_heights['overture_height'] = None
        if 'overture_floors' not in buildings_with_heights.columns:
            buildings_with_heights['overture_floors'] = None
        if 'index_right' in buildings_with_heights.columns:
            buildings_with_heights = buildings_with_heights.drop(columns=['index_right'])

        buildings_reprojected_for_mesh = buildings_with_heights.to_crs('EPSG:3857')
        print(f"Successfully processed {len(buildings_reprojected_for_mesh)} buildings with heights.")
    except Exception as e:
        print(f"Error processing building data: {e}")
        # Continue, buildings might be missing but other layers can still be drawn

    # --- 9. Generate Building Mesh Data ---
    all_buildings_vertices_x = []
    all_buildings_vertices_y = []
    all_buildings_vertices_z = []
    all_buildings_faces_i = []
    all_buildings_faces_j = []
    all_buildings_faces_k = []
    current_vertex_offset = 0

    for idx, row in buildings_reprojected_for_mesh.iterrows():
        geom = row['geometry']
        polygons_to_process = []
        if isinstance(geom, MultiPolygon):
            polygons_to_process = list(geom.geoms)
        elif isinstance(geom, Polygon):
            polygons_to_process = [geom]
        else:
            continue

        for polygon in polygons_to_process:
            if not polygon.is_valid or polygon.is_empty or not polygon.exterior:
                continue

            centroid = polygon.centroid
            z_base = get_elevation(centroid.x, centroid.y, data_reprojected_3d, transform_reprojected_3d)
            if np.isnan(z_base):
                z_base = 0.0 # Default to 0 if elevation is unknown

            relative_building_height = row['overture_height']
            if pd.isna(relative_building_height):
                relative_building_height = 0.0

            coords_2d = list(polygon.exterior.coords)
            num_unique_points = len(coords_2d) - 1

            if num_unique_points < 3:
                continue

            local_verts_x = []
            local_verts_y = []
            local_verts_z = []

            for i in range(num_unique_points):
                local_verts_x.append(coords_2d[i][0])
                local_verts_y.append(coords_2d[i][1])
                local_verts_z.append(z_base)
            for i in range(num_unique_points):
                local_verts_x.append(coords_2d[i][0])
                local_verts_y.append(coords_2d[i][1])
                local_verts_z.append(z_base + relative_building_height)

            local_faces_i = []
            local_faces_j = []
            local_faces_k = []

            for k in range(num_unique_points):
                idx_b_curr = k
                idx_b_next = (k + 1) % num_unique_points
                idx_t_curr = k + num_unique_points
                idx_t_next = ((k + 1) % num_unique_points) + num_unique_points

                local_faces_i.append(idx_b_curr)
                local_faces_j.append(idx_b_next)
                local_faces_k.append(idx_t_next)

                local_faces_i.append(idx_b_curr)
                local_faces_j.append(idx_t_next)
                local_faces_k.append(idx_t_curr)

            if num_unique_points >= 3:
                for k in range(1, num_unique_points - 1):
                    local_faces_i.append(0)
                    local_faces_j.append(k)
                    local_faces_k.append(k + 1)

                for k in range(1, num_unique_points - 1):
                    local_faces_i.append(num_unique_points)
                    local_faces_j.append(k + num_unique_points)
                    local_faces_k.append(k + 1 + num_unique_points)

            all_buildings_vertices_x.extend(local_verts_x)
            all_buildings_vertices_y.extend(local_verts_y)
            all_buildings_vertices_z.extend(local_verts_z)

            all_buildings_faces_i.extend([f_idx + current_vertex_offset for f_idx in local_faces_i])
            all_buildings_faces_j.extend([f_idx + current_vertex_offset for f_idx in local_faces_j])
            all_buildings_faces_k.extend([f_idx + current_vertex_offset for f_idx in local_faces_k])

            current_vertex_offset += len(local_verts_x)
    print(f"Generated mesh for {len(all_buildings_vertices_x)} vertices and {len(all_buildings_faces_i)} triangles across all buildings.")

    # --- 10. Load Terrain Mesh ---
    # This part assumes 'terrain.obj' is available in the environment.
    # If not, the terrain layer will be skipped.
    terrain_vertices_x, terrain_vertices_y, terrain_vertices_z = [], [], []
    terrain_faces_i, terrain_faces_j, terrain_faces_k = [], [], []
    terrain_obj_path = 'terrain.obj' # Path to the terrain OBJ file
    if os.path.exists(terrain_obj_path):
        try:
            mesh = trimesh.load(terrain_obj_path)
            terrain_vertices = mesh.vertices
            terrain_faces = mesh.faces

            terrain_vertices_x = terrain_vertices[:, 0]
            terrain_vertices_y = terrain_vertices[:, 1]
            terrain_vertices_z = terrain_vertices[:, 2]

            terrain_faces_i = terrain_faces[:, 0]
            terrain_faces_j = terrain_faces[:, 1]
            terrain_faces_k = terrain_faces[:, 2]
            print(f"Successfully loaded terrain mesh from {terrain_obj_path}.")
        except Exception as e:
            print(f"Error loading terrain OBJ file '{terrain_obj_path}': {e}. Skipping terrain visualization.")
    else:
        print(f"Terrain OBJ file '{terrain_obj_path}' not found. Skipping terrain visualization.")

    # --- 11. Create Plotly Figure ---
    print("Generating interactive 3D visualization with Plotly...")
    fig = go.Figure()

    # Add the terrain mesh
    if len(terrain_vertices_x) > 0: # Changed from 'if terrain_vertices_x:' to handle NumPy array truthiness
        fig.add_trace(go.Mesh3d(
            x=terrain_vertices_x,
            y=terrain_vertices_y,
            z=terrain_vertices_z,
            i=terrain_faces_i,
            j=terrain_faces_j,
            k=terrain_faces_k,
            color='gray', # Lighter gray for terrain
            opacity=0.9,
            name='Terrain Mesh',
            hovertemplate='Elevation: %{z:.2f}m<extra></extra>'
        ))

    # Define colors for different highway types
    highway_colors = {
        'motorway': 'white',#'red',
        'trunk': 'white',#'yellow',
        'primary': 'white',#'orange',
        'secondary': 'white',#'yellow',
        'tertiary': 'white',#'purple',
        'residential': 'white',#'yellow',
        'service': 'white',#'blue',
        'footway': 'white',
        'path': 'white',
        'cycleway': 'white',#'yellow',
        'pedestrian': 'white',#'blue',
        'track': 'white',#'blue',
        None: 'white'#'blue' # For roads with no specified highway type
    }

    # print("111111111111") # I was debugging here
    # print(gdf_roads_3d)
    # print("222222222222")

    # Add road network as 3D lines
    for idx, row in gdf_roads_3d.iterrows():
        geom_3d = row['geometry_3d']
        if geom_3d is not None and geom_3d.geom_type == 'LineString':
            x_coords, y_coords, z_coords = zip(*geom_3d.coords)

            highway_type = row.get('highway')
            if isinstance(highway_type, list):
                if highway_type:
                    highway_type = highway_type[0]
                else:
                    highway_type = None

            color = highway_colors.get(highway_type, 'white')

            fig.add_trace(go.Scatter3d(
                x=list(x_coords),
                y=list(y_coords),
                z=list(z_coords),
                mode='lines',
                line=dict(color=color, width=4),
                name=f"Road: {row.get('name', 'Unnamed')} ({highway_type})",
                showlegend=False,
                hovertemplate='<b>Road:</b> %{customdata[0]}<br><b>Type:</b> %{customdata[1]}<br><b>Length:</b> %{customdata[2]:.2f}m<extra></extra>',
                customdata=[[row.get('name', 'Unnamed Road')], [highway_type], [row.get('length')]]
            ))


    # -----------Add power grid as 3D lines
    # No_powerline_symbol = 0 # This is just for test purpose and need to remove this line in regular execution
    if No_powerline_symbol == 1:

        for idx, row in gdf_powerline_3d.iterrows():
            geom_3d_grid = row['geometry_3d']
            if geom_3d_grid is not None and geom_3d_grid.geom_type == 'LineString':
                x_coords_grid, y_coords_grid, z_coords_grid = zip(*geom_3d_grid.coords)

                #highway_type = row.get('highway')
                #if isinstance(highway_type, list):
                #    if highway_type:
                #        highway_type = highway_type[0]
                #    else:
                #        highway_type = None

                #color = highway_colors.get(highway_type, 'white')

                fig.add_trace(go.Scatter3d(
                    x=list(x_coords_grid),
                    y=list(y_coords_grid),
                    z=list(z_coords_grid),
                    mode='lines',
                    line=dict(color='red', width=4),
                    #name=f"Road: {row.get('name', 'Unnamed')} ({highway_type})",
                    showlegend=False#,
                    #hovertemplate='<b>Road:</b> %{customdata[0]}<br><b>Type:</b> %{customdata[1]}<br><b>Length:</b> %{customdata[2]:.2f}m<extra></extra>',
                    #customdata=[[row.get('name', 'Unnamed Road')], [highway_type], [row.get('length')]]
                ))
    # -----------Add power grid as 3D lines


    # Add buildings mesh
    if all_buildings_vertices_x: # Only add if there are buildings to display
        fig.add_trace(go.Mesh3d(
            x=all_buildings_vertices_x,
            y=all_buildings_vertices_y,
            z=all_buildings_vertices_z,
            i=all_buildings_faces_i,
            j=all_buildings_faces_j,
            k=all_buildings_faces_k,
            color='lightblue',
            opacity=0.9,
            name='Buildings',
            hovertemplate='Building<extra></extra>' # Can add more info if available in GeoDataFrame
        ))

    # Update layout for better visualization
    # Determine overall bounds for aspect ratio calculation
    all_x = []
    all_y = []
    all_z = []

    if len(terrain_vertices_x) > 0: # Prioritize terrain for scene bounds - Changed from 'if terrain_vertices_x:'
        all_x.extend(terrain_vertices_x)
        all_y.extend(terrain_vertices_y)
        all_z.extend(terrain_vertices_z)
    else:
        # If no terrain, try to use roads and buildings for bounds
        for geom_3d in gdf_roads_3d['geometry_3d']:
            if geom_3d is not None and geom_3d.geom_type == 'LineString':
                x_c, y_c, z_c = zip(*geom_3d.coords)
                all_x.extend(x_c)
                all_y.extend(y_c)
                all_z.extend(z_c)
        if all_buildings_vertices_x:
            all_x.extend(all_buildings_vertices_x)
            all_y.extend(all_buildings_vertices_y)
            all_z.extend(all_buildings_vertices_z)

    if all_x and all_y and all_z:
        x_range_val = np.max(all_x) - np.min(all_x)
        y_range_val = np.max(all_y) - np.min(all_y)
        z_range_val = np.max(all_z) - np.min(all_z)
    else:
        # Fallback if no data to calculate ranges
        x_range_val = 1000 # arbitrary values
        y_range_val = 1000
        z_range_val = 100

    avg_xy_range = (x_range_val + y_range_val) / 2
    z_exaggeration_factor = 2.0 # Consistent exaggeration

    fig.update_layout(
        title=f'Interactive 3D terrain, road network, and buildings visualization of {TARGET_PLACE}',
        scene=dict(
            xaxis=dict(title_text='East-West (meters)', visible=False),
            yaxis=dict(title_text='North-South (meters)', visible=False),
            zaxis=dict(title_text='Elevation (meters)', visible=False),
            aspectmode='manual',
            aspectratio=dict(
                x=1,
                y=y_range_val/x_range_val if x_range_val != 0 else 1,
                z=(z_range_val / avg_xy_range) * z_exaggeration_factor if avg_xy_range != 0 else 1
            ),
            camera=dict(
                eye=dict(x=1.2, y=1.2, z=1.2) # Optional: set an initial camera angle
            )
        ),
        height=2000, # Adjust height/width as needed for good viewing
        width=2000,
        showlegend=True
    )

    print("Interactive 3D visualization with terrain, roads, and buildings generated.")

    # --- 12. Clean up temporary files ---
    if os.path.exists(OUTPUT_DEM_FILENAME):
        os.remove(OUTPUT_DEM_FILENAME)
    # If GeoJSON files were saved temporarily, remove them here if desired
    # if os.path.exists(OUTPUT_BUILDINGS_GEOJSON): os.remove(OUTPUT_BUILDINGS_GEOJSON)
    # if os.path.exists(OUTPUT_ROADS_GEOJSON): os.remove(OUTPUT_ROADS_GEOJSON)
    if os.path.exists(OUTPUT_GEOJSON_FILE):
        os.remove(OUTPUT_GEOJSON_FILE)
    # remove obj file
    if os.path.exists(terrain_obj_path):
        os.remove(terrain_obj_path)

    #return fig.to_dict() #fig.to_json()


    fig_json = fig.to_json()  # this is json object that can be readly used by python
    #print(fig_json) # I am debugging

    #json_string = orjson.dumps(fig_json).decode() # this is a json string that for transfer across network. It is no longer usable in Python
    #print(json_string)  # I am debugging
    #return json_string
    return fig_json

import plotly.io as pio

def save_3d_model(fig_json):
    fig = pio.from_json(fig_json)
    output_html_file = '3d_visualization.html'
    fig.write_html(output_html_file)

def plot_3d_model(fig_json):
    fig = pio.from_json(fig_json)
    fig.show()
