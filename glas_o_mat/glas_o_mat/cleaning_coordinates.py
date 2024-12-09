from glas_o_mat.dataset import Dataset
import pandas as pd
import numpy as np

# Parameters for outlier classification
RELATIVE_DIFF_THRESHOLD = 20        # Maximum allowed relative difference for consistency
HARD_OUTLIER_THRESHOLD = 400        # Hard limit for outliers
OUTLIER_ABSOLUTE_THRESHOLD = 150    # Absolute threshold for deviation from the mean
OUTLIER_MULTIPLIER = 3.5            # Multiplier for the standard deviation to detect outliers
MIN_DISTANCE_FOR_SHIFT = 15         # Minimum DISTANCE to classify as a shift

# Dynamic parameters for temporary shift detection
SCALING_FACTOR_SPAN = 0.3           # Factor for shift_span (30% of the range)
SCALING_FACTOR_MIN_DISTANCE = 0.3   # Factor for min_distance_for_shift (30% of the mean distance)
MIN_SHIFT_THRESHOLD = 35            # Minimum value for min_distance_for_shift
MIN_POINTS_FOR_SHIFT = 3            # Minimum number of points to qualify as a shift
ROLLING_WINDOW_SIZE = 3             # Window size for rolling mean/median


def outlier_classification(group: pd.DataFrame) -> pd.DataFrame:
    """
    Classifies data points in the group based on distance as 'accurate' or 'outlier'.

    Parameters:
        group (pd.DataFrame): A group of data with at least 'RECORDED_DATE' and 'DISTANCE' columns.

    Returns:
        pd.DataFrame: The group with added columns 'CLASSIFICATION' and 'outlier'.
    """
    # Sort data by recorded date to ensure sequential processing
    group = group.sort_values('RECORDED_DATE')
    group = group.copy()  # Avoid modifying the original DataFrame

    # Initialize classifications
    group['CLASSIFICATION'] = 'accurate'
    group['OUTLIER'] = False

    # Step 1: Apply a hard threshold to mark outliers
    for i in group.index:
        if group.loc[i, 'DISTANCE'] > HARD_OUTLIER_THRESHOLD:
            group.loc[i, 'CLASSIFICATION'] = 'outlier'
            group.loc[i, 'OUTLIER'] = True

    # Step 2: Iteratively calculate and remove outliers based on rolling statistics
    remaining_points = group[group['CLASSIFICATION'] != 'outlier']
    while True:
        # Calculate rolling mean and standard deviation for remaining points
        rolling_mean = pd.Series(remaining_points['DISTANCE'].values).rolling(window=4, center=True).mean()
        rolling_std = pd.Series(remaining_points['DISTANCE'].values).rolling(window=4, center=True).std()

        # Identify new outliers based on dynamic statistics
        new_outliers = []
        for i in remaining_points.index:
            current_distance = group.loc[i, 'DISTANCE']
            mean_val = rolling_mean.iloc[remaining_points.index.get_loc(i)]
            std_val = rolling_std.iloc[remaining_points.index.get_loc(i)]
            diff = abs(current_distance - mean_val)

            # Check if the point exceeds the absolute or statistical thresholds
            if diff > OUTLIER_ABSOLUTE_THRESHOLD or (std_val > 0 and diff > OUTLIER_MULTIPLIER * std_val):
                new_outliers.append(i)

        # If no new outliers are found, exit the loop
        if not new_outliers:
            break

        # Mark new outliers and exclude them from remaining points
        group.loc[new_outliers, 'CLASSIFICATION'] = 'outlier'
        group.loc[new_outliers, 'OUTLIER'] = True
        remaining_points = group[group['CLASSIFICATION'] != 'outlier']

    # Step 3: Mark all points with DISTANCE < MIN_DISTANCE_FOR_SHIFT as 'accurate'
    for i in group.index:
        if group.loc[i, 'DISTANCE'] < MIN_DISTANCE_FOR_SHIFT:
            group.loc[i, 'CLASSIFICATION'] = 'accurate'

    return group


