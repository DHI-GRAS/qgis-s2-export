#Definition of inputs and outputs
#==================================
##Sentinel Tools=group
##Export Sentinel-2 data=name
##ParameterFile|infile|Sentinel-2 product (.SAFE or .XML)|True|False|
##ParameterBoolean|B1|Band 1 (Aerosol 60m)|False
##ParameterBoolean|B2|Band 2 (Blue 10m)|False
##ParameterBoolean|B3|Band 3 (Green 10m)|False
##ParameterBoolean|B4|Band 4 (Red 10m)|False
##ParameterBoolean|B5|Band 5 (Red edge 20m)|False
##ParameterBoolean|B6|Band 6 (Red edge 20m)|False
##ParameterBoolean|B7|Band 7 (Red edge 20m)|False
##ParameterBoolean|B8|Band 8 (NIR 10m)|False
##ParameterBoolean|B8A|Band 8A (Red edge 20m)|False
##ParameterBoolean|B9|Band 9 (Water vapour 60m|False
##ParameterBoolean|B10|Band 10 (Cirrus 60m)|False
##ParameterBoolean|B11|Band 11 (Snow/Ice/Cloud 20m)|False
##ParameterBoolean|B12|Band 12 (Snow/Ice/Cloud 20m)|False
##ParameterBoolean|allVISNIR|All VIS + NIR bands (1-8A, needed for atmospheric correction)|True
##ParameterSelection|out_res|Output resolution|10 meter;20 meter;60 meter
##ParameterString|granules|Only process given granules separated with comma eg. 32UNG,33UUB (To find relevant granules - check ESA kml file).|
##*ParameterNumber|maxCldCov|Maximum cloud cover %|0|100|100
##*ParameterNumber|minDataCov|Minimum data cover %|0|100|0
##OutputDirectory|outdir|Directory to save the exported data in
import os
import sys
import re
here = os.path.dirname(scriptDescriptionFile)
if here not in sys.path:
    sys.path.append(here)
import s2_export
from qgis_logging import set_progress_logger


def _sortfunc(s):
    s = re.sub('(?<=\d)A', '.5', s)
    return float(re.search('\d+\.?\d*', s).group(0))


def flags_to_bandlist(allVISNIR=False, **bandflags):
    if allVISNIR:
        return ['B01', 'B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B08', 'B8A']

    else:
        bands = [k for k in bandflags if bandflags[k]]
        bands.sort(key=_sortfunc)
        return bands


set_progress_logger(name='s2_export', progress=progress)

kwargs = {}

kwargs['bands'] = flags_to_bandlist(
        B1=B1, B2=B2, B3=B3, B4=B4, B5=B5,
        B6=B6, B7=B7, B8=B8, B8A=B8A, B9=B9,
        B10=B10, B11=B11, B12=B12, allVISNIR=allVISNIR)

kwargs['res_dst'] = ["10m", "20m", "60m"][out_res]

if granules.strip():
    kwargs['granules'] = granules.split(',')

kwargs['infile'] = infile
kwargs['outdir'] = outdir


s2_export.export(**kwargs)
