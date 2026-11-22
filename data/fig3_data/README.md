# Data of Fig. 3

The notebook EEI_fig3_control_entropy.ipynb reads this folder, or the folder named by the
environment variable F3_DIR. The ensembles and the cortex of Fig. 3 come from the code of the
second paper, pasted in the notebook, and from its data in the folder data/paper2. Everything else Fig. 3 draws
comes from the three sources below.

## murphy2018

The bone and muscle incidence of the human musculoskeletal network of Murphy et al. (2018).

* Murphy AC, Muldoon SF, Baker D, Lastowka A, Bennett B, Yang M, Bassett DS. Structure, function, and
  control of the human musculoskeletal network. PLoS Biol 16(1): e2002811 (2018).
  https://doi.org/10.1371/journal.pbio.2002811
* incidence_matrix.csv, 173 bones by 270 muscles, 1,010 attachments, and supplementaryData.xlsx, the
  supplementary workbook of the paper, both as distributed in inst/extdata of the R package PhysioMSKNet,
  version 0.3.1 by Yusuke Matsui (https://github.com/x-biosignal/PhysioMSKNet, commit
  4b245c1a2cdc9c5d2b53a774f62537f0f18468b5). MIT license, copied in LICENSE_PhysioMSKNet.txt. The workbook
  belongs to the article, which PLOS Biology publishes under CC BY 4.0.
* The notebook checks that incidence_matrix.csv equals the sheet Table S9 of the workbook entry by entry
  once its row of hyperedge degrees is set aside, and it reads the sheet Table S10, the same muscles mapped
  from a second atlas, as a second reading.

## schaefer2018

The centroids of the 100-parcel cortical atlas of Schaefer et al. (2018), in MNI space at 2 mm, in three
region orders.

* Schaefer A, Kong R, Gordon EM, Laumann TO, Zuo XN, Holmes AJ, Eickhoff SB, Yeo BTT. Local-global
  parcellation of the human cerebral cortex from intrinsic functional connectivity MRI. Cereb Cortex 28,
  3095 to 3114 (2018). https://doi.org/10.1093/cercor/bhx179
* From stable_projects/brain_parcellation/Schaefer2018_LocalGlobal/Parcellations/MNI/Centroid_coordinates of
  the CBIG repository (https://github.com/ThomasYeoLab/CBIG, commit
  634f676630929a71297852d01dd92a287103e861). MIT license, copied in LICENSE_CBIG.md.
* The cortical matrix of the second paper (cov_MOTOR of Weaver et al. 2026) names the atlas but not the
  order of its regions. The notebook shows that the matrix follows the 17-network order and uses the
  centroids only to place the regions in the drawing.

## multisensebadminton

The muscles and joints of badminton strokes from MultiSenseBadminton.

* Seong M, Kim G, Yeo D, Kang Y, Yang H, DelPreto J, Matusik W, Rus D, Kim S. MultiSenseBadminton:
  Wearable sensor-based biomechanical dataset for evaluation of badminton performance. Sci Data 11, 343
  (2024). https://doi.org/10.1038/s41597-024-03144-z
* Data on figshare, collection https://doi.org/10.6084/m9.figshare.c.6725706, CC0. Code of the dataset at
  https://github.com/dailyminiii/MultiSenseBadminton, MIT license.
* documentation holds three files of the Documentations archive of the dataset: the annotation of every
  stroke (start and stop time, stroke type, rating group, landing cell, hitting point and sound), the data
  summary and the skill rating detail.
* coupling holds one file per sensor file, 51 in all, written by scripts/msb_process.py. The sensor files
  themselves, 6.55 GB packed and 12.04 GB unpacked, are not redistributed here. Each .npz file holds

  | key | content |
  |---|---|
  | sub, fname | participant and sensor file |
  | type, skill | stroke type and coach-rated group, from the annotation |
  | n | number of strokes kept, 0 for the calibration file of Sub05 |
  | t0, t1, num | start and stop time of each stroke kept (Unix seconds) and its stroke number |
  | RE | n by 20 by 20 Pearson correlations between the electromyography envelopes of 20 sites within each stroke, forearm channels 1 to 8, upper-arm channels 1 to 8, then rectus femoris, vastus medialis, vastus lateralis and biceps femoris |
  | RJ | n by 21 by 21 Pearson correlations between the angular speeds of 21 joints within each stroke |
  | rates | mean sampling rate of the thigh, forearm and upper-arm electromyography and of the joint rotations in the file |

* fetch_manifest.csv lists the 51 sensor files with their archive, packed and unpacked size and CRC-32, and
  archive_members.csv the members of the released archives that hold them.
* scripts
  * msb_probe.py lists the members of the released archives on figshare without downloading them.
  * msb_fetch.py copies the sensor files alone, by ranged requests, into one zip per file, and checks each
    against the CRC-32 of its archive.
  * msb_coupling.py cuts every annotated stroke out of a sensor file, prepares the envelopes and joint speeds
    on a 50 Hz grid and correlates them.
  * msb_process.py runs msb_coupling.py over the sensor files and writes the coupling folder:
    `python msb_process.py documentation coupling path/to/MSB_hdf5/*/*.zip`.
  The scripts need NumPy, SciPy, pandas with openpyxl, and h5py or the pure-Python pyfive. Rerun on the
  released files, they return the coupling folder exactly.
