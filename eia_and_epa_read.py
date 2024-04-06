#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jul 24 17:13:54 2023
Read in EPA and EIA data on ISO-NE power plants and their fossil emissions
Determine marginal generation for every hour of 2018

Read in Boston area temperatures

Determine marginal fuels, including inferring active fuel for fuel switching generation units

Determine marginal emissions from fossil generation


Determine effective coefficient of performance (COP) for heatpump

Compare heatpump efficency to marginal generation

Compare heatpump emissions to marginal generation
@author: dpg
"""
import pandas as pd
import matplotlib.pyplot  as plt
import numpy as np
from readtemp import readtemp
from interp_COP import interp_COP

#assumptions for economics
furnace_efficiency = 0.9
gas_price = 4.5 #say this for gas prices except in cold snaps
coal_price_ton =52
#https://www.eia.gov/coal/markets/
#https://markets.businessinsider.com/commodities/coal-price
wood_price = .25

diesel_price_gal = 3.0 #fuel oil price
diesel_price = diesel_price_gal / 0.12497 # convert to $/mmbtu

resid_price_gal = 1.86 #price/gal
resid_price = resid_price_gal/0.1498 #per mmbtu
coal_price = coal_price_ton/27.78 + 1.50  #again, generic since it depends on coal type. Allow 1.50 for transportation
LNG_price = 8 #for Mystic only, and of course not the post-Ukraine war price of $20/mmbtu!!

#set emissions per different fuel types- source EIA 
#https://www.eia.gov/environment/emissions/co2_vol_mass.php
#tonnes/mmbtu
gas_CO2 = 0.05291
resid_CO2 = 0.07509
diesel_CO2 = 0.07414
coal_CO2 = 0.096 #generic since coal emissions depends by type
wood_CO2 = 0  #just going to ignore wood

gasNOx_UL = 0.1  #upper limit lbs/mmbtu NOx emissions for gas, otherwise oil or something else
#for LNG (Mystic) see Renewable & Sustainable Energy Reviews 99 (2019) pp 1-15
#0.4kwh/kg for liquification
#see https://www.eaglelng.com/lng-calculator   for kg to mmbtu conversion : 1 tonne = 48.9 mmbtu

#that is, 0.4 MWh for 48.9 mmbtu LNG, or roughly, 4 mmbtu depending on what used to generate power for liquifaction
#considering evaporation & transportation, apply 15% emissions penalty for LNG of equivalent thermal value as gas

LNG_CO2 = gas_CO2 * 1.15



residSOx_LL = 0.1 #lower limit for resid



epacols = ['State',	'Facility Name',	'Facility ID',	'Unit ID',	'Associated Stacks',	'Date','Hour',	'Operating Time',	
           'Gross Load (MW)',	'Steam Load (1000 lb/hr)',	'SO2 Mass (lbs)',	'SO2 Mass Measure Indicator',	'SO2 Rate (lbs/mmBtu)',	
           'SO2 Rate Measure Indicator', 'CO2 Mass (short tons)',	'CO2 Mass Measure Indicator', 'CO2 Rate (short tons/mmBtu)',	
           'CO2 Rate Measure Indicator',	'NOx Mass (lbs)',	'NOx Mass Measure Indicator',	'NOx Rate (lbs/mmBtu)','NOx Rate Measure Indicator',	'Heat Input (mmBtu)',	
           'Heat Input Measure Indicator',	'Primary Fuel Type',	'Secondary Fuel Type',	'Unit Type',	'SO2 Controls','NOx Controls',	'PM Controls',	'Hg Controls',	'Program Code']
          
epacols_short = ['State',	'Facility Name',	'Facility ID',	'Unit ID','Date','Hour',	'Operating Time',	
           'Gross Load (MW)',	'Steam Load (1000 lb/hr)',	
           'Heat Input (mmBtu)',	
           'Primary Fuel Type',	'Secondary Fuel Type',	'Unit Type']   
eia_energysourcecodes = ['KER', 'DFO', 'RFO', 'JF','NG', 'SUB','WDS','WDS','BIT','BLQ','MSW','OBG','LFG','TDF','PUR','OTH','CT','CA']
# to get maxes, read in hourly-emissions-2018.csv  then groupby Facility ID and Unit ID and obtain max for Gross Load (MW)
"""
epa_df = pd.read_excel('hourly-emissions-by_unit_jan_2018.xlsx')
epa_df = epa_df[epacols_short]		
"""																																						
eia_df = pd.read_excel('/Users/dpg/My Drive/gd_smart grid docs/EPA emissions info/february_generator2018_EIA860.xlsx', sheet_name='EPA fossil w form 860', index_col=None )
esc = eia_df["Energy Source Code"]

#screen out values that are not fossil generation
fossil_i = esc.isin(eia_energysourcecodes)

eia_df = eia_df[fossil_i]
eia_df['Plant ID'] = eia_df['Plant ID'].astype(str)
eia_df['EPA Unit ID'] = eia_df['EPA Unit ID'].astype(str)

epa_2018 = pd.read_csv('/Users/dpg/My Drive/gd_smart grid docs/EPA emissions info/hourly-emissions-2018.csv')
epa_2018 =  epa_2018[epacols]
epa_2018.fillna(value=0, inplace=True)

#fix up stupid data source here
fixind = (epa_2018['Facility ID'] == '55170') & (epa_2018['Unit ID'] == '0001')
epa_2018[fixind] = '1'
#clean up Pipeline natural gas/ gas
isgas = epa_2018["Primary Fuel Type"] == "Pipeline Natural Gas"

epa_2018.loc[isgas, "Primary Fuel Type"]= "Gas"

isgas = epa_2018["Primary Fuel Type"] == "Natural Gas"
epa_2018.loc[isgas, "Primary Fuel Type"]= "Gas"

isotheroil  = epa_2018["Primary Fuel Type"] == 'Other Oil'
epa_2018.loc[isotheroil, "Primary Fuel Type"] = "Diesel Oil"

epa_2018["inferred_fuel"]=epa_2018['Primary Fuel Type']


pft = epa_2018['Primary Fuel Type']
sft = epa_2018['Secondary Fuel Type']


pft = pft.unique()
sft = sft.unique()

coal_index = epa_2018["Primary Fuel Type"] == "Coal"


#fuel switching logic
#set all gas generators' inferred fuel to gas first, before changing to others based on emissions conditions

#but 1st clean up stupid shit like 0 being '0'
epa_2018["NOx Rate (lbs/mmBtu)"] = epa_2018["NOx Rate (lbs/mmBtu)"].astype(float)
epa_2018["SO2 Rate (lbs/mmBtu)"] = epa_2018["SO2 Rate (lbs/mmBtu)"].astype(float)




fuel_swit_resid = (epa_2018["Primary Fuel Type"] == "Gas") & (epa_2018["NOx Rate (lbs/mmBtu)"] > gasNOx_UL ) \
    & (epa_2018["SO2 Rate (lbs/mmBtu)"] > residSOx_LL) \
& ('Residual Oil' in epa_2018["Secondary Fuel Type"] )

fuel_swit_diesel = (epa_2018["Primary Fuel Type"] == "Gas") & (epa_2018["NOx Rate (lbs/mmBtu)"] >= gasNOx_UL) \
    & (epa_2018["SO2 Rate (lbs/mmBtu)"] <  residSOx_LL ) \
 & ('Diesel Oil' in epa_2018["Secondary Fuel Type"] )

epa_2018.loc[fuel_swit_resid]["inferred_fuel"]= "Residual Oil"

epa_2018.loc[fuel_swit_diesel]["inferred_fuel"]= "Diesel Oil"

#ismysticgas = (epa_2018['Facility ID'] == 1588) & (epa_2018['Primary Fuel Type'] == 'Gas')
#epa_2018.loc[ismysticgas,"inferred_fuel"] = "LNG"

MWonly = ['Facility ID', 'Unit ID', 'Gross Load (MW)']
epaMW = epa_2018[MWonly]

epa_2018max = epaMW.groupby(['Facility ID', 'Unit ID']).max()


epa_2018max.rename(columns={'Gross Load (MW)': 'Max Load'}, inplace=True)

epa_2018max = epa_2018max['Max Load' ]

#need to adjust heatrate by operating time because Heat Input is absolute, per hour, but Gross Load is whatever the Load was
#when the unit was on, even if only a few minutes.
#remove ZEROS but 1st convert to float
epa_2018['Operating Time']  = epa_2018['Operating Time'].astype(float)
epa_2018['Gross Load (MW)']  = epa_2018['Gross Load (MW)'].astype(float)
epa_2018 = epa_2018[(epa_2018['Operating Time'] > 0) & (epa_2018['Gross Load (MW)']) > 0]
                                                        
epa_2018["EPA_heatrate"]= 1000*epa_2018['Heat Input (mmBtu)']/epa_2018['Gross Load (MW)']/epa_2018['Operating Time']
epa_2018["MWh"] = epa_2018['Gross Load (MW)']* epa_2018['Operating Time']

epa_2018 = epa_2018.merge(epa_2018max, on=[ 'Facility ID', 'Unit ID'], how='left') 



epa_2018["EPA_ncf"] = epa_2018["Gross Load (MW)"] * epa_2018['Operating Time']/epa_2018["Max Load"]

epa_2018["EPA_heatrate"].replace([np.inf, -np.inf], np.nan, inplace=True)

epa_2018["EPA_heatrate"].fillna(value=0, inplace=True)

#clean up
epa_2018["EPA_ncf"] = epa_2018["EPA_ncf"].fillna(value=0)
epa_2018['Facility ID'] = epa_2018['Facility ID'].astype(str)
epa_2018['Unit ID'] = epa_2018['Unit ID'].astype(str)

epa_2018i = epa_2018.set_index(['Date','Hour', 'Facility ID', 'Unit ID'])

#screen out zero values for generation

epa_2018i["Gross Load (MW)"] = epa_2018i["Gross Load (MW)"].astype(float)
epa_2018i_nz = epa_2018i[epa_2018i["Gross Load (MW)"]>0  ]
#cogens may run even though their heatrate is high because they need steam - so exclude them from marginal cost stack
epa_2018_nocogen = epa_2018i_nz[epa_2018i_nz['Steam Load (1000 lb/hr)'] == 0]
#get rid of part-hour use, eg ramping- doesn't count
epa_nocogenf = epa_2018_nocogen[(epa_2018_nocogen["Operating Time"] == 1) & (epa_2018_nocogen["EPA_ncf"] > 0.4)] #
epa_short = epa_nocogenf[0:1000]

#isolate just one operating hour to see what's going on
# see https://stackoverflow.com/questions/18835077/selecting-from-multi-index-pandas 
#
# to understand how to query multiple index
epa_04268 = epa_nocogenf.query('Date == "2018-04-26" and Hour == 8')
epa_042610 = epa_nocogenf.query('Date == "2018-04-26" and Hour == 10')
#heatratecols = ['inferred_fuel', 'EPA_heatrate', 'MWh']

#aa = epa_2018_nocogen.loc('UnitID' == 3236)  #to get Manchester Station only

manchester = epa_nocogenf.iloc[epa_nocogenf.index.get_level_values('Facility ID') == 3236]


heatratecols1 = [ 'Facility Name', 'Facility ID', 'Unit ID', 'inferred_fuel', 'EPA_heatrate',  'Operating Time',
       'Gross Load (MW)',  'EPA_heatrate', 'MWh', 'Max Load', 'EPA_ncf']

epa_nocogenf=epa_nocogenf.reset_index(['Facility ID', 'Unit ID'])  # gets Facility Index Unit ID OUT of the index

#now do heatrates

heatratecols = [ 'Date', 'Hour', 'Facility Name', 'Facility ID', 'Unit ID', 'inferred_fuel', 'heatrate',  'Operating Time',
       'Gross Load (MW)',  'EPA_heatrate', 'MWh', 'Max Load', 'EPA_ncf']
heatrateonlycols  =  [ 'Date', 'Hour', 'Facility Name', 'Facility ID', 'Unit ID', 'inferred_fuel', 'heatrate']

#CLEAN UP UNITS WITH LOW LOAD FACTOR (don't let them distoryt picture)
lo_lim = 0.15  #exclude any plants operating below this EPA_ncf level
lo_power = 75  #exclude plantsproducing less than 75MW




genbyhr = epa_2018i.groupby(['Date', 'Hour', 'inferred_fuel']).sum()
#genbyhr = genbyhr[['Gross Load (MW)','MWh', 'Heat Input (mmBtu)']]


#now make a pivot table for each hour by inferred fuel type
gen_by_fuel = epa_2018.pivot_table(index=['Date', 'Hour'], columns= 'inferred_fuel', values='Gross Load (MW)', aggfunc='sum')
gen_by_fuel.fillna(value=0, inplace=True)
#epa_pt = epa_2018i.pivot_table(index = 'inferred_fuel')
epa_short = epa_2018i[0:1000]

gindex = epa_2018i.index

#NEED TO MERGE USING PLANT ID AND EPA UNIT IDS AS TWO-LEVEL KEYS
#eianepa = epa_2018i.merge(eia_df, how='inner', left_on= 'Facility ID', right_on='Plant ID')
epa_2018i = epa_2018i.reset_index()
eianepa = epa_2018i.merge(eia_df, how='inner', left_on=['Facility ID', 'Unit ID'], right_on = ['Plant ID', 'EPA Unit ID'])

#********* NOW CALCULATE HEATRATES USING EIA DATA
#get rid of cogens - they have to run to produce steam even if uneconomic for power
eianepa_nocogen = eianepa[eianepa['Steam Load (1000 lb/hr)'] == 0]

eianepa_nocogen = eianepa_nocogen [(eianepa_nocogen["cogen"] == "no") & (eianepa_nocogen["Operating Time"] > 0.5)]





heatrates = eianepa_nocogen[heatratecols]

#screen out dogs and cats

heatrates = heatrates[(heatrates.EPA_ncf > lo_lim)  & (heatrates.MWh > lo_power)]

hrs =  eianepa_nocogen[heatrateonlycols]   #less clutter in here by only putting in heatrates as sole numerica columns

#marg_hr = hrs.groupby(['Date', 'Hour', "inferred_fuel" ]).max()
grouped_df = heatrates.groupby(['Date', 'Hour', "inferred_fuel" ])

#decide whether to use EIA heatrates (annual average) or EPA (hourly data)
choice_EIA = 'heatrate'
choice_EPA = 'EPA_heatrate'

#************* PICK HEAT RATE CALC METHOD HERE ***********

#heatrate_choice = choice_EIA
heatrate_choice  = choice_EIA
# ********************************************************

# this finds the highest heat rates of any running plants for each fuel type
max_indices = grouped_df[heatrate_choice].idxmax()

marg_plants = heatrates.loc[max_indices]
marg_gas = marg_plants[marg_plants["inferred_fuel"] == "Gas"]
marg_gas1= marg_plants.query("inferred_fuel == 'Gas' ")
marg_oil = marg_plants.query("inferred_fuel == 'Diesel Oil' ")
marg_resid = marg_plants.query("inferred_fuel == 'Residual Oil' ")
#marg_LNG = marg_plants.query("inferred_fuel == 'LNG' ")
#plot the fricking heatrates
h1 = list(marg_gas[heatrate_choice])
h2 = list(marg_oil[heatrate_choice])
h3 = list(marg_resid[heatrate_choice])
#h4 = list(marg_LNG['heatrate'])
h_all = list(marg_plants)
#plt.figure()
#plt.plot(h1)



#NOW DO POWER ECONOMICS AND EMISSIONS

iscoal = heatrates['inferred_fuel'] == 'Coal'
isgas =  heatrates['inferred_fuel'] == 'Gas'
isdiesel =  heatrates['inferred_fuel'] == 'Diesel Oil'
isresid =  heatrates['inferred_fuel'] == 'Residual Oil'
iswood =  heatrates['inferred_fuel'] == 'Wood'
#isLNG =  heatrates['inferred_fuel'] == 'LNG'


heatrates["fuel_cost"]= 0
heatrates["power_cost"]= 0
heatrates["emissions"]= 0

heatrates.loc[iscoal,"fuel_cost"] = coal_price

heatrates.loc[isgas,"fuel_cost"] = gas_price

heatrates.loc[isresid,"fuel_cost"] = resid_price

heatrates.loc[isdiesel,"fuel_cost"] = diesel_price

heatrates.loc[iswood,"fuel_cost"] = wood_price

#heatrates.loc[isLNG,"fuel_cost"] = LNG_price


heatrates["power_cost"] = heatrates["fuel_cost"] *heatrates[heatrate_choice]/1000
heatrates.loc[heatrates["power_cost"].isna(), "power_cost"] = 0

heatrates.loc[isgas,"emissions"] = gas_CO2 * heatrates.loc[isgas,heatrate_choice]/1000
heatrates.loc[iscoal,"emissions"] = coal_CO2 * heatrates.loc[iscoal,heatrate_choice]/1000
heatrates.loc[isresid,"emissions"] = resid_CO2 * heatrates.loc[isresid,heatrate_choice]/1000
heatrates.loc[isdiesel,"emissions"] = diesel_CO2 * heatrates.loc[isdiesel,heatrate_choice]/1000
heatrates.loc[isdiesel,"emissions"] = diesel_CO2 * heatrates.loc[isdiesel,heatrate_choice]/1000
heatrates.loc[iswood,"emissions"] = wood_CO2 * heatrates.loc[iswood,heatrate_choice]/1000
#heatrates.loc[isLNG,"emissions"] = LNG_CO2 * heatrates.loc[isLNG,"heatrate"]/1000


#now find marginal generators IRRESPECTIVE of fuels - based on which has the highesst power cost
heatrates_sorted = heatrates.sort_values(by=['Date','Hour', 'power_cost'], ascending = [True, True, True])

grouped_dfnofuel = heatrates.groupby(['Date', 'Hour'])

max_indicesnofuel = grouped_dfnofuel['power_cost'].idxmax()



#here, below, are the marginal plants overall (not by fuel type)
marg_plants_nofuel = heatrates.loc[max_indicesnofuel]



#integrate temperature time series
tempfn = '/Users/dpg/My Drive/gd_smart grid docs/EPA emissions info/NCDC temp weather data/72509014739.csv'

kav = readtemp(tempfn)

marg_plants_nofuel = marg_plants_nofuel.merge(kav, left_on=['Date', 'Hour'], right_on=['DATE', 'hourno'], how='left')
#diagnostic
#df_slice = epa_2018[(epa_2018["Date"] == 	"2018-01-30") & (epa_2018["Hour"] == 17)] 

#now add COP
COPfn = '/Users/dpg/My Drive/gd_smart grid docs/EPA emissions info/NCDC temp weather data/ESTCP_COP.csv'  #get data from ESTCP heat pump program

#add COP and heatload to marg_plants_nofuel
marg_plants_nofuel = interp_COP(marg_plants_nofuel,COPfn )

#make a table of all the marginal plants, how many hours each
marg_plant_table = marg_plants_nofuel.groupby(["Facility Name", heatrate_choice, "inferred_fuel", "power_cost", "emissions"]).count()

effective_COPavg = marg_plants_nofuel['heatload'] * marg_plants_nofuel['COP'] #create array of normalized COP's
effective_COPavg = effective_COPavg.sum() #do the integral to get the effective COP over the year. 

#now do same to get emissions per MWh weighted by how many MWh are used per hour for heating
effective_emissionsavg = marg_plants_nofuel['heatload'] * marg_plants_nofuel['emissions']
effective_emissionsavg = effective_emissionsavg.sum()  #is the heating load-weighted tons of CO2/MWh generated
overall_gen = epa_2018i.groupby(['Date', 'Hour']).sum() #most of the columns will be junk but 'MWh' will be interesting usable data

TDlosses = 1.06
#A HIGHER VALUE OF EFFICIENCY COMPARISON, EG WITH HIGHER COP, MEANS HEAT PUMPS ARE BETTER
efficiency_comparison = marg_plants_nofuel['COP'] * (1/TDlosses)  * 3412.14/marg_plants_nofuel[heatrate_choice]/furnace_efficiency
effective_efficiency_comparison = marg_plants_nofuel['heatload']* efficiency_comparison 

effective_efficiency_comparison = effective_efficiency_comparison.sum()

effective_hr_avg = marg_plants_nofuel[heatrate_choice] * marg_plants_nofuel['heatload']
effective_hr_avg = effective_hr_avg.sum()

#emissions comparison to 1MWh gas being burned in a furnace or boiler
#eff_emissions_comparison = effective_emissionsavg*TDlosses/ (gas_CO2*3.41214)/effective_COPavg

#the below is the effective (heatload weighted) emissions per MWh marginal power generation divided by the effective COP since you only need 1 COP'th MWh
#to cool 1 MWh equivalent of heating; compared to a perfectly 100% efficient gas furnace - burning 1MWh of gas (= 3.412 x the tons of gas per mmbtu)
#eff_emissions_comparison = effective_emissionsavg*TDlosses/ (gas_CO2*3.41214*effective_COPavg)

#NOTE HERE THE EMMISSIONS COMPARISON- A HIGHER # WITH HIGHER COP'S MEANS HEAT PUMPS ARE BETTER
eff_emissions_comparison =   marg_plants_nofuel['COP'] *(gas_CO2*3.41214)/(TDlosses * marg_plants_nofuel['emissions'] )
#do this the right way with 'integration' instead of multiplying averages
# NOTE THIS MEASURE IS INVERSE OF THE EFFICIENCY MEASURE


#RATIO OF fossil boiler emissions/ HP emissions:
emissions_comparison = marg_plants_nofuel['COP'] *(gas_CO2*3.41214)/(TDlosses * marg_plants_nofuel['emissions'] )/furnace_efficiency


eff_emissions_comparison_int =  marg_plants_nofuel['heatload'] * marg_plants_nofuel['COP'] *(gas_CO2*3.41214)/(TDlosses * marg_plants_nofuel['emissions'] )/furnace_efficiency
eff_emissions_comparison_int = eff_emissions_comparison_int.sum()


eec = marg_plants_nofuel['heatload'] * marg_plants_nofuel['COP'] *gas_CO2*3.41214 /(TDlosses * marg_plants_nofuel['emissions'] )/furnace_efficiency
eecsum = eec.sum()


#now find out the marginal heat rate every hour
gg = overall_gen["Gross Load (MW)"]
ll = list(gg) #for some reason can't plot gg- says it's a tuple . maybe b/c miultiple index
#plt.figure()
#plt.plot(ll)


#only look at certain times - exclude cold wave
marg_plants_test = marg_plants_nofuel.copy()
marg_plants_test = marg_plants_test[24*20:] #exclude the 1st 20 days, when weather was cold
effective_COPtest = marg_plants_test['heatload'] * marg_plants_test['COP'] 
effective_COPtest = effective_COPtest.sum()

marg_plants_test["heatload"] = marg_plants_test["heatload"]/marg_plants_test["heatload"].sum()   #renormalize

eff_efficiency_comparison_test = marg_plants_test["heatload"] * marg_plants_test['COP'] * (1/TDlosses)  * 3412.14/marg_plants_test[heatrate_choice]/furnace_efficiency
eff_efficiency_comparison_test = eff_efficiency_comparison_test.sum()

eff_emissions_comparison_test =  marg_plants_test['heatload']* marg_plants_test['COP'] * gas_CO2*3.41214/ (TDlosses * marg_plants_test['emissions'])/furnace_efficiency
eff_emissions_comparison_test = eff_emissions_comparison_test.sum()

#the above DO NOT account for gas furnaces or boilers being LESS than 100% efficient

#before merging you'll need to fix the keys- Unit ID in EPA is a number sometimes, always text in EIA; sometimes eia's 'EPA unit id' is '1 & 2'


"""
  
           
cols_of_interest = ['State', 'Facility Name', 'Facility ID', 'Unit ID', 'Associated Stacks',
       'Date', 'Hour', 'Operating Time', 'Gross Load (MW)','Heat Input (mmBtu)','Heat Input Measure Indicator',
       'Primary Fuel Type','Secondary Fuel Type','Unit Type','Entity ID','Entity Name','cogen','Plant ID','Plant Name','Sector',
       'Plant State','Generator ID','EPA Unit ID','notes', 'heatrate','Unit Code','Nameplate Capacity (MW)',
       'Net summer capacity (MW)', 'Net winter capacity (MW)', 'Technology','Energy Source Code','Prime Mover Code', 
       'Operating Month', 'Operating Year','Planned Retirement Month','Planned Retirement Year', 'Load pct']





