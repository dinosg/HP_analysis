#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Nov 28 14:36:14 2023
reads in COP [coefficient of performance] table from ESTCP program on heat pumps
fills in effective COP 
@author: dpg
"""
import pandas as pd
import matplotlib.pyplot  as plt
import numpy as np

from scipy.interpolate import interp2d

def interp_COP(marg_plants_nofuel, COPfn):
    COP = pd.read_csv(COPfn)
    #2-D interp from scikit-learn (abandoned this approach so commented out)
    #interp_fn = interp2d(COP['Temp C'], COP['Temp C'], COP['COP'], kind= 'linear' )
    
    #interp_values = interp_fn(marg_plants_nofuel['temp'], marg_plants_nofuel['temp'])
    
    #try this instead for 1-D:
        
    interp_values = np.interp(marg_plants_nofuel['temp'], COP['Temp C'], COP['COP'])
    warm55 = 12.77777 #55 F in C
    iswarm = marg_plants_nofuel['temp'] > warm55
    interp_values[iswarm] = 3.5#  peg this as max COP sine we don't have data beyond this
    
    marg_plants_nofuel['heatload'] = warm55 - marg_plants_nofuel.temp
    marg_plants_nofuel['heatload'] = marg_plants_nofuel['heatload'].apply(lambda x: max(x,0)) #no heat load above 55F
    marg_plants_nofuel['heatload'] = marg_plants_nofuel['heatload']/marg_plants_nofuel['heatload'].sum()
    
    marg_plants_nofuel['COP'] = interp_values
    return marg_plants_nofuel
    
        
    
    
    