import csv
import os
from io import StringIO

import click
import numpy
import rasterio
from clover.geometry.bbox import BBox
from clover.netcdf.crs import set_crs
from clover.netcdf.variable import SpatialCoordinateVariables
from netCDF4._netCDF4 import Dataset
from pyproj import Proj

VARIABLES = [
    ('MAT', True), ('MWMT', True), ('MCMT', True), ('TD', True), ('MAP', False), ('MSP', False), ('AHM', True),
    ('SHM', True), ('DD_0', False), ('DD5', False), ('FFP', False), ('PAS', False), ('EMT', True), ('EXT', True),
    ('Eref', False), ('CMD', False)
]


@click.command()
@click.argument('original_file', type=click.Path(exists=True))
@click.argument('climatena_file', type=click.Path(exists=True))
@click.argument('out_dir', type=click.Path(exists=True))
def main(original_file, climatena_file, out_dir):
    with rasterio.open(original_file) as ds:
        bounds = ds.bounds
        affine = ds.profile['affine']
        shape = ds.shape

    with open(climatena_file, 'r') as f_in:
        headers = csv.DictReader(f_in).fieldnames

    print('Creating datasets...')

    grid = numpy.zeros(shape, dtype='int32')
    grid = numpy.ma.masked_where(grid == 0, grid)

    for i, var in enumerate(VARIABLES):
        out_path = os.path.join(
            out_dir, '{}_{}.nc'.format(os.path.splitext(os.path.basename(climatena_file))[0], var[0])
        )

        with Dataset(out_path, 'w', format='NETCDF4') as ds:
            projection = Proj('+init=EPSG:4326')
            coord_vars = SpatialCoordinateVariables.from_bbox(
                BBox(bounds, projection=projection), *reversed(grid.shape)
            )
            coord_vars.add_to_dataset(ds, 'longitude', 'latitude')
            data_var = ds.createVariable(
                var[0], grid.dtype, dimensions=('latitude', 'longitude'), fill_value=grid.fill_value
            )
            data_var[:] = grid
            set_crs(ds, var[0], projection)

    print('Copying from ClimateNA data... (0%)', end='\r')
    with open(climatena_file, 'r') as f_in:
        f_in.seek(0, os.SEEK_END)
        end = f_in.tell()
        f_in.seek(0)
        f_in.readline()  # Skip headers

        while f_in.tell() < end:
            lines = ''.join(f_in.readline() for _ in range(1000000))

            arr = numpy.loadtxt(
                StringIO(lines),
                delimiter=',',
                usecols=[headers.index(x) for x in (['Latitude', 'Longitude'] + [v[0] for v in VARIABLES])]
            )
            arr = numpy.moveaxis(arr, 1, 0)

            latitudes = arr[0]
            longitudes = arr[1]

            for i, var in enumerate(VARIABLES):
                variable = arr[i + 2]

                out_path = os.path.join(
                    out_dir, '{}_{}.nc'.format(os.path.splitext(os.path.basename(climatena_file))[0], var[0])
                )
                with Dataset(out_path, 'a') as ds:
                    grid = ds.variables[var[0]][:]
                    fill_value = grid.fill_value
                    grid = grid.data

                    for j, value in enumerate(variable):
                        if value == -9999:
                            continue

                        col, row = [int(round(x)) for x in ~affine * (longitudes[j], latitudes[j])]

                        if var[1]:
                            value *= 10

                        grid[row][col] = value

                    ds.variables[var[0]][:] = numpy.ma.masked_where(grid == fill_value, grid)

            print('Copying from ClimateNA data... ({}%)'.format(round(f_in.tell() / end * 100)), end='\r')
        print('Copying from ClimateNA data... (100%)')
    print('Done.')


if __name__ == '__main__':
    main()
