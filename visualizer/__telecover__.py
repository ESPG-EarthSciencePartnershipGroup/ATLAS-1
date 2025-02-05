#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Sep  1 12:02:25 2022

@author: nick
"""

import warnings, os, sys, glob
import xarray as xr
import numpy as np
import netCDF4 as nc
from .readers.parse_tlc_args import call_parser, check_parser
from .readers.check import check_channels
from .plotting import make_axis, make_title, make_plot
from .writters import make_header, export_ascii 
from .tools.smoothing import sliding_average_2D, sliding_average_1D
from .tools import normalize, sector

# Ignores all warnings --> they are not printed in terminal
warnings.filterwarnings('ignore')

def main(args, __version__):
    # Check the command line argument information
    args = check_parser(args)
    
    print('-----------------------------------------')
    print('Initializing the Telecover Test...')
    print('-----------------------------------------')

    # Read the quicklook file
    data = xr.open_dataset(args['input_file'])
    ranges = data.Range_levels

    dwl = data.Detected_Wavelength
    
    # Extract signal
    if 'Range_Corrected_Signals_North_Sector' in data.keys():
        sig_n = data['Range_Corrected_Signals_North_Sector']
        sig_e = data['Range_Corrected_Signals_East_Sector']
        sig_s = data['Range_Corrected_Signals_South_Sector']
        sig_w = data['Range_Corrected_Signals_West_Sector']
        
        sig_n = sig_n.copy().where(sig_n != nc.default_fillvals['f8'])
        sig_e = sig_e.copy().where(sig_e != nc.default_fillvals['f8'])
        sig_s = sig_s.copy().where(sig_s != nc.default_fillvals['f8'])
        sig_w = sig_w.copy().where(sig_w != nc.default_fillvals['f8'])
        
        sampling_sec = np.min([np.min((data.Raw_Data_Stop_Time_North_Sector-data.Raw_Data_Start_Time_North_Sector).values),
                               np.min((data.Raw_Data_Stop_Time_East_Sector-data.Raw_Data_Start_Time_East_Sector).values),
                               np.min((data.Raw_Data_Stop_Time_South_Sector-data.Raw_Data_Start_Time_South_Sector).values),
                               np.min((data.Raw_Data_Stop_Time_West_Sector-data.Raw_Data_Start_Time_West_Sector).values)])
                    
    else:
        sig_n = []
        sig_e = []
        sig_s = []
        sig_w = []
        sampling_sec = np.nan
        
    if 'Range_Corrected_Signals_Outer_Ring' in data.keys():
        sig_o = data['Range_Corrected_Signals_Outer_Ring']
        sig_i = data['Range_Corrected_Signals_Inner_Ring']
        
        sig_o = sig_n.copy().where(sig_o != nc.default_fillvals['f8'])
        sig_i = sig_e.copy().where(sig_i != nc.default_fillvals['f8'])
        
        sampling_rin = np.min([np.min((data.Raw_Data_Stop_Time_Outer_Ring-data.Raw_Data_Start_Time_Outer_Ring).values),
                               np.min((data.Raw_Data_Stop_Time_Inner_Ring-data.Raw_Data_Start_Time_Inner_Ring).values)])

    else:
        sig_o = []
        sig_i = []
        sampling_rin = np.nan
    
    # Check if the parsed channels exist
    channels = \
        check_channels(sel_channels = args['channels'], 
                       all_channels = data.channel.values,
                       exclude_telescope_type = args['exclude_telescope_type'], 
                       exclude_channel_type = args['exclude_channel_type'], 
                       exclude_acquisition_mode = args['exclude_acquisition_mode'], 
                       exclude_channel_subtype = args['exclude_channel_subtype'])
    
    # iterate over the channels
    for ch in channels:
        print(f"-- channel: {ch}")
        
        ch_d = dict(channel = ch)
        
        ranges_ch = ranges.copy().loc[ch_d].values
        
        dwl_ch = dwl.loc[ch_d].values
        
        # Create the x axis (height/range)
        x_lbin, x_ubin, x_llim, x_ulim, x_vals, x_label = \
            make_axis.telecover_x(heights = data.Height_levels.loc[ch_d].values, 
                                  ranges = data.Range_levels.loc[ch_d].values,
                                  x_lims = args['x_lims'], 
                                  use_dis = args['use_distance'])
    
        if isinstance(sig_n,list) == False:
            iters = np.min([sig_n.time_n.size,
                            sig_e.time_e.size,
                            sig_s.time_s.size,
                            sig_w.time_w.size])
    
            extra_sec = {'N' : False,
                         'E' : False,
                         'S' : False,
                         'W' : False}

            coef_n, y_m_n, y_sm_n, y_m_sm_n, y_l_sm_n, y_u_sm_n, \
            y_extra_n, y_extra_sm_n, extra_sec['N'] = \
                sector.process(x = x_vals, 
                               y = sig_n.loc[ch_d].values, 
                               iters = iters, 
                               smooth = args['smooth'], 
                               x_sm_lims = args['smoothing_range'],
                               x_sm_win = args['smoothing_window'],
                               expo = args['smooth_exponential'],
                               region = args['normalization_region'])
                
            coef_e, y_m_e, y_sm_e, y_m_sm_e, y_l_sm_e, y_u_sm_e, \
            y_extra_e, y_extra_sm_e, extra_sec['E'] = \
                sector.process(x = x_vals, 
                               y = sig_e.loc[ch_d].values, 
                               iters = iters, 
                               smooth = args['smooth'], 
                               x_sm_lims = args['smoothing_range'],
                               x_sm_win = args['smoothing_window'],
                               expo = args['smooth_exponential'],
                               region = args['normalization_region'])
                
            coef_s, y_m_s, y_sm_s, y_m_sm_s, y_l_sm_s, y_u_sm_s, \
            y_extra_s, y_extra_sm_s, extra_sec['S'] = \
                sector.process(x = x_vals, 
                               y = sig_s.loc[ch_d].values, 
                               iters = iters, 
                               smooth = args['smooth'], 
                               x_sm_lims = args['smoothing_range'],
                               x_sm_win = args['smoothing_window'],
                               expo = args['smooth_exponential'],
                               region = args['normalization_region'])
                
            coef_w, y_m_w, y_sm_w, y_m_sm_w, y_l_sm_w, y_u_sm_w, \
            y_extra_w, y_extra_sm_w, extra_sec['W'] = \
                sector.process(x = x_vals, 
                               y = sig_w.loc[ch_d].values, 
                               iters = iters, 
                               smooth = args['smooth'], 
                               x_sm_lims = args['smoothing_range'],
                               x_sm_win = args['smoothing_window'],
                               expo = args['smooth_exponential'],
                               region = args['normalization_region'])

            # Create the y axis (signal)
            y_llim, y_ulim, y_llim_nr, y_ulim_nr = \
                make_axis.telecover_y(sig = [y_m_sm_n[slice(x_lbin,x_ubin+1)],
                                             y_m_sm_e[slice(x_lbin,x_ubin+1)],
                                             y_m_sm_s[slice(x_lbin,x_ubin+1)],
                                             y_m_sm_w[slice(x_lbin,x_ubin+1)]],
                                      sig_nr = [coef_n * y_m_sm_n[slice(x_lbin,x_ubin+1)],
                                                coef_e * y_m_sm_e[slice(x_lbin,x_ubin+1)],
                                                coef_s * y_m_sm_s[slice(x_lbin,x_ubin+1)],
                                                coef_w * y_m_sm_w[slice(x_lbin,x_ubin+1)]],
                                      y_lims = args['y_lims'])
            
                    
            # Make title
            title = make_title.telecover(start_date = data.RawData_Start_Date,
                                        start_time = data.RawData_Start_Time_UT, 
                                        end_time = data.RawData_Stop_Time_UT, 
                                        lidar = data.Lidar_Name, 
                                        channel = ch, 
                                        zan = data.Laser_Pointing_Angle,
                                        loc = data.Lidar_Location,
                                        iters = iters,
                                        sampling = sampling_sec,
                                        smooth = args['smooth'],
                                        sm_lims = args['smoothing_range'],
                                        sm_win = args['smoothing_window'],
                                        sm_expo = args['smooth_exponential'])
        
        
            # Make filename
            fname = f'{data.Measurement_ID}_{data.Lidar_Name}_tlc_sectors_{ch}_ATLAS_{__version__}.png'

            # Make the plot
            fpath = \
                make_plot.telecover_sec(dir_out = args['output_folder'], 
                                        fname = fname, title = title,
                                        dpi_val = args['dpi'],
                                        color_reduction = args['color_reduction'],
                                        norm_region = args['normalization_region'],
                                        use_nonrc = args['use_non_rangecor'],
                                        x_vals = x_vals, 
                                        y1_raw = y_m_n, 
                                        y2_raw = y_m_e, 
                                        y3_raw = y_m_s, 
                                        y4_raw = y_m_w,   
                                        y1_vals = y_m_sm_n, 
                                        y2_vals = y_m_sm_e, 
                                        y3_vals = y_m_sm_s, 
                                        y4_vals = y_m_sm_w,
                                        y1_extr = y_extra_sm_n, 
                                        y2_extr = y_extra_sm_e, 
                                        y3_extr = y_extra_sm_s, 
                                        y4_extr = y_extra_sm_w,
                                        y1_extr_raw = y_extra_n, 
                                        y2_extr_raw = y_extra_e, 
                                        y3_extr_raw = y_extra_s, 
                                        y4_extr_raw = y_extra_w,
                                        y1_lvar = y_l_sm_n, 
                                        y2_lvar = y_l_sm_e, 
                                        y3_lvar = y_l_sm_s, 
                                        y4_lvar = y_l_sm_w,
                                        y1_uvar = y_u_sm_n, 
                                        y2_uvar = y_u_sm_e, 
                                        y3_uvar = y_u_sm_s, 
                                        y4_uvar = y_u_sm_w,
                                        coef_1 = coef_n, 
                                        coef_2 = coef_e, 
                                        coef_3 = coef_s, 
                                        coef_4 = coef_w,
                                        ranges = ranges_ch,
                                        x_lbin = x_lbin, x_ubin = x_ubin,
                                        x_llim = x_llim, x_ulim = x_ulim, 
                                        y_llim = y_llim, y_ulim = y_ulim, 
                                        y_llim_nr = y_llim_nr, 
                                        y_ulim_nr = y_ulim_nr, 
                                        x_label = x_label,
                                        x_tick = args['x_tick'],
                                        use_last = args['use_last'],
                                        iters = iters)
            
            sectors = {'N' : y_m_n,
                       'E' : y_m_e,
                       'S' : y_m_s,
                       'W' : y_m_w}
            
            sectors_e = {'N' : y_extra_n,
                         'E' : y_extra_e,
                         'S' : y_extra_s,
                         'W' : y_extra_w}
            
            # Make ascii file header
            header = \
                make_header.telecover(start_date = data.RawData_Start_Date, 
                                      start_time = data.RawData_Start_Time_UT, 
                                      sampling_sec = iters * sampling_sec, 
                                      wave = dwl_ch, 
                                      lidar = data.Lidar_Name, 
                                      loc = data.Lidar_Location, 
                                      meas_id = data.Measurement_ID, 
                                      channel = ch,
                                      iters = 1,
                                      extra_sec = extra_sec)
            
            # Make the ascii filename
            ascii_name = f'{data.Measurement_ID}_{data.Lidar_Name}_tlc_sectors_{ch}_ATLAS_{__version__}.txt'
    
            # Export to ascii (Volker's format)        
            export_ascii.telecover(dir_out = args['output_folder'], 
                                   fname = ascii_name, 
                                   header = header,
                                   iters = 1, 
                                   alt = x_vals, 
                                   sectors = sectors, 
                                   sectors_e = sectors_e)

            # Add metadata to the quicklook plot
            from PIL import Image
            from PIL import PngImagePlugin
                       
            METADATA = {"processing_software" : f"ATLAS_{data.version}",
                        "measurement_id" : f"{data.Measurement_ID}",
                        "channel" : f"{ch}",
                        "smooth" : f"{args['smooth']}",
                        "smoothing_exponential" : f"{args['smooth_exponential']}",
                        "smoothing_range" : f"{args['smoothing_range']}",
                        "smoothing_window": f"{args['smoothing_window']}",
                        "dpi" : f"{args['dpi']}",
                        "color_reduction" : f"{args['color_reduction']}",
                        "normalization_region" : f"{args['normalization_region']}",
                        "use_distance" : f"{args['use_distance']}",
                        "use_last" : f"{args['use_last']}",
                        "use_non_rangecor" : f"{args['use_non_rangecor']}",
                        "x_lims" : f"{args['x_lims']}",
                        "y_lims" : f"{args['y_lims']}",
                        "x_tick" : f"{args['x_tick']}"}
    
                    
            im = Image.open(fpath)
            meta = PngImagePlugin.PngInfo()
        
            for x in METADATA.keys():
                meta.add_text(x, METADATA[x])
                
            im.save(fpath, "png", pnginfo = meta)
        
        if isinstance(sig_o,list) == False:
            iters = np.min([sig_o.time_n.size,
                            sig_i.time_e.size])
        
            extra_sec = {'O' : False,
                         'I' : False}
        
            coef_o, y_m_o, y_sm_o, y_m_sm_o, y_l_sm_o, y_u_sm_o, \
            y_extra_o, y_extra_sm_o, extra_sec['O'] = \
                sector.process(x = x_vals, 
                               y = sig_o.loc[ch_d].values, 
                               iters = iters, 
                               smooth = args['smooth'], 
                               x_sm_lims = args['smoothing_range'],
                               x_sm_win = args['smoothing_window'],
                               expo = args['smooth_exponential'],
                               region = args['normalization_region'])
                
            coef_i, y_m_i, y_sm_i, y_m_sm_i, y_l_sm_i, y_u_sm_i, \
            y_extra_i, y_extra_sm_i, extra_sec['I'] = \
                sector.process(x = x_vals, 
                               y = sig_i.loc[ch_d].values, 
                               iters = iters, 
                               smooth = args['smooth'], 
                               x_sm_lims = args['smoothing_range'],
                               x_sm_win = args['smoothing_window'],
                               expo = args['smooth_exponential'],
                               region = args['normalization_region'])
                
            # Create the y axis (signal)
            y_llim, y_ulim, y_llim_nr, y_ulim_nr = \
                make_axis.telecover_y(sig = [y_m_sm_o[slice(x_lbin,x_ubin+1)],
                                             y_m_sm_i[slice(x_lbin,x_ubin+1)]],
                                      sig_nr = [coef_o * y_m_sm_n[slice(x_lbin,x_ubin+1)],
                                                coef_i * y_m_sm_e[slice(x_lbin,x_ubin+1)]],
                                      y_lims = args['y_lims'])
            
                    
                    
            # Make title
            title = make_title.telecover(start_date = data.RawData_Start_Date,
                                        start_time = data.RawData_Start_Time_UT, 
                                        end_time = data.RawData_Stop_Time_UT, 
                                        lidar = data.Lidar_Name, 
                                        channel = ch, 
                                        zan = data.Laser_Pointing_Angle,
                                        loc = data.Lidar_Location,
                                        iters = iters,
                                        sampling = sampling_sec,
                                        smooth = args['smooth'],
                                        sm_lims = args['smoothing_range'],
                                        sm_win = args['smoothing_window'],
                                        sm_expo = args['smooth_exponential'])
        
            # Make filename
            fname = f'{data.Measurement_ID}_{data.Lidar_Name}_tlc_sectors_{ch}_ATLAS_{__version__}.png'

            # Make the plot
            fpath = \
                make_plot.telecover_sec(dir_out = args['output_folder'], 
                                        fname = fname, title = title,
                                        dpi_val = args['dpi'],
                                        color_reduction = args['color_reduction'],
                                        norm_region = args['normalization_region'],
                                        use_nonrc = args['use_non_rangecor'],
                                        x_vals = x_vals, 
                                        y1_raw = y_m_o, 
                                        y2_raw = y_m_i, 
                                        y1_vals = y_m_sm_o, 
                                        y2_vals = y_m_sm_i, 
                                        y1_extr = y_extra_sm_o, 
                                        y2_extr = y_extra_sm_i, 
                                        y1_extr_raw = y_extra_o, 
                                        y2_extr_raw = y_extra_i, 
                                        y1_lvar = y_l_sm_o, 
                                        y2_lvar = y_l_sm_i, 
                                        y1_uvar = y_u_sm_o, 
                                        y2_uvar = y_u_sm_i, 
                                        coef_1 = coef_o, 
                                        coef_2 = coef_i, 
                                        ranges = ranges_ch,
                                        x_lbin = x_lbin, x_ubin = x_ubin,
                                        x_llim = x_llim, x_ulim = x_ulim, 
                                        y_llim = y_llim, y_ulim = y_ulim, 
                                        y_llim_nr = y_llim_nr, 
                                        y_ulim_nr = y_ulim_nr, 
                                        x_label = x_label,
                                        x_tick = args['x_tick'],
                                        use_last = args['use_last'],
                                        iters = iters)
            
            sectors = {'O' : y_m_n,
                       'I' : y_m_e}
            
            sectors_e = {'O' : y_extra_n,
                         'I' : y_extra_e}
            
            # Make ascii file header
            header = \
                make_header.telecover(start_date = data.RawData_Start_Date, 
                                      start_time = data.RawData_Start_Time_UT, 
                                      sampling_sec = iters * sampling_sec, 
                                      wave = dwl_ch, 
                                      lidar = data.Lidar_Name, 
                                      loc = data.Lidar_Location, 
                                      meas_id = data.Measurement_ID, 
                                      channel = ch,
                                      iters = 1,
                                      extra_sec = extra_sec)
            
            # Make the ascii filename
            ascii_name = f'{data.Measurement_ID}_{data.Lidar_Name}_tlc_sectors_{ch}_ATLAS_{__version__}.txt'
    
            # Export to ascii (Volker's format)        
            export_ascii.telecover(dir_out = args['output_folder'], 
                                   fname = ascii_name, 
                                   header = header,
                                   iters = 1, 
                                   alt = x_vals, 
                                   sectors = sectors, 
                                   sectors_e = sectors_e)

            # Add metadata to the quicklook plot
            from PIL import Image
            from PIL import PngImagePlugin
                       
            METADATA = {"processing_software" : f"ATLAS_{data.version}",
                        "measurement_id" : f"{data.Measurement_ID}",
                        "channel" : f"{ch}",
                        "smooth" : f"{args['smooth']}",
                        "smoothing_exponential" : f"{args['smooth_exponential']}",
                        "smoothing_range" : f"{args['smoothing_range']}",
                        "smoothing_window": f"{args['smoothing_window']}",
                        "dpi" : f"{args['dpi']}",
                        "color_reduction" : f"{args['color_reduction']}",
                        "normalization_region" : f"{args['normalization_region']}",
                        "use_distance" : f"{args['use_distance']}",
                        "use_last" : f"{args['use_last']}",
                        "use_non_rangecor" : f"{args['use_non_rangecor']}",
                        "x_lims" : f"{args['x_lims']}",
                        "y_lims" : f"{args['y_lims']}",
                        "x_tick" : f"{args['x_tick']}"}
    
                    
            im = Image.open(fpath)
            meta = PngImagePlugin.PngInfo()
        
            for x in METADATA.keys():
                meta.add_text(x, METADATA[x])
                
            im.save(fpath, "png", pnginfo = meta)
    
    print('-----------------------------------------')
    print(' ')
    
    return()

if __name__ == '__main__':
    
    sys.path.append('../')
    
    from version import __version__
    
    # Get the command line argument information
    args = call_parser()
    
    # Call main
    main(args, __version__)
    
