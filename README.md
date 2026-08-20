# Computational fluid dynamics analysis of pottery kiln morphology: a case study from Hanseong-period Baekje, Korea

## Author
- Ju, Chanhyeok (Researcher, Seoul National Research Institute of Cultural Heritage)

## Information
This repository organises the case files, code, data and figures used in the study *Computational fluid dynamics analysis of pottery kiln morphology: a case study from Hanseong-period Baekje, Korea*.

The computation is divided into two models. A three-dimensional flow computation on a scale of seconds obtains the path and the temperature of the heated gas reaching the ware chamber, and a reduced-order model covering the whole firing operation receives the convective heat transfer coefficient and the effective hot area from the former and computes the fuel consumption and the temperature on the scale of the whole operation.

The repository is structured into seven directories:
- `mesh` : The nine STL surfaces used in the analysis.
- `cases` : OpenFOAM case dictionaries for the three firebox forms.
- `cfd` : Script that measures the penetration depth.
- `rom` : The reduced-order model and the scripts that drive it.
- `Rscripts` : Includes R code for graph generation.
- `Results` : Stores the final visual outputs produced.
- `Data` : Contains the measured series that drive the model and the tabulated results used by the R code.

Reproducing the whole set takes several hours: about 20 minutes per CFD case and ten to forty minutes per reduced-order script on a desktop machine.

## CFD

### Requirements
```
OpenFOAM v2312
Python 3 (standard library only; no external packages)
ParaView / pvbatch   (required only for flame_penetration.py)
```

### 1. Mesh and solve
The nine STL surfaces used in the analysis are deposited in `mesh` as gzip-compressed ASCII (`.stl.gz`, 6.4 MB in total), and the dictionaries deposited in `cases` are the ones actually used. Only the surface has to be placed inside each case.

```bash
for m in A:A_horizontal_unstepped B:B_horizontal_stepped C:C_vertical_stepped; do
    s=${m%%:*}; d=${m##*:}
    mkdir -p cases/$d/constant/triSurface
    gunzip -c mesh/kiln_${s}_L065.stl.gz > cases/$d/constant/triSurface/kiln.stl
done

cd cases/A_horizontal_unstepped
blockMesh && snappyHexMesh -overwrite && topoSet && buoyantPimpleFoam
```
`topoSet` creates the `fuelbed` cell zone on which the volumetric heat source of `constant/fvModels` acts, and must not be skipped. One case takes about 20 minutes and writes 46 time directories.

### 2. Penetration depth
The maximum x of the 1,000 °C isosurface is extracted at each of the 46 time steps.

```bash
pvbatch cfd/flame_penetration.py
```

### 3. Reduced-order model
The model does not take the quantity of fuel as an input; it iteratively computes the fuel input rate required to reproduce the heating curve of the Yangsan Hogye-dong kiln 2 experiment. The calibration must be run first, as it writes `Results/rom_phi.csv`, which every subsequent script reads.
```bash
python3 rom/run.py
```
By default this adopts the firemouth opening ratios of `Data/phi_calibration.csv`, the fit on which the published figures rest. To solve the inverse problem again instead:

```bash
REFIT=1 python3 rom/run.py
```
Refitting reproduces the first five intervals to four decimal places but returns a value about 2 % lower for the 52–78 h hold, because over that plateau a range of opening ratios reproduces 1,140 °C equally well. The absolute fuel figures then come out about 1 % lower throughout, while the differences between forms and between lengths are unchanged. Each of the following corresponds to one table in the paper. Each takes roughly ten minutes.

```bash
python3 rom/efficiency.py         # fuel by firebox form            -> rom_efficiency.txt
python3 rom/form_axial.py         # axial temperature by form        -> rom_form_axial.txt
python3 rom/length_study.py       # fuel and spread by length        -> rom_length.txt
python3 rom/study_data.py         # the three series plotted in R    -> study_*.csv
python3 rom/sensitivity.py        # sensitivity to the assumed values -> rom_sensitivity.txt
python3 rom/ware_sensitivity.py   # sensitivity to the heat capacity of the load
```

### Input data
Three files in `Data` drive the reduced-order model. `fuel_schedule.csv` is the heat release schedule after Hong (2011). `heating_curve_Hong2011.csv` is the heating curve of the Yangsan Hogye-dong kiln 2 experiment read off the published graph; it is a graph reading, not the original tabulated figures, and carries roughly ±30 °C and ±1 h. `cfd_calibration.csv` holds the mass flow rate, bulk temperature, outlet temperature and wall loss of each firebox form, averaged over the last 2,000 iterations of the steady-state runs. Those solver logs are about 17 MB each and are not deposited, so the four averaged quantities are given directly; without them the model cannot distinguish form C and silently substitutes form B. `phi_calibration.csv` holds the firemouth opening ratio fitted against the measured heating curve, described in step 4 above.

### Viewing in ParaView
ParaView recognises a case when an empty `.foam` file is placed inside it.

```bash
touch cases/A_horizontal_unstepped/case.foam
```
Note that ParaView decomposes polyhedral cells by default, so the cell count is reported as **117,649**, whereas the actual mesh has **52,755** cells. Turning off `Decompose polyhedra` in the reader gives the latter, which is the range of 5.3–5.6 × 10⁴ stated in the paper.

## R Script

The figures of the Discussion were produced in an `R` environment and are saved as `.R` files, with each figure documented in a separate file. Each script reads the tabulated results from `Data`, fits the regressions with `lm()` and writes both TIFF and JPEG to `Results`.

### Requirements
```
R version 4.3.3
ggplot2   3.5.2
here      1.0.1
patchwork 1.3.2
png       0.1.8
```
```R
install.packages(c("ggplot2", "here", "patchwork", "png"))
```

### Scripts
| Script | Figure | Data |
| --- | --- | --- |
| `Fig_Form.R` | Fuel and penetration depth by firebox form | `Kiln_Form.csv` |
| `Fig_Length.R` | Fuel and front-to-back temperature difference by ware chamber length | `Kiln_Length.csv` |
| `Fig_Steps.R` | Fuel by number of steps, paired with the firing-colour photograph | `Kiln_Steps.csv` |

```R
source("Rscripts/Fig_Form.R")
source("Rscripts/Fig_Length.R")
source("Rscripts/Fig_Steps.R")
```

### Source of the data
| CSV | Origin |
| --- | --- |
| `Kiln_Form.csv` (fuel) | `rom/study_data.py` → `Results/study_form.csv` |
| `Kiln_Form.csv` (penetration) | `cfd/flame_penetration.py`, t ≈ 43 s |
| `Kiln_Length.csv` | `rom/study_data.py` → `Results/study_length.csv` |
| `Kiln_Steps.csv` | `rom/study_data.py` → `Results/study_steps.csv` |