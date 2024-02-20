import dash
from dash import dcc
from dash import html
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import trimesh
import base64
import zipfile
import io
from PIL import Image
import subprocess
import os
import dash_bootstrap_components as dbc 

app = dash.Dash(__name__)

app.layout = html.Div([
    html.H1("STL File Segmentation App"),

    dcc.Upload(
        id='stl-upload',
        children=html.Div([
            'Drag and Drop or ',
            html.A('Select STL .zip File')
        ]),
        multiple=False  # Allow only one file to be uploaded
    ),

    dcc.Loading(
        id="loading-stl",
        type="default",
        children=[
            html.Div(id='stl-3d-viewers', className="row-container"),
            html.Div(id='error-output', style={'color': 'red'}, className="row-container"),
        ],
    ),

    html.Button("Segment STL", id="segment-button", n_clicks=0),  # Add a button

    dbc.Button("Open Configuration", id="config-button", n_clicks=0),
    
    dbc.Modal([
        dbc.ModalHeader("Configuration"),
        dbc.ModalBody([
            dcc.Input(id='number-input', type='number', min=1, max=3, placeholder='Enter a number between 1 and 3'),
            dcc.Checklist(id='complex-checkbox', options=[{'label': 'Complex', 'value': 'complex'}]),
        ]),
        dbc.ModalFooter([
            dbc.Button("Save", id="save-button"),
            dbc.Button("Close", id="close-button", className="ml-auto"),
        ]),
    ], id="config-modal", is_open=False),

    dcc.Graph(id='segmented-stl-viewer'),  # Display the segmented STL file

    html.Div(id='segment-output'),  # Display the segmentation output

    html.Button("Show Segmentation Results", id="show-results-button", n_clicks=0),  # Add a button to display results

    html.Div(id='segmentation-results'),  # Display segmentation results

    dbc.Button("Add Labels", id="add-labels-button", n_clicks=0),  # Add a button to open a dialog
    dcc.Loading(
        id="loading-labels",
        type="default",
        children=[
            dcc.Upload(
                id='label-upload',
                style={'display': 'none'},  # Hidden by default
                multiple=False
            ),
        ],
    ),

    html.Div(id='label-output')  # Display label output
], className="main-container")

@app.callback(
    [Output('stl-3d-viewers', 'children'), Output('error-output', 'children')],
    [Input('stl-upload', 'contents')],
    [State('stl-upload', 'filename')]
)
def load_stl_files(contents, filename):
    if contents is None:
        raise PreventUpdate

    try:
        # Check if the uploaded file is a .zip archive
        if not filename.endswith(".zip"):
            raise Exception("Please select a .zip file containing .stl files.")
        content_type, content_string = contents.split(',')

        decoded = base64.b64decode(content_string)
        zfile = zipfile.ZipFile(io.BytesIO(decoded))
        # Extract the .stl files from the .zip archive
        stl_files = [file for file in zfile.namelist() if file.lower().endswith('.stl')]
        if not stl_files:
            raise Exception("No .stl files found in the .zip archive.")

        viewers = []
        errors = []
        upper_files = [f for f in stl_files if f.endswith("_u.stl")]
        lower_files = [f for f in stl_files if f.endswith("_l.stl")]
        for upper_filename in upper_files:
            # Find corresponding "_l.stl" file
            matching_lower_files = [f for f in lower_files if upper_filename[:-6] in f]
            if matching_lower_files:
                lower_filename = matching_lower_files[0]
            else:
                errors.append(f"No matching '_l.stl' file found for '{upper_filename}'")
                continue

            upper_content = contents[stl_files.index(upper_filename)]
            lower_content = contents[stl_files.index(lower_filename)]

            try:
                upper_mesh = trimesh.load_mesh(upper_filename)
                lower_mesh = trimesh.load_mesh(lower_filename)

                if isinstance(upper_mesh, trimesh.Trimesh) and isinstance(lower_mesh, trimesh.Trimesh):
                    layout = {
                        'scene': {
                            'xaxis': {'showticklabels': False, 'showbackground': False, 'title': ''},
                            'yaxis': {'showticklabels': False, 'showbackground': False, 'title': ''},
                            'zaxis': {'showticklabels': False, 'showbackground': False, 'title': ''},
                            'grid': {'visible': False},
                            'colorscale': 'Viridis',  # Remove colorscale
                        }
                    }

                    # Set 'hoverinfo' to 'none' to remove coordinate display
                    upper_figure = {
                        'data': [{
                            'type': 'mesh3d',
                            'x': upper_mesh.vertices[:, 0],
                            'y': upper_mesh.vertices[:, 1],
                            'z': upper_mesh.vertices[:, 2],
                            'intensity': upper_mesh.vertices[:, 2],
                            'i': upper_mesh.faces[:, 0],
                            'j': upper_mesh.faces[:, 1],
                            'k': upper_mesh.faces[:, 2],
                            'opacity': 1,
                            'hoverinfo': 'none'  # Remove coordinate display
                        }],
                        'layout': layout
                    }

                    lower_figure = {
                        'data': [{
                            'type': 'mesh3d',
                            'x': lower_mesh.vertices[:, 0],
                            'y': lower_mesh.vertices[:, 1],
                            'z': lower_mesh.vertices[:, 2],
                            'intensity': lower_mesh.vertices[:, 2],
                            'i': lower_mesh.faces[:, 0],
                            'j': lower_mesh.faces[:, 1],
                            'k': lower_mesh.faces[:, 2],
                            'opacity': 1,
                            'hoverinfo': 'none'  # Remove coordinate display
                        }],
                        'layout': layout
                    }

                    upper_viewer = dcc.Graph(figure=upper_figure, className="viewer")
                    lower_viewer = dcc.Graph(figure=lower_figure, className="viewer")

                    # Create a row of upper and lower viewers
                    viewer_row = html.Div([upper_viewer, lower_viewer], className="viewer-row")
                    viewers.append(viewer_row)
                else:
                    errors.append(f'Invalid mesh format for file: {upper_filename} or {lower_filename}')

            except Exception as e:
                errors.append(f'Error loading file: {upper_filename} or {lower_filename} - {str(e)}')

        jpg_files = [file for file in zfile.namelist() if file.lower().endswith('.jpg') and ("front" in file.lower() or "left" in file.lower() or "right" in file.lower())]
        images = [html.Img(src=f'data:image/jpeg;base64,{base64.b64encode(zfile.read(jpg_file)).decode()}', width="400") for jpg_file in jpg_files]

        # Create a row of images
        image_row = html.Div(images, className="image-row")
        viewers.append(image_row)

        return viewers, errors

    except Exception as e:
        return [], str(e)
