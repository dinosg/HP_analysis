#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Nov 27 10:21:12 2023

@author: dpg
"""
from datetime import datetime, timedelta
def round_to_nearest_hour(time_obj):
    datetime_obj = datetime.combine(datetime.today(), time_obj)
    rounded_datetime = datetime_obj + timedelta(minutes=30)
    rounded_datetime = rounded_datetime.replace(minute=0, second=0)
    return rounded_datetime.time()