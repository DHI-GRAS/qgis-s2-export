import os
import sys
import re
from processing.tools import dataobjects
import logging
import glob
import logging
from collections import OrderedDict

import gdal
import scipy.ndimage

#import s2_export # TODO IMPORT
#from qgis_logging import set_progress_logger TODO IMPORT
from qgis.processing import alg
@alg(
    name="exportsentinel2data",
    label=alg.tr("Export Sentinel-2 data"),
    group="sentineltools",
    group_label=alg.tr("Sentinel Tools"),
)
@alg.input(
    type=alg.FILE,
    name="inFile",
    label="Sentinel-2 product (.SAFE or .XML)",
    behavior=1,
    optional=False,
)
@alg.input(
    type=bool,
    name="B1",
    label="Band 1 (Aerosol 60m)",
    default=False,
)
@alg.input(
    type=bool,
    name="B2",
    label="Band 2 (Blue 10m)",
    default=False,
)
@alg.input(
    type=bool,
    name="B3",
    label="Band 3 (Green 10m)",
    default=False,
)
@alg.input(
    type=bool,
    name="B4",
    label="Band 4 (Red 10m)",
    default=False,
)
@alg.input(
    type=bool,
    name="B5",
    label="Band 5 (Red edge 20m)",
    default=False,
)
@alg.input(
    type=bool,
    name="B6",
    label="Band 6 (Red edge 20m)",
    default=False,
)
@alg.input(
    type=bool,
    name="B7",
    label="Band 7 (Red edge 20m)",
    default=False,
)
@alg.input(
    type=bool,
    name="B8",
    label="Band 8 (NIR 10m)",
    default=False,
)
@alg.input(
    type=bool,
    name="B8A",
    label="Band 8A (Red edge 20m)",
    default=False,
)
@alg.input(
    type=bool,
    name="B9",
    label="Band 9 (Water vapour 60m)",
    default=False,
)
@alg.input(
    type=bool,
    name="B10",
    label="Band 10 (Cirrus 60m)",
    default=False,
)
@alg.input(
    type=bool,
    name="B11",
    label="Band 11 (Snow/Ice/Cloud 20m)",
    default=False,
)
@alg.input(
    type=bool,
    name="B12",
    label="Band 12 (Snow/Ice/Cloud 20m)",
    default=False,
)
@alg.input(
    type=bool,
    name="allVISNIR",
    label="All VIS + NIR bands (1-8A, needed for atmospheric correction)",
    default=True,
)
@alg.input(
    type=str,
    name="bands_param",
    label="List of bands to export (to preserve order), e.g. 'B4,B3,B2'",
    optional=True,
)
@alg.input(
    type=alg.ENUM,
    name="out_res",
    label="Output resolution",
    options=['10 meter','20 meter','60 meter'],
    default=0,
)
@alg.input(
    type=str,
    name="granules",
    label="Only process given granules separated with comma eg. 32UNG,33UUB (To find relevant granules - check ESA kml file).",
    optional=True,
)
@alg.input(type=alg.FILE_DEST, name="outdir", label="Directory to save the exported data in")
def exportsentinel2data(instance, parameters, context, feedback, inputs):
    """ exportsentinel2data """
    inFile = instance.parameterAsString(parameters, 'inFile', context)
    B1 = instance.parameterAsBool(parameters, 'B1', context)
    B2 = instance.parameterAsBool(parameters, 'B2', context)
    B3 = instance.parameterAsBool(parameters, 'B3', context)
    B4 = instance.parameterAsBool(parameters, 'B4', context)
    B5 = instance.parameterAsBool(parameters, 'B5', context)
    B6 = instance.parameterAsBool(parameters, 'B6', context)
    B7 = instance.parameterAsBool(parameters, 'B7', context)
    B8 = instance.parameterAsBool(parameters, 'B8', context)
    B8A = instance.parameterAsBool(parameters, 'B8A', context)
    B9 = instance.parameterAsBool(parameters, 'B9', context)
    B10 = instance.parameterAsBool(parameters, 'B10', context)
    B11 = instance.parameterAsBool(parameters, 'B11', context)
    B12 = instance.parameterAsBool(parameters, 'B12', context)
    allVISNIR = instance.parameterAsBool(parameters, 'allVISNIR', context)
    bands_param = instance.parameterAsString(parameters, 'bands_param', context)
    out_res = instance.parameterAsString(parameters, 'out_res', context)
    granules = instance.parameterAsString(parameters, 'granules', context)
    
    logger = logging.getLogger('s2_export')

    _res_bands = OrderedDict([
        ('10m', ['B2', 'B3', 'B4', 'B8']),
        ('20m', ['B5', 'B6', 'B7', 'B8A', 'B11', 'B12']),
        ('60m', ['B1', 'B9', 'B10'])])


    def get_bands_res():
        bands_res = OrderedDict()
        for reskey in _res_bands:
            for bandname in _res_bands[reskey]:
                bands_res[bandname] = reskey
        return bands_res


    _bands_res = get_bands_res()


    def res_to_float(reskey):
        return float(reskey[:2])


    def open_res_datasets(subdatasets):
        res_dss = OrderedDict((reskey, gdal.Open(subdatasets[k][0])) for k, reskey in enumerate(_res_bands))
        return res_dss


    def get_gdal_bands(dss):
        bands_gdal = OrderedDict()
        for reskey in dss:
            for b, bandname in enumerate(_res_bands[reskey]):
                bands_gdal[bandname] = dss[reskey].GetRasterBand(b+1)
        return bands_gdal


    def create_outfile_from_templates(outfile, nbands, template_ds, template_band,
            driver_name='GTiff',
            gdal_dtype=gdal.GDT_Int16, create_options=['COMPRESS=LZW', 'BIGTIFF=IF_SAFER']):

        geotransform = template_ds.GetGeoTransform()
        projection = template_ds.GetProjection()
        nx = template_band.XSize
        ny = template_band.YSize
        gdal_dtype = template_band.DataType

        drv = gdal.GetDriverByName(driver_name)
        out = drv.Create(outfile, ny, nx, nbands, gdal_dtype, create_options)
        if out is None:
            raise IOError('Unable to create new dataset in {}.'.format(outfile))
        out.SetGeoTransform(geotransform)
        out.SetProjection(projection)

        tgt_nodata = template_band.GetNoDataValue()
        if tgt_nodata is not None:
            for b in range(nbands):
                out.GetRasterBand(b+1).SetNoDataValue(tgt_nodata)

        return out


    def write_bands(outds, bands_gdal, bands, tgt_res, tgt_nodata=None):
        """Read band data, zoom and write to output dataset

        Parameters
        ----------
        outds : gdal Dataset
            dataset to write to
        bands_gdal : dict
            dictionary mapping band names to open gdal bands
        tgt_res : str
            target resolution
            e.g. 10m
        tgt_nodata : float
            target nodata
        """
        tgt_res_float = res_to_float(tgt_res)
        for b, bandname in enumerate(bands):
            logger.info('Adding data from band {}'.format(bandname))
            data = bands_gdal[bandname].ReadAsArray()
            zoom = res_to_float(_bands_res[bandname]) / tgt_res_float
            if zoom != 1:
                logger.info('Scaling data to {} resolution ...'.format(tgt_res))
                logger.debug('Zoom factor is {}'.format(zoom))
                data = scipy.ndimage.interpolation.zoom(data, zoom, order=0)
            outds.GetRasterBand(b+1).WriteArray(data)
        logger.info('Writing to disk ...')
        outds = None
        logger.info('Done.')


    def export_from_subdatasets(subdatasets, bands, tgt_res, outfile):
        """Export selected bands from subdatasets

        Parameters
        ----------
        subdatasets : list of (str, str)
            returned from ds.GetSubDatasets()
        bands : list of str
            names of bands to extract
        tgt_res : str
            target resolution
            e.g. 10m
        outfile : str
            path to output file
        """
        res_dss = open_res_datasets(subdatasets)
        bands_gdal = get_gdal_bands(res_dss)

        nbands = len(bands)

        template_ds = res_dss[tgt_res]
        template_bandname = _res_bands[tgt_res][0]
        template_band = bands_gdal[template_bandname]

        outds = create_outfile_from_templates(outfile, nbands, template_ds, template_band)
        write_bands(outds, bands_gdal, bands, tgt_res)


    def find_granule_name(s):
        try:
            return re.search('(?<=T)\d{2}[A-Z]{3}', s).group(0)
        except AttributeError:
            return None


    def get_granule_xml(filelist):
        granule_xml = OrderedDict()
        for fname in filelist:
            if not fname.endswith('.xml'):
                continue
            granule = find_granule_name(fname)
            if granule is None:
                continue
            granule_xml[granule] = fname
        return granule_xml


    def get_multi_granule_xml(ds):
        granule_xml = OrderedDict()
        subfiles = [e[0] for e in ds.GetSubDatasets() if 'PREVIEW' not in e[0]]
        for sf in subfiles:
            subsubfiles = gdal.Open(sf).GetFileList()
            subgx = get_granule_xml(subsubfiles)
            granule_xml.update(subgx)
        return granule_xml


    def get_multi_granule_subdatasets(ds):
        granule_xml = get_multi_granule_xml(ds)
        granule_subdatasets = OrderedDict()
        for granule in granule_xml:
            fname = granule_xml[granule]
            granule_subdatasets[granule] = gdal.Open(fname).GetSubDatasets()
        return granule_subdatasets


    def get_single_granule_subdatasets(ds):
        subdatasets = ds.GetSubDatasets()
        filelist = gdal.Open(subdatasets[0][0]).GetFileList()
        for fname in filelist:
            if not fname.endswith('.xml'):
                continue
            granule = find_granule_name(fname)
        if granule is None:
            raise ValueError('Unable to determine granule name.')
        return {granule: subdatasets}


    def get_subdatasets(ds):
        subdatasets = ds.GetSubDatasets()
        if len(subdatasets) <= 5:
            logger.info('Got single-tile S2 product')
            return get_single_granule_subdatasets(ds)
        else:
            logger.info('Got multi-tile S2 product')
            return get_multi_granule_subdatasets(ds)


    def ensure_xml(infile):
        if not infile.endswith('.xml'):
            pattern = os.path.join(infile, '*MTD*.xml')
            try:
                return glob.glob(pattern)[0]
            except IndexError:
                raise ValueError('Unable to find MTD XML file with pattern \'{}\'.'.format(pattern))
        else:
            return infile


    def get_metadata_from_xml(xmlfile):
        """Very simple XML reader"""
        date = None
        platform = None
        with open(xmlfile, 'r') as f:
            for line in f:
                if date and platform:
                    break
                try:
                    if 'PRODUCT_START_TIME' in line:
                        date = re.search('\d{4}-\d{2}-\d{2}', line).group(0).replace('-', '')
                    elif 'SPACECRAFT_NAME' in line:
                        platform = 'S' + re.search('(?<=Sentinel-)2[AB]', line).group(0)
                except AttributeError:
                    pass
        if date is None or platform is None:
            raise ValueError('Unable to get all metdatada from XML file \'{}\'.'.format(xmlfile))
        return dict(date=date, platform=platform)


    def generate_outfilename(xmlfile, granule):
        meta = get_metadata_from_xml(xmlfile)
        return '{platform}_{date}_T{granule}'.format(granule=granule, **meta)


    def export(infile, outdir, bands, tgt_res, granules=None):
        """Export selected S2 bands and granules to GeoTIFF

        Parameters
        ----------
        infile : str
            path to input SAFE or MTD xml file
        outdir : str
            path to output dir
        bands : list of str
            names of bands to extract
            e.g. B1, B10 (no leading zero!)
        tgt_res : str
            target resolution e.g. 10m
            data not in this resolution will be interpolated
        granules : list of str
            extract only these granules

        Returns
        -------
        outfiles : list of str
            list of output files generated
        """
        infile = ensure_xml(infile)

        ds = gdal.Open(infile)
        if ds is None:
            raise IOError('Failed to read input file \'{}\'. Please provide a valid S2 MTD XML file.'.format(infile))

        logger.info('Retrieving granule subdatasets ...')
        granule_subdatasets = get_subdatasets(ds)

        if granules:
            logger.info('Selecting granules ...')
            for granule in granule_subdatasets:
                if granule not in granules:
                    granule_subdatasets.pop(granule)
        if not granule_subdatasets:
            logger.info('No granules left to export. Exiting.')
            return

        logger.info('Granules to export: {}'.format(list(granule_subdatasets)))

        outfiles = []
        for granule in granule_subdatasets:
            logger.info('Exporting granule {} ...'.format(granule))
            subdatasets = granule_subdatasets[granule]
            outfname = generate_outfilename(infile, granule) + '.tif'
            outfile = os.path.join(outdir, outfname)
            export_from_subdatasets(subdatasets, bands=bands, tgt_res=tgt_res, outfile=outfile)
            outfiles.append(outfile)
        return outfiles

    class ProgressHandler(logging.StreamHandler):

        def __init__(self, progress):
            super(self.__class__, self).__init__()
            self.progress = progress

        def emit(self, record):
            msg = self.format(record)
            self.feedback.pushConsoleInfo(msg)

    def set_progress_logger(name, progress, level='INFO'):
        logger = logging.getLogger(name)
        progress_handler = ProgressHandler(progress)
        logger.addHandler(progress_handler)
        logger.setLevel(level)
        return logger

    def _sortfunc(s):  
        s = re.sub('(?<=\d)A', '.5', s)
        return float(re.search('\d+\.?\d*', s).group(0))


    def flags_to_bandlist(allVISNIR=False, **bandflags):
        if allVISNIR:
            return ['B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B8A']

        else:
            bands = [k for k in bandflags if bandflags[k]]
            bands.sort(key=_sortfunc)
            return bands


    set_progress_logger(name='s2_export', progress=progress)

    kwargs = {}

    bands_param = bands_param.replace(' ', '')
    if bands_param:
        kwargs['bands'] = bands_param.split(',')
    else:
        kwargs['bands'] = flags_to_bandlist(
                B1=B1, B2=B2, B3=B3, B4=B4, B5=B5,
                B6=B6, B7=B7, B8=B8, B8A=B8A, B9=B9,
                B10=B10, B11=B11, B12=B12, allVISNIR=allVISNIR)

    kwargs['tgt_res'] = ["10m", "20m", "60m"][out_res]

    if granules.strip():
        kwargs['granules'] = granules.split(',')

    kwargs['infile'] = infile
    kwargs['outdir'] = outdir


    outfiles = export(**kwargs)

    for outfile in outfiles:
        dataobjects.load(outfile)
