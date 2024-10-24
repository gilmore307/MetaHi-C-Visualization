import os
import uuid
import dash
import base64
import numpy as np
from dash import dcc, html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import pandas as pd
from stages.a_uploading import create_upload_component, register_callbacks
from stages.b_processing import process_data

# Define stages mapping for each method
stages_mapping = {
    'method1': ['File Uploading', 'Data Processing', 'Normalization', 'Spurious Contact Removal', 'Visualization'],
    'method2': ['File Uploading', 'Normalization', 'Spurious Contact Removal', 'Visualization'],
    'method3': ['File Uploading', 'Visualization']
}

# Initialize the Dash app with Bootstrap theme
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.config.suppress_callback_exceptions = True

# Helper function to save uploaded files to a user's folder
def save_file_to_user_folder(contents, filename, user_folder, folder_name='output'):
    # Ensure the user folder exists
    user_folder_path = os.path.join('assets', folder_name, user_folder)
    os.makedirs(user_folder_path, exist_ok=True)
    
    # File path where the file will be saved
    file_path = os.path.join(user_folder_path, filename)
    
    # Handle .npz files by extracting data from the content
    if filename.endswith('.npz'):
        # Assuming contents is the matrix object like contig_contact_matrix
        contig_contact_data = contents.data
        contig_contact_indices = contents.indices
        contig_contact_indptr = contents.indptr
        contig_contact_shape = contents.shape
        
        npz_data = {
            'data': contig_contact_data,
            'indices': contig_contact_indices,
            'indptr': contig_contact_indptr,
            'shape': contig_contact_shape
        }

        # Save the npz file using numpy's compressed format
        np.savez_compressed(file_path, **npz_data)
        return file_path

    # Handle 7z files differently (requires decoding)
    elif filename.endswith('.7z'):
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        
        # Write the decoded content to the .7z archive
        with open(file_path, 'wb') as f:
            f.write(decoded)
        return file_path

    # For other file types (like .csv), decode the contents and save
    elif isinstance(contents, str) and ',' in contents:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
    else:
        decoded = contents
    
    # Save the file (either .csv or other formats)
    with open(file_path, 'wb') as f:
        f.write(decoded)
    
    return file_path

# Function to generate the flowchart using buttons for stages_mapping
def create_flowchart(current_stage, method='method1'):
    method_stages = stages_mapping.get(method, stages_mapping['method1'])
    buttons = []
    for idx, stage in enumerate(method_stages):
        # Determine the color based on whether the stage is finished, current, or upcoming
        if stage == current_stage:
            color = 'primary'  # Current stage
        elif method_stages.index(current_stage) > idx:
            color = 'success'  # Finished stages
        else:
            color = 'light'  # Upcoming stages

        buttons.append(
            dbc.Button(stage, color=color, disabled=True, className="mx-2 my-2")
        )

        if idx < len(method_stages) - 1:
            # Add an arrow between stages
            buttons.append(html.Span("→", style={'font-size': '24px', 'margin': '0 10px'}))

    return html.Div(buttons, style={'display': 'flex', 'align-items': 'center', 'justify-content': 'center'})

# Define the layout of the app
app.layout = dbc.Container([
    html.H1("Meta Hi-C Visualization", className="my-4 text-center"),

    # Store to hold the current stage and user folder for each method
    dcc.Store(id='current-stage-method1', data='File Uploading'),
    dcc.Store(id='current-stage-method2', data='File Uploading'),
    dcc.Store(id='current-stage-method3', data='File Uploading'),
    dcc.Store(id='user-folder', data=str(uuid.uuid4())),  # Generate a unique folder for the user

    dcc.Tabs(id='tabs-method', value='method1', children=[
        # Method 1: Raw Data Uploads
        dcc.Tab(label='First-time users: Upload raw data', value='method1', children=[
            html.Div(id='flowchart-container-method1'),
            html.Div(id='upload-component-container-method1'),
            dbc.Button("Validate All Files", id="validate-button", color="success", className="mt-3"),
            html.Div(id="validation-output", style={'padding': '0px', 'color': 'green'}),
            html.Div(id="output-preview-method1", style={'padding': '10px'})
        ]),

        # Method 2: Unnormalized Data Uploads
        dcc.Tab(label='Change normalization method: Upload unnormalized data', value='method2', children=[
            html.Div(id='flowchart-container-method2'),
            html.Div(id='upload-component-container-method2'),
            dbc.Button("Validate All Files", id="validate-button-unnormalized", color="success", className="mt-3"),
            html.Div(id="validation-output-unnormalized", style={'padding': '0px', 'color': 'green'})
        ]),

        # Method 3: Normalized Data Uploads
        dcc.Tab(label='Continue previous visualization: Upload normalized data', value='method3', children=[
            html.Div(id='flowchart-container-method3'),
            html.Div(id='upload-component-container-method3'),
            dbc.Button("Validate All Files", id="validate-button-normalized", color="success", className="mt-3"),
            html.Div(id="validation-output-normalized", style={'padding': '0px', 'color': 'green'})
        ]),
    ]),
], fluid=True)