# Add a callback for the "Segment STL" button click
@app.callback(
    [Output('segmented-stl-viewer', 'figure'), Output('segment-output', 'children')],
    Input('segment-button', 'n_clicks'),
    State('stl-upload', 'contents'),
    State('stl-upload', 'filename')
)
def segment_stl_files(n_clicks, contents, filename):
    if n_clicks == 0 or contents is None:
        raise PreventUpdate

    try:
        # Check if the uploaded file is a .zip archive
        if not filename.endswith(".zip"):
            return None, "Please select a .zip file containing .stl files for segmentation."

        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        zfile = zipfile.ZipFile(io.BytesIO(decoded))

        # Extract the .stl files from the .zip archive
        stl_files = [file for file in zfile.namelist() if file.lower().endswith('.stl')]
        if not stl_files:
            return None, "No .stl files found in the .zip archive for segmentation."

        # Check that there are at least two .stl files for segmentation
        if len(stl_files) < 2:
            return None, "Please provide at least two .stl files for segmentation."

        # Get the file paths of the first two STL files for segmentation
        file1_stl = stl_files[0]
        file2_stl = stl_files[1]

        # Run the 'segment.py' script with the file paths as arguments
        cmd = ["python", "segment.py", file1_stl, file2_stl]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            # 'segment.py' script ran successfully
            # Load and display the segmented STL file
            segmented_stl_path = "segmented.stl"
            segmented_mesh = trimesh.load_mesh(segmented_stl_path)
            layout = {
                'scene': {
                    'xaxis': {'showticklabels': False, 'showbackground': False, 'title': ''},
                    'yaxis': {'showticklabels': False, 'showbackground': False, 'title': ''},
                    'zaxis': {'showticklabels': False, 'showbackground': False, 'title': ''},
                    'grid': {'visible': False},
                    'colorscale': 'Viridis',  # Remove colorscale
                }
            }
            segmented_figure = {
                'data': [{
                    'type': 'mesh3d',
                    'x': segmented_mesh.vertices[:, 0],
                    'y': segmented_mesh.vertices[:, 1],
                    'z': segmented_mesh.vertices[:, 2],
                    'intensity': segmented_mesh.vertices[:, 2],
                    'i': segmented_mesh.faces[:, 0],
                    'j': segmented_mesh.faces[:, 1],
                    'k': segmented_mesh.faces[:, 2],
                    'opacity': 1,
                    'hoverinfo': 'none'  # Remove coordinate display
                }],
                'layout': layout
            }
            return segmented_figure, "Segmentation completed successfully."
        else:
            # 'segment.py' script encountered an error
            return None, "Error during segmentation: " + result.stderr

    except Exception as e:
        return None, "Error during segmentation: " + str(e)
    

