# Registry of data and code sources

Every file of this repository that was not written for this study is listed here with its source, its license
and the place where it is used. Everything else, the ten notebooks, the model, the verification script and the
derived coupling files, was written or computed for this study.

| Source | Files here | Used for | License or terms |
|---|---|---|---|
| Park C (2026). Coordinative structures as scale-free networks: Cascade and percolation dynamics in motor learning with empirical validation. PLoS Comput Biol. https://doi.org/10.1371/journal.pcbi.1014523. Code at https://github.com/pcw8531/Coordinative-structures-scale-free-networks, archived at https://doi.org/10.5281/zenodo.20694466 | `src/paper1/01_network_generation.py`, `02_cascade_dynamics.py`, `03_percolation_robustness.py`, and the same scripts inside `EEI_fig2_topology.ipynb` | Fig. 2 and SI Table S3 | Code of the same author, copied unchanged |
| Park C (2026). Average information across a network quantifies what a coordinative structure achieves in motor control. Code and data. Zenodo. https://doi.org/10.5281/zenodo.21789488 | `data/paper2`, seven files, and five code cells inside `EEI_fig3_control_entropy.ipynb` | Fig. 3, panels A and C, the cortex of panel B, and SI Table S4 | Archive of the same author. Each data file states its own source in its header |
| Weaver NJ, Faskowitz JI, Betzel RF, Lynn CW (2026). Quantifying the compressibility of the human brain. Proc Natl Acad Sci USA 123(4): e2531115123. Matrix `task_covs/cov_MOTOR` of https://github.com/NicholasJWeaver/BrainCompressibility2025 | `data/paper2/cov_MOTOR_matrix.csv` and the two files derived from it, `cortical_coupling_shares.csv` and `cortical_threshold_sweep.csv` | The cortex of Fig. 3B | As distributed by its authors. The matrix is derived from data of the Human Connectome Project, see the note below |
| Schaefer A, Kong R, Gordon EM, Laumann TO, Zuo XN, Holmes AJ, Eickhoff SB, Yeo BTT (2018). Local-global parcellation of the human cerebral cortex from intrinsic functional connectivity MRI. Cereb Cortex 28: 3095-3114. https://doi.org/10.1093/cercor/bhx179. Centroid files of https://github.com/ThomasYeoLab/CBIG | `data/fig3_data/schaefer2018`, three centroid files | Placing the cortical regions in the drawing of Fig. 3B. They enter no value | MIT License, copied in `data/fig3_data/schaefer2018/LICENSE_CBIG.md` |
| Murphy AC, Muldoon SF, Baker D, Lastowka A, Bennett B, Yang M, Bassett DS (2018). Structure, function, and control of the human musculoskeletal network. PLoS Biol 16(1): e2002811. https://doi.org/10.1371/journal.pbio.2002811. Files of the R package PhysioMSKNet, version 0.3.1, https://github.com/x-biosignal/PhysioMSKNet | `data/fig3_data/murphy2018/incidence_matrix.csv`, `supplementaryData.xlsx` | The musculoskeletal map of Fig. 3B and SI Table S4 | Package under the MIT License, copied in `data/fig3_data/murphy2018/LICENSE_PhysioMSKNet.txt`. The workbook belongs to the article, published under CC BY 4.0 |
| Seong M, Kim G, Yeo D, Kang Y, Yang H, DelPreto J, Matusik W, Rus D, Kim S (2024). MultiSenseBadminton: Wearable sensor-based biomechanical dataset for evaluation of badminton performance. Sci Data 11: 343. https://doi.org/10.1038/s41597-024-03144-z. Data at https://doi.org/10.6084/m9.figshare.c.6725706 | `data/fig3_data/multisensebadminton/documentation`, three files of the dataset. The sensor files, 6.55 GB, are not copied here | The muscles of a stroke and the outcome entropy of Fig. 3B, SI Tables S4 and S5 | CC0 |

## Derived here

* `data/fig3_data/multisensebadminton/coupling`, 51 files, one per sensor file of MultiSenseBadminton, written by
  `data/fig3_data/multisensebadminton/scripts/msb_process.py`. Each holds the correlations between the
  electromyography envelopes and between the joint speeds within every stroke. `data/fig3_data/README.md` describes
  the files and the scripts. Released under CC BY 4.0.
* `data/fig3_data/multisensebadminton/archive_members.csv` and `fetch_manifest.csv`, the lists of the sensor files
  in the archives of the dataset, with their sizes and checksums.

## Note on the Human Connectome Project

The cortical matrix of Weaver et al. (2026) was computed by its authors from data of the Human Connectome
Project, which are released under the Open Access Data Use Terms of the project. The project asks that work
using its data carry this acknowledgment.

Data were provided in part by the Human Connectome Project, WU-Minn Consortium (Principal Investigators: David
Van Essen and Kamil Ugurbil; 1U54MH091657) funded by the 16 NIH Institutes and Centers that support the NIH
Blueprint for Neuroscience Research; and by the McDonnell Center for Systems Neuroscience at Washington
University.
