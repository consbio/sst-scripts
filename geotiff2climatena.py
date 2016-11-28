import csv
import os
import sys

import click
import fiona
import numpy
import rasterio
from numpy.ma import is_masked
from pyproj import Proj, transform
from rasterio.features import rasterize
from rasterio.warp import transform_geom


@click.command()
@click.argument('in_file', type=click.Path(exists=True))
@click.argument('out_file', type=click.Path(exists=False))
@click.option(
    '--boundary', type=click.Path(exists=True), default=None, help='Land boundary file used to mask out oceans'
)
def main(in_file, out_file, boundary):
    if os.path.exists(out_file):
        confirm = input("The output file '{}' already exists. Do you wish to replace it? [y/n] ".format(out_file))
        if confirm.lower().strip() not in ['y', 'yes']:
            sys.exit()

    print('Loading DEM...')
    with rasterio.open(in_file) as ds:
        grid = ds.read()[0]
        bounds = ds.bounds
        affine = ds.profile['affine']
        width = ds.profile['width']

    if boundary:
        mask = numpy.zeros(grid.shape, dtype='uint8')

        with fiona.open(boundary, 'r') as shp:
            grid_projection = Proj('+init=EPSG:4326')
            shp_projection = Proj(shp.crs)

            ll = transform(grid_projection, shp_projection, bounds.left, bounds.bottom)
            ur = transform(grid_projection, shp_projection, bounds.right, bounds.top)

            features = list(shp.items(bbox=(*ll, *ur)))
            num_features = len(features)

            for i, feature in enumerate(features):
                geometry = transform_geom(shp.crs, {'init': 'EPSG:4326'}, feature[1]['geometry'])
                mask |= rasterize(
                    ((geometry, 1),), out_shape=mask.shape, transform=affine, fill=0, dtype=numpy.dtype('uint8'),
                    default_value=1
                )

                print('Masking DEM... ({}%)'.format(round(i / float(num_features) * 100)), end='\r')
            print('')

            grid = numpy.ma.masked_where(mask == 0, grid)

    print('Writing CSV...')
    with open(out_file, 'w') as f_out:
        csv_file = csv.writer(f_out)
        csv_file.writerow(['ID1', 'ID2', 'Lat', 'Lon', 'El'])

        for i, value in enumerate(grid.ravel()):
            if is_masked(value):
                continue

            col = i % width
            row = i // width
            x, y = affine * (col, row)

            # Todo: adjust to center of cell?

            csv_file.writerow([row, col, round(y, 7), round(x, 7), value])

    print('Done.')


if __name__ == '__main__':
    main()
