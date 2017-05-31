# sst-scripts
Data processing scripts related to the Seedlot Selection Tool

## Generating ClimateNA data for the Seedlot Selection Tool  
1. Download elevation data for the area of interest ([example source](https://topotools.cr.usgs.gov/GMTED_viewer/viewer.htm))
2. If necessary, combine individual datasets into a single raster
3. Clip the raster dataset as needed
4. Run the `geotiff2climatena.py` script to convert the clipped DEM to the ClimateNA format, with the region boundary or a [continent boundaries](http://openstreetmapdata.com/data/land-polygons) shapefile that can be used to mask out oceans  
  ```$ python geotiff2climatena.py path/to/clipped_dem.tif path/to/climatena_dem.csv --boundary=path/to/boundary.shp```  
5. Run the ClimateNA tool, using the DEM CSV file as input to generate the desired outputs. For SST, we use:  
  * Normal 1961-1990 / Annual variables
  * More Normal Data / 1981_2010 / Annual Variables
  * Future Periods / 15GCM-Ensemble_rcp45_2025 / Annual Variables
  * Future Periods / 15GCM-Ensemble_rcp45_2055 / Annual Variables
  * Future Periods / 15GCM-Ensemble_rcp45_2085 / Annual Variables
  * Future Periods / 15GCM-Ensemble_rcp85_2025 / Annual Variables
  * Future Periods / 15GCM-Ensemble_rcp85_2055 / Annual Variables
  * Future Periods / 15GCM-Ensemble_rcp85_2085 / Annual Variables
6. Run the `climatena2netcdf.py` script to convert each of your ClimateNA outputs to NetCDF  
  `$ python climatena2netcdf.py path/to/clipped_dem.tif path/to/climatena_output.csv path/to/netcdf/dir`  
7. If needed, run the `cut_to_region.py` script to clip the NetCDF datasets from the previous step to smaller regions. Since you will have one NetCDF per variable, use `{variable}` to note where in the filename the variable is; the script will clip each NetCDF matching the file pattern.  
  `$ python cut_to_region.py path/to/full_netcdf_{variable}.nc path/to/clipped_netcdf_{variable}.nc`
