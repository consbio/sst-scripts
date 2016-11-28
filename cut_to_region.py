import os
import sys

import click
import fiona
import numpy
from clover.geometry.bbox import BBox
from clover.netcdf.crs import set_crs
from clover.netcdf.variable import SpatialCoordinateVariables
from netCDF4 import Dataset
from numpy.ma.core import is_masked
from pyproj import transform, Proj
from rasterio.features import rasterize
from rasterio.warp import transform_geom

VARIABLES = [
    'MAT', 'MWMT', 'MCMT', 'TD', 'MAP', 'MSP', 'AHM', 'SHM', 'DD_0', 'DD5', 'FFP', 'PAS', 'EMT', 'EXT', 'Eref', 'CMD'
]


@click.command()
@click.argument('in_pattern')
@click.argument('out_pattern')
@click.argument('boundary', type=click.Path(exists=True))
@click.option('--single', is_flag=True, help='Process a single dataset (e.g., a DEM) instead of variable datasets')
@click.option('--varname', help='The name of the NetCDF variable when --single is used')
def main(in_pattern, out_pattern, boundary, single, varname):
    """
    Clips and masks large NetCDF datasets to regional datasets based on the boundary. The in_pattern and out_pattern
    arguments should be filename patterns (can include path) with the pattern: /path/to/in_netcdf_{variable}.nc.

    Example usage: python cut_to_region.py NorthAmerica/NA_{variable}.nc USWest/west_{variable}.nc west.shp
    """

    if single and not varname:
        print('--varname is required when --single is used')
        sys.exit(-1)

    if single:
        if not os.path.exists(in_pattern):
            print('Input file {} does not exist.'.format(in_pattern))
            sys.exit(-1)

        input_paths = [(in_pattern, varname)]
    else:
        input_paths = [(in_pattern.format(variable=x), x) for x in VARIABLES]

        for path, _ in input_paths:
            if not os.path.exists(path):
                print('Input file {} does not exist.'.format(path))
                sys.exit(-1)

    with fiona.open(boundary, 'r') as shp:
        features = []
        wgs84 = Proj('+init=EPSG:4326')
        shp_projection = Proj(shp.crs)
        bounds = shp.bounds

        ll = transform(shp_projection, wgs84, bounds[0], bounds[1])
        ur = transform(shp_projection, wgs84, bounds[2], bounds[3])

        bbox = BBox([*ll, *ur], projection=wgs84)

        for feature in shp.items():
            geometry = transform_geom(shp.crs, {'init': 'EPSG: 4326'}, feature[1]['geometry'])
            features.append(geometry)

    for in_path, variable in input_paths:
        if single:
            out_path = out_pattern
        else:
            out_path = out_pattern.format(variable=variable)

        if os.path.exists(out_path):
            confirm = input("The output file '{}' already exists? Do you with to replace it? [y/n] ".format(out_path))
            if confirm.lower().strip() not in ['y', 'yes']:
                print('Exiting...')
                sys.exit()

        with Dataset(in_path, 'r') as ds:
            coords = SpatialCoordinateVariables.from_dataset(ds, x_name='longitude', y_name='latitude')

            x_start, x_stop = coords.x.indices_for_range(bbox.xmin, bbox.xmax)
            y_start, y_stop = coords.y.indices_for_range(bbox.ymin, bbox.ymax)

            x_slice = slice(x_start, x_stop + 1)
            y_slice = slice(y_start, y_stop + 1)

            clipped_coords = coords.slice_by_bbox(bbox)

            grid = ds.variables[variable][y_slice, x_slice]

        if is_masked(grid):
            mask = grid.mask.astype('uint8')
        else:
            mask = numpy.zeros(grid.shape, dtype='uint8')

        mask |= rasterize(
            ((x, 0) for x in features), out_shape=mask.shape, transform=clipped_coords.affine, fill=1, default_value=0
        )
        grid = numpy.ma.masked_where(mask == 1, grid.data)

        print('Writing {}...'.format(out_path))
        with Dataset(out_path, 'w', format='NETCDF4') as ds:
            clipped_coords.add_to_dataset(ds, 'longitude', 'latitude')
            data_var = ds.createVariable(
                variable, grid.dtype, dimensions=('latitude', 'longitude'), fill_value=grid.fill_value
            )
            data_var[:] = grid
            set_crs(ds, variable, Proj('+init=EPSG:4326'))


if __name__ == '__main__':
    main()