# Separate callback for Method 1
@app.callback(
    [Output('flowchart-container-method1', 'children'),
     Output('upload-component-container-method1', 'children'),
     Output('output-preview-method1', 'children')],
    [Input('tabs-method', 'value'),
     Input('current-stage-method1', 'data'),
     State('user-folder', 'data')]
)
def update_layout_method1(selected_method, stage_method1, user_folder):
    if selected_method != 'method1':
        return None, None, None

    # Create a unique folder for each user inside the assets/output directory
    user_folder_path = os.path.join('assets/output', user_folder)
    os.makedirs(user_folder_path, exist_ok=True)

    flowchart1 = create_flowchart(stage_method1, method='method1')
    if stage_method1 == 'File Uploading':
        upload_component1 = html.Div([
            dbc.Row([
                dbc.Col(create_upload_component(
                    'raw-contig-info',
                    'Upload Contig Information File (.csv)',
                    'assets/examples/contig_information.csv',
                    "This file must include the following columns: 'Contig', 'Restriction sites', 'Length', 'Coverage', and 'Self-contact'."
                )),
                dbc.Col(create_upload_component(
                    'raw-contig-matrix',
                    'Upload Raw Contact Matrix File (.npz)',
                    'assets/examples/raw_contact_matrix.npz',
                    "The Unnormalized Contact Matrix must include the following keys: 'indices', 'indptr', 'format', 'shape', 'data'."
                )),
            ]),
            dbc.Row([
                dbc.Col(create_upload_component(
                    'raw-binning-info',
                    'Upload Binning Information File (.csv)',
                    'assets/examples/binning_information.csv',
                    "This file must include the following columns: 'Contig', 'Bin', and 'Type'."
                )),
                dbc.Col(create_upload_component(
                    'raw-bin-taxonomy',
                    'Upload Bin Taxonomy File (.csv)',
                    'assets/examples/taxonomy.csv',
                    "This file must include the following columns: 'Bin', 'Domain', 'Kingdom', 'Phylum', 'Class', 'Order', 'Family', 'Genus', 'Species', 'Plasmid ID'."
                )),
            ]),
        ])
        return flowchart1, upload_component1, None
    elif stage_method1 == 'Data Processing':
        # Process data after validation and return a preview of the output file
        contig_info_path = os.path.join(user_folder_path, 'contig_information.csv')
        binning_info_path = os.path.join(user_folder_path, 'binning_information.csv')
        taxonomy_path = os.path.join(user_folder_path, 'taxonomy.csv')

        output_file_path = process_data(contig_info_path, binning_info_path, taxonomy_path, user_folder_path)
        if os.path.exists(output_file_path):
            df = pd.read_csv(output_file_path)
            preview = dbc.Table.from_dataframe(df.head(), striped=True, bordered=True, hover=True)
            return flowchart1, None, html.Div([html.H5('Processed Data Preview'), preview])
    return flowchart1, None, None

# Separate callback for Method 2
@app.callback(
    [Output('flowchart-container-method2', 'children'),
     Output('upload-component-container-method2', 'children')],
    [Input('tabs-method', 'value'),
     Input('current-stage-method2', 'data')]
)
def update_layout_method2(selected_method, stage_method2):
    if selected_method != 'method2':
        return None, None

    flowchart2 = create_flowchart(stage_method2, method='method2')
    if stage_method2 == 'File Uploading':
        upload_component2 = html.Div([
            dbc.Row([
                dbc.Col(create_upload_component(
                    'unnormalized-data-folder',
                    'Upload Unnormalized Data Folder (.7z)',
                    'assets/examples/unnormalized_information.7z',
                    "Please upload the 'unnormalized_information' folder generated from your previous visualization.  \n"
                    "It must include the following files: 'contig_info_final.csv', 'raw_contact_matrix.npz'."
                )),
            ]),
        ])
        return flowchart2, upload_component2
    return flowchart2, None

# Separate callback for Method 3
@app.callback(
    [Output('flowchart-container-method3', 'children'),
     Output('upload-component-container-method3', 'children')],
    [Input('tabs-method', 'value'),
     Input('current-stage-method3', 'data')]
)
def update_layout_method3(selected_method, stage_method3):
    if selected_method != 'method3':
        return None, None

    flowchart3 = create_flowchart(stage_method3, method='method3')
    if stage_method3 == 'File Uploading':
        upload_component3 = html.Div([
            dbc.Row([
                dbc.Col(create_upload_component(
                    'normalized-data-folder',
                    'Upload Visualization Data Folder (.7z)',
                    'assets/examples/normalized_information.7z',
                    "Please upload the 'normalized_information' folder generated from your previous visualization.  \n"
                    "It must include the following files: 'bin_info_final.csv', 'contig_info_final.csv', 'contig_contact_matrix.npz', 'bin_contact_matrix.npz'."
                )),
            ]),
        ])
        return flowchart3, upload_component3
    return flowchart3, None

# Register all the callbacks from file_upload.py
register_callbacks(app)

# Run the Dash app
if __name__ == '__main__':
    app.run_server(debug=True)
