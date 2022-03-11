import csv
import os
from io import StringIO

import click
import numpy
import rasterio
from trefoil.geometry.bbox import BBox
from trefoil.netcdf.crs import set_crs
from trefoil.netcdf.variable import SpatialCoordinateVariables
from netCDF4 import Dataset
from pyproj import Proj

MULTIPLIERS = {
    'MAT': 10,
    'MWMT': 10,
    'MCMT': 10,
    'TD': 10,
    'AHM': 10,
    'SHM': 10,
    'EMT': 10,
    'EXT': 10,
    'Tave_sm': 10,
    'Tave_wt': 10,
    'Tmin_sp': 10
}


@click.command()
@click.argument('original_file', type=click.Path(exists=True))
@click.argument('climatena_file', type=click.Path(exists=True))
@click.argument('out_dir', type=click.Path(exists=True))
@click.option('--variables', 'valid_variables', default=None)
def main(original_file, climatena_file, out_dir, valid_variables):
    with rasterio.open(original_file) as ds:
        bounds = ds.bounds
        affine = ds.transform
        shape = ds.shape

    with open(climatena_file, 'r') as f_in:
        headers = csv.DictReader(f_in).fieldnames
        variables = [x for x in headers if x not in ('ID1', 'ID2', 'Latitude', 'Longitude', 'Elevation')]

    if valid_variables:
        valid = [x.strip().lower() for x in valid_variables.split(',')]
    else:
        valid = variables

    print('Creating datasets...')

    grid = numpy.zeros(shape, dtype='int32')
    grid = numpy.ma.masked_where(grid == 0, grid)

    for var in (x for x in variables if x.lower() in valid):
        out_path = os.path.join(
            out_dir, '{}_{}.nc'.format(os.path.splitext(os.path.basename(climatena_file))[0], var)
        )

        if os.path.exists(out_path):
            continue

        with Dataset(out_path, 'w', format='NETCDF4') as ds:
            projection = Proj('EPSG:4326')
            coord_vars = SpatialCoordinateVariables.from_bbox(
                BBox(bounds, projection=projection), *reversed(grid.shape)
            )
            coord_vars.add_to_dataset(ds, 'longitude', 'latitude')
            data_var = ds.createVariable(
                var, grid.dtype, dimensions=('latitude', 'longitude'), fill_value=grid.fill_value
            )
            data_var[:] = grid
            set_crs(ds, var, projection)

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
                usecols=[headers.index(x) for x in ['Latitude', 'Longitude'] + variables]
            )
            arr = numpy.moveaxis(arr, 1, 0)

            latitudes = arr[0]
            longitudes = arr[1]

            for i, var in enumerate(variables):
                if var.lower() in valid:
                    out_path = os.path.join(
                        out_dir, '{}_{}.nc'.format(os.path.splitext(os.path.basename(climatena_file))[0], var)
                    )

                    variable = arr[i + 2]

                    with Dataset(out_path, 'a') as ds:
                        grid = ds.variables[var][:]
                        fill_value = grid.fill_value
                        grid = grid.data

                        for j, value in enumerate(variable):
                            if value == -9999:
                                continue

                            col, row = [int(round(x)) for x in ~affine * (longitudes[j], latitudes[j])]

                            if var in MULTIPLIERS:
                                value *= MULTIPLIERS[var]

                            grid[row][col] = value

                        ds.variables[var][:] = numpy.ma.masked_where(grid == fill_value, grid)

            print('Copying from ClimateNA data... ({}%)'.format(round(f_in.tell() / end * 100)), end='\r')
        print('Copying from ClimateNA data... (100%)')
    print('Done.')


if __name__ == '__main__':
    main()
