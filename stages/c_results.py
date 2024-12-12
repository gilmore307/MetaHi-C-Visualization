from dash import dcc, html
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from scipy.sparse import load_npz
import dash_ag_grid as dag
import plotly.express as px
import pandas as pd
import numpy as np
import os
import io
import py7zr
from scipy.stats import pearsonr
from sklearn.cluster import DBSCAN

def normalization_visualization(norm_sparse_matrix, unnorm_sparse_matrix, contig_info):
    # Extract relevant columns
    restriction_sites = contig_info['The number of restriction sites']
    contig_length = contig_info['Contig length']
    contig_coverage = contig_info['Contig coverage']

    def compute_product_values(data, row, col):
        product_sites = restriction_sites.iloc[row].values * restriction_sites.iloc[col].values
        product_length = contig_length.iloc[row].values * contig_length.iloc[col].values
        product_coverage = contig_coverage.iloc[row].values * contig_coverage.iloc[col].values
        contacts = data
        return pd.DataFrame({
            'Product Sites': product_sites,
            'Product Length': product_length,
            'Product Coverage': product_coverage,
            'Contacts': contacts,
        })

    def compute_plot_data(data, row, col):
        product_sites = restriction_sites.iloc[row].values * restriction_sites.iloc[col].values
        product_length = contig_length.iloc[row].values * contig_length.iloc[col].values
        product_coverage = contig_coverage.iloc[row].values * contig_coverage.iloc[col].values
        contacts = data
        
        # Create the DataFrame
        plot_data = pd.DataFrame({
            'Product Sites': np.log1p(product_sites),
            'Product Length': np.log1p(product_length),
            'Product Coverage': np.log1p(product_coverage),
            'Contacts': contacts,
        })
        
        # Filter out rows where Contacts equals 0
        plot_data = plot_data[plot_data['Contacts'] > 0].reset_index(drop=True)
        
        # Filter out rows where Contacts exceeds the 99th percentile
        threshold = plot_data['Contacts'].quantile(0.99)
        plot_data = plot_data[plot_data['Contacts'] <= threshold].reset_index(drop=True)
        
        return plot_data

    def calculate_pearson(df, factors, contacts_col="Contacts"):
        correlations = {}
        for factor in factors:
            correlation, _ = pearsonr(df[contacts_col], df[factor])
            correlations[factor] = abs(correlation)
        return correlations

    norm_data, norm_row, norm_col = norm_sparse_matrix.data, norm_sparse_matrix.row, norm_sparse_matrix.col
    unnorm_data, unnorm_row, unnorm_col = unnorm_sparse_matrix.data, unnorm_sparse_matrix.row, unnorm_sparse_matrix.col

    normalized_product_values = compute_product_values(norm_data, norm_row, norm_col)
    unnormalized_product_values = compute_product_values(unnorm_data, unnorm_row, unnorm_col)

    normalized_plot_data = compute_plot_data(norm_data, norm_row, norm_col)
    unnormalized_plot_data = compute_plot_data(unnorm_data, unnorm_row, unnorm_col)

    factors = ["Product Sites", "Product Length", "Product Coverage"]
    normalized_correlations = calculate_pearson(normalized_product_values, factors)
    unnormalized_correlations = calculate_pearson(unnormalized_product_values, factors)

    correlation_results = pd.DataFrame({
        "Metric": ["Normalized", "Unnormalized"],
        "Site": [normalized_correlations["Product Sites"], unnormalized_correlations["Product Sites"]],
        "Length": [normalized_correlations["Product Length"], unnormalized_correlations["Product Length"]],
        "Coverage": [normalized_correlations["Product Coverage"], unnormalized_correlations["Product Coverage"]],
    })
    correlation_results = correlation_results.round(5)

    def filter_close_nodes(plot_data, eps=0.1):
        coordinates = plot_data[["Product Sites", "Product Length", "Product Coverage"]].values
        clustering = DBSCAN(eps=eps, min_samples=1).fit(coordinates)
        plot_data['Cluster'] = clustering.labels_
        filtered_data = (
            plot_data.groupby('Cluster', group_keys=False)
            .apply(lambda group: group.iloc[0])
            .reset_index(drop=True)
        )
        return filtered_data

    filtered_normalized_plot_data = filter_close_nodes(normalized_plot_data)
    filtered_unnormalized_plot_data = filter_close_nodes(unnormalized_plot_data)

    return correlation_results, filtered_normalized_plot_data, filtered_unnormalized_plot_data

