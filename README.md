# Computational fluid dynamics analysis of pottery kiln morphology: a case study from Hanseong-period Baekje, Korea

## Author
- Ju, Chanhyeok (Ph.D Student, Soongsil University)

## Information
This repository contains everything needed to reproduce the computations of the study *Computational fluid dynamics analysis of pottery kiln morphology: a case study from Hanseong-period Baekje, Korea*: the geometry generator, the OpenFOAM cases, the reduced-order model, the numerical checks, the scripts that draw every figure and supporting table, and the outputs and solver logs of the published run.

The computation is divided into two models. Steady three-dimensional flow computations at a calibration point give the effective hot area and the reference convective coefficient of each firebox form; a reduced-order model of the whole 78 h firing receives these two quantities and computes the fuel and the temperatures. Transient flow computations over the first 45 s compare how far the hot gas enters the ware chamber.

Versions: the tag `Article` is the version deposited with the original submission. The current version corresponds to the revised manuscript.

The repository keeps the seven directories of the first version:

| Directory | Contents |
| --- | --- |
| `mesh` | The STL surfaces (`.stl.gz`), the geometry generator that creates them, the meshing dictionaries and scripts, and the scripts that draw the geometry figures |
| `cases` | OpenFOAM cases: transient (`A_horizontal_unstepped`, `B_horizontal_stepped`, `C_vertical_stepped`) and steady calibration (`*_steady`) |
| `cfd` | Scripts that run the cases, post-process them (penetration of the 1,000 °C isotherm, temperature panels), and set up and summarise the numerical checks |
| `rom` | The reduced-order model, its calibration, the comparisons, the sensitivity analysis and the energy balance |
| `Rscripts` | R scripts of the graphs, and the scripts that prepare their data, run all figures and write the supporting tables |
| `Results` | Outputs of the published run: tables and summaries, figure panels, supporting tables and compressed logs of all computations |
| `Data` | Measured series that drive the model, and the tables plotted by the R scripts |

Top-level files: `run_all.sh` (the whole workflow), `verify.py` (compares a run with the values reported in the article), `paths.sh` (locations of the tools), `setup_env.sh` and `kiln-explicit.txt` (Python and R environments).

## Requirements
```
OpenFOAM v2312 (openfoam.com)   blockMesh, snappyHexMesh, buoyantSimpleFoam, buoyantPimpleFoam, mpirun
ParaView 5.10 (pvbatch)         penetration depth and temperature panels; needs a display (DISPLAY)
micromamba                      installs the Python and R environments below
Python 3 (system)               reduced-order model and post-processing (standard library only)
xz                              log archive
```
The locations of OpenFOAM and ParaView are set in `paths.sh` (`KILN_OPENFOAM_BASHRC`, `KILN_PVBATCH`) and can be overridden by environment variables of the same names. The published run used 20 cores; the numerical checks run up to 16 processes at a time (`KILN_BUDGET`).

```bash
bash setup_env.sh      # env/kiln: Python 3.11 + numpy; R 4.3.3 + ggplot2 3.5.2, here 1.0.1, patchwork 1.3.2, png, jpeg
                       # env/doc : Python 3.11 + openpyxl 3.1.5 (supporting tables)
```
`kiln-explicit.txt` fixes every package of `env/kiln` (linux-64); `bash setup_env.sh --solve` fixes only the main packages.

### Fonts
The figures use Times New Roman, which cannot be redistributed. Place `times.ttf` (and `timesbd.ttf`) in a folder `fonts/` at the top level. Without it the figures are drawn with another serif font; the numbers are unaffected.

## Running
```bash
bash run_all.sh                    # everything, about 13 h on 20 cores
bash run_all.sh rom figures        # selected steps
```

