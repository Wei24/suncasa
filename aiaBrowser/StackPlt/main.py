import astropy.units as u
import matplotlib.cm as cm
import matplotlib.colors as colors
import numpy as np
import pandas as pd
import glob
import json
import os
import pandas as pd
import bokeh.palettes as bp
from astropy.time import Time
from bokeh.layouts import row, column, widgetbox
from bokeh.models import (ColumnDataSource, Slider, Button, TextInput, CheckboxGroup, RadioGroup,
                          BoxSelectTool, TapTool, Div, Spacer, Range1d, RadioButtonGroup)
from bokeh.models.mappers import LogColorMapper, LinearColorMapper
from bokeh.plotting import figure, curdoc
from suncasa.utils import DButil
from suncasa.utils.puffin import getAIApalette

__author__ = ["Sijie Yu"]
__email__ = "sijie.yu@njit.edu"


def exit_update():
    Div_info.text = """<p><b>You may close the tab anytime you like.</b></p>"""
    raise SystemExit

def XYswitch_update(attrname, old, new):
    if RadioButG_XYswitch.active == 0:
        imgdata = {'left': np.repeat(xbd[0], ndy), 'right': np.repeat(xbd[-1] + dx, ndy),
                   'bottom': yBTE.ravel(),
                   'top': yTPE.ravel()}
    else:
        imgdata = {'left': xLFE.ravel(), 'right': xRTE.ravel(), 'bottom': np.repeat(ybd[0], ndx),
                   'top': np.repeat(ybd[-1] + dy, ndx)}
    r_img_quad.data_source.data = imgdata
    r_imgprofile.data_source.data = {'xx': [], 'yy': []}


def update_imgprofile(attrname, old, new):
    img_quad_selected = SRC_img_quad.selected['1d']['indices']
    if img_quad_selected:
        if RadioButG_XYswitch.active == 0:
            imgprofiledata = {'xx': xbd.ravel(), 'yy': zz[img_quad_selected, :].ravel()}
        else:
            imgprofiledata = {'xx': ybd.ravel(), 'yy': zz[:, img_quad_selected].ravel()}
        r_imgprofile.data_source.data = imgprofiledata
        p_imgprofile.x_range.start, p_imgprofile.x_range.end = imgprofiledata['xx'][0], imgprofiledata['xx'][-1]
    else:
        r_imgprofile.data_source.data = {'xx': [], 'yy': []}



'''load config file'''
suncasa_dir = os.path.expandvars("${SUNCASA}") + '/'
'''load config file'''
config_main = DButil.loadjsonfile(suncasa_dir + 'DataBrowser/config.json')

database_dir = config_main['datadir']['database']
database_dir = os.path.expandvars(database_dir) + '/aiaBrowserData/'
if not os.path.exists(database_dir):
    os.system('mkdir {}'.format(database_dir))
SDOdir = database_dir + 'Download/'
if not os.path.exists(database_dir):
    os.system('mkdir {}'.format(database_dir))
infile = database_dir + 'MkPlot_args.json'
try:
    with open(infile, 'rb') as fp:
        MkPlot_args_dict = json.load(fp)
except:
    print 'Error: No MkPlot_args.json found!!!'
    raise SystemExit

PlotID = MkPlot_args_dict['PlotID']
try:
    img_save = database_dir + 'stackplt-' + PlotID + '.npy'
    imgdict = np.load(img_save).item()
except:
    print 'Error: No img-xxxxxxxxxx.npz found!!!'
    raise SystemExit

zz = imgdict['zz']
x = imgdict['x']
y = imgdict['y']

wavelngth = imgdict['wavelength']
xbd = (x - x[0]) * 24. * 3600
ybd = y
zz, xx, yy = DButil.regridimage(zz, xbd, y)
xbd = xx[0, :]
ybd = yy[:, 0]
dx = np.median(np.diff(xbd))
dy = np.median(np.diff(ybd))
ndy, ndx = zz.shape
dataDF = pd.DataFrame({'xx': xx.ravel(), 'yy': yy.ravel(), 'zz': zz.ravel()})

TOOLS = "crosshair,pan,wheel_zoom,box_zoom,reset,save"
p_img = figure(tools=TOOLS,
               plot_width=config_main['plot_config']['tab_StackPlt']['stackplt_wdth'],
               plot_height=config_main['plot_config']['tab_StackPlt']['stackplt_hght'],
               x_range=(xbd[0], xbd[-1] + dx), y_range=(ybd[0], ybd[-1] + dy),
               toolbar_location="above")
