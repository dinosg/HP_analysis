#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Feb 28 13:50:13 2024

@author: dpg
"""
import pandas as pd
import matplotlib.pyplot  as plt
import numpy as np
from readtemp import readtemp
from interp_COP import interp_COP

def find_max_cost(heatrates, Date, Hour):
    
    #find the maximum rate for a generating plant for a specific day and hour
    #return the index with the max power cost AND that max power cost
    findi= (heatrates['Date'] == Date) & (heatrates['Hour'] == Hour)
    
    subhr = heatrates[findi] # get submatrix for just the stuff with the desired day & hour
    
    maxcost = max(subhr["power_cost"])
    
    findindex = (heatrates['Date'] == Date) & (heatrates['Hour'] == Hour) & (heatrates["power_cost"] == maxcost)
    return findindex, maxcost
                                                                        
                                                                             
def find_dyhr(heatrates, Date, Hour):
    
    #return the subset of times for that specific day & hour
    findi= (heatrates['Date'] == Date) & (heatrates['Hour'] == Hour)
    
    subhr = heatrates[findi] # get submatrix for just the stuff with the desired day & hour
    subhr["cum_MWh"]  = subhr["MWh"].cumsum()
    
    
    return subhr

#add cumulative MWh column to everything. by Date and Hour
hr_sorted = heatrates_sorted.copy()
hr_sorted["cum_MWh"] = 0
for date_txt in hr_sorted.Date.unique():
    print(date_txt)
    for hourno in hr_sorted.Hour.unique():
        print(hourno)
        datehr_ind =  (hr_sorted.Date == date_txt) & (hr_sorted["Hour"] == hourno)
        hr_sorted.loc[datehr_ind,"cum_MWh"] = hr_sorted.loc[datehr_ind,"MWh"].cumsum()


##  FIGURE OUT HOW much of each merit order stack is crappy plants (with heatrates  hr_limit)
# hr_break will contain the stats on crappy plants
hr_limit = 9000
hr_break = pd.DataFrame(columns = ['Date', 'Hour', 'MaxMWh', 'overhrlim'])        
for date_txt in hr_sorted.Date.unique():
    print(date_txt)
    for hourno in hr_sorted.Hour.unique():
        #print(hourno)
        datehr_ind =  (hr_sorted.Date == date_txt) & (hr_sorted["Hour"] == hourno)
        maxmwh = hr_sorted.loc[datehr_ind,"cum_MWh"].max()
        condition = (hr_sorted.loc[datehr_ind,"heatrate"] > hr_limit)  & (hr_sorted.loc[datehr_ind,"inferred_fuel"] != 'Wood' )
        wherehrlim =  condition.idxmax()
        
        if sum(condition) > 0: 
            overhrlim = hr_sorted.loc[wherehrlim, "cum_MWh"] - hr_sorted.loc[wherehrlim, "MWh"]
        else:
            overhrlim = nan
        
        
        new_element = {'Date' : date_txt, 'Hour': hourno, 'MaxMWh': maxmwh  , 'overhrlim':overhrlim}
        hr_break = hr_break.append(new_element, ignore_index=True)
        
plt.figure()
#plot total # of MWh's from fossil for every hour
plt.plot(hr_break["MaxMWh"])
#superpose the # of MWh's from generation over the hrlim heatrate- ie how much is crappy generation
plt.plot(hr_break["MaxMWh"] - hr_break["overhrlim"])

plt.figure()
plt.xlabel('Hour of Year')
plt.ylabel('MWh Total')
plt.plot(hr_break.loc[0:2000,"MaxMWh"], label='Total Fossil MWh')
#superpose the # of MWh's from generation over the hrlim heatrate- ie how much is crappy generation
plt.plot(hr_break.loc[0:2000,"MaxMWh"] - hr_break.loc[0:2000,"overhrlim"], label = 'Fossil MWh with heatrate > 9000')
plt.legend(loc='upper right')


#save the variable since it took an hour to compute
import pickle as pk

f1 = open('heatrate_sorted', 'wb')

pk.dump(hr_sorted,f1)
        
def heatrates_offset(heatrates, offset):
    