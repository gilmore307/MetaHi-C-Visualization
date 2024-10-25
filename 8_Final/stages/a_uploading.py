import dash
from dash import dcc, html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import base64
import io
import py7zr
import pandas as pd
import numpy as np
from scipy.sparse import csr_matrix
from helper import save_file_to_user_folder

# Helper functions (for parsing contents and validations)
def parse_contents(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    
    if 'csv' in filename:
        return pd.read_csv(io.StringIO(decoded.decode('utf-8')))
    elif 'npz' in filename:
        npzfile = np.load(io.BytesIO(decoded))
        return npzfile
    elif '7z' in filename:
        with py7zr.SevenZipFile(io.BytesIO(decoded), mode='r') as z:
            return z.getnames()
    else:
        return None

# Helper function to get file size
def get_file_size(contents):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    size_in_bytes = len(decoded)
    size_in_kb = size_in_bytes / 1024
    return f"{size_in_kb:.2f} KB"

# Function to validate CSV files
def validate_csv(df, required_columns, optional_columns=[]):
    all_columns = required_columns + optional_columns
    if not all(column in df.columns for column in all_columns):
        raise ValueError(f"Missing columns in the file: {set(required_columns) - set(df.columns)}")
    for col in required_columns:
        if df[col].isnull().any():
            raise ValueError(f"Required column '{col}' has missing values.")
    return True

# Validation for contact matrix
def validate_contig_matrix(contig_data, contact_matrix):
    num_contigs = len(contig_data)

    if isinstance(contact_matrix, np.lib.npyio.NpzFile):
        if all(key in contact_matrix for key in ['data', 'indices', 'indptr', 'shape']):
            data = contact_matrix['data']
            indices = contact_matrix['indices']
            indptr = contact_matrix['indptr']
            shape = tuple(contact_matrix['shape'])
            contact_matrix = csr_matrix((data, indices, indptr), shape=shape)
        else:
            raise ValueError("The contact matrix file does not contain the expected sparse matrix keys.")
    
    matrix_shape = contact_matrix.shape
    if matrix_shape[0] != matrix_shape[1]:
        raise ValueError("The contact matrix is not square.")
    if matrix_shape[0] != num_contigs:
        raise ValueError(f"The contact matrix dimensions {matrix_shape} do not match the number of contigs.")
    
    if 'Self-contact' in contig_data.columns:
        diagonal_values = np.diag(contact_matrix.toarray())
        self_contact = contig_data['Self-contact'].dropna()
        if not np.allclose(self_contact, diagonal_values[:len(self_contact)]):
            raise ValueError("The 'Self-contact' column values do not match the diagonal of the contact matrix.")
    
    return True

# Validation for unnormalized folder contents
def validate_unnormalized_folder(folder):
    expected_files = ['contig_info_final.csv', 'raw_contact_matrix.npz']
    missing_files = [file for file in expected_files if file not in folder]
    if missing_files:
        raise ValueError(f"Missing files in unnormalized folder: {', '.join(missing_files)}")
    return True

# Validation for normalized folder contents
def validate_normalized_folder(folder):
    expected_files = ['bin_info_final.csv', 'contig_info_final.csv', 'contig_contact_matrix.npz', 'bin_contact_matrix.npz']
    missing_files = [file for file in expected_files if file not in folder]
    if missing_files:
        raise ValueError(f"Missing files in normalized folder: {', '.join(missing_files)}")
    return True

# Extract and list files from a .7z archive
def list_files_in_7z(decoded):
    with py7zr.SevenZipFile(io.BytesIO(decoded), mode='r') as z:
        file_list = z.getnames()
    return file_list

# Define the upload component layout
def create_upload_component(component_id, text, example_url, instructions):
    return dbc.Card(
        [
            dcc.Upload(
                id=component_id,
                children=dbc.Button(text, color="primary", className="me-2", style={"width": "100%"}),
                multiple=False,
                style={'textAlign': 'center'}
            ),
            dbc.Row(
                [
                    dbc.Col(html.A('Download Example File', href=example_url, target='_blank', style={'textAlign': 'center'})),
                ],
                style={'padding': '5px'}
            ),
            dbc.CardBody([
                html.H6("Instructions:"),
                dcc.Markdown(instructions, style={'fontSize': '0.9rem', 'color': '#555'})
            ]),
            html.Div(id=f'overview-{component_id}', style={'padding': '10px'}),
            dbc.Button("Remove File", id=f'remove-{component_id}', color="danger", style={'display': 'none'}),
            dcc.Store(id=f'store-{component_id}')
        ],
        body=True,
        className="my-3"
    )

# Upload layouts for different methods
def create_upload_layout_method1():
    return html.Div([
        dbc.Row([
            dbc.Col(create_upload_component(
                'raw-contig-info', 
                'Upload Contig Information File (.csv)', 
                'assets/examples/contig_information.csv',
                "This file must include columns like 'Contig', 'Restriction sites', 'Length', 'Coverage', and 'Self-contact'."
            )),
            dbc.Col(create_upload_component(
                'raw-contig-matrix', 
                'Upload Raw Contact Matrix File (.npz)', 
                'assets/examples/raw_contact_matrix.npz',
                "Matrix file must include keys such as 'indices', 'indptr', 'format', 'shape', 'data'."
            ))
        ]),
        dbc.Row([
            dbc.Col(create_upload_component(
                'raw-binning-info', 
                'Upload Binning Information File (.csv)', 
                'assets/examples/binning_information.csv',
                "This file must include columns like 'Contig', 'Bin', and 'Type'."
            )),
            dbc.Col(create_upload_component(
                'raw-bin-taxonomy', 
                'Upload Bin Taxonomy File (.csv)', 
                'assets/examples/taxonomy.csv',
                "This file must include columns like 'Bin', 'Domain', 'Kingdom', 'Phylum', 'Class', 'Order', 'Family', 'Genus', 'Species', 'Plasmid ID'."
            ))
        ]),
        dbc.Button("Validate All Files", id="validate-button", color="success", className="mt-3"),
        html.Div(id="validation-output", style={'padding': '0px', 'color': 'green'})
    ])

def create_upload_layout_method2():
    return html.Div([
        dbc.Row([
            dbc.Col(create_upload_component(
                'unnormalized-data-folder', 
                'Upload Unnormalized Data Folder (.7z)', 
                'assets/examples/unnormalized_information.7z',
                "The folder must include files like 'contig_info_final.csv' and 'raw_contact_matrix.npz'."
            ))
        ]),
        dbc.Button("Validate All Files", id="validate-button-unnormalized", color="success", className="mt-3"),
        html.Div(id="validation-output-unnormalized", style={'padding': '0px', 'color': 'green'})
    ])

def create_upload_layout_method3():
    return html.Div([
        dbc.Row([
            dbc.Col(create_upload_component(
                'normalized-data-folder', 
                'Upload Visualization Data Folder (.7z)', 
                'assets/examples/normalized_information.7z',
                "This folder should include files like 'bin_info_final.csv', 'contig_info_final.csv', 'contig_contact_matrix.npz', 'bin_contact_matrix.npz'."
            ))
        ]),
        dbc.Button("Validate All Files", id="validate-button-normalized", color="success", className="mt-3"),
        html.Div(id="validation-output-normalized", style={'padding': '0px', 'color': 'green'})
    ])

# Registering callbacks for uploads
def register_upload_callbacks(app):
    # Callback for raw contig info upload (Method 1)
    @app.callback(
        [Output('overview-raw-contig-info', 'children'),
         Output('remove-raw-contig-info', 'style'),
         Output('raw-contig-info', 'contents')],
        [Input('raw-contig-info', 'contents'),
         Input('remove-raw-contig-info', 'n_clicks')],
        [State('raw-contig-info', 'filename')]
    )
    def handle_contig_info_upload(contents, remove_click, filename):
        ctx = dash.callback_context
        if not contents:
            raise PreventUpdate
        
        if remove_click and ctx.triggered_id == 'remove-raw-contig-info':
            return '', {'display': 'none'}, None
        
        file_size = get_file_size(contents)
        if 'csv' in filename:
            df = parse_contents(contents, filename)
            return [dbc.Table.from_dataframe(df.head(), striped=True, bordered=True, hover=True),
                    html.P(f"File Size: {file_size}")], {'display': 'block'}, contents
        
        return "Unsupported file format", {'display': 'block'}, contents

    # Callback for raw contact matrix upload (Method 1)
    @app.callback(
        [Output('overview-raw-contig-matrix', 'children'),
         Output('remove-raw-contig-matrix', 'style'),
         Output('raw-contig-matrix', 'contents')],
        [Input('raw-contig-matrix', 'contents'),
         Input('remove-raw-contig-matrix', 'n_clicks')],
        [State('raw-contig-matrix', 'filename')]
    )
    def handle_raw_matrix_upload(contents, remove_click, filename):
        ctx = dash.callback_context
        if not contents:
            raise PreventUpdate
        
        if remove_click and ctx.triggered_id == 'remove-raw-contig-matrix':
            return '', {'display': 'none'}, None
        
        file_size = get_file_size(contents)
        if 'npz' in filename:
            npzfile = parse_contents(contents, filename)
            overview = html.Ul([html.Li(file) for file in npzfile.files])
            return [overview, html.P(f"File Size: {file_size}")], {'display': 'block'}, contents
        
        return "Unsupported file format", {'display': 'block'}, contents

    # Callback for binning info upload (Method 1)
    @app.callback(
        [Output('overview-raw-binning-info', 'children'),
         Output('remove-raw-binning-info', 'style'),
         Output('raw-binning-info', 'contents')],
        [Input('raw-binning-info', 'contents'),
         Input('remove-raw-binning-info', 'n_clicks')],
        [State('raw-binning-info', 'filename')]
    )
    def handle_binning_info_upload(contents, remove_click, filename):
        ctx = dash.callback_context
        if not contents:
            raise PreventUpdate
        
        if remove_click and ctx.triggered_id == 'remove-raw-binning-info':
            return '', {'display': 'none'}, None
        
        file_size = get_file_size(contents)
        if 'csv' in filename:
            df = parse_contents(contents, filename)
            return [dbc.Table.from_dataframe(df.head(), striped=True, bordered=True, hover=True),
                    html.P(f"File Size: {file_size}")], {'display': 'block'}, contents
        
        return "Unsupported file format", {'display': 'block'}, contents

    # Callback for bin taxonomy upload (Method 1)
    @app.callback(
        [Output('overview-raw-bin-taxonomy', 'children'),
         Output('remove-raw-bin-taxonomy', 'style'),
         Output('raw-bin-taxonomy', 'contents')],
        [Input('raw-bin-taxonomy', 'contents'),
         Input('remove-raw-bin-taxonomy', 'n_clicks')],
        [State('raw-bin-taxonomy', 'filename')]
    )
    def handle_bin_taxonomy_upload(contents, remove_click, filename):
        ctx = dash.callback_context
        if not contents:
            raise PreventUpdate
        
        if remove_click and ctx.triggered_id == 'remove-raw-bin-taxonomy':
            return '', {'display': 'none'}, None
        
        file_size = get_file_size(contents)
        if 'csv' in filename:
            df = parse_contents(contents, filename)
            return [dbc.Table.from_dataframe(df.head(), striped=True, bordered=True, hover=True),
                    html.P(f"File Size: {file_size}")], {'display': 'block'}, contents
        
        return "Unsupported file format", {'display': 'block'}, contents
    
    # Validation Callback for Method 1
    @app.callback(
        [Output('current-stage-method1', 'data'),
         Output('validation-output', 'children')],
        [Input('validate-button', 'n_clicks')],
        [State('raw-contig-info', 'contents'),
         State('raw-contig-matrix', 'contents'),
         State('raw-binning-info', 'contents'),
         State('raw-bin-taxonomy', 'contents'),
         State('raw-contig-info', 'filename'),
         State('raw-contig-matrix', 'filename'),
         State('raw-binning-info', 'filename'),
         State('raw-bin-taxonomy', 'filename'),
         State('user-folder', 'data'),
         State('current-stage-method1', 'data')]
    )
    def validate_method_1(n_clicks, contig_info, contig_matrix, binning_info, bin_taxonomy,
                          contig_info_name, contig_matrix_name, binning_info_name, bin_taxonomy_name,
                          user_folder, current_stage):
        if n_clicks is None or not all([contig_info, contig_matrix, binning_info, bin_taxonomy]):
            return dash.no_update, "Please upload all required files to validate."
        try:
            # Validate contig information file
            contig_data = parse_contents(contig_info, contig_info_name)
            required_columns = ['Contig', 'Restriction sites', 'Length', 'Coverage']
            validate_csv(contig_data, required_columns, optional_columns=['Self-contact'])

            # Validate contig matrix
            contig_matrix_data = parse_contents(contig_matrix, contig_matrix_name)
            validate_contig_matrix(contig_data, contig_matrix_data)

            # Validate binning information file
            binning_data = parse_contents(binning_info, binning_info_name)
            required_columns = ['Contig', 'Bin', 'Type']
            validate_csv(binning_data, required_columns)

            # Validate bin taxonomy file
            taxonomy_data = parse_contents(bin_taxonomy, bin_taxonomy_name)
            required_columns = ['Bin']
            optional_columns = ['Domain', 'Kingdom', 'Phylum', 'Class', 'Order', 'Family', 'Genus', 'Species', 'Plasmid ID']
            validate_csv(taxonomy_data, required_columns, optional_columns)

            # Perform validations (assuming existing validation functions)
            save_file_to_user_folder(contig_info, contig_info_name, user_folder)
            save_file_to_user_folder(contig_matrix, contig_matrix_name, user_folder)
            save_file_to_user_folder(binning_info, binning_info_name, user_folder)
            save_file_to_user_folder(bin_taxonomy, bin_taxonomy_name, user_folder)
            
            print("All files successfully validated and saved!")
            
            return 'Data Processing', "All files successfully validated and saved!"
        except Exception as e:
            print("Validation failed")
            return dash.no_update, f"Validation failed: {str(e)}"

    # Callback for Unnormalized Folder Upload (Method 2)
    @app.callback(
        [Output('overview-unnormalized-data-folder', 'children'),
         Output('remove-unnormalized-data-folder', 'style'),
         Output('unnormalized-data-folder', 'contents')],
        [Input('unnormalized-data-folder', 'contents'),
         Input('remove-unnormalized-data-folder', 'n_clicks')],
        [State('unnormalized-data-folder', 'filename')]
    )
    def handle_method_2(contents, remove_click, filename):
        ctx = dash.callback_context
        if not contents:
            return '', {'display': 'none'}, None
        
        if remove_click and ctx.triggered_id == 'remove-unnormalized-data-folder':
            return '', {'display': 'none'}, None

        file_size = get_file_size(contents)
        decoded = base64.b64decode(contents.split(',')[1])
        file_list = list_files_in_7z(decoded)
        overview = html.Ul([html.Li(file) for file in file_list])
        return [overview, html.P(f"File uploaded: {filename} ({file_size})")], {'display': 'block'}, contents

    # Validation Callback for Method 2
    @app.callback(
        [Output('current-stage-method2', 'data'),
         Output('validation-output-unnormalized', 'children')],
        [Input('validate-button-unnormalized', 'n_clicks')],
        [State('unnormalized-data-folder', 'contents'),
         State('unnormalized-data-folder', 'filename'),
         State('user-folder', 'data'),
         State('current-stage-method2', 'data')]
    )
    def validate_method_2(n_clicks, contents, filename, user_folder, current_stage):
        if n_clicks is None or contents is None:
            return dash.no_update, "No file uploaded. Please upload a file to validate."
        try:
            decoded = base64.b64decode(contents.split(',')[1])
            file_list = list_files_in_7z(decoded)
            validate_unnormalized_folder(file_list)
            save_file_to_user_folder(contents, filename, user_folder)
            return 'Normalization', "Unnormalized folder successfully validated and saved!"
        except Exception as e:
            return dash.no_update, f"Validation failed: {str(e)}"

    # Callback for Normalized Folder Upload (Method 3)
    @app.callback(
        [Output('overview-normalized-data-folder', 'children'),
         Output('remove-normalized-data-folder', 'style'),
         Output('normalized-data-folder', 'contents')],
        [Input('normalized-data-folder', 'contents'),
         Input('remove-normalized-data-folder', 'n_clicks')],
        [State('normalized-data-folder', 'filename')]
    )
    def handle_method_3(contents, remove_click, filename):
        ctx = dash.callback_context
        if not contents:
            return '', {'display': 'none'}, None
        
        if remove_click and ctx.triggered_id == 'remove-normalized-data-folder':
            return '', {'display': 'none'}, None

        file_size = get_file_size(contents)
        decoded = base64.b64decode(contents.split(',')[1])
        file_list = list_files_in_7z(decoded)
        overview = html.Ul([html.Li(file) for file in file_list])
        return [overview, html.P(f"File uploaded: {filename} ({file_size})")], {'display': 'block'}, contents

    # Validation Callback for Method 3
    @app.callback(
        [Output('current-stage-method3', 'data'),
         Output('validation-output-normalized', 'children')],
        [Input('validate-button-normalized', 'n_clicks')],
        [State('normalized-data-folder', 'contents'),
         State('normalized-data-folder', 'filename'),
         State('user-folder', 'data'),
         State('current-stage-method3', 'data')]
    )
    def validate_method_3(n_clicks, contents, filename, user_folder, current_stage):
        if n_clicks is None or contents is None:
            return dash.no_update, "No file uploaded. Please upload a file to validate."
        try:
            decoded = base64.b64decode(contents.split(',')[1])
            file_list = list_files_in_7z(decoded)
            validate_normalized_folder(file_list)
            save_file_to_user_folder(contents, filename, user_folder)
            return 'Visualization', "Normalized folder successfully validated and saved!"
        except Exception as e:
            return dash.no_update, f"Validation failed: {str(e)}"
