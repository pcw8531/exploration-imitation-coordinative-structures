# Element-level exploration and imitation in a network-agent model: code and data

[![Code license: MIT](https://img.shields.io/badge/code-MIT-blue.svg)](LICENSE)
[![Data license: CC BY 4.0](https://img.shields.io/badge/data-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](requirements.txt)

Code and data for the manuscript *What makes motor coordinative structures change? Element-level exploration
and imitation in a network-agent model* by Chulwook Park.

Ten Jupyter notebooks reproduce every value, figure and table of the manuscript and its supplementary
information (SI). Seeds are fixed and every value the text uses is printed, so a rerun returns the same
numbers. The notebooks are stored with their printed output, so every value can be read without running
anything. The figures are not stored. Each notebook draws its figures when it is run.

## Layout

| Folder or file | Content |
|---|---|
| `notebooks` | The ten notebooks, one for each figure of the manuscript and four for the SI |
| `src` | The model `eei_model_v3.py`, the check script `verify_notebooks.py` and, in `src/paper1`, the three scripts of the first earlier study |
| `data` | `data/fig3_data`, the open data of Fig. 3 with their licenses and the coupling derived from them, and `data/paper2`, the seven data files of the second earlier study |
| `DATA_SOURCES.md` | The registry of every source of code and data, with its license and the place where it is used |
| `requirements.txt` | The Python packages the notebooks need |
| `CITATION.cff`, `LICENSE` | The reference of this repository and the license of its code |

## Notebooks

| Notebook | Reproduces | Reads | Run time |
|---|---|---|---|
| EEI_fig1_problem_and_checks.ipynb | Fig. 1, the checks of the six analytic results and SI Fig. S1 | no data | under a minute |
| EEI_fig2_topology.ipynb | Fig. 2 and SI Table S3 | no data | about 6 minutes |
| EEI_fig3_control_entropy.ipynb | Fig. 3 and SI Tables S4 and S5 | `data/paper2`, `data/fig3_data` | under a minute |
| EEI_fig4_mechanism.ipynb | Fig. 4 | no data | about 4 minutes |
| EEI_fig5_game.ipynb | Fig. 5 and the degree-share columns of SI Tables S6 and S7 | no data | about 8 minutes |
| EEI_fig6_budget.ipynb | Fig. 6 | no data | about 18 minutes |
| EEI_supp1_copying.ipynb | SI Fig. S2 | no data | about 2 minutes |
| EEI_supp2_lineage.ipynb | SI Figs. S3 and S4 and SI Table S8 | no data | about 7 minutes |
| EEI_supp3_hypotheses.ipynb | SI Figs. S5, S6 and S8 and SI Tables S6 and S7 | no data | about 40 minutes |
| EEI_supp4_regime_map.ipynb | SI Fig. S7 | no data | about 14 minutes |

Run times were measured on a two-core machine. Setting `QUICK = True` in the first cell of a notebook
shortens its runs for a check, and the printed values then differ from the stored ones.

The model of the manuscript, Eqs. 1 to 11 and Eqs. S1 and S2 of the SI, is the file `src/eei_model_v3.py`.
The same code is the model cell of eight notebooks, those of Figs. 1 and 4 to 6 and the four supplementary
notebooks, so each of them runs on its own. The notebook of Fig. 2 holds and runs scripts 01 to 03 of the
first earlier study, and the notebook of Fig. 3 reads the data of the second earlier study with five code
cells of that study. The notebooks call the two earlier studies the first paper and the second paper.

## How to run

1. Install Python 3.13 and the packages of `requirements.txt` with `pip install -r requirements.txt`.
2. Open a notebook in the folder `notebooks` and run all cells.
3. To check the whole repository, run `python src/verify_notebooks.py` from the top folder. The script reruns
   the notebooks and compares every printed line with the stored one. One notebook can be checked by giving
   its name.

The notebooks of Figs. 1, 5 and 6 also write each panel of their figure as PNG, PDF and SVG to the folder
`notebooks/figs`, or to the folder named by the environment variable `FIG_DIR`.

## Requirements

The notebooks were run with Python 3.13, NumPy 2.5, SciPy 1.18, NetworkX 3.7, Matplotlib 3.11, pandas 3.0 and
openpyxl 3.1. Older versions were not tested. The scripts in `data/fig3_data/multisensebadminton/scripts` are
needed only to derive the badminton coupling again from the sensor files, and they also need h5py or pyfive.

## License

The code of this repository is released under the MIT License (`LICENSE`). The data derived here and the text
of this repository are released under the Creative Commons Attribution 4.0 International License
(https://creativecommons.org/licenses/by/4.0/). Data and code taken from other sources keep the licenses of
their sources, which `DATA_SOURCES.md` lists.

## Citation

Please cite the manuscript and this repository. `CITATION.cff` gives the reference of the repository.

Park, C. (2026). What makes motor coordinative structures change? Element-level exploration and imitation in
a network-agent model. Code and data (version 1.0.0).
https://github.com/pcw8531/exploration-imitation-coordinative-structures

The two earlier studies this work builds on:

* Park, C. (2026). Coordinative structures as scale-free networks: Cascade and percolation dynamics in motor
  learning with empirical validation. PLoS Comput. Biol. https://doi.org/10.1371/journal.pcbi.1014523
* Park, C. (2026). Average information across a network quantifies what a coordinative structure achieves in
  motor control. Code and data. Zenodo. https://doi.org/10.5281/zenodo.21789488