def temporary_shift_detection(group: pd.DataFrame) -> pd.DataFrame:
    """
    Detects temporary shifts in the given group based on dynamic thresholds and rolling statistics.

    Parameters:
        group (pd.DataFrame): Data for a specific location group.

    Returns:
        pd.DataFrame: Updated group with temporary shifts classified.
    """
    # Temporarily remove outliers
    non_outliers = group[group['CLASSIFICATION'] != 'outlier'].copy()
    non_outliers['CLASSIFICATION'] = 'accurate'  # Default classification to accurate

    # Calculate dynamic parameters
    location_range = non_outliers['DISTANCE'].max() - non_outliers['DISTANCE'].min()
    location_mean = non_outliers['DISTANCE'].mean()

    # Dynamic shift_span
    shift_span = max(10, SCALING_FACTOR_SPAN * location_range)  # Minimum value of 10
    # Dynamic min_distance_for_shift
    min_distance_for_shift = max(MIN_SHIFT_THRESHOLD, SCALING_FACTOR_MIN_DISTANCE * location_mean)

    # Step 1: Calculate rolling median
    non_outliers['rolling_median'] = non_outliers['DISTANCE'].rolling(window=ROLLING_WINDOW_SIZE, center=True).median()

    # Step 2: Identify temporary shifts
    potential_shift_group = []
    for i in non_outliers.index:
        distance = non_outliers.loc[i, 'DISTANCE']
        rolling_median = non_outliers.loc[i, 'rolling_median']

        # Check if the point lies within the dynamic shift span
        if distance >= min_distance_for_shift and abs(distance - rolling_median) <= shift_span:
            potential_shift_group.append(i)
        else:
            # If the condition is not met, check the current group
            if len(potential_shift_group) >= MIN_POINTS_FOR_SHIFT:
                # Mark the group as temporary shift
                non_outliers.loc[potential_shift_group, 'CLASSIFICATION'] = 'temporary_shift'
            # Reset the group
            potential_shift_group = []

    # Check the last group after the loop
    if len(potential_shift_group) >= MIN_POINTS_FOR_SHIFT:
        non_outliers.loc[potential_shift_group, 'CLASSIFICATION'] = 'temporary_shift'

    # Step 3: Check individual points between two shift phases
    indices = non_outliers.index
    for i in range(1, len(indices) - 1):
        prev_idx = indices[i - 1]
        curr_idx = indices[i]
        next_idx = indices[i + 1]

        # Check if the points before and after are temporary shifts
        if (
            non_outliers.loc[prev_idx, 'CLASSIFICATION'] == 'temporary_shift' and
            non_outliers.loc[next_idx, 'CLASSIFICATION'] == 'temporary_shift' and
            non_outliers.loc[curr_idx, 'CLASSIFICATION'] == 'accurate'
        ):
            prev_value = non_outliers.loc[prev_idx, 'DISTANCE']
            next_value = non_outliers.loc[next_idx, 'DISTANCE']

            # Check if the two outer points are at a similar level
            if abs(prev_value - next_value) <= shift_span:
                # Mark the middle point as temporary shift
                non_outliers.loc[curr_idx, 'CLASSIFICATION'] = 'temporary_shift'

    # Step 4: Update the original group with new classifications
    group.update(non_outliers)
    return group


