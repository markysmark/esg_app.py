"""
ESG Data Upload Module
Handles bulk upload of ESG data from CSV/Excel files with validation and mapping.
"""

import streamlit as st
import pandas as pd
import os
import json
from main_app import ESGEntry, session, log_action, _utcnow

# persistent mapping profiles
PROFILE_FILE = "mapping_profiles.json"


def load_mapping_profiles():
    """Return persisted column mapping profiles."""
    if os.path.exists(PROFILE_FILE):
        try:
            with open(PROFILE_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_mapping_profiles(profiles: dict):
    """Write mapping profiles back to disk."""
    try:
        with open(PROFILE_FILE, 'w') as f:
            json.dump(profiles, f, indent=2)
    except Exception:
        pass


def profile_option_index(profile_mapping: dict, key: str, columns: list) -> int:
    """
    Return the selectbox index for a saved profile mapping.
    The selectbox options always prefix the real columns with a `None` option,
    so we offset by +1 when the column exists.

    Args:
        profile_mapping: Saved mapping profile dictionary.
        key: Field name to look up inside the profile.
        columns: List of available column names from the uploaded file.

    Returns:
        Integer index to use for the selectbox (0 when no saved column exists).
    """
    if not profile_mapping:
        return 0
    col_name = profile_mapping.get(key)
    if col_name and col_name in columns:
        return columns.index(col_name) + 1
    return 0


def validate_required_fields(df, field_mapping):
    """
    Validate that all required ESG fields are present in the uploaded file.
    
    Args:
        df: Pandas DataFrame from uploaded file
        field_mapping: Dict mapping expected ESG fields to column names
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    required_fields = ['building', 'waste_tonnes', 'employee_count', 'hours_worked', 
                      'chem_litres', 'eco_chem_pct', 'energy_kwh']
    
    missing_fields = [f for f in required_fields if field_mapping.get(f) is None]
    
    if missing_fields:
        return False, f"Missing required field mappings: {', '.join(missing_fields)}"
    
    # Check if mapped columns exist in DataFrame
    missing_columns = [field_mapping[f] for f in required_fields 
                      if field_mapping[f] and field_mapping[f] not in df.columns]
    
    if missing_columns:
        return False, f"Columns not found in file: {', '.join(missing_columns)}"
    
    return True, ""


def preview_data(df, field_mapping, max_rows=10):
    """
    Preview how data will be imported with the current field mapping.
    
    Args:
        df: DataFrame from uploaded file
        field_mapping: Dict mapping ESG fields to column names
        max_rows: Number of rows to preview
    
    Returns:
        DataFrame with mapped columns
    """
    preview_df = pd.DataFrame()

    for esg_field, csv_column in field_mapping.items():
        if csv_column and csv_column in df.columns:
            preview_df[esg_field] = df[csv_column]

    # add simple validation column
    def row_validations(row):
        issues = []
        try:
            if 'waste_tonnes' in row.index and pd.notna(row['waste_tonnes']):
                if float(row['waste_tonnes']) < 0:
                    issues.append('negative waste')
        except Exception:
            pass
        try:
            if 'energy_kwh' in row.index and pd.notna(row['energy_kwh']):
                if float(row['energy_kwh']) < 0:
                    issues.append('negative energy')
        except Exception:
            pass
        try:
            if 'eco_chem_pct' in row.index and pd.notna(row['eco_chem_pct']):
                v = float(row['eco_chem_pct'])
                if v < 0 or v > 100:
                    issues.append('eco_chem_pct out of range')
        except Exception:
            pass
        try:
            if 'employee_count' in row.index and pd.notna(row['employee_count']):
                if int(float(row['employee_count'])) < 0:
                    issues.append('negative staff')
        except Exception:
            pass
        return '; '.join(issues)

    if not preview_df.empty:
        preview_df = preview_df.copy()
        preview_df['__validation'] = preview_df.apply(row_validations, axis=1)

        # limit rows returned
        return preview_df.head(max_rows)

    return preview_df.head(max_rows)


def process_bulk_upload(df, field_mapping, client, agent, overwrite=False):
    """
    Process and import bulk ESG data from DataFrame.
    
    Args:
        df: DataFrame with ESG data
        field_mapping: Dict mapping ESG fields to column names
        client: Client name for all entries
        agent: Agent name for all entries
        overwrite: Whether to overwrite existing data for same buildings
    
    Returns:
        Tuple of (success_count, error_list, warning_list)
    """
    success_count = 0
    errors = []
    warnings = []
    
    for idx, row in df.iterrows():
        try:
            # Extract values from mapped columns
            building = str(row.get(field_mapping.get('building', ''))).strip()
            
            if not building or building == 'nan':
                errors.append(f"Row {idx + 2}: Missing building name")
                continue
            
            # Parse numeric fields with error handling
            def safe_float(val, default=0.0):
                try:
                    if pd.isna(val):
                        return default
                    return float(val)
                except (ValueError, TypeError):
                    return default
            
            waste_tonnes = safe_float(row.get(field_mapping.get('waste_tonnes', '')))
            energy_kwh = safe_float(row.get(field_mapping.get('energy_kwh', '')))
            chem_litres = safe_float(row.get(field_mapping.get('chem_litres', '')))
            eco_chem_pct = safe_float(row.get(field_mapping.get('eco_chem_pct', '')), 0.0)
            employee_count = int(safe_float(row.get(field_mapping.get('employee_count', '')), 0))
            hours_worked = safe_float(row.get(field_mapping.get('hours_worked', '')))
            
            # Optional timestamp field
            timestamp = None
            if field_mapping.get('timestamp') and field_mapping['timestamp'] in row.index:
                try:
                    timestamp = pd.to_datetime(row.get(field_mapping['timestamp']))
                except Exception:
                    pass
            
            # Check for duplicate building data in current batch
            existing = session.query(ESGEntry).filter(
                ESGEntry.building == building,
                ESGEntry.client == client,
                ESGEntry.agent == agent
            ).first()
            
            if existing and not overwrite:
                warnings.append(f"Row {idx + 2}: '{building}' already exists (skipped, enable 'Overwrite' to replace)")
                continue
            
            # Create new entry
            new_entry = ESGEntry(
                client=client,
                agent=agent,
                building=building,
                waste_tonnes=waste_tonnes,
                energy_kwh=energy_kwh,
                chem_litres=chem_litres,
                eco_chem_pct=eco_chem_pct,
                employee_count=employee_count,
                hours_worked=hours_worked,
                timestamp=timestamp or _utcnow()
            )
            
            session.add(new_entry)
            success_count += 1
            
        except Exception as e:
            errors.append(f"Row {idx + 2}: {str(e)}")
    
    # Commit all successful entries
    if success_count > 0:
        session.commit()
        log_action('', 'system', f"Bulk upload: {success_count} entries imported for {agent}")
    
    return success_count, errors, warnings


def load_example_csv():
    """
    Generate an example CSV with proper column structure.
    
    Returns:
        CSV string
    """
    example_data = {
        'Building Name': ['The Shard', 'One Churchill Place', 'Broadgate Tower'],
        'Waste (Tonnes)': [15.5, 22.3, 18.7],
        'Energy (kWh)': [45000, 67000, 52000],
        'Chemicals (L)': [120, 180, 150],
        'Eco Chemicals %': [85, 75, 88],
        'Staff Count': [450, 680, 520],
        'Total Hours': [94000, 141000, 108000],
        'Date': ['2024-01-31', '2024-01-31', '2024-01-31']
    }
    
    df = pd.DataFrame(example_data)
    return df.to_csv(index=False)


def render_upload_interface():
    """
    Render the complete data upload interface with validation and preview.
    """
    st.header("📤 Bulk ESG Data Upload")
    st.markdown("""
    Upload ESG metrics for multiple sites at once. Support for CSV and Excel files.
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Example CSV download
        example_csv = load_example_csv()
        st.download_button(
            label="📋 Download Example CSV",
            data=example_csv,
            file_name="esg_template.csv",
            mime="text/csv",
            help="Download a sample CSV file to see the required format"
        )
    
    with col2:
        st.info("💡 Tip: Prepare your file with columns for waste, energy, chemicals, staff, and hours")
    
    # File upload
    uploaded_file = st.file_uploader(
        "Choose a CSV or Excel file",
        type=['csv', 'xlsx', 'xls'],
        help="Upload a file containing ESG data for multiple locations"
    )
    
    if uploaded_file is not None:
        try:
            # Read file
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            st.success(f"✅ File loaded: {uploaded_file.name} ({len(df)} rows)")
            st.divider()
            columns = list(df.columns)
            
            # Column mapping section
            st.subheader("🔀 Map Your Columns")
            st.markdown("Match your file columns to ESG data fields:")

            # mapping profile selector
            profiles = load_mapping_profiles()
            profile_names = ["<new>"] + sorted(profiles.keys())
            selected_profile = st.selectbox("Existing profile", profile_names, key="profile_sel")
            if selected_profile != "<new>":
                profile_mapping = profiles.get(selected_profile, {})
            else:
                profile_mapping = {}

            col1, col2 = st.columns(2)
            
            with col1:
                field_mapping = {
                    'building': st.selectbox(
                        'Building Name Column',
                        [None] + columns,
                        index=profile_option_index(profile_mapping, 'building', columns),
                        help="Required: Column containing site/building names"
                    ),
                    'waste_tonnes': st.selectbox(
                        'Waste (Tonnes) Column',
                        [None] + columns,
                        index=profile_option_index(profile_mapping, 'waste_tonnes', columns),
                        help="Required: Total waste generated"
                    ),
                    'energy_kwh': st.selectbox(
                        'Energy (kWh) Column',
                        [None] + columns,
                        index=profile_option_index(profile_mapping, 'energy_kwh', columns),
                        help="Required: Total energy consumption"
                    ),
                }
            
            with col2:
                field_mapping.update({
                    'chem_litres': st.selectbox(
                        'Chemicals (Litres) Column',
                        [None] + columns,
                        index=profile_option_index(profile_mapping, 'chem_litres', columns),
                        help="Required: Chemical volume used"
                    ),
                    'eco_chem_pct': st.selectbox(
                        'Eco-Chemical % Column',
                        [None] + columns,
                        index=profile_option_index(profile_mapping, 'eco_chem_pct', columns),
                        help="Required: Percentage of eco-friendly chemicals"
                    ),
                    'employee_count': st.selectbox(
                        'Staff Count Column',
                        [None] + columns,
                        index=profile_option_index(profile_mapping, 'employee_count', columns),
                        help="Required: Number of employees"
                    ),
                })

            field_mapping['hours_worked'] = st.selectbox(
                'Total Hours Worked Column',
                [None] + columns,
                index=profile_option_index(profile_mapping, 'hours_worked', columns),
                help="Required: Total work hours"
            )
            
            # Optional timestamp
            field_mapping['timestamp'] = st.selectbox(
                'Date/Timestamp Column (Optional)',
                [None] + columns,
                index=profile_option_index(profile_mapping, 'timestamp', columns),
                help="Optional: If not provided, current date will be used"
            )
            
            st.divider()

            # profile save/delete UI
            with st.expander("💾 Save / manage profile", expanded=False):
                newname = st.text_input("Profile name",
                                       value="" if selected_profile == "<new>" else selected_profile)
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("Save profile"):
                        if newname:
                            profiles[newname] = field_mapping.copy()
                            save_mapping_profiles(profiles)
                            st.success(f"Profile '{newname}' saved")
                        else:
                            st.error("Provide a name to save")
                with col_b:
                    if selected_profile not in (None, "<new>"):
                        if st.button("Delete profile", type="secondary"):
                            profiles.pop(selected_profile, None)
                            save_mapping_profiles(profiles)
                            st.success(f"Profile '{selected_profile}' removed")

            # Validate mapping
            is_valid, error_msg = validate_required_fields(df, field_mapping)
            
            if is_valid:
                st.success("✅ All required mappings are set!")
                
                # Preview
                with st.expander("👁️ Preview Data", expanded=True):
                    preview_df = preview_data(df, field_mapping, max_rows=len(df))
                    # Pagination controls
                    page_size = st.selectbox("Rows per page", [10, 25, 50, 100], index=0)
                    total = len(preview_df)
                    total_pages = max(1, (total + page_size - 1) // page_size)
                    page = st.number_input("Page", min_value=1, max_value=total_pages, value=1)
                    start = (page - 1) * page_size
                    end = start + page_size
                    st.write(f"Showing rows {start+1}–{min(end, total)} of {total}")
                    if not preview_df.empty:
                        if '__validation' in preview_df.columns:
                            # highlight invalid rows
                            def highlight_row(s):
                                if s['__validation']:
                                    return ['background-color: #ffdddd'] * len(s.index)
                                return [''] * len(s.index)

                            try:
                                st.dataframe(preview_df.style.apply(lambda r: ['background-color: #ffdddd' if r['__validation'] else '' for _ in r], axis=1), width="stretch")
                            except Exception:
                                # fallback to raw dataframe and show validation column
                                st.dataframe(preview_df, width="stretch")
                        else:
                            st.dataframe(preview_df, width="stretch")
                    else:
                        st.info("No previewable rows found")
                
                st.divider()
                
                # Import settings
                col1, col2 = st.columns(2)
                
                with col1:
                    client_sel = st.selectbox(
                        "Target Client",
                        ["New Client"] + list(st.session_state.clients_data.keys()),
                        help="Select which client these entries belong to"
                    )
                    
                    if client_sel == "New Client":
                        client_name = st.text_input("Create New Client", placeholder="e.g., Workspace Group")
                        if client_name:
                            if client_name not in st.session_state.clients_data:
                                st.session_state.clients_data[client_name] = {"Agents": [], "Buildings": []}
                            client_sel = client_name
                    
                    agent_sel = st.selectbox(
                        "Managing Agent",
                        ["New Agent"] + st.session_state.clients_data.get(client_sel, {}).get("Agents", []),
                        help="Select or create the managing agent"
                    )
                    
                    if agent_sel == "New Agent":
                        agent_name = st.text_input("Create New Agent", placeholder="e.g., Savills")
                        if agent_name:
                            agent_sel = agent_name
                
                with col2:
                    overwrite = st.checkbox(
                        "Overwrite Existing Data",
                        value=False,
                        help="Check to replace data for buildings that already exist"
                    )
                    
                    st.info(f"📊 **Summary**: Importing {len(df)} entries for **{client_sel}** / **{agent_sel}**")
                
                # Import button
                if st.button("🚀 Import Data", type="primary", width="stretch"):
                    if not client_sel or client_sel == "New Client":
                        st.error("Please select or create a client")
                    elif not agent_sel or agent_sel == "New Agent":
                        st.error("Please select or create an agent")
                    else:
                        with st.spinner("Processing upload..."):
                            # Add new agent to client if needed
                            if agent_sel not in st.session_state.clients_data[client_sel]["Agents"]:
                                st.session_state.clients_data[client_sel]["Agents"].append(agent_sel)
                            
                            # Add buildings to client if needed
                            buildings_for_client = st.session_state.clients_data[client_sel]["Buildings"]
                            mapped_buildings = df[field_mapping['building']].unique().tolist()
                            for bld in mapped_buildings:
                                if str(bld) not in buildings_for_client:
                                    st.session_state.clients_data[client_sel]["Buildings"].append(str(bld))
                            
                            # Save updated client structure
                            from main_app import save_clients_data
                            save_clients_data(st.session_state.clients_data)
                            
                            # Process upload
                            success_count, errors, warnings = process_bulk_upload(
                                df, field_mapping, client_sel, agent_sel, overwrite
                            )
                            
                            st.success(f"✅ Import Complete: {success_count} entries successfully imported")

                            if warnings:
                                st.warning(f"⚠️ {len(warnings)} warnings")
                                # offer download of warnings
                                try:
                                    import pandas as _pd
                                    wdf = _pd.DataFrame({'warning': warnings})
                                    csv_w = wdf.to_csv(index=False)
                                    st.download_button("📥 Download Warnings CSV", csv_w, "warnings.csv", "text/csv")
                                except Exception:
                                    pass

                            if errors:
                                with st.expander(f"❌ {len(errors)} errors encountered"):
                                    st.code("\n".join(errors[:50]))
                                try:
                                    import pandas as _pd
                                    edf = _pd.DataFrame({'error': errors})
                                    csv_e = edf.to_csv(index=False)
                                    st.download_button("📥 Download Errors CSV", csv_e, "errors.csv", "text/csv")
                                except Exception:
                                    pass

                            st.rerun()
            else:
                st.error(f"❌ {error_msg}")
        
        except Exception as e:
            st.error(f"Error reading file: {str(e)}")