| Step | Script | What it does | Time |
| --- | --- | --- | --- |
| `geometry` | `mesh/make_stl.sh` | Unpacks `mesh/*.stl.gz` to `mesh/stl/`, regenerates every STL with the generator and checks it against the deposited one | 10 s |
| `mesh` | `mesh/make_mesh.sh` | blockMesh → snappyHexMesh → checkMesh for A, B, C; copies the mesh into the steady and transient cases | 30 s |
| `steady` | `cfd/run_steady.sh` | Steady calibration computations (150 kW, firemouth fully open) | 30 min |
| `transient` | `cfd/run_transient.sh` | Transient computations from a cold kiln (163.3 kW, 0.10 kg/s, 45 s) | 30 min |
| `transient-np` | `cfd/run_transient_np.sh` | The same transient computations with 4, 8 and 10 parallel subdomains (the base run uses 6) | 100 min |
| `cfd-post` | `cfd/post/flame_penetration.py`, `penetration_max.py` | Penetration of the 1,000 °C isotherm and its maximum within 45 s | 1 min |
| `rom` | `rom/run_rom.sh` | Calibration, opening ratios, comparisons of forms, lengths and steps, sensitivity (27 cases), energy balance | 90 min |
| `checks` | `cfd/checks/*` | Finer grids, maximum Courant number 2, operating points, temperature-limiter swap; convergence, grid quality and balances | 8 h |
| `figures` | `Rscripts/make_figures.sh` | Figure panels and graphs | 30 min |
| `supporting` | `Rscripts/make_supporting.py`, `S1_Fig.R` | S1–S8 Table, S1 Fig | 1 min |
| `logs` | `cfd/archive_logs.sh` | Compresses all logs into `Results/logs` | 5 min |
| `verify` | `verify.py` | Compares the run with the values of the article | 1 s |

Each step writes its console output to `Results/run/<step>.log`.

Without the flow computations, the reduced-order model can be rerun from the deposited solver logs: `bash run_all.sh geometry rom verify`. The calibration then reads `Results/logs/cases/*_steady/log.solver.xz` and checks that the case dictionaries are those of the logged runs.

### Logs
`Results/logs` holds the logs of every computation reported in the article, compressed with xz, at the path of the case they come from: `cases/A_horizontal_unstepped_steady/log.solver` → `Results/logs/cases/A_horizontal_unstepped_steady/log.solver.xz`; the numerical checks are under `Results/logs/checks/`. `log.inputs.md5` records the dictionaries and the mesh with which each case was solved. Read a log with `xz -dc <file>`. The computed fields (time directories) are not deposited because of their size; they are regenerated by running the cases.

### Reproducibility
The reduced-order model is deterministic. The flow computations give the same results with the same build of OpenFOAM and the same decomposition. In form C the 1,000 °C isotherm advances and retreats, and its position at a given time depends on the parallel decomposition; the article therefore reports the range over four decompositions. `verify.py` accepts values derived from the flow computations within the tolerances stated in the script.

## Article ↔ outputs
Figures are produced as separate panels; their arrangement and lettering in the article were done afterwards. The folder names of the panels follow the numbering of the original submission.