tim0_char = Time(x[0], format='jd', scale='utc', precision=3, out_subfmt='date_hms').iso
p_img.axis.visible = True
p_img.title.text = "Stack plot"
p_img.xaxis.axis_label = 'Seconds since ' + tim0_char
p_img.yaxis.axis_label = 'distance [arcsec]'
p_img.border_fill_alpha = 0.4
p_img.axis.major_tick_out = 0
p_img.axis.major_tick_in = 5
p_img.axis.minor_tick_out = 0
p_img.axis.minor_tick_in = 3
p_img.axis.major_tick_line_color = "white"
p_img.axis.minor_tick_line_color = "white"
if imgdict['observatory'] == 'SDO' and imgdict['instrument'] == 'AIA':
    palette = getAIApalette(wavelngth)
    clrange = DButil.sdo_aia_scale_dict(wavelength=wavelngth)
    colormapper = LogColorMapper(palette=palette, low=clrange['low'], high=clrange['high'])
else:
    palette = bp.viridis(256)
    colormapper = LinearColorMapper(palette=palette)

r_img = p_img.image(image=[zz], x=xbd[0], y=ybd[0], dw=xbd[-1] - xbd[0] + dx,
                    dh=ybd[-1] - ybd[0] + dy,
                    color_mapper=colormapper)

xLFE = xbd
xRTE = np.append(xbd[1:], xbd[-1] + dx)
yBTE = ybd
yTPE = np.append(ybd[1:], ybd[-1] + dy)

imgquadDF = pd.DataFrame(
    {'left': np.repeat(xbd[0], ndy), 'right': np.repeat(xbd[-1] + dx, ndy), 'bottom': yBTE.ravel(),
     'top': yTPE.ravel()})

SRC_img_quad = ColumnDataSource(imgquadDF)
r_img_quad = p_img.quad('left', 'right', 'top', 'bottom', source=SRC_img_quad,
                        fill_color=None, fill_alpha=1.0,
                        line_color=None, line_alpha=0.0, selection_fill_alpha=0.2,
                        selection_fill_color='white',
                        nonselection_fill_alpha=1.0, nonselection_fill_color=None,
                        selection_line_alpha=0.0, selection_line_color=None,
                        nonselection_line_alpha=0.0, nonselection_line_color=None)

p_img.add_tools(TapTool(renderers=[r_img_quad]))
Div_info = Div(text="""<p><b>Warning</b>: Click <b>Exit</b>
            first before closing the tab</p></b>""", width=config_main['plot_config']['tab_MkPlot']['button_wdth'])

TOOLS = "pan,wheel_zoom,box_zoom,reset,save"
p_imgprofile = figure(tools=TOOLS,
                      plot_width=config_main['plot_config']['tab_StackPlt']['stackplt_wdth'],
                      plot_height=config_main['plot_config']['tab_StackPlt']['stackpltpro_hght'],
                      toolbar_location='above', x_range=(xbd[0], xbd[-1]), y_range=(np.nanmin(zz), np.nanmax(zz)))
p_imgprofile.axis.visible = True
p_imgprofile.title.text = "light Curve"
p_imgprofile.xaxis.axis_label = 'Seconds since ' + tim0_char
p_imgprofile.yaxis.axis_label = 'Count rate [DN/s]'
p_imgprofile.border_fill_alpha = 0.4
p_imgprofile.axis.major_tick_out = 0
p_imgprofile.axis.major_tick_in = 5
p_imgprofile.axis.minor_tick_out = 0
p_imgprofile.axis.minor_tick_in = 3
SRC_imgprofile = ColumnDataSource({'xx': [], 'yy': []})
r_imgprofile = p_imgprofile.line(x='xx', y='yy', alpha=0.8, line_width=1, line_color='black', source=SRC_imgprofile)


RadioButG_XYswitch = RadioButtonGroup(labels=["X profile", "Y profile"], active=0)
RadioButG_XYswitch.on_change('active', XYswitch_update)

SRC_img_quad.on_change('selected', update_imgprofile)

BUT_exit = Button(label='Exit', width=config_main['plot_config']['tab_MkPlot']['button_wdth'], button_type='danger')
BUT_exit.on_click(exit_update)

lout = row(column(p_img, p_imgprofile), column(RadioButG_XYswitch, BUT_exit, Div_info))

curdoc().add_root(lout)
curdoc().title = "StackPlt"
