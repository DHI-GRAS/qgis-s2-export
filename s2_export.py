import os
import glob
import re
import logging
from collections import OrderedDict

import gdal
import scipy.ndimage

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
            logger.info('Interpolating data to new resolution ...')
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


def get_subdatasets(ds):
    subdatasets = ds.GetSubDatasets()
    if len(subdatasets) <= 5:
        logger.info('Got single-tile S2 product')
        granule = find_granule_name(subdatasets[0][0])
        return {granule: subdatasets}
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

    for granule in granule_subdatasets:
        logger.info('Exporting granule {} ...'.format(granule))
        subdatasets = granule_subdatasets[granule]
        outfname = '{}_T{}.tif'.format(os.path.splitext(os.path.basename(infile))[0], granule)
        outfile = os.path.join(outdir, outfname)
        export_from_subdatasets(subdatasets, bands=bands, tgt_res=tgt_res, outfile=outfile)