# Add a callback for the "Show Segmentation Results" button click
@app.callback(
    Output('segmentation-results', 'children'),
    Input('show-results-button', 'n_clicks'),
    prevent_initial_call=True  # Prevent initial call when the app starts
)
def show_segmentation_results(n_clicks):
    if n_clicks is None:
        return None

    # Replace this section with your logic to display segmentation results (e.g., images)
    result_images = []
    result_directory = r"C:\Users\Emman\Desktop\JE\Ortho\Ortho\STL-Segmentation\segmentation_results" # Directory where segmentation results are stored

    if os.path.exists(result_directory) and os.path.isdir(result_directory):
        for image_file in os.listdir(result_directory):
            if image_file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                # Assuming image files are in the directory, you may adjust the criteria
                image_path = os.path.join(result_directory, image_file)
                buf = io.BytesIO()
                im=Image.open(image_path)
                im.save(buf,format='png')
                result_images.append(html.Img(src=f'data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}', width="400"))
    if not result_images:
        return "No segmentation results to display."

    return result_images

@app.callback(
    Output('label-upload', 'style'),
    Output('label-output', 'children'),
    Input('add-labels-button', 'n_clicks'),
    Input('label-upload', 'contents'),
    State('label-upload', 'style')
)
def open_label_dialog(n_clicks, label_upload_contents, label_upload_style):
    if n_clicks % 2 == 1:
        # Read and display the image for labeling
        image_path = r"C:\Users\Emman\Desktop\JE\Ortho\STL-Segmentation\2DTeeth.png"  # Path to the image you want to open
        with open(image_path, 'rb') as img_file:
            image_bytes = base64.b64encode(img_file.read()).decode()
        
        image_element = html.Img(src=f'data:image/jpeg;base64,{image_bytes}', width="400")
        
        # Toggle the 'display' style of the label upload component to show the dialog
        label_upload_style = {'display': 'block'}
        return label_upload_style, [image_element]
    else:
        # Hide the dialog and display the label output
        label_upload_style = {'display': 'none'}
        return label_upload_style, None
    
    
def process_uploaded_labels(contents, filename):
    if contents is None:
        raise PreventUpdate

    # Process the uploaded labels here and save the coordinates to a CSV file
    decoded = base64.b64decode(contents.split(',')[1])
    img = Image.open(io.BytesIO(decoded))

    # For demonstration purposes, let's assume you select points by clicking on the image.
    # You can modify this logic to suit your needs.

    # Example: Get X and Y components of selected points (assumes a list of points in the format [(x1, y1), (x2, y2), ...])
    selected_points = [(100, 200), (300, 400)]  # Replace with your logic

    # Convert the selected points to a DataFrame
    df = pd.DataFrame(selected_points, columns=['X', 'Y'])

    # Save the DataFrame as a CSV file
    csv_filename = 'labels.csv'
    df.to_csv(csv_filename, index=False)

    # Return a message to indicate that the labels are saved
    return f"Labels saved to {csv_filename}"
@app.callback(
    Output("config-modal", "is_open"),
    [Input("config-button", "n_clicks"), Input("save-button", "n_clicks"), Input("close-button", "n_clicks")],
    [State("config-modal", "is_open")]
)
def toggle_modal(n1, n2, n3, is_open):
    if n1 or n2 or n3:
        return not is_open
    return is_open

@app.callback(
    Output('config-output', 'children'),
    Input('save-button', 'n_clicks'),
    State('number-input', 'value'),
    State('complex-checkbox', 'value')
)
def save_configuration(n_clicks, number_value, checkbox_value):
    if n_clicks:
        # Do something with the saved configuration
        config_output = f"Saved Configuration: Number = {number_value}, Complex = {'Complex' if 'complex' in checkbox_value else 'Not Complex'}"
        #open file
        with open(r"C:\Users\Emman\Desktop\JE\Ortho\Ortho\STL-Segmentation\config.txt", 'w') as file:
            file.write(config_output)
        #convert variable to string
        file.write(config_output)
        return config_output

    raise PreventUpdate

if __name__ == '__main__':
    app.run_server(debug=True)