def results_layout(user_folder):
    contig_info_path = os.path.join('output', user_folder, 'contig_info.csv')
    normalized_matrix_path = os.path.join('output', user_folder, 'normalized_matrix.npz')
    unnormalized_matrix_path = os.path.join('output', user_folder, 'unnormalized_matrix.npz')
    
    contig_info = pd.read_csv(contig_info_path)
    normalized_matrix = load_npz(normalized_matrix_path).tocoo()
    unnormalized_matrix = load_npz(unnormalized_matrix_path).tocoo()
    
    correlation_results, filtered_normalized_plot_data, filtered_unnormalized_plot_data = normalization_visualization(
        normalized_matrix, unnormalized_matrix, contig_info
    )
    
    instructions = (
        "The Download button allows users to download the dataset they are currently working with.  \n\n"
        "This downloaded data can be re-uploaded to the app when visiting the website again, "
        "enabling returning users to continue from where they left off with their previously analyzed data.  \n\n"
        "Use this to save your progress or share your dataset for collaborative analysis.")
         
    return html.Div([
        dcc.Loading(
            id="loading",
            type="circle",
            children=[
                dbc.Button("Switch to Interaction Network", id="switch-visualization-results", color="primary",
                            style={'height': '38px',
                                   'width': '300px',
                                   'display': 'inline-block',
                                   'margin-right': '10px',
                                   'margin-top': '20px',
                                   'vertical-align': 'middle'}),
    
                html.H2("Hi-C Contact Normalization Results", className="main-title text-center my-4"),
    
                html.H4("Download User Folder", className="main-title text-center my-4", style={'marginTop': '100px'}),
                dcc.Download(id="download"),
                dbc.Card(
                    [
                        dbc.CardBody([ 
                            html.H6("Instructions:"),
                            dcc.Markdown(instructions, style={'fontSize': '0.9rem', 'color': '#555'})
                        ]),
                        dbc.Button("Download Files", id="download-btn", color="primary", style={'marginTop': '10px'}),
                    ],
                    body=True,
                    className="my-3"
                ),
    
                html.H4("Pearson Correlation Coefficients", className="main-title text-center my-4", style={'marginTop': '100px'}),
                html.Div([
                    dag.AgGrid(
                        id="correlation-table",
                        columnDefs=[
                            {"headerName": "", "field": "Metric", "sortable": True, "filter": True, "width": 200},
                            {"headerName": "Site", "field": "Site", "sortable": True, "filter": True, "width": 200},
                            {"headerName": "Length", "field": "Length", "sortable": True, "filter": True, "width": 200},
                            {"headerName": "Coverage", "field": "Coverage", "sortable": True, "filter": True, "width": 200},
                        ],
                        rowData=correlation_results.to_dict("records"),
                        dashGridOptions={"rowHeight": 47},
                        defaultColDef={"resizable": True, "sortable": True, "filter": True},
                        style={"height": "16vh", "width": "42vw", "margin": "auto"},
                    ),
                ]),
    
                html.H4("Comparison between Normalized and Unnormalized Data", className="main-title text-center my-4", style={'marginTop': '100px'}),
                html.Div([
                    dcc.Graph(
                        id='plot-sites-norm-filtered',
                        figure=px.scatter(
                            filtered_normalized_plot_data,
                            x='Product Sites',
                            y='Contacts',
                            title='Normalized: Product of sites vs. Contacts',
                            labels={'Product Sites': 'Product of Sites (log scale)', 'Contacts': 'Contacts'},
                            hover_data={}
                        ),
                        style={'width': '32%', 'display': 'inline-block'}
                    ),
                    dcc.Graph(
                        id='plot-lengths-norm-filtered',
                        figure=px.scatter(
                            filtered_normalized_plot_data,
                            x='Product Length',
                            y='Contacts',
                            title='Normalized: Product of lengths vs. Contacts',
                            labels={'Product Length': 'Product of Length (log scale)', 'Contacts': 'Contacts'},
                            hover_data={}
                        ),
                        style={'width': '32%', 'display': 'inline-block'}
                    ),
                    dcc.Graph(
                        id='plot-coverage-norm-filtered',
                        figure=px.scatter(
                            filtered_normalized_plot_data,
                            x='Product Coverage',
                            y='Contacts',
                            title='Normalized: Product of coverage vs. Contacts',
                            labels={'Product Coverage': 'Product of Coverage (log scale)', 'Contacts': 'Contacts'},
                            hover_data={}
                        ),
                        style={'width': '32%', 'display': 'inline-block'}
                    )
                ], style={'display': 'flex', 'justify-content': 'space-between'}),
    
                html.Div([
                    dcc.Graph(
                        id='plot-sites-unnorm-filtered',
                        figure=px.scatter(
                            filtered_unnormalized_plot_data,
                            x='Product Sites',
                            y='Contacts',
                            title='Unnormalized: Product of sites vs. Contacts',
                            labels={'Product Sites': 'Product of Sites (log scale)', 'Contacts': 'Contacts'},
                            hover_data={}
                        ),
                        style={'width': '32%', 'display': 'inline-block'}
                    ),
                    dcc.Graph(
                        id='plot-lengths-unnorm-filtered',
                        figure=px.scatter(
                            filtered_unnormalized_plot_data,
                            x='Product Length',
                            y='Contacts',
                            title='Unnormalized: Product of lengths vs. Contacts',
                            labels={'Product Length': 'Product of Length (log scale)', 'Contacts': 'Contacts'},
                            hover_data={}
                        ),
                        style={'width': '32%', 'display': 'inline-block'}
                    ),
                    dcc.Graph(
                        id='plot-coverage-unnorm-filtered',
                        figure=px.scatter(
                            filtered_unnormalized_plot_data,
                            x='Product Coverage',
                            y='Contacts',
                            title='Unnormalized: Product of coverage vs. Contacts',
                            labels={'Product Coverage': 'Product of Coverage (log scale)', 'Contacts': 'Contacts'},
                            hover_data={}
                        ),
                        style={'width': '32%', 'display': 'inline-block'}
                    )
                ], style={'display': 'flex', 'justify-content': 'space-between'})
            ]
        ),
    ])

def register_results_callbacks(app):
    @app.callback(
        Output("download", "data"),
        [Input("download-btn", "n_clicks")],
        [State("user-folder", "data")]
    )
    def download_user_folder(n_clicks, user_folder):
        if not n_clicks:
            raise PreventUpdate
    
        # Path to the user folder
        folder_path = f"output/{user_folder}"
    
        # Create a 7z archive in memory
        memory_file = io.BytesIO()
        with py7zr.SevenZipFile(memory_file, 'w') as archive:
            # Add files to the archive
            for root, _, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    archive.write(file_path, arcname=os.path.relpath(file_path, folder_path))
        memory_file.seek(0)
    
        # Return the 7z file to download
        return dcc.send_bytes(
            memory_file.getvalue(),
            filename=f"{user_folder}.7z"
        )
    
    @app.callback(
        Output('visualization-status', 'data'),
        Input('switch-visualization-results', 'n_clicks'),
        prevent_initial_call=True
    )
    def switch_to_network(n_clicks):
        if n_clicks:
            return 'network'