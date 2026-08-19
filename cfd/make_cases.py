#!/usr/bin/env python3
import os, sys, struct, math

KILN = "/home/chanhyeok/Kiln"
MESH = f"{KILN}/mesh"
CFD  = f"{KILN}/cfd"

WOOD_KGH     = 40.0
LHV_MJKG     = 15.0
AF_STOICH    = 6.0
LAMBDA       = 1.5
FUEL_KW      = WOOD_KGH / 3600.0 * LHV_MJKG * 1000.0
MDOT_AIR     = WOOD_KGH / 3600.0 * AF_STOICH * LAMBDA

T_AMB        = 288.0
P_AMB        = 101325.0
RHO_AMB      = 1.225
G            = 9.81

WALL_T       = 0.20
WALL_K       = 0.80
WALL_H       = 10.0

FUELBED_H    = 0.35
FUELBED_Y    = 0.60
CELL         = 0.10

COMB_X0, COMB_X1 = -1.55, -0.05


MODELS = ["A_L065", "B_L065", "C_L065"]


def read_ascii_stl(path):
    solids, name, tri, cur = {}, None, [], []
    with open(path) as f:
        for line in f:
            t = line.split()
            if not t:
                continue
            if t[0] == "solid":
                name = t[1] if len(t) > 1 else "solid"
                cur = []
            elif t[0] == "vertex":
                tri.append((float(t[1]), float(t[2]), float(t[3])))
                if len(tri) == 3:
                    cur.append(tuple(tri)); tri = []
            elif t[0] == "endsolid":
                solids[name] = cur
    return solids


def bbox(tris):
    xs = [v[0] for t in tris for v in t]
    ys = [v[1] for t in tris for v in t]
    zs = [v[2] for t in tris for v in t]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def inside_point(tris, x_target):
    sel = [v for t in tris for v in t if abs(v[0] - x_target) < 0.15]
    if len(sel) < 30:
        return None
    n = len(sel)
    return (sum(v[0] for v in sel) / n,
            sum(v[1] for v in sel) / n,
            sum(v[2] for v in sel) / n)


HEAD = """/*--------------------------------*- C++ -*----------------------------------*\\
| 백제 한성기 토기가마 CFD 테스트                                              |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       {cls};
    {extra}object      {obj};
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //
"""


