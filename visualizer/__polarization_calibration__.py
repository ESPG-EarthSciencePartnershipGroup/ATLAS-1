#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Sep  1 12:02:25 2022

@author: nick
"""

import warnings, sys
import xarray as xr
import numpy as np
import netCDF4 as nc
from .readers.parse_pcb_args import call_parser, check_parser
from .readers.check import check_channels_no_exclude as check_channels
from .plotting import make_axis, make_title, make_plot
from .tools import average
from .writters import make_header, export_ascii 

# Ignores all warnings --> they are not printed in terminal
warnings.filterwarnings('ignore')

def main(args, __version__):
    # Check the command line argument information
    args = check_parser(args)
    
    print('-----------------------------------------')
    print('Initializing the pcb. Calibration...')
    print('-----------------------------------------')
    
    # Read the pcb cal file
    data = xr.open_dataset(args['input_file'])
    
    # Extract signal
    sig_ray = data.Range_Corrected_Signals_Rayleigh
    sig_ray = sig_ray.copy().where(sig_ray != nc.default_fillvals['f8'])
    
    sig_m45 = data.Range_Corrected_Signals_minus_45
    sig_m45 = sig_m45.copy().where(sig_m45 != nc.default_fillvals['f8'])\
        .mean(dim = 'time_m45')
    
    sig_p45 = data.Range_Corrected_Signals_plus_45
    sig_p45 = sig_p45.copy().where(sig_p45 != nc.default_fillvals['f8'])\
        .mean(dim = 'time_p45')
    
    sampling_cal = (data.Raw_Data_Stop_Time_minus_45 - data.Raw_Data_Start_Time_minus_45).values[0] +\
        (data.Raw_Data_Stop_Time_plus_45 - data.Raw_Data_Start_Time_plus_45).values[0]

    sampling_ray = (data.Raw_Data_Stop_Time_Rayleigh - data.Raw_Data_Start_Time_Rayleigh).values
    
    # Extract signal time, channels, and bins
    channels = data.channel.values
    
    # Extract IFF info
    dwl = data.Detected_Wavelength_Rayleigh
    ewl = data.Emitted_Wavelength_Rayleigh
    bdw = data.Channel_Bandwidth_Rayleigh
    
    mol_method = data.Molecular_atmosphere_method
    if 'Sounding_Station_Name' in data.attrs:
        st_name = data.Sounding_Station_Name
    else: st_name = ''
    if 'Sounding_Start_Date' in data.attrs:
        rs_start_date = data.Sounding_Start_Date
    else: rs_start_date = ''
    if 'Sounding_Start_Time_UT' in data.attrs:
        rs_start_time = data.Sounding_Start_Time_UT
    else: rs_start_time = ''
    if 'WMO_Station_Number' in data.attrs:
        wmo_id = data.WMO_Station_Number
    else: wmo_id = ''
    if 'WBAN_Station_Number' in data.attrs:
        wban_id = data.WBAN_Station_Number
    else: wban_id = ''
    
    if args['ch_r'] == None or args['ch_t'] == None:
        channels_r = []
        channels_t = []
        ch_r_all = np.array([ch for ch in channels if ch[7] == 'r'])
        ch_t_all = np.array([ch for ch in channels if ch[7] == 't'])
        for ch_r in ch_r_all:
            for ch_t in ch_t_all:
                if ch_r[4]  == ch_t[4] and ch_r[6]  == ch_t[6] and \
                    ch_r[:4]  == ch_t[:4]:
                        channels_r.extend([ch_r])
                        channels_t.extend([ch_t])
    else:
        channels_r = args['ch_r']
        channels_t = args['ch_t']

    # Check if the parsed channels exist
    channels_r = check_channels(sel_channels = channels_r, all_channels = channels)
    channels_t = check_channels(sel_channels = channels_t, all_channels = channels)
    
    G_R_def = len(channels_r) * [1.]
    G_T_def = len(channels_r) * [1.]
    H_R_def = len(channels_r) * [1.]
    H_T_def = len(channels_r) * [1.]

    for i in range(len(channels_r)):
        if channels_r[i][5] == 'c' and channels_t[i][5] == 'p':
            H_R_def[i] = -1.
        if channels_r[i][5] == 'p' and channels_t[i][5] == 'c':
            H_T_def[i] = -1.
        if channels_r[i][5] == 't' and channels_t[i][5] == 'p':
            H_R_def[i] =  0.
        if channels_r[i][5] == 'p' and channels_t[i][5] == 't':
            H_T_def[i] =  0.
        if channels_r[i][5] == 't' and channels_t[i][5] == 'c':
            H_R_def[i] =  0.
            H_T_def[i] = -1.
        if channels_r[i][5] == 'c' and channels_t[i][5] == 't':
            H_R_def[i] = -1.
            H_T_def[i] =  0.

    # Extract pair values
    if args['K'] == None:
        K = len(channels_r) * [1.]
    else:
        K = args['K']

    if args['G_R'] == None:
        G_R = G_R_def
    else:
        G_R = args['G_R']

    if args['G_T'] == None:
        G_T = G_T_def
    else:
        G_T = args['G_T']

    if args['H_R'] == None:
        H_R = H_R_def
    else:
        H_R = args['H_R']

    if args['H_T'] == None:
        H_T = H_T_def
    else:
        H_T = args['H_T']

    if args['R_to_T_transmission_ratio'] == None:
        TR_to_TT = len(channels_r) * [1.]
    else:
        TR_to_TT = args['R_to_T_transmission_ratio']

    # Extract Molecular Depolarization Ratio and Calucalte the Atm. Parameter alpha
    mldr = data.Molecular_Linear_Depolarization_Ratio
        
    # Iterate over the channels
    for i in range(len(channels_r)):
                
        ch_r = channels_r[i]
        ch_t = channels_t[i]
        K_ch = K[i]
        G_R_ch = G_R[i]
        G_T_ch = G_T[i]
        H_R_ch = H_R[i]
        H_T_ch = H_T[i]
        G_R_def_ch = G_R_def[i]
        G_T_def_ch = G_T_def[i]
        H_R_def_ch = H_R_def[i]
        H_T_def_ch = H_T_def[i]
        TR_to_TT_ch = TR_to_TT[i]
        
        print(f"-- channels: {ch_r} & {ch_t}")

        ch_r_d = dict(channel = ch_r)
        ch_t_d = dict(channel = ch_t)
        
        dwl_ch = dwl.copy().loc[ch_r_d].values
        ewl_ch = ewl.copy().loc[ch_r_d].values
        bdw_ch = bdw.copy().loc[ch_r_d].values
        
        sig_r_p45_ch = sig_p45.copy().loc[ch_r_d].values
        sig_t_p45_ch = sig_p45.copy().loc[ch_t_d].values
        sig_r_m45_ch = sig_m45.copy().loc[ch_r_d].values
        sig_t_m45_ch = sig_m45.copy().loc[ch_t_d].values
        sig_r_ray_ch = sig_ray.copy().loc[ch_r_d].values
        sig_t_ray_ch = sig_ray.copy().loc[ch_t_d].values
        
        delta_m_prf = mldr.loc[ch_r_d].values

        # Create the y axis (height/range)
        x_lbin_cal, x_ubin_cal, x_llim_cal, x_ulim_cal, x_vals_cal, x_label_cal = \
            make_axis.polarization_calibration_x(
                heights = data.Height_levels_Calibration.loc[ch_r_d].values, 
                ranges = data.Range_levels_Calibration.loc[ch_r_d].values,
                x_lims = args['x_lims_calibration'], 
                use_dis = args['use_distance'])
    
        # Create the y axis (height/range)
        x_lbin_ray, x_ubin_ray, x_llim_ray, x_ulim_ray, x_vals_ray, x_label_ray = \
            make_axis.polarization_calibration_x(
                heights = data.Height_levels_Rayleigh.loc[ch_r_d].values, 
                ranges = data.Range_levels_Rayleigh.loc[ch_r_d].values,
                x_lims = args['x_lims_rayleigh'], 
                use_dis = args['use_distance'])
    
        # Smoothing
        if args['smooth']== True:
            if not isinstance(args['smoothing_window'],list):
                from .tools.smoothing import sliding_average_1D_fast as smooth_1D
            else:
                from .tools.smoothing import sliding_average_1D as smooth_1D

            y_r_m45_sm, _ = \
                smooth_1D(y_vals = sig_r_m45_ch, 
                          x_vals = x_vals_cal,
                          x_sm_lims = args['smoothing_range'],
                          x_sm_win = args['smoothing_window'],
                          expo = args['smooth_exponential'])
    
            y_t_m45_sm, _ = \
                smooth_1D(y_vals = sig_t_m45_ch, 
                          x_vals = x_vals_cal,
                          x_sm_lims = args['smoothing_range'],
                          x_sm_win = args['smoothing_window'],
                          expo = args['smooth_exponential'])
                
            y_r_p45_sm, _ = \
                smooth_1D(y_vals = sig_r_p45_ch, 
                          x_vals = x_vals_cal,
                          x_sm_lims = args['smoothing_range'],
                          x_sm_win = args['smoothing_window'],
                          expo = args['smooth_exponential'])
    
            y_t_p45_sm, _ = \
                smooth_1D(y_vals = sig_t_p45_ch, 
                          x_vals = x_vals_cal,
                          x_sm_lims = args['smoothing_range'],
                          x_sm_win = args['smoothing_window'],
                          expo = args['smooth_exponential'])
    
            y_r_rax_sm, _ = \
                smooth_1D(y_vals = sig_r_ray_ch, 
                          x_vals = x_vals_ray,
                          x_sm_lims = args['smoothing_range'],
                          x_sm_win = args['smoothing_window'],
                          expo = args['smooth_exponential'])    
                
            y_t_rax_sm, _ = \
                smooth_1D(y_vals = sig_t_ray_ch, 
                          x_vals = x_vals_ray,
                          x_sm_lims = args['smoothing_range'],
                          x_sm_win = args['smoothing_window'],
                          expo = args['smooth_exponential'])      
                
        else:
            y_r_m45_sm = sig_r_m45_ch
            y_t_m45_sm = sig_t_m45_ch
            y_r_p45_sm = sig_r_p45_ch
            y_t_p45_sm = sig_t_p45_ch
            y_r_rax_sm = sig_r_ray_ch
            y_t_rax_sm = sig_t_ray_ch
        
        avg_r_m45, _, sem_r_m45 = \
            average.region(sig = sig_r_m45_ch, 
                           x_vals = x_vals_cal, 
                           region = args['calibration_region'], 
                           axis = 0,
                           squeeze = True)
        
        avg_t_m45, _, sem_t_m45 = \
            average.region(sig = sig_t_m45_ch, 
                           x_vals = x_vals_cal, 
                           region = args['calibration_region'], 
                           axis = 0,
                           squeeze = True)
        
        avg_r_p45, _, sem_r_p45 = \
            average.region(sig = sig_r_p45_ch, 
                           x_vals = x_vals_cal, 
                           region = args['calibration_region'], 
                           axis = 0,
                           squeeze = True)
        
        avg_t_p45, _, sem_t_p45 = \
            average.region(sig = sig_t_p45_ch, 
                           x_vals = x_vals_cal, 
                           region = args['calibration_region'], 
                           axis = 0,
                           squeeze = True)
        
        avg_r_ray, _, sem_r_ray = \
            average.region(sig = sig_r_ray_ch, 
                           x_vals = x_vals_ray, 
                           region = args['rayleigh_region'], 
                           axis = 0,
                           squeeze = True)
        
        avg_t_ray, _, sem_t_ray = \
            average.region(sig = sig_t_ray_ch, 
                           x_vals = x_vals_ray, 
                           region = args['rayleigh_region'], 
                           axis = 0,
                           squeeze = True)

        delta_m, _, _ = \
            average.region(sig = delta_m_prf, 
                           x_vals = x_vals_ray, 
                           region = args['rayleigh_region'], 
                           axis = 0,
                           squeeze = True) 
                
        eta_m45_prf = (y_r_m45_sm / y_t_m45_sm) 
    
        eta_p45_prf = (y_r_p45_sm / y_t_p45_sm)
        
        eta_prf = np.sqrt(eta_m45_prf * eta_p45_prf)
        
        avg_r_m45_i = np.random.normal(loc = avg_r_m45, scale = sem_r_m45, size = 200)
        avg_t_m45_i = np.random.normal(loc = avg_t_m45, scale = sem_t_m45, size = 200)
        avg_r_p45_i = np.random.normal(loc = avg_r_p45, scale = sem_r_p45, size = 200)
        avg_t_p45_i = np.random.normal(loc = avg_t_p45, scale = sem_t_p45, size = 200)
        avg_r_ray_i = np.random.normal(loc = avg_r_ray, scale = sem_r_ray, size = 200)
        avg_t_ray_i = np.random.normal(loc = avg_t_p45, scale = sem_t_p45, size = 200)

        eta_f_s_m45 = (avg_r_m45_i / avg_t_m45_i)
        
        eta_f_s_m45[0] = (avg_r_m45 / avg_t_m45)
        
        eta_f_s_p45 = (avg_r_p45_i / avg_t_p45_i)

        eta_f_s_p45[0] = (avg_r_p45 / avg_t_p45)
        
        eta_f_s = np.sqrt(eta_f_s_p45 * eta_f_s_m45)
        
        eta_s = eta_f_s / TR_to_TT_ch

        eta = eta_s / K_ch

        delta_s_prf = (y_r_rax_sm / y_t_rax_sm) / eta[0]

        delta_s = (avg_r_ray_i / avg_t_ray_i) / eta
        delta_s[0] = (avg_r_ray / avg_t_ray) / eta[0]

        delta_s_prf = (y_r_rax_sm / y_t_rax_sm) / eta[0]

        delta_c_prf = (delta_s_prf * (G_T_def_ch + H_T_def_ch) - (G_R_def_ch + H_R_def_ch)) /\
            ((G_R_def_ch - H_R_def_ch) - delta_s_prf * (G_T_def_ch - H_T_def_ch))
        
        delta_c = (delta_s * (G_T_def_ch+ H_T_def_ch) - (G_R_def_ch + H_R_def_ch)) /\
            ((G_R_def_ch - H_R_def_ch) - delta_s * (G_T_def_ch - H_T_def_ch))

        delta_prf = (delta_s_prf * (G_T_ch + H_T_ch) - (G_R_ch + H_R_ch)) /\
            ((G_R_ch - H_R_ch) - delta_s_prf * (G_T_ch - H_T_ch))

        delta = (delta_s * (G_T_ch + H_T_ch) - (G_R_ch + H_R_ch)) /\
            ((G_R_ch - H_R_ch) - delta_s * (G_T_ch - H_T_ch))
                    
        psi = (eta_f_s_p45 - eta_f_s_m45) / (eta_f_s_p45 + eta_f_s_m45)
        
        kappa = 1.
        
        epsilon = np.rad2deg(0.5 * np.arcsin(np.tan(0.5 * np.arcsin(psi) / kappa)))
        # kappa = np.tan(0.5 * np.arcsin(psi)) / np.sin(2. * np.deg2rad(epsilon)) 
    
            
        # Create the y axis (calibration)
        y_llim_cal, y_ulim_cal, y_label_cal = \
            make_axis.polarization_calibration_cal_y(
                ratio_m = eta_f_s_m45[0], ratio_p = eta_f_s_p45[0],
                y_lims_cal = args['y_lims_calibration'])
            
        # Create the y axis (rayleigh)
        y_llim_ray, y_ulim_ray, y_label_ray = \
            make_axis.polarization_calibration_ray_y(
                ratio = delta_c[0], y_lims_ray = args['y_lims_rayleigh'])
        
                
        # Make title
        title = make_title.polarization_calibration(
                start_date_cal = data.RawData_Start_Date_Calibration,
                start_time_cal = data.RawData_Start_Time_UT_Calibration, 
                end_time_cal = data.RawData_Stop_Time_UT_Calibration,
                start_date_ray = data.RawData_Start_Date_Rayleigh,
                start_time_ray = data.RawData_Start_Time_UT_Rayleigh, 
                end_time_ray = data.RawData_Stop_Time_UT_Rayleigh,
                lidar = data.Lidar_Name, 
                channel_r = ch_r, 
                channel_t = ch_t, 
                zan = data.Laser_Pointing_Angle_Calibration,
                loc = data.Lidar_Location,
                dwl = dwl_ch,
                ewl = ewl_ch,
                bdw = bdw_ch,
                smooth = args['smooth'],
                sm_lims = args['smoothing_range'],
                sm_win = args['smoothing_window'],
                sm_expo = args['smooth_exponential'],
                mol_method = mol_method,
                st_name = st_name,
                rs_start_date = rs_start_date,
                rs_start_time = rs_start_time, 
                wmo_id = wmo_id,
                wban_id = wban_id)
        
       
        # Make filename
        fname = f'{data.Measurement_ID_Calibration}_{data.Lidar_Name}_pcb_{ch_r}_to_{ch_t}_ATLAS_{__version__}.png'

        fpath = \
            make_plot.polarization_calibration(dir_out = args['output_folder'], 
                                               fname = fname, title = title,
                                               dpi_val = args['dpi'],
                                               color_reduction = args['color_reduction'],
                                               cal_region = args['calibration_region'],
                                               vdr_region = args['rayleigh_region'],
                                               x_vals_cal = x_vals_cal, 
                                               x_vals_vdr = x_vals_ray, 
                                               y1_vals = eta_prf, 
                                               y2_vals = eta_p45_prf, 
                                               y3_vals = eta_m45_prf, 
                                               y4_vals = delta_c_prf,
                                               y5_vals = delta_prf,
                                               y6_vals = delta_m_prf,
                                               eta = eta[0], 
                                               eta_f_s = eta_f_s[0], 
                                               eta_s = eta_s[0], 
                                               delta_m = delta_m,
                                               delta_c = delta_c[0],
                                               delta = delta[0],
                                               epsilon = epsilon[0],
                                               eta_err = np.std(eta[1:]), 
                                               eta_f_s_err = np.std(eta_f_s[1:]), 
                                               eta_s_err = np.std(eta_s[1:]), 
                                               delta_c_err = np.std(delta_c[1:]),
                                               delta_err = np.std(delta[1:]),
                                               epsilon_err = np.std(epsilon[0]),
                                               x_lbin_cal = x_lbin_cal,
                                               x_ubin_cal = x_ubin_cal, 
                                               x_llim_cal = x_llim_cal,
                                               x_ulim_cal = x_ulim_cal, 
                                               y_llim_cal = y_llim_cal, 
                                               y_ulim_cal = y_ulim_cal, 
                                               x_lbin_vdr = x_lbin_ray, 
                                               x_ubin_vdr = x_ubin_ray, 
                                               x_llim_vdr = x_llim_ray, 
                                               x_ulim_vdr = x_ulim_ray, 
                                               y_llim_vdr = y_llim_ray, 
                                               y_ulim_vdr = y_ulim_ray, 
                                               y_label_cal = y_label_cal, 
                                               x_label_cal = x_label_cal, 
                                               K = K_ch,
                                               G_R = G_R_ch,
                                               G_T = G_T_ch,
                                               H_R = H_R_ch,
                                               H_T = H_T_ch,
                                               x_tick_cal = args['x_tick_calibration'],
                                               y_label_vdr = y_label_ray, 
                                               x_label_vdr = x_label_ray, 
                                               x_tick_vdr = args['x_tick_rayleigh'])  
    
        # pack = np.vstack((x_vals_ray, delta_fit_prf, delta_prf)).T
    
        # ascii_name = f'{data.Measurement_ID_Calibration}_{data.Lidar_Name_Calibration}_pcb_{ch_r}_to_{ch_t}_ATLAS_{__version__}.txt'
        # np.savetxt(os.path.join(args['output_folder'],'ascii',ascii_name), pack, 
        #             delimiter = ',', header = 'alt, delta_eta_s, delta')

        # Make ascii file header
        header = \
            make_header.polarisation_calibration(cal_start_date = data.RawData_Start_Date_Calibration,
                                                 cal_start_time = data.RawData_Start_Time_UT_Calibration, 
                                                 cal_duration = sampling_cal,
                                                 ray_start_date = data.RawData_Start_Date_Rayleigh,
                                                 ray_start_time = data.RawData_Start_Time_UT_Rayleigh, 
                                                 ray_duration = sampling_ray,
                                                 K = K_ch,
                                                 G_R = G_R_ch,
                                                 G_T = G_T_ch,
                                                 H_R = H_R_ch,
                                                 H_T = H_T_ch,   
                                                 wave = dwl_ch, 
                                                 lidar = data.Lidar_Name, 
                                                 loc = data.Lidar_Location, 
                                                 meas_id = data.Measurement_ID_Calibration, 
                                                 channel_r = ch_r,
                                                 channel_t = ch_t)
        
        # Make the ascii filename
        ascii_name = f'{data.Measurement_ID_Calibration}_{data.Lidar_Name}_pcb_{ch_r}_to_{ch_t}_ATLAS_{__version__}.txt'

        # Export to ascii (Volker's format)        
        export_ascii.polarisation_calibration(dir_out = args['output_folder'], 
                                              fname = ascii_name, 
                                              alt_cal = x_vals_cal,                                              
                                              alt_ray = x_vals_ray,
                                              r_p45 = sig_r_p45_ch,
                                              t_p45 = sig_t_p45_ch,
                                              r_m45 = sig_r_m45_ch,
                                              t_m45 = sig_t_m45_ch,   
                                              ray_r = sig_r_ray_ch,
                                              ray_t = sig_t_ray_ch,
                                              header = header)
        
        # Add metadata to the quicklook plot
        from PIL import Image
        from PIL import PngImagePlugin
       
        METADATA = {"processing_software" : f"ATLAS_{data.version}",
                    "measurement_id_calibration" : f"{data.Measurement_ID_Calibration}",
                    "measurement_id_rayleigh" : f"{data.Measurement_ID_Rayleigh}",
                    "channel_r" : f"{ch_r}",
                    "channel_t" : f"{ch_t}",
                    "smooth" : f"{args['smooth']}",
                    "smoothing_exponential" : f"{args['smooth_exponential']}",
                    "smoothing_range" : f"{args['smoothing_range']}",
                    "smoothing_window": f"{args['smoothing_window']}",
                    "dpi" : f"{args['dpi']}",
                    "color_reduction" : f"{args['color_reduction']}",
                    "calibration_region" : f"{args['calibration_region']}",
                    "rayleigh_region" : f"{args['rayleigh_region']}",
                    "use_distance" : f"{args['use_distance']}",
                    "x_lims_calibration" : f"{args['x_lims_calibration']}",
                    "x_lims_rayleigh" : f"{args['x_lims_rayleigh']}",
                    "y_lims_calibration" : f"{args['y_lims_calibration']}",
                    "y_lims_rayleigh" : f"{args['y_lims_rayleigh']}",
                    "x_tick_calibration" : f"{args['x_tick_calibration']}",
                    "x_tick_rayleigh" : f"{args['x_tick_rayleigh']}"}

                
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
    
    # sys.exit()
    # # Add metadata to the quicklook plot
    # from PIL import Image
    # from PIL import PngImagePlugin
   
    # METADATA = {"processing_software" : f"ATLAS_{data.version}",
    #             "measurement_id" : f"{data.Measurement_ID}",
    #             "channel" : f"{ch}",
    #             "smooth" : f"{args['smooth']}",
    #             "smoothing_exponential" : f"{args['smooth_exponential']}",
    #             "smoothing_range (lower)" : f"{args['smoothing_range'][0]}",
    #             "smoothing_range (upper)" : f"{args['smoothing_range'][-1]}",
    #             "smoothing_window (lower)": f"{args['smoothing_window'][0]}",
    #             "smoothing_window (upper)": f"{args['smoothing_window'][-1]}",
    #             "dpi" : f"{args['dpi']}",
    #             "use_log_scale" : f"{args['use_log_scale']}",
    #             "use_distance" : f"{args['use_distance']}",
    #             "y_lims (lower)" : f"{y_llim}",
    #             "y_lims (upper)" : f"{y_ulim}",
    #             "x_lims (lower)" : f"{y_vals[x_llim]}",
    #             "x_lims (upper)" : f"{y_vals[x_ulim]}",
    #             "y_lims (lower)" : f"{y_llim}",
    #             "y_lims (upper)" : f"{y_ulim}",
    #             "y_tick" : f"{y_tick}",
    #             "x_tick" : f"{args['x_tick']}"}
            
    # im = Image.open(fpath)
    # meta = PngImagePlugin.PngInfo()

    # for x in METADATA.keys():
    #     meta.add_text(x, METADATA[x])
        
    # im.save(fpath, "png", pnginfo = meta)
