# Cenergy3

This is our developed approach and openly released software that automate the generation of digital 3D urban energy model from open data. We synthesize data from OpenTopography, OpenStreetMap, and Overture Maps in generating 3D models. The rendered model visualizes and contextualizes distribution power grids alongside the built environment and transportation networks. Our developed software, including an open python library and a free [API](https://arxiv.org/pdf/2512.06459), provides interactive figures for the 3D models. The rendered models are essential for analyzing infrastructure alignment and spatially linking energy demand nodes (buildings) with energy supply (utility grids). The developed API leverages standard Web Mercator coordinates (EPSG:3857) and JSON serialization to ensure interoperability within smart city and energy simulation platforms. We also provide a [graphic user interface (GUI)](https://sites.google.com/view/cenergy3/home) where end-users can access our API via a cloud-based server, regardless of their programming skills and what devices and platforms their are using.

# How to use Cenergy3?

Below is a python programming example in Google Colab environment:

```python
!pip install cenergy

from cenergy3 import generate_3d_model, plot_3d_model, save_3d_model

api_key = "123456789123456789123456789" # please change to your own OpenTopography API key, which is free can can be obtained from http://opentopography.org/
target_place = "Rousay-Orkney Islands-Scotland" # You can change to the name of the place you want

fig_json = generate_3d_model(api_key=api_key, target_place=target_place)
plot_3d_model(fig_json)
save_3d_model(fig_json)


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
