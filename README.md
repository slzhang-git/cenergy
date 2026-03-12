# Cenergy3

This is our developed approach and openly released software that automate the generation of digital 3D urban energy model from open data. We synthesize data from OpenTopography, OpenStreetMap, and Overture Maps in generating 3D models. The rendered model visualizes and contextualizes distribution power grids alongside the built environment and transportation networks. Our developed software, including an **open python library** and **a free [API](https://arxiv.org/pdf/2512.06459)**, provides interactive figures for the 3D models. The rendered models are essential for analyzing infrastructure alignment and spatially linking energy demand nodes (buildings) with energy supply (utility grids). The developed API leverages standard Web Mercator coordinates (EPSG:3857) and JSON serialization to ensure interoperability within smart city and energy simulation platforms. We also provide a **graphic user interface [(GUI)](https://sites.google.com/view/cenergy3/home)** where end-users can access our API via a cloud-based server, regardless of their programming skills and what devices and platforms their are using. Below we explain how to use our software package through Python and MATLAB programming. If you do not want to deal with coding, then just visit our [GUI](https://sites.google.com/view/cenergy3/home) and you can get 3D models conveniently.

Below are two examples of the resulted 3D models, where white lines indicate road networks, light blue blocks represents buildings, and red lines are power lines. The example in the left is for the place of **Rousay, Orkney Islands, Scotland**. According to the log of our API, for this area, we collect 129,652 records of elevations, 988 road segments, 36 power lines, and 716 buildings with height. The example in the right is for the place of **Avalon, Los Angeles County, United States**. According to the log of our API, for this area, we collect 9,494 records of elevations, 929 road segments, 4 power lines, and 1,285 buildings with height. 

<img width="414" height="201" alt="Rousay_python" src="https://github.com/user-attachments/assets/b1551ed1-8c7f-46cc-9cb2-d0c69c2eb88c" />

<img width="416" height="256" alt="Avalon_example_matlab" src="https://github.com/user-attachments/assets/666ee3ba-5807-4994-a516-ca40f5a156d5" />

Note that the raw visualization is in high resolution, see here for the 3D model example of [Kurnell, Sydney, Australia](https://slzhang-git.github.io/Example-for-Kurnell-Sydney-Australia/3d_visualization_Kurnell_Sydney_Australia.html).

**Citation for our work**:

Shiliang Zhang, Sabita Maharjan, "Cenergy3: An API for city energy 3D modeling," _arXiv preprint arXiv:2512.06459_, 2026. [10.48550/arXiv.2512.06459](https://doi.org/10.48550/arXiv.2512.06459)

BibTex:<br>
@article{zhang2025cenergy3,<br>
  title={Cenergy3: An API for city energy 3D modeling},<br>
  author={Zhang, Shiliang and Maharjan, Sabita},<br>
  journal={arXiv preprint arXiv:2512.06459},<br>
  doi={10.48550/arXiv.2512.06459},<br>
  year={2025}<br>
}

# How to use Cenergy3?

**Below is a python programming example for using our released Python library, in Google Colab environment:**

```python
!pip install cenergy

from cenergy3 import generate_3d_model, plot_3d_model, save_3d_model

api_key = "123456789123456789123456789" # please change to your own OpenTopography API key, which is free can can be obtained from http://opentopography.org/
target_place = "Rousay-Orkney Islands-Scotland" # You can change to the name of the place you want

fig_json = generate_3d_model(api_key=api_key, target_place=target_place)
plot_3d_model(fig_json)
save_3d_model(fig_json)
```

**We also provide the programming examples below that you can access our API via Python or MATLAB:**

Python example:

```python
import requests
import json
from io import StringIO

api_key = '111222333444555666777888999'   
# Replace it by your OpenTopography API key, which is free from https://opentopography.org
target_place = 'Måøyna-Gulen-Vestland-Norway' 
# This is just an example of the place name, please replace the name in your case

# Below we show how to construct the url for the request to our API
BASE_URL = "https://cenergy3-qjbps.ondigitalocean.app"
api_request_url = f"{BASE_URL}/{api_key}/{target_place}"

# Fetch data from API by sending a request
try:
    response = requests.get(api_request_url)
    response.raise_for_status() # Check for the status of the request
    figure_dict = response.json()   # Gain the requested data in json format
except requests.exceptions.RequestException as e:
    print(f"Error fetching data: {e}")

import plotly.graph_objects as go

try:
    fig = go.Figure(figure_dict)
    fig.show()  # Display the interactive figure for the 3D model
except Exception as e:
    print(f"\nError in displaying the requested data: {e}")
```
MATLAB example:

```matlab
api_key = '111222333444555666777888999'; % Please replace it
target_place = 'Kurnell, Sydney, Australia';
BASE_URL = "https://cenergy3-qjbps.ondigitalocean.app"; 
api_endpoint_url = sprintf('%s/%s/%s', BASE_URL, api_key, target_place);
disp(['Fetching data from: ' api_endpoint_url]);
% Fetch data from API 
try
    options = weboptions('RequestMethod', 'get', 'ContentType', 'text', 'Timeout', 3000);
    response_text = webread(api_endpoint_url, options);
    figure_struct = jsondecode(response_text);
    disp(' ');
    disp('Successfully fetched and decoded the JSON structure.');
catch ME % Catch errors
    disp(' ');
    disp(['Error during data fetching or processing: ' ME.message]);
end

% Read JSON file in a browser
outHtml = fullfile('3D_visualization.html');
htmlTemplate = [...
'<!doctype html>\n' ...
'<html>\n' ...
'<head>\n' ...
'  <meta charset="utf-8">\n' ...
'  <title>Plotly JSON Viewer</title>\n' ...
'  <!-- Load Plotly from CDN -->\n' ...
'  <script src="https://cdn.plot.ly/plotly-2.29.1.min.js"></script>\n' ...
'  <style>body{margin:0;font-family:Arial,Helvetica,sans-serif} #plot{width:100vw;height:100vh;}</style>\n' ...
'</head>\n' ...
'<body>\n' ...
'  <div id="plot"></div>\n' ...
'  <script>\n' ...
'    // The JSON figure object is inserted below. It should be an object with "data" and optionally "layout" and "frames".\n' ...
'    var fig = '];
htmlTail = [...
';\n' ...
'    // If fig is an array of traces, convert to {data: fig}\n' ...
'    if (Array.isArray(fig)) {\n' ...
'      Plotly.newPlot("plot", fig, {});\n' ...
'    } else if (fig && fig.data) {\n' ...
'      var layout = fig.layout || {};\n' ...
'      var config = fig.config || {};\n' ...
'      Plotly.newPlot("plot", fig.data, layout, config);\n' ...
'    } else {\n' ...
'      // If the structure is unexpected, try to print it and attempt to plot\n' ...
'      console.warn("Loaded JSON not recognized as Plotly figure. Attempting to plot if possible.");\n' ...
'      try { Plotly.newPlot("plot", fig, {}); } catch(e){ document.getElementById("plot").innerText = "Unable to render JSON as Plotly figure. See console for details."; console.error(e); }\n' ...
'    }\n' ...
'  </script>\n' ...
'</body>\n' ...
'</html>\n'];
% Combine and write HTML
fid = fopen(outHtml, 'w', 'n', 'UTF-8');
if fid == -1, error('Cannot create output HTML file: %s', outHtml); end
fprintf(fid, htmlTemplate); 
fprintf(fid, '%s', figure_struct); 
fprintf(fid, htmlTail);  
fclose(fid);
% Open in system browser
fprintf('Wrote HTML to: %s\n', outHtml);
web(outHtml, '-browser'); 
```