def head(cls, obj, loc=None):
    extra = f'location    "{loc}";\n    ' if loc else ""
    return HEAD.format(cls=cls, obj=obj, extra=extra)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def make_case(model):
    typ = model[0]
    case = f"{CFD}/{model}"
    stl = f"{MESH}/kiln_{model}.stl"
    solids = read_ascii_stl(stl)
    alltris = [t for v in solids.values() for t in v]
    lo, hi = bbox(alltris)

    m = 2 * CELL
    b0 = [math.floor((lo[i] - m) / CELL) * CELL for i in range(3)]
    b1 = [math.ceil((hi[i] + m) / CELL) * CELL for i in range(3)]
    nx, ny, nz = [max(1, int(round((b1[i] - b0[i]) / CELL))) for i in range(3)]

    ip = inside_point(alltris, 3.0) or (3.0, 0.0, 0.804 + 0.4)

    def patch_z(nm):
        vs = [v for t in solids[nm] for v in t]
        return sum(v[2] for v in vs) / len(vs)
    z_in, z_out = patch_z("inlet"), patch_z("outlet")
    p0_in  = P_AMB - RHO_AMB * G * z_in
    p0_out = P_AMB - RHO_AMB * G * z_out
    draft  = RHO_AMB * G * (z_out - z_in)
    print(f"[{model}] inlet z={z_in:.3f} p0={p0_in:.2f} | outlet z={z_out:.3f} p0={p0_out:.2f} "
          f"| 대기기둥차 {draft:.2f} Pa")

    print(f"[{model}] bbox {tuple(round(v,2) for v in lo)} ~ {tuple(round(v,2) for v in hi)}")
    print(f"[{model}] blockMesh {nx}x{ny}x{nz} = {nx*ny*nz:,} cells,  "
          f"locationInMesh {tuple(round(v,3) for v in ip)}")

    os.makedirs(f"{case}/constant/triSurface", exist_ok=True)
    with open(stl) as s, open(f"{case}/constant/triSurface/kiln.stl", "w") as d:
        d.write(s.read())

    write(f"{case}/system/blockMeshDict", head("dictionary", "blockMeshDict") + f"""
scale 1;

vertices
(
    ({b0[0]} {b0[1]} {b0[2]}) ({b1[0]} {b0[1]} {b0[2]})
    ({b1[0]} {b1[1]} {b0[2]}) ({b0[0]} {b1[1]} {b0[2]})
    ({b0[0]} {b0[1]} {b1[2]}) ({b1[0]} {b0[1]} {b1[2]})
    ({b1[0]} {b1[1]} {b1[2]}) ({b0[0]} {b1[1]} {b1[2]})
);

blocks ( hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz}) simpleGrading (1 1 1) );

edges ();

boundary
(
    background
    {{
        type patch;
        faces ( (0 3 2 1) (4 5 6 7) (0 1 5 4) (2 3 7 6) (0 4 7 3) (1 2 6 5) );
    }}
);

mergePatchPairs ();
""")

    write(f"{case}/system/snappyHexMeshDict", head("dictionary", "snappyHexMeshDict") + f"""
castellatedMesh true;
snap            true;
addLayers       false;

geometry
{{
    kiln.stl
    {{
        type triSurfaceMesh;
        name kiln;
        regions
        {{
            walls  {{ name walls;  }}
            inlet  {{ name inlet;  }}
            outlet {{ name outlet; }}
        }}
    }}
}}

castellatedMeshControls
{{
    maxLocalCells       2000000;
    maxGlobalCells      4000000;
    minRefinementCells  10;
    nCellsBetweenLevels 2;
    resolveFeatureAngle 30;
    allowFreeStandingZoneFaces true;

    features ();

    refinementSurfaces
    {{
        kiln
        {{
            level (1 1);
            regions
            {{
                walls  {{ level (1 1); patchInfo {{ type wall;  }} }}
                inlet  {{ level (1 1); patchInfo {{ type patch; }} }}
                outlet {{ level (1 1); patchInfo {{ type patch; }} }}
            }}
        }}
    }}

    refinementRegions {{}}

    locationInMesh ({ip[0]:.4f} {ip[1]:.4f} {ip[2]:.4f});
}}

snapControls
{{
    nSmoothPatch    3;
    tolerance       2.0;
    nSolveIter      50;
    nRelaxIter      5;
    nFeatureSnapIter 10;
    implicitFeatureSnap    true;
    explicitFeatureSnap    false;
    multiRegionFeatureSnap false;
}}

addLayersControls
{{
    relativeSizes true;
    layers {{}}
    expansionRatio 1.2;
    finalLayerThickness 0.3;
    minThickness 0.1;
    nGrow 0;
    featureAngle 60;
    nRelaxIter 3;
    nSmoothSurfaceNormals 1;
    nSmoothNormals 3;
    nSmoothThickness 10;
    maxFaceThicknessRatio 0.5;
    maxThicknessToMedialRatio 0.3;
    minMedialAxisAngle 90;
    nBufferCellsNoExtrude 0;
    nLayerIter 50;
}}

meshQualityControls
{{
    maxNonOrtho         65;
    maxBoundarySkewness 20;
    maxInternalSkewness 4;
    maxConcave          80;
    minVol              1e-13;
    minTetQuality       1e-15;
    minArea             -1;
    minTwist            0.02;
    minDeterminant      0.001;
    minFaceWeight       0.02;
    minVolRatio         0.01;
    minTriangleTwist    -1;
    nSmoothScale        4;
    errorReduction      0.75;
}}

mergeTolerance 1e-6;
""")

    zs = [v[2] for t in alltris for v in t if COMB_X0 <= v[0] <= COMB_X1]
    z0 = min(zs)
    z1 = z0 + FUELBED_H
    print(f"[{model}] 연소부 바닥 z={z0:+.3f} -> 연료층 {z0:+.3f}~{z1:+.3f} m")
    write(f"{case}/system/topoSetDict", head("dictionary", "topoSetDict") + f"""
actions
(
    {{
        name    fuelbed;
        type    cellSet;
        action  new;
        source  boxToCell;
        box     ({COMB_X0} {-FUELBED_Y} {z0:.3f}) ({COMB_X1} {FUELBED_Y} {z1:.3f});
    }}
    {{
        name    fuelbed;
        type    cellZoneSet;
        action  new;
        source  setToCellZone;
        set     fuelbed;
    }}
);
""")

    write(f"{case}/system/fvOptions", head("dictionary", "fvOptions") + f"""
heatSource
{{
    type            scalarSemiImplicitSource;
    selectionMode   cellZone;
    cellZone        fuelbed;
    volumeMode      absolute;

    injectionRateSuSp
    {{
        h  ({FUEL_KW*1000.0:.1f} 0);
    }}
}}
""")
    write(f"{case}/constant/fvModels", head("dictionary", "fvModels") + f"""
heatSource
{{
    type            semiImplicitSource;
    selectionMode   cellZone;
    cellZone        fuelbed;
    volumeMode      absolute;

    sources
    {{
        h  {{ explicit {FUEL_KW*1000.0:.1f}; implicit 0; }}
    }}
}}
""")

    thermo = """
thermoType
{
    type            heRhoThermo;
    mixture         pureMixture;
    transport       sutherland;
    thermo          hConst;
    equationOfState perfectGas;
    specie          specie;
    energy          sensibleEnthalpy;
}

mixture
{
    specie          { molWeight 28.96; }
    thermodynamics  { Cp 1100; Hf 0; }
    transport       { As 1.4792e-06; Ts 116; }
}
"""
    write(f"{case}/constant/physicalProperties", head("dictionary", "physicalProperties") + thermo)
    write(f"{case}/constant/thermophysicalProperties",
          head("dictionary", "thermophysicalProperties") + thermo)

    turb = """
simulationType RAS;

RAS
{
    model           kEpsilon;
    turbulence      on;
    printCoeffs     on;
}
"""
    write(f"{case}/constant/momentumTransport", head("dictionary", "momentumTransport") + turb)
    write(f"{case}/constant/turbulenceProperties",
          head("dictionary", "turbulenceProperties") + turb)

    write(f"{case}/constant/g",
          head("uniformDimensionedVectorField", "g", "constant") +
          "\ndimensions [0 1 -2 0 0 0 0];\nvalue (0 0 -9.81);\n")

    def field(cls, obj, dims, internal, bcs):
        s = head(cls, obj, "0") + f"\ndimensions {dims};\n\ninternalField uniform {internal};\n\nboundaryField\n{{\n"
        for p, b in bcs.items():
            s += f"    {p}\n    {{\n"
            for k, v in b.items():
                s += f"        {k:<24}{v};\n"
            s += "    }\n"
        return s + "}\n"

    write(f"{case}/0/T", field("volScalarField", "T", "[0 0 0 1 0 0 0]", T_AMB, {
        "inlet":  {"type": "fixedValue", "value": f"uniform {T_AMB}"},
        "outlet": {"type": "inletOutlet", "inletValue": f"uniform {T_AMB}", "value": f"uniform {T_AMB}"},
        "walls":  {"type": "externalWallHeatFluxTemperature",
                   "mode": "coefficient",
                   "h": f"uniform {WALL_H}",
                   "Ta": f"uniform {T_AMB}",
                   "thicknessLayers": f"({WALL_T})",
                   "kappaLayers": f"({WALL_K})",
                   "kappaMethod": "fluidThermo",
                   "value": f"uniform {T_AMB}"},
    }))

    write(f"{case}/0/p_rgh", field("volScalarField", "p_rgh", "[1 -1 -2 0 0 0 0]", P_AMB, {
        "inlet":  {"type": "fixedFluxPressure", "value": f"uniform {P_AMB}"},
        "outlet": {"type": "prghTotalPressure", "p0": f"uniform {p0_out:.3f}",
                   "value": f"uniform {p0_out:.3f}"},
        "walls":  {"type": "fixedFluxPressure", "value": f"uniform {P_AMB}"},
    }))

    write(f"{case}/0/p", field("volScalarField", "p", "[1 -1 -2 0 0 0 0]", P_AMB, {
        "inlet":  {"type": "calculated", "value": f"uniform {P_AMB}"},
        "outlet": {"type": "calculated", "value": f"uniform {P_AMB}"},
        "walls":  {"type": "calculated", "value": f"uniform {P_AMB}"},
    }))

    write(f"{case}/0/U", field("volVectorField", "U", "[0 1 -1 0 0 0 0]", "(0 0 0)", {
        "inlet":  {"type": "flowRateInletVelocity",
                   "massFlowRate": f"constant {MDOT_AIR:.5f}",
                   "rhoInlet": f"{RHO_AMB}",
                   "value": "uniform (0 0 0)"},
        "outlet": {"type": "pressureInletOutletVelocity", "value": "uniform (0 0 0)"},
        "walls":  {"type": "noSlip"},
    }))

    write(f"{case}/0/k", field("volScalarField", "k", "[0 2 -2 0 0 0 0]", 0.01, {
        "inlet":  {"type": "inletOutlet", "inletValue": "uniform 0.01", "value": "uniform 0.01"},
        "outlet": {"type": "inletOutlet", "inletValue": "uniform 0.01", "value": "uniform 0.01"},
        "walls":  {"type": "kqRWallFunction", "value": "uniform 0.01"},
    }))

    write(f"{case}/0/epsilon", field("volScalarField", "epsilon", "[0 2 -3 0 0 0 0]", 0.01, {
        "inlet":  {"type": "inletOutlet", "inletValue": "uniform 0.01", "value": "uniform 0.01"},
        "outlet": {"type": "inletOutlet", "inletValue": "uniform 0.01", "value": "uniform 0.01"},
        "walls":  {"type": "epsilonWallFunction", "value": "uniform 0.01"},
    }))

    write(f"{case}/0/alphat", field("volScalarField", "alphat", "[1 -1 -1 0 0 0 0]", 0, {
        "inlet":  {"type": "calculated", "value": "uniform 0"},
        "outlet": {"type": "calculated", "value": "uniform 0"},
        "walls":  {"type": "compressible::alphatWallFunction", "Prt": "0.85", "value": "uniform 0"},
    }))

    write(f"{case}/0/nut", field("volScalarField", "nut", "[0 2 -1 0 0 0 0]", 0, {
        "inlet":  {"type": "calculated", "value": "uniform 0"},
        "outlet": {"type": "calculated", "value": "uniform 0"},
        "walls":  {"type": "nutkWallFunction", "value": "uniform 0"},
    }))

    write(f"{case}/system/controlDict", head("dictionary", "controlDict") + """
application     buoyantSimpleFoam;
startFrom       latestTime;
startTime       0;
stopAt          endTime;
endTime         15000;
deltaT          1;
writeControl    runTime;
writeInterval   500;
purgeWrite      2;
writeFormat     ascii;
writePrecision  7;
writeCompression off;
timeFormat      general;
timePrecision   6;
runTimeModifiable true;

functions
{
    outletFlux
    {
        type            surfaceFieldValue;
        libs            ("libfieldFunctionObjects.so");
        writeControl    timeStep;
        writeInterval   50;
        log             true;
        writeFields     false;
        regionType      patch;
        name            outlet;
        operation       sum;
        fields          ( phi );
    }

    outletT
    {
        type            surfaceFieldValue;
        libs            ("libfieldFunctionObjects.so");
        writeControl    timeStep;
        writeInterval   50;
        log             true;
        writeFields     false;
        regionType      patch;
        name            outlet;
        operation       areaAverage;
        fields          ( T );
    }

    inletFlux
    {
        type            surfaceFieldValue;
        libs            ("libfieldFunctionObjects.so");
        writeControl    timeStep;
        writeInterval   50;
        log             true;
        writeFields     false;
        regionType      patch;
        name            inlet;
        operation       sum;
        fields          ( phi );
    }

    // 화구가 끌어와야 하는 통풍압 — 자연통풍으로 가능한지 판정하는 지표
    inletP
    {
        type            surfaceFieldValue;
        libs            ("libfieldFunctionObjects.so");
        writeControl    timeStep;
        writeInterval   50;
        log             true;
        writeFields     false;
        regionType      patch;
        name            inlet;
        operation       areaAverage;
        fields          ( p_rgh );
    }

    wallHeatFlux
    {
        type            wallHeatFlux;
        libs            ("libfieldFunctionObjects.so");
        writeControl    writeTime;
        patches         ( walls );
    }

    // 소성부 전체 평균온도
    volT
    {
        type            volFieldValue;
        libs            ("libfieldFunctionObjects.so");
        writeControl    timeStep;
        writeInterval   50;
        log             true;
        writeFields     false;
        regionType      all;
        operation       volAverage;
        fields          ( T );
    }
}
""")

    write(f"{case}/system/fvSchemes", head("dictionary", "fvSchemes") + """
ddtSchemes      { default steadyState; }

gradSchemes     { default cellLimited Gauss linear 1; }

divSchemes
{
    default         none;
    div(phi,U)      bounded Gauss upwind;
    div(phi,h)      bounded Gauss upwind;
    div(phi,e)      bounded Gauss upwind;
    div(phi,K)      bounded Gauss upwind;
    div(phi,Ekp)    bounded Gauss upwind;
    div(phi,k)      bounded Gauss upwind;
    div(phi,epsilon) bounded Gauss upwind;
    div(((rho*nuEff)*dev2(T(grad(U))))) Gauss linear;
    div(phi,Yi_h)   bounded Gauss upwind;
}

laplacianSchemes { default Gauss linear limited corrected 0.33; }
interpolationSchemes { default linear; }
snGradSchemes   { default limited corrected 0.33; }
wallDist        { method meshWave; }
""")

    write(f"{case}/system/fvSolution", head("dictionary", "fvSolution") + """
solvers
{
    p_rgh
    {
        solver          GAMG;
        tolerance       1e-7;
        relTol          0.01;
        smoother        GaussSeidel;
    }

    "(U|h|e|k|epsilon)"
    {
        solver          PBiCGStab;
        preconditioner  DILU;
        tolerance       1e-8;
        relTol          0.1;
    }
}

SIMPLE
{
    momentumPredictor yes;
    nNonOrthogonalCorrectors 1;
    pRefCell        0;
    pRefValue       101325;

    residualControl
    {
        p_rgh           1e-4;
        U               1e-4;
        h               1e-4;
        e               1e-4;
        "(k|epsilon)"   1e-4;
    }
}

relaxationFactors
{
    fields
    {
        rho             1.0;
        p_rgh           0.4;
    }
    equations
    {
        U               0.5;
        h               0.7;
        e               0.7;
        "(k|epsilon)"   0.5;
    }
}
""")

    write(f"{case}/system/decomposeParDict", head("dictionary", "decomposeParDict") + """
numberOfSubdomains 4;
method          scotch;
""")

    return case


if __name__ == "__main__":
    os.makedirs(CFD, exist_ok=True)
    targets = sys.argv[1:] or MODELS
    for m in targets:
        make_case(m)
    print(f"\n케이스 생성 완료: {', '.join(targets)}")
    print(f"연소부 총 발열량 {FUEL_KW} kW (전 형식 동일), 외기 {T_AMB} K")