#get unique values from epa dataframe together with counts
epai = epa_2018i.reset_index()
epaiu = epai.loc[:,['Facility ID', 'Unit ID']]
epaiuf = epaiu.groupby(['Facility ID', 'Unit ID']).size().reset_index(name='Freq')
epau = epaiuf.loc[:,['Facility ID', 'Unit ID']]
#now do EIA

eiai = eia_df.reset_index()
eiau = eiai.loc[:,['Plant ID', 'EPA Unit ID']]
eiauf =  eiau.groupby(['Plant ID', 'EPA Unit ID']).size().reset_index(name='Freq')
eiau = eiauf.loc[:,['Plant ID', 'EPA Unit ID']]

#gives the rows that are in BOTH dfs


##using my EIA API key: api_key=axQZnZ1kHu0dxRFn5LUhdI3gINwXXWbtyBg8S13Z

ss2 = "http://www.eia.gov/opendata/embed/iframev2.php?api_key=axQZnZ1kHu0dxRFn5LUhdI3gINwXXWbtyBg8S13Z&api_version=v2&data=%5B%22value%22%5D&facet_params=%7B%22fromba%22:%5B%22ISNE%22%5D,%22toba%22:%5B%22HQT%22%5D%7D&freq=hourly&start=2018-01-01T00&end=2018-12-31T00&url=/v2/electricity/rto/interchange-data/data/&title=fromba:%20ISNE%20toba:%20HQT%20"

ss1= 'http://www.eia.gov/opendata/embed/iframev2.php?api_key=axQZnZ1kHu0dxRFn5LUhdI3gINwXXWbtyBg8S13Z&api_version=v2&data=%5B%22value%22%5D&facet_params=%7B%22fromba%22:%5B%22ISNE%22%5D,%22toba%22:%5B%22HQT%22%5D%7D&freq=hourly&start=2018-01-01T00&end=2018-12-31T00&url=/v2/electricity/rto/interchange-data/data/&title=fromba:%20ISNE%20toba:%20HQT%20'

"""