def detect_temporary_shifts(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applies temporary shift detection to all groups in the DataFrame.

    Parameters:
        df (pd.DataFrame): Input DataFrame with location and distance data.

    Returns:
        pd.DataFrame: Updated DataFrame with temporary shifts classified.
    """
    # Apply the shift detection to each location group
    df = df.groupby('LOCATION_ID', group_keys=False).apply(temporary_shift_detection)

    # Remove helper columns if no longer needed
    df.drop(columns=['rolling_median'], inplace=True, errors='ignore')

    return df


def calculate_shifted_coords_with_outliers(location_group: pd.DataFrame) -> pd.DataFrame:
    """
    Groups 'temporary_shift' points based on consecutive order after sorting
    and accounts for outliers between two phases.

    Parameters:
        location_group (pd.DataFrame): Data for a specific location group.

    Returns:
        pd.DataFrame: Updated location group with adjusted coordinates for shifts and outliers.
    """
    # Consider only temporarily shifted points and outliers
    temp_shifted = location_group[location_group['CLASSIFICATION'] == 'temporary_shift']
    outliers = location_group[location_group['CLASSIFICATION'] == 'outlier']

    # Check if there are any temporarily shifted points
    if temp_shifted.empty:
        return location_group

    # Save original index and sort data by recorded date
    temp_shifted = temp_shifted.sort_values('RECORDED_DATE')
    temp_shifted['original_index'] = temp_shifted.index  # Save original index
    temp_shifted = temp_shifted.reset_index(drop=True)  # Reset index

    # Identify new phases based on gaps in the index
    temp_shifted['shift_phase'] = (temp_shifted.index.to_series().diff() > 1).cumsum()

    # Calculate mean coordinates for each phase
    phase_means = temp_shifted.groupby('shift_phase')[['LATITUDE', 'LONGITUDE']].mean()

    # Apply mean coordinates to respective phases
    for phase_id, phase_coords in phase_means.iterrows():
        phase_indices = temp_shifted[temp_shifted['shift_phase'] == phase_id]['original_index']
        location_group.loc[phase_indices, 'NEW_LAT'] = phase_coords['LATITUDE']
        location_group.loc[phase_indices, 'NEW_LON'] = phase_coords['LONGITUDE']

    # Identify outliers between phases
    for index, outlier in outliers.iterrows():
        outlier_date = outlier['RECORDED_DATE']

        # Find neighboring phases based on date
        before_phase = temp_shifted[temp_shifted['RECORDED_DATE'] < outlier_date].tail(1)
        after_phase = temp_shifted[temp_shifted['RECORDED_DATE'] > outlier_date].head(1)

        if not before_phase.empty and not after_phase.empty:
            # Get phase IDs and mean coordinates of neighbors
            before_phase_id = before_phase['shift_phase'].iloc[0]
            after_phase_id = after_phase['shift_phase'].iloc[0]
            before_coords = phase_means.loc[before_phase_id]
            after_coords = phase_means.loc[after_phase_id]

            # Calculate the mean coordinates of neighboring phases
            mean_lat = (before_coords['LATITUDE'] + after_coords['LATITUDE']) / 2
            mean_lon = (before_coords['LONGITUDE'] + after_coords['LONGITUDE']) / 2

            # Adjust the outlier
            location_group.loc[index, 'NEW_LAT'] = mean_lat
            location_group.loc[index, 'NEW_LON'] = mean_lon
            location_group.loc[index, 'CLASSIFICATION'] = 'temporary_shift'

    return location_group


def update_coordinates_with_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Updates coordinates for all location IDs, handling shifts and outliers.

    Parameters:
        df (pd.DataFrame): Input DataFrame with 'LOCATION_ID', 'CLASSIFICATION',
                           'LATITUDE', 'LONGITUDE', 'RECORDED_DATE', and 'DISTANCE'.

    Returns:
        pd.DataFrame: Updated DataFrame with adjusted coordinates.
    """
    # Initialize columns for new coordinates
    df['NEW_LAT'] = np.nan
    df['NEW_LON'] = np.nan

    # Set coordinates for 'accurate' classifications
    df.loc[df['CLASSIFICATION'] == 'accurate', 'NEW_LAT'] = df['GEO_LAT']
    df.loc[df['CLASSIFICATION'] == 'accurate', 'NEW_LON'] = df['GEO_LON']

    # Process each location group
    df = df.groupby('LOCATION_ID', group_keys=False).apply(calculate_shifted_coords_with_outliers)

    # Handle remaining outliers with no new coordinates
    remaining_outliers = (df['CLASSIFICATION'] == 'outlier') & (df['NEW_LAT'].isna()) & (df['NEW_LON'].isna())
    df.loc[remaining_outliers, 'NEW_LAT'] = df.loc[remaining_outliers, 'GEO_LAT']
    df.loc[remaining_outliers, 'NEW_LON'] = df.loc[remaining_outliers, 'GEO_LON']

    # Drop temporary columns if not needed
    df.drop(columns=['shift_phase', 'original_index'], inplace=True, errors='ignore')

    return df