| Article | Output (`Results/`) | Script ← data |
| --- | --- | --- |
| Fig 1 Longitudinal section | `figures/section/Fig_Section`, `Firebox_A/B/C` | `Rscripts/Fig_Section.R` ← `mesh/section_data.py` (generator `mesh/kiln_geometry.py`) |
| Fig 2 Geometry by firebox form | `figures/fig1_forms_3d` | `mesh/render_geometry_panels.py` ← `mesh/stl` |
| Fig 3 CFD by firebox form | `figures/fig2_cfd_panels`, `figures/colorbar_0-1200C.png` | `cfd/post/render_panels.py`, `panel_axes.py` ← transient cases |
| Fig 4 Geometry by ware chamber length | `figures/fig3_length_3d` | `mesh/render_geometry_panels.py` |
| Fig 5 Segment temperatures by length | `figures/fig4_length_panels`, `figures/graphs/Fig_Segments_Length` | `rom/panels_length.py`, `Rscripts/Fig_Segments.R` |
| Fig 6 Geometry by number of steps | `figures/fig5_steps_3d` | `mesh/render_geometry_panels.py` |
| Fig 7 Segment temperatures by steps | `figures/fig6_steps_panels`, `figures/graphs/Fig_Segments_Steps` | `rom/panels_length.py`, `Rscripts/Fig_Segments.R` |
| Fig 8 Variables by firebox form | `figures/graphs/Fig_Form` | `Rscripts/Fig_Form.R` ← `Data/Kiln_Form.csv` ← `rom/study_form.csv`, `cfd/flame_penetration_max.csv` |
| Fig 9 Variables by ware chamber length | `figures/graphs/Fig_Length` | `Rscripts/Fig_Length.R` ← `Data/Kiln_Length.csv` ← `rom/study_length.csv` |
| Table 2 Geometrical variables | `mesh/stl_manifest.csv` | `mesh/generate_rev4.py`, `rev4_builder.py`, `kiln_geometry.py` |
| Table 3 CFD settings, cell counts | `checks/convergence/mesh_quality.csv` | `cases/*/system`, `cases/*/constant`, `mesh/*/system` |
| Table 4 Variables from the experiment | — | `Data/fuel_schedule.csv`, `heating_curve_Hong2011.csv`, `table4_Hong2011.csv`; constants in `rom/rom.py` |
| Table 5 Calibrated and assumed variables | `rom/calibration.txt`, `rom/rom_phi.csv` | `rom/calibrate.py`, `rom/run.py` |
| Fuel and temperatures by form, length, steps | `rom/study_form.csv`, `study_length.csv`, `study_steps.csv` | `rom/study_data.py` |
| Penetration of the 1,000 °C isotherm | `cfd/flame_penetration.csv`, `cfd/flame_penetration_max.csv`, `cfd/np/flame_penetration_np.csv` | `cfd/post/flame_penetration.py`, `penetration_max.py` |
| Grid, time step, operating points | `checks/summary_2-2abd.txt`, `checks/grid_steady.csv`, `checks/oppoint.csv` | `cfd/checks/setup_checks.py`, `summarize_checks.py` |
| S1 Table Classification of quantities | `supporting/S1_Table.xlsx` | `rom/value_classes.py` → `rom/value_classes.csv` |
| S2 Table Calibration of the opening ratio | `supporting/S2_Table.xlsx` | `rom/run.py` → `rom/rom_phi.csv` |
| S3 Table Comparison with the report | `supporting/S3_Table.xlsx` | `rom/sensitivity.py` → `rom/sensitivity.txt`; `Data/table4_Hong2011.csv` |
| S4 Table Sensitivity (27 cases) | `supporting/S4_Table.xlsx` | `rom/sensitivity.py` → `rom/sensitivity_cases.csv` |
| S5 Table Grid quality, convergence, balances | `supporting/S5_Table.xlsx` | `cfd/checks/convergence_summary.py` → `checks/convergence/`; `cfd/checks/limiter_swap.sh` → `checks/limiter_swap/요약.txt` |
| S1 Fig Residual histories | `supporting/S1_Fig.tif`, `.jpg` | `Rscripts/S1_Fig.R` ← `checks/convergence/residuals_*.csv` |
| S6 Table Grid and time-step tests | `supporting/S6_Table.xlsx` | `cfd/checks/summarize_checks.py` → `checks/grid_steady.csv`, `summary_2-2abd.txt` |
| S7 Table Operating points | `supporting/S7_Table.xlsx` | `cfd/checks/summarize_checks.py` → `checks/oppoint.csv` |
| S8 Table Energy balance | `supporting/S8_Table.xlsx` | `rom/energy_audit.py` → `rom/energy_audit.txt`, `energy_audit_series.csv` |
| Response to Reviewers, Fig R1 Overall length of kilns | `figures/kiln_length/Kiln_Length`, `Kiln_Length_summary.csv` | `Rscripts/Fig_KilnLength.R` ← `Data/yun2024_table2_kilns.csv` |

`Rscripts/make_supporting.py` writes all eight supporting tables; each table states its source file.

## Input data
- `Data/fuel_schedule.csv`: heat-release schedule from the fuel input rates recorded by Hong (2011); the last interval is set by the recorded fuel total of 3,600 kg.
- `Data/heating_curve_Hong2011.csv`: heating curve of the Yangsan Hogye-dong kiln 2 experiment read off the published graph (Hong 2011, Table 3), about ±30 °C. The model applies it 2 h earlier, to agree with the temperatures tabulated in the same report.
- `Data/table4_Hong2011.csv`: temperatures tabulated in the report for two measuring points, used only as a check (S3 Table).
- `Data/yun2024_table2_kilns.csv`: the 69 pottery kilns of the Hanseong period of Baekje in the central region listed in Table 2 of Yun, Ju and Song (2024, *Journal of the Korean Archaeological Society*), with overall length and width; the 45 kilns with both dimensions recorded (excluding one value given in parentheses) are plotted in Fig R1.

## Viewing in ParaView
After a case has been run, open the `.foam` file inside it. ParaView decomposes polyhedral cells by default, so the cell count it reports is larger than that of the mesh; turning off `Decompose polyhedra` gives the cell counts of Table 3.
