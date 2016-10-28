# The plot server must be running
# Go to http://localhost:5006/bokeh to view this plot
import json
import os
import pickle
import time
from collections import OrderedDict
import astropy.units as u
import matplotlib.cm as cm
import matplotlib.colors as colors
import numpy as np
import pandas as pd
import sunpy.map
from astropy.io import fits
from bokeh.layouts import row, column, widgetbox, gridplot
from bokeh.models import (ColumnDataSource, CustomJS, Slider, Button, TextInput, RadioButtonGroup, CheckboxGroup,
                          BoxSelectTool, LassoSelectTool, HoverTool, ResizeTool, Spacer, LabelSet, Div)
from bokeh.models.mappers import LinearColorMapper
from bokeh.models.widgets import Panel, Tabs, Select
from bokeh.palettes import Spectral11
from bokeh.plotting import figure, curdoc
import jdutil
from QLook_util import get_contour_data, twoD_Gaussian
from puffin import PuffinMap

__author__ = ["Sijie Yu"]
__email__ = "sijie.yu@njit.edu"

'''load config file'''
with open('../QLook/config.json', 'r') as fp:
    config_plot = json.load(fp)
with open('../QLook/config_EvtID.json', 'r') as fp:
    config_EvtID = json.load(fp)

'''define the colormaps'''
colormap_jet = cm.get_cmap("jet")  # choose any matplotlib colormap here
bokehpalette_jet = [colors.rgb2hex(m) for m in colormap_jet(np.arange(colormap_jet.N))]

'''
-------------------------- panel 2,3   --------------------------
'''

database_dir = config_EvtID['datadir']['database']
event_id = config_EvtID['datadir']['event_id']
try:
    with open(database_dir + event_id + 'CurrFS.json', 'r') as fp:
        FS_config = json.load(fp)
except:
    print 'Error: No CurrFS.json found!!!'
    raise SystemExit
struct_id = FS_config['datadir']['struct_id']
FS_specfile = FS_config['datadir']['FS_specfile']
# try:
tab2_specdata = np.load(FS_specfile)
tab2_spec = tab2_specdata['spec']
tab2_npol = tab2_specdata['npol']
tab2_nbl = tab2_specdata['nbl']
tab2_ntim = tab2_specdata['ntim']
tab2_nfreq = tab2_specdata['nfreq']
tab2_tim = tab2_specdata['tim']
tab2_freq = tab2_specdata['freq'] / 1e9
tab2_bl = tab2_specdata['bl'].item().split(';')
bl_index = 0
tab2_pol = 'LL'
sz_spec = tab2_spec.shape
tab2_spec_plt_R = tab2_spec[0, bl_index, :, :]
tab2_spec_plt_L = tab2_spec[1, bl_index, :, :]
tab2_spec_plt_I = (tab2_spec[0, bl_index, :, :] + tab2_spec[1, bl_index, :, :]) / 2.
tab2_spec_plt_V = (tab2_spec[0, bl_index, :, :] - tab2_spec[1, bl_index, :, :]) / 2.
spec_plt_max_IRL = (int(max(tab2_spec_plt_R.max(), tab2_spec_plt_L.max(), tab2_spec_plt_I.max())) / 100 + 1) * 100
spec_plt_min_IRL = (int(min(tab2_spec_plt_R.min(), tab2_spec_plt_L.min(), tab2_spec_plt_I.min())) / 100) * 100
spec_plt_max_V = (max(abs(int(tab2_spec_plt_V.max())), abs(int(tab2_spec_plt_V.min()))) / 100 + 1) * 100
spec_plt_min_V = -spec_plt_max_V
if tab2_pol == 'RR':
    tab2_spec_plt = tab2_spec[0, bl_index, :, :]
    spec_plt_max = spec_plt_max_IRL
    spec_plt_min = spec_plt_min_IRL
elif tab2_pol == 'LL':
    tab2_spec_plt = tab2_spec[1, bl_index, :, :]
    spec_plt_max = spec_plt_max_IRL
    spec_plt_min = spec_plt_min_IRL
elif tab2_pol == 'I':
    tab2_spec_plt = (tab2_spec[0, bl_index, :, :] + tab2_spec[1, bl_index, :, :]) / 2.
    spec_plt_max = spec_plt_max_IRL
    spec_plt_min = spec_plt_min_IRL
elif tab2_pol == 'V':
    tab2_spec_plt = (tab2_spec[0, bl_index, :, :] - tab2_spec[1, bl_index, :, :]) / 2.
    spec_plt_max = spec_plt_max_V
    spec_plt_min = spec_plt_min_V

tab2_dtim = tab2_tim - tab2_tim[0]
tim_map = ((np.tile(tab2_tim, tab2_nfreq).reshape(tab2_nfreq, tab2_ntim) / 3600. / 24. + 2400000.5)) * 86400.
freq_map = np.tile(tab2_freq, tab2_ntim).reshape(tab2_ntim, tab2_nfreq).swapaxes(0, 1)
xx = tim_map.flatten()
yy = freq_map.flatten()
fits_LOCL = config_EvtID['datadir']['fits_LOCL']
fits_GLOB = config_EvtID['datadir']['fits_GLOB']
fits_LOCL_dir = database_dir + event_id + struct_id + fits_LOCL
fits_GLOB_dir = database_dir + event_id + struct_id + fits_GLOB

FS_dspecDF = database_dir + event_id + struct_id + config_EvtID['datadir']['dspecDF']
if os.path.exists(FS_dspecDF):
    with open(FS_dspecDF, 'rb') as f:
        dspecDF0 = pickle.load(f)
        dspecDF = dspecDF0.copy()
    '''FS_view'''
    tab2_panel2_Div_exit = Div(text="""<p><b>Warning</b>: Click the <b>Exit FSview</b>
                            first before closing the tab</p></b>""", width=150)
    tab2_panel3_Div_exit = Div(text="""<p><b>Warning</b>: Click the <b>Exit FSview</b>
                            first before closing the tab</p></b>""", width=150)
    rmax, rmin = tab2_spec_plt.max(), tab2_spec_plt.min()
    colors_dspec = [colors.rgb2hex(m) for m in colormap_jet((tab2_spec_plt.flatten() - rmin) / (rmax - rmin))]

    TOOLS = "crosshair,pan,wheel_zoom,tap,box_zoom,reset,save"

    tab2_SRC_dspec = ColumnDataSource(dspecDF)

    '''create the dynamic spectrum plot'''
    tab2_p_dspec = figure(tools=TOOLS, webgl=config_plot['plot_config']['WebGL'],
                          plot_width=config_plot['plot_config']['tab2']['dspec_wdth'],
                          plot_height=config_plot['plot_config']['tab2']['dspec_hght'],
                          x_range=(tab2_dtim[0], tab2_dtim[-1]), y_range=(tab2_freq[0], tab2_freq[-1]),
                          toolbar_location="above")
    tim0_char = jdutil.jd_to_datetime(xx[0] / 3600. / 24.)
    tim0_char = tim0_char.strftime('%Y-%b-%d %H:%M:%S') + '.{}'.format(
        round(tim0_char.microsecond / 1e3) * 1e3)[0:4]
    tab2_p_dspec.axis.visible = True
    tab2_p_dspec.title.text = "Dynamic spectrum"
    tab2_p_dspec.xaxis.axis_label = 'Seconds since ' + tim0_char
    tab2_p_dspec.yaxis.axis_label = 'Frequency [GHz]'
    tab2_SRC_dspec_image = ColumnDataSource(
        data={'data': [tab2_spec_plt], 'xx': [tab2_dtim], 'yy': [tab2_freq]})
    tab2_p_dspec.image(image="data", x=tab2_dtim[0], y=tab2_freq[0], dw=tab2_dtim[-1] - tab2_dtim[0],
                       dh=tab2_freq[-1] - tab2_freq[0],
                       source=tab2_SRC_dspec_image, palette=bokehpalette_jet)

    # make the plot lasso selectable
    tab2_r_square = tab2_p_dspec.square('time', 'freq', source=tab2_SRC_dspec, fill_color=colors_dspec,
                                        fill_alpha=0.0,
                                        line_color=None, line_alpha=0.0, selection_fill_alpha=0.1,
                                        selection_fill_color='black',
                                        nonselection_fill_alpha=0.0,
                                        selection_line_alpha=0.2, selection_line_color='white',
                                        nonselection_line_alpha=0.0,
                                        size=min(config_plot['plot_config']['tab2']['dspec_wdth'] / tab2_ntim,
                                                 config_plot['plot_config']['tab2']['dspec_hght'] / tab2_nfreq))

    tab2_p_dspec.add_tools(BoxSelectTool())
    tab2_p_dspec.add_tools(LassoSelectTool())
    tab2_p_dspec.select(BoxSelectTool).select_every_mousemove = False
    tab2_p_dspec.select(LassoSelectTool).select_every_mousemove = False
    tab2_p_dspec.border_fill_color = "whitesmoke"
    tab2_p_dspec.axis.major_tick_out = 0
    tab2_p_dspec.axis.major_tick_in = 5
    tab2_p_dspec.axis.minor_tick_out = 0
    tab2_p_dspec.axis.minor_tick_in = 3
    tab2_p_dspec.axis.major_tick_line_color = "white"
    tab2_p_dspec.axis.minor_tick_line_color = "white"

    tab2_Select_pol = Select(title="Polarization:", value="LL", options=["RR", "LL", "I", "V"], width=150)
    tab2_Select_bl = Select(title="Baseline:", value=tab2_bl[0], options=tab2_bl, width=150)
    tab2_Select_colormap = Select(title="Colormap:", value="linear", options=["linear", "log"], width=150)

    map = Select(title="Colormap:", value="linear", options=["linear", "log"], width=150)

    tab2_p_dspec_xPro = figure(tools='', plot_width=config_plot['plot_config']['tab2']['dspec_xPro_wdth'],
                               plot_height=config_plot['plot_config']['tab2']['dspec_xPro_hght'],
                               x_range=tab2_p_dspec.x_range, y_range=(spec_plt_min, spec_plt_max),
                               title="Time profile", toolbar_location=None)
    tab2_SRC_dspec_xPro = ColumnDataSource({'x': [], 'y': []})
    tab2_SRC_dspec_xPro_hover = ColumnDataSource({'x': [], 'y': [], 'tooltips': []})
    r_dspec_xPro = tab2_p_dspec_xPro.line(x='x', y='y', alpha=1.0, line_width=1, source=tab2_SRC_dspec_xPro)
    r_dspec_xPro_c = tab2_p_dspec_xPro.circle(x='x', y='y', size=5, fill_alpha=0.2, fill_color='grey',
                                              line_color=None,
                                              source=tab2_SRC_dspec_xPro)
    r_dspec_xPro_hover = tab2_p_dspec_xPro.circle(x='x', y='y', size=5, fill_alpha=0.5, fill_color='firebrick',
                                                  line_color='firebrick', source=tab2_SRC_dspec_xPro_hover)
    tab2_l_dspec_xPro_hover = LabelSet(x='x', y='y', text='tooltips', level='glyph',
                                       source=tab2_SRC_dspec_xPro_hover,
                                       render_mode='canvas')
    tab2_l_dspec_xPro_hover.text_font_size = '5pt'
    tab2_p_dspec_xPro.add_layout(tab2_l_dspec_xPro_hover)
    tab2_p_dspec_xPro.title.text_font_size = '6pt'
    tab2_p_dspec_xPro.background_fill_color = "beige"
    tab2_p_dspec_xPro.background_fill_alpha = 0.4
    tab2_p_dspec_xPro.xaxis.axis_label = 'Seconds since ' + tim0_char
    tab2_p_dspec_xPro.yaxis.axis_label_text_font_size = '5px'
    tab2_p_dspec_xPro.yaxis.axis_label = 'Intensity [sfu]'
    tab2_p_dspec_xPro.border_fill_color = "whitesmoke"
    tab2_p_dspec_xPro.axis.major_tick_out = 0
    tab2_p_dspec_xPro.axis.major_tick_in = 5
    tab2_p_dspec_xPro.axis.minor_tick_out = 0
    tab2_p_dspec_xPro.axis.minor_tick_in = 3
    tab2_p_dspec_xPro.axis.major_tick_line_color = "black"
    tab2_p_dspec_xPro.axis.minor_tick_line_color = "black"

    tab2_p_dspec_yPro = figure(tools='', plot_width=config_plot['plot_config']['tab2']['dspec_yPro_wdth'],
                               plot_height=config_plot['plot_config']['tab2']['dspec_yPro_hght'],
                               x_range=tab2_p_dspec.y_range, y_range=(spec_plt_min, spec_plt_max),
                               title="Frequency profile", toolbar_location=None)
    tab2_SRC_dspec_yPro = ColumnDataSource({'x': [], 'y': []})
    tab2_SRC_dspec_yPro_hover = ColumnDataSource({'x': [], 'y': [], 'tooltips': []})
    r_dspec_yPro = tab2_p_dspec_yPro.line(x='x', y='y', alpha=1.0, line_width=1, source=tab2_SRC_dspec_yPro)
    r_dspec_yPro_c = tab2_p_dspec_yPro.circle(x='x', y='y', size=5, fill_alpha=0.2, fill_color='grey',
                                              line_color=None,
                                              source=tab2_SRC_dspec_yPro)
    r_dspec_yPro_hover = tab2_p_dspec_yPro.circle(x='x', y='y', size=5, fill_alpha=0.5, fill_color='firebrick',
                                                  line_color='firebrick', source=tab2_SRC_dspec_yPro_hover)
    l_dspec_yPro_hover = LabelSet(x='x', y='y', text='tooltips', level='glyph',
                                  source=tab2_SRC_dspec_yPro_hover,
                                  render_mode='canvas')
    l_dspec_yPro_hover.text_font_size = '5pt'
    tab2_p_dspec_yPro.add_layout(l_dspec_yPro_hover)
    tab2_p_dspec_yPro.title.text_font_size = '6pt'
    tab2_p_dspec_yPro.yaxis.visible = False
    tab2_p_dspec_yPro.background_fill_color = "beige"
    tab2_p_dspec_yPro.background_fill_alpha = 0.4
    tab2_p_dspec_yPro.xaxis.axis_label = 'Frequency [GHz]'
    tab2_p_dspec_yPro.yaxis.axis_label_text_font_size = '5px'
    tab2_p_dspec_yPro.border_fill_color = "whitesmoke"
    tab2_p_dspec_yPro.min_border_bottom = 0
    tab2_p_dspec_yPro.min_border_left = 0
    tab2_p_dspec_yPro.border_fill_color = "whitesmoke"
    tab2_p_dspec_yPro.axis.major_tick_out = 0
    tab2_p_dspec_yPro.axis.major_tick_in = 5
    tab2_p_dspec_yPro.axis.minor_tick_out = 0
    tab2_p_dspec_yPro.axis.minor_tick_in = 3
    tab2_p_dspec_yPro.axis.major_tick_line_color = "black"
    tab2_p_dspec_yPro.axis.minor_tick_line_color = "black"


    def tab2_update_dspec_image(attrname, old, new):
        global tab2_spec, tab2_dtim, tab2_freq, tab2_bl
        select_pol = tab2_Select_pol.value
        select_bl = tab2_Select_bl.value
        bl_index = tab2_bl.index(select_bl)
        spec_plt_R = tab2_spec[0, bl_index, :, :]
        spec_plt_L = tab2_spec[1, bl_index, :, :]
        spec_plt_I = (tab2_spec[0, bl_index, :, :] + tab2_spec[1, bl_index, :, :]) / 2.
        spec_plt_V = (tab2_spec[0, bl_index, :, :] - tab2_spec[1, bl_index, :, :]) / 2.
        spec_plt_max_IRL = int(
            max(spec_plt_R.max(), spec_plt_L.max(), spec_plt_I.max())) * 1.2
        spec_plt_min_IRL = (int(min(spec_plt_R.min(), spec_plt_L.min(), spec_plt_I.min())) / 10) * 10
        spec_plt_max_V = max(abs(int(spec_plt_V.max())), abs(int(spec_plt_V.min()))) * 1.2
        spec_plt_min_V = -spec_plt_max_V
        if select_pol == 'RR':
            spec_plt = spec_plt_R
            spec_plt_max = spec_plt_max_IRL
            spec_plt_min = spec_plt_min_IRL
        elif select_pol == 'LL':
            spec_plt = spec_plt_L
            spec_plt_max = spec_plt_max_IRL
            spec_plt_min = spec_plt_min_IRL
        elif select_pol == 'I':
            spec_plt = spec_plt_I
            spec_plt_max = spec_plt_max_IRL
            spec_plt_min = spec_plt_min_IRL
        elif select_pol == 'V':
            spec_plt = spec_plt_V
            spec_plt_max = spec_plt_max_V
            spec_plt_min = spec_plt_min_V
            tab2_Select_colormap.value = 'linear'
        if tab2_Select_colormap.value == 'log' and select_pol != 'V':
            tab2_SRC_dspec_image.data = {'data': [np.log(spec_plt)], 'xx': [tab2_dtim], 'yy': [tab2_freq]}
        else:
            tab2_SRC_dspec_image.data = {'data': [spec_plt], 'xx': [tab2_dtim], 'yy': [tab2_freq]}
        tab2_SRC_dspec.data['dspec'] = spec_plt.flatten()
        tab2_p_dspec_xPro.y_range.start = spec_plt_min
        tab2_p_dspec_xPro.y_range.end = spec_plt_max
        tab2_p_dspec_yPro.y_range.start = spec_plt_min
        tab2_p_dspec_yPro.y_range.end = spec_plt_max


    tab2_ctrls = [tab2_Select_bl, tab2_Select_pol, tab2_Select_colormap]
    for ctrl in tab2_ctrls:
        ctrl.on_change('value', tab2_update_dspec_image)

    url = ""
    tab2_SRC_p_dspec_thumb = ColumnDataSource(
        dict(url=[url], x1=[0], y1=[0], w1=[config_plot['plot_config']['tab2']['dspec_thumb_wdth']],
             h1=[config_plot['plot_config']['tab2']['dspec_thumb_hght']], ))
    tab2_p_dspec_thumb = figure(tools="pan,wheel_zoom,save",
                                plot_width=config_plot['plot_config']['tab2']['dspec_thumb_wdth'],
                                plot_height=config_plot['plot_config']['tab2']['dspec_thumb_hght'],
                                x_range=(0, config_plot['plot_config']['tab2']['dspec_thumb_wdth']),
                                y_range=(0, config_plot['plot_config']['tab2']['dspec_thumb_hght']),
                                title="EVLA thumbnail",
                                toolbar_location="right")
    r_dspec_thumb = tab2_p_dspec_thumb.image_url(url="url", x="x1", y="y1", w="w1", h="h1",
                                                 source=tab2_SRC_p_dspec_thumb, anchor='bottom_left')
    tab2_p_dspec_thumb.xaxis.visible = False
    tab2_p_dspec_thumb.yaxis.visible = False
    tab2_p_dspec_thumb.title.text_font_size = '6pt'
    tab2_p_dspec_thumb.border_fill_color = "whitesmoke"

    # # Add a hover tool
    tooltips = None

    hover_JScode = """
        var nx = %d;
        var ny = %d;
        var data = {'x': [], 'y': []};
        var cdata = rs.get('data');
        var indices = cb_data.index['1d'].indices;
        var idx_offset = indices[0] - (indices[0] %% nx);
        for (i=0; i < nx; i++) {
            data['x'].push(cdata.time[i+idx_offset]);
            data['y'].push(cdata.dspec[i+idx_offset]);
        }
        rdx.set('data', data);
        idx_offset = indices[0] %% nx;
        data = {'x': [], 'y': []};
        for (i=0; i < ny; i++) {
            data['x'].push(cdata.freq[i*nx+idx_offset]);
            data['y'].push(cdata.dspec[i*nx+idx_offset]);
        }
        rdy.set('data', data);
        var time = cdata.timestr[indices[0]]+' '
        var freq = cdata.freq[indices[0]].toFixed(3)+'[GHz] '
        var dspec = cdata.dspec[indices[0]].toFixed(3)+ '[sfu]'
        var tooltips = freq + time + dspec
        data = {'x': [], 'y': [], 'tooltips': []};
        data['x'].push(cdata.time[indices[0]]);
        data['y'].push(cdata.dspec[indices[0]]);
        data['tooltips'].push(tooltips);
        rdx_hover.set('data', data);
        tooltips = time + freq + dspec
        data = {'x': [], 'y': [], 'tooltips': []};
        data['x'].push(cdata.freq[indices[0]]);
        data['y'].push(cdata.dspec[indices[0]]);
        data['tooltips'].push(tooltips);
        rdy_hover.set('data', data);
        rdt.data['url'] = []
        rdt.data['url'].push(cdata.thumbnail[indices[0]])
        rdt.trigger('change');
        """ % (tab2_ntim, tab2_nfreq)

    tab2_p_dspec_hover_callback = CustomJS(
        args={'rs': tab2_r_square.data_source, 'rdx': r_dspec_xPro.data_source, 'rdy': r_dspec_yPro.data_source,
              'rdt': r_dspec_thumb.data_source, 'rdx_hover': r_dspec_xPro_hover.data_source,
              'rdy_hover': r_dspec_yPro_hover.data_source}, code=hover_JScode)
    tab2_p_dspec_hover = HoverTool(tooltips=tooltips, callback=tab2_p_dspec_hover_callback,
                                   renderers=[tab2_r_square])
    tab2_p_dspec.add_tools(tab2_p_dspec_hover)

    # initial the VLA map contour source
    tab2_SRC_vlamap_contour = ColumnDataSource(
        data={'xs': [], 'ys': [], 'line_color': [], 'xt': [], 'yt': [], 'text': []})
    tab2_SRC_vlamap_peak = ColumnDataSource(data={'dspec': [], 'x_pos': [], 'y_pos': [], 'amp_gaus': []})


    # initial the source of maxfit centroid
    def tab2_SRC_maxfit_centroid_init(dspecDF):
        start_timestamp = time.time()
        global SRC_maxfit_centroid
        SRC_maxfit_centroid = {}
        for ll in np.unique(dspecDF['time']):
            df_tmp = pd.DataFrame(
                {'freq': [], 'x_pos': [], 'y_pos': [], 'x_width': [], 'y_width': [], 'amp_gaus': [],
                 'theta': [],
                 'amp_offset': []})
            SRC_maxfit_centroid[np.where(abs(tab2_dtim - ll) < 0.02)[0].tolist()[0]] = ColumnDataSource(df_tmp)
        print("--- %s seconds ---" % (time.time() - start_timestamp))


    tab2_SRC_maxfit_centroid_init(dspecDF)

    # import the vla image
    if dspecDF.loc[76, :]['fits_exist']:
        hdulist = fits.open(fits_GLOB_dir + dspecDF.loc[76, :]['fits_global'])
        hdu = hdulist[0]
        vla_global_pfmap = PuffinMap(hdu.data[0, 0, :, :], hdu.header,
                                     plot_height=config_plot['plot_config']['tab2']['vla_hght'],
                                     plot_width=config_plot['plot_config']['tab2']['vla_wdth'])
        hdulist = fits.open(fits_LOCL_dir + dspecDF.loc[76, :]['fits_local'])
        hdu = hdulist[0]
        vla_local_pfmap = PuffinMap(hdu.data[0, 0, :, :], hdu.header)
        # plot the contour of vla image
        popt = [dspecDF.loc[76, :]['amp_gaus'], dspecDF.loc[76, :]['x_pos'], dspecDF.loc[76, :]['y_pos'],
                dspecDF.loc[76, :]['x_width'], dspecDF.loc[76, :]['y_width'], dspecDF.loc[76, :]['theta'],
                dspecDF.loc[76, :]['amp_offset']]
        mapx, mapy = vla_local_pfmap.meshgrid()
        mapx, mapy = mapx.value, mapy.value
        vlamap_fitted = twoD_Gaussian((mapx, mapy), *popt).reshape(vla_local_pfmap.smap.data.shape)
        tab2_SRC_vlamap_contour = get_contour_data(mapx, mapy, vlamap_fitted)
        tab2_SRC_vlamap_peak = ColumnDataSource(
            data={'dspec': [dspecDF.loc[76, :]['dspec']], 'x_pos': [dspecDF.loc[76, :]['x_pos']],
                  'y_pos': [dspecDF.loc[76, :]['y_pos']], 'amp_gaus': [dspecDF.loc[76, :]['amp_gaus']]})

    # import the aia image
    # from sunpy.net.helioviewer import HelioviewerClient
    #
    # hv = HelioviewerClient()
    # filepath = hv.download_jp2(jdutil.jd_to_datetime(xx[0] / 3600. / 24.), observatory='SDO', instrument='AIA',
    #                            detector='AIA', measurement='171',
    #                            directory=database_dir + event_id + struct_id + config_EvtID['datadir']['J2000'],
    #                            overwrite=True)
    filepath = database_dir + event_id + struct_id + config_EvtID['datadir'][
        'J2000'] + '2014_11_01__16_45_59_34__SDO_AIA_AIA_171.jp2'
    colormap = cm.get_cmap("sdoaia171")  # choose any matplotlib colormap here
    bokehpalette_sdoaia171 = [colors.rgb2hex(m) for m in colormap(np.arange(colormap.N))]
    aiamap = sunpy.map.Map(filepath)
    lengthx = vla_local_pfmap.dw[0] * u.arcsec
    lengthy = vla_local_pfmap.dh[0] * u.arcsec
    x0 = vla_local_pfmap.smap.center.x
    y0 = vla_local_pfmap.smap.center.y
    aiamap_submap = aiamap.submap(u.Quantity([x0 - lengthx, x0 + lengthx]),
                                  u.Quantity([y0 - lengthy, y0 + lengthy]))
    dimensions = u.Quantity([1024, 1024], u.pixel)
    aia_resampled_map = aiamap.resample(dimensions)

    # plot the global AIA image

    aia_resampled_pfmap = PuffinMap(smap=aia_resampled_map,
                                    plot_height=config_plot['plot_config']['tab2']['aia_hght'],
                                    plot_width=config_plot['plot_config']['tab2']['aia_wdth'])

    tab2_p_aia, r1_aia = aia_resampled_pfmap.PlotMap(DrawLimb=True, DrawGrid=True,
                                                     palette=bokehpalette_sdoaia171)
    tab2_p_aia.multi_line(xs='xs', ys='ys', line_color='line_color', source=tab2_SRC_vlamap_contour)
    tab2_p_aia.circle(x='x_pos', y='y_pos',  # size=10.*dspecDF.loc[76,:]['amp_gaus']/50.,
                      radius=3, radius_units='data', source=tab2_SRC_vlamap_peak, fill_alpha=0.8,
                      fill_color='#7c7e71',
                      line_color='#7c7e71')
    tab2_p_aia.title.text_font_size = '6pt'
    tab2_p_aia.border_fill_color = "whitesmoke"
    tab2_p_aia.axis.major_tick_out = 0
    tab2_p_aia.axis.major_tick_in = 5
    tab2_p_aia.axis.minor_tick_out = 0
    tab2_p_aia.axis.minor_tick_in = 3
    tab2_p_aia.axis.major_tick_line_color = "white"
    tab2_p_aia.axis.minor_tick_line_color = "white"

    # plot the detail AIA image
    aia_submap_pfmap = PuffinMap(smap=aiamap_submap,
                                 plot_height=config_plot['plot_config']['tab3']['aia_submap_hght'],
                                 plot_width=config_plot['plot_config']['tab3']['aia_submap_wdth'])

    tab3_p_aia_submap, tab3_r_aia_submap = aia_submap_pfmap.PlotMap(DrawLimb=True, DrawGrid=True,
                                                                    title='EM sources centroid map',
                                                                    palette=bokehpalette_sdoaia171)

    tab3_p_aia_submap.add_tools(ResizeTool())
    tab3_p_aia_submap.border_fill_color = "whitesmoke"
    tab3_p_aia_submap.axis.major_tick_out = 0
    tab3_p_aia_submap.axis.major_tick_in = 5
    tab3_p_aia_submap.axis.minor_tick_out = 0
    tab3_p_aia_submap.axis.minor_tick_in = 3
    tab3_p_aia_submap.axis.major_tick_line_color = "white"
    tab3_p_aia_submap.axis.minor_tick_line_color = "white"
    color_mapper = LinearColorMapper(Spectral11)
    tab3_r_aia_submap_oval = tab3_p_aia_submap.oval(x='x_pos', y='y_pos', width_units='screen',
                                                    height_units='screen',
                                                    width='x_width', height='y_width', angle='theta',
                                                    source=SRC_maxfit_centroid[tab2_dtim[0]],
                                                    fill_color={'field': 'freq', 'transform': color_mapper},
                                                    fill_alpha=0.2,
                                                    line_color={'field': 'freq', 'transform': color_mapper},
                                                    line_width=0.5, line_alpha=0.9)

    # plot the global HMI image
    # filepath = hv.download_jp2(jdutil.jd_to_datetime(xx[0] / 3600. / 24.), observatory='SDO', instrument='HMI',
    #                            detector='HMI', measurement='magnetogram',
    #                            directory=database_dir + event_id + struct_id + config_EvtID['datadir']['J2000'],
    #                            overwrite=True)
    filepath = database_dir + event_id + struct_id + config_EvtID['datadir'][
        'J2000'] + '2014_11_01__16_46_58_605__SDO_HMI_HMI_magnetogram.jp2'
    colormap = cm.get_cmap("gray")  # choose any matplotlib colormap here
    bokehpalette_sdohmimag = [colors.rgb2hex(m) for m in colormap(np.arange(colormap.N))]
    hmimap = sunpy.map.Map(filepath)
    # plot the global HMI image
    dimensions = u.Quantity([1024, 1024], u.pixel)
    hmi_resampled_map = hmimap.resample(dimensions)
    hmi_resampled_pfmap = PuffinMap(smap=hmi_resampled_map,
                                    plot_height=config_plot['plot_config']['tab2']['vla_hght'],
                                    plot_width=config_plot['plot_config']['tab2']['vla_wdth'])

    tab2_p_hmi, tab2_r_hmi = hmi_resampled_pfmap.PlotMap(DrawLimb=True, DrawGrid=True,
                                                         x_range=tab2_p_aia.x_range,
                                                         y_range=tab2_p_aia.y_range,
                                                         palette=bokehpalette_sdohmimag)
    tab2_p_hmi.multi_line(xs='xs', ys='ys', line_color='line_color', source=tab2_SRC_vlamap_contour)
    tab2_p_hmi.circle(x='x_pos', y='y_pos', radius=3, radius_units='data', source=tab2_SRC_vlamap_peak,
                      fill_alpha=0.8,
                      fill_color='#7c7e71', line_color='#7c7e71')
    tab2_p_hmi.yaxis.visible = False
    tab2_p_hmi.border_fill_color = "whitesmoke"
    tab2_p_hmi.axis.major_tick_out = 0
    tab2_p_hmi.axis.major_tick_in = 5
    tab2_p_hmi.axis.minor_tick_out = 0
    tab2_p_hmi.axis.minor_tick_in = 3
    tab2_p_hmi.axis.major_tick_line_color = "white"
    tab2_p_hmi.axis.minor_tick_line_color = "white"

    # plot the global vla image
    if dspecDF.loc[76, :]['fits_exist']:
        tab2_p_vla, tab2_r_vla = vla_global_pfmap.PlotMap(DrawLimb=True, DrawGrid=True,
                                                          palette=bokehpalette_jet,
                                                          x_range=tab2_p_aia.x_range,
                                                          y_range=tab2_p_aia.y_range)
        tab2_p_vla.title.text_font_size = '6pt'
        tab2_p_vla.yaxis.visible = False
        tab2_p_vla.border_fill_color = "whitesmoke"
        tab2_p_vla.axis.major_tick_out = 0
        tab2_p_vla.axis.major_tick_in = 5
        tab2_p_vla.axis.minor_tick_out = 0
        tab2_p_vla.axis.minor_tick_in = 3
        tab2_p_vla.axis.major_tick_line_color = "white"
        tab2_p_vla.axis.minor_tick_line_color = "white"

        tab2_r_vla_multi_line = tab2_p_vla.multi_line(xs='xs', ys='ys', line_color='line_color',
                                                      source=tab2_SRC_vlamap_contour)
        tab2_r_vla_circle = tab2_p_vla.circle(x='x_pos', y='y_pos',
                                              # size=10.*dspecDF.loc[76,:]['amp_gaus']/50.,
                                              radius=3, radius_units='data', source=tab2_SRC_vlamap_peak,
                                              fill_alpha=0.8, fill_color='#7c7e71',
                                              line_color='#7c7e71')


    def tab2_SRC_maxfit_centroid_update(dspecDF):
        start_timestamp = time.time()
        global SRC_maxfit_centroid
        SRC_maxfit_centroid = {}
        for ll in np.unique(dspecDF['time']):
            dftmp = dspecDF[dspecDF.time == ll]
            dftmp = dftmp.dropna(how='any')
            df_tmp = pd.concat(
                [dftmp.loc[:, 'freq'], dftmp.loc[:, 'x_pos'], dftmp.loc[:, 'y_pos'], dftmp.loc[:, 'x_width'],
                 dftmp.loc[:, 'y_width'], dftmp.loc[:, 'amp_gaus'], dftmp.loc[:, 'theta'] - np.pi / 2,
                 dftmp.loc[:, 'amp_offset']], axis=1)
            SRC_maxfit_centroid[np.where(abs(tab2_dtim - ll) < 0.02)[0].tolist()[0]] = ColumnDataSource(df_tmp)
        print("--- %s seconds ---" % (time.time() - start_timestamp))


    tab2_LinkImg_HGHT = config_plot['plot_config']['tab2']['vla_hght']
    tab2_LinkImg_WDTH = config_plot['plot_config']['tab2']['vla_wdth']


    def tab2_LinkImg_replot_update():
        global fits_LOCL_dir, fits_GLOB_dir, dspecDF, tab2_LinkImg_HGHT, tab2_LinkImg_WDTH
        idx_selected = dspecDF.index[len(dspecDF) / 2]
        if dspecDF.loc[idx_selected, :]['fits_exist']:
            hdulist = fits.open(fits_GLOB_dir + dspecDF.loc[idx_selected, :]['fits_global'])
            hdu = hdulist[0]
            pfmap = PuffinMap(hdu.data[0, 0, :, :], hdu.header, plot_height=tab2_LinkImg_HGHT,
                              plot_width=tab2_LinkImg_WDTH)
            SRC_Img = pfmap.ImageSource()
            tab2_r_vla.data_source.data['data'] = SRC_Img.data['data']
            popt = [dspecDF.loc[idx_selected, :]['amp_gaus'], dspecDF.loc[idx_selected, :]['x_pos'],
                    dspecDF.loc[idx_selected, :]['y_pos'], dspecDF.loc[idx_selected, :]['x_width'],
                    dspecDF.loc[idx_selected, :]['y_width'], dspecDF.loc[idx_selected, :]['theta'],
                    dspecDF.loc[idx_selected, :]['amp_offset']]
            hdulist = fits.open(fits_LOCL_dir + dspecDF.loc[idx_selected, :]['fits_local'])
            hdu = hdulist[0]
            pfmap_local = PuffinMap(hdu.data[0, 0, :, :], hdu.header)
            mapx, mapy = pfmap_local.meshgrid()
            mapx, mapy = mapx.value, mapy.value
            vlamap_fitted = twoD_Gaussian((mapx, mapy), *popt).reshape(pfmap_local.smap.data.shape)
            SRC_contour = get_contour_data(mapx, mapy, vlamap_fitted)
            tab2_r_vla_multi_line.data_source.data = SRC_contour.data
            SRC_peak = ColumnDataSource(data={'dspec': [dspecDF.loc[idx_selected, :]['dspec']],
                                              'x_pos': [dspecDF.loc[idx_selected, :]['x_pos']],
                                              'y_pos': [dspecDF.loc[idx_selected, :]['y_pos']],
                                              'amp_gaus': [dspecDF.loc[idx_selected, :]['amp_gaus']]})
            tab2_r_vla_circle.data_source.data = SRC_peak.data


    tab2_BUT_LinkImg_replot = Button(label='replot', width=100)
    tab2_BUT_LinkImg_replot.on_click(tab2_LinkImg_replot_update)


    def tab2_panel_exit():
        tab2_panel2_Div_exit.text = """<p><b>You may close the tab anytime you like.</b></p>"""
        tab2_panel3_Div_exit.text = """<p><b>You may close the tab anytime you like.</b></p>"""
        raise SystemExit


    tab2_panel2_BUT_exit = Button(label='Exit FSview', width=150, button_type='danger')
    tab2_panel2_BUT_exit.on_click(tab2_panel_exit)

    tab2_panel3_BUT_exit = Button(label='Exit FSview', width=150, button_type='danger')
    tab2_panel3_BUT_exit.on_click(tab2_panel_exit)

    tab3_p_dspec_small = figure(tools='pan,wheel_zoom,box_zoom,resize,save,reset',
                                plot_width=config_plot['plot_config']['tab3']['dspec_small_wdth'],
                                plot_height=config_plot['plot_config']['tab3']['dspec_small_hght'],
                                x_range=(tab2_dtim[0], tab2_dtim[-1]),
                                y_range=(tab2_freq[0], tab2_freq[-1]), toolbar_location='above')
    tab3_p_dspecvx_small = figure(tools='pan,wheel_zoom,box_zoom,resize,save,reset',
                                  plot_width=config_plot['plot_config']['tab3']['dspec_small_wdth'],
                                  plot_height=config_plot['plot_config']['tab3']['dspec_small_hght'],
                                  x_range=tab3_p_dspec_small.x_range,
                                  y_range=tab3_p_dspec_small.y_range, toolbar_location='above')
    tab3_p_dspecvy_small = figure(tools='pan,wheel_zoom,box_zoom,resize,save,reset',
                                  plot_width=config_plot['plot_config']['tab3']['dspec_small_wdth'],
                                  plot_height=config_plot['plot_config']['tab3']['dspec_small_hght'] + 40,
                                  x_range=tab3_p_dspec_small.x_range,
                                  y_range=tab3_p_dspec_small.y_range, toolbar_location='above')
    tim0_char = jdutil.jd_to_datetime(xx[0] / 3600. / 24.)
    tim0_char = tim0_char.strftime('%Y-%b-%d %H:%M:%S') + '.{}'.format(
        round(tim0_char.microsecond / 1e3) * 1e3)[0:4]
    tab3_p_dspec_small.xaxis.visible = False
    tab3_p_dspecvx_small.xaxis.visible = False
    tab3_p_dspec_small.title.text = "Vector Dynamic spectrum (Intensity)"
    tab3_p_dspecvx_small.title.text = "Vector Dynamic spectrum (Vx)"
    tab3_p_dspecvy_small.title.text = "Vector Dynamic spectrum (Vy)"
    tab3_p_dspecvy_small.xaxis.axis_label = 'Seconds since ' + tim0_char
    tab3_p_dspec_small.yaxis.axis_label = 'Frequency [GHz]'
    tab3_p_dspecvx_small.yaxis.axis_label = 'Frequency [GHz]'
    tab3_p_dspecvy_small.yaxis.axis_label = 'Frequency [GHz]'
    tab3_p_dspec_small.border_fill_color = "whitesmoke"
    tab3_p_dspec_small.axis.major_tick_out = 0
    tab3_p_dspec_small.axis.major_tick_in = 5
    tab3_p_dspec_small.axis.minor_tick_out = 0
    tab3_p_dspec_small.axis.minor_tick_in = 3
    tab3_p_dspec_small.axis.major_tick_line_color = "white"
    tab3_p_dspec_small.axis.minor_tick_line_color = "white"
    tab3_p_dspecvx_small.border_fill_color = "whitesmoke"
    tab3_p_dspecvx_small.axis.major_tick_out = 0
    tab3_p_dspecvx_small.axis.major_tick_in = 5
    tab3_p_dspecvx_small.axis.minor_tick_out = 0
    tab3_p_dspecvx_small.axis.minor_tick_in = 3
    tab3_p_dspecvx_small.axis.major_tick_line_color = "white"
    tab3_p_dspecvx_small.axis.minor_tick_line_color = "white"
    tab3_p_dspecvy_small.border_fill_color = "whitesmoke"
    tab3_p_dspecvy_small.axis.major_tick_out = 0
    tab3_p_dspecvy_small.axis.major_tick_in = 5
    tab3_p_dspecvy_small.axis.minor_tick_out = 0
    tab3_p_dspecvy_small.axis.minor_tick_in = 3
    tab3_p_dspecvy_small.axis.major_tick_line_color = "white"
    tab3_p_dspecvy_small.axis.minor_tick_line_color = "white"


    def dspecDFtmp_init():
        global dspecDFtmp
        dspecDFtmp = pd.DataFrame()
        nrows_dspecDF = len(dspecDF0.index)
        dspecDFtmp['x_pos'] = pd.Series([np.nan] * nrows_dspecDF, index=dspecDF0.index)
        dspecDFtmp['y_pos'] = pd.Series([np.nan] * nrows_dspecDF, index=dspecDF0.index)
        dspecDFtmp['amp_gaus'] = pd.Series([np.nan] * nrows_dspecDF, index=dspecDF0.index)


    dspecDFtmp_init()


    def tab3_SRC_dspec_small_init():
        global tab3_SRC_dspec_small, tab3_SRC_dspecvx_small, tab3_SRC_dspecvy_small
        global mean_amp_g, mean_vx, mean_vy, drange_amp_g, drange_vx, drange_vy
        global vmax_amp_g, vmax_vx, vmax_vy, vmin_amp_g, vmin_vx, vmin_vy
        start_timestamp = time.time()
        amp_g = (dspecDF0['amp_gaus'].copy()).reshape(tab2_nfreq, tab2_ntim)
        mean_amp_g = np.nanmean(amp_g)
        drange_amp_g = 40.
        vmax_amp_g, vmin_amp_g = mean_amp_g + drange_amp_g * np.asarray([1., -1.])
        amp_g[amp_g > vmax_amp_g] = vmax_amp_g
        amp_g[amp_g < vmin_amp_g] = vmin_amp_g
        tab3_SRC_dspec_small = ColumnDataSource(data={'data': [amp_g], 'xx': [tab2_dtim], 'yy': [tab2_freq]})
        vx = (dspecDF0['x_pos'].copy()).reshape(tab2_nfreq, tab2_ntim)
        mean_vx = np.nanmean(vx)
        drange_vx = 40.
        vmax_vx, vmin_vx = mean_vx + drange_vx * np.asarray([1., -1.])
        vx[vx > vmax_vx] = vmax_vx
        vx[vx < vmin_vx] = vmin_vx
        tab3_SRC_dspecvx_small = ColumnDataSource(data={'data': [vx], 'xx': [tab2_dtim], 'yy': [tab2_freq]})
        vy = (dspecDF0['y_pos'].copy()).reshape(tab2_nfreq, tab2_ntim)
        mean_vy = np.nanmean(vy)
        drange_vy = 40.
        vmax_vy, vmin_vy = mean_vy + drange_vy * np.asarray([1., -1.])
        vy[vy > vmax_vy] = vmax_vy
        vy[vy < vmin_vy] = vmin_vy
        tab3_SRC_dspecvy_small = ColumnDataSource(data={'data': [vy], 'xx': [tab2_dtim], 'yy': [tab2_freq]})
        print("--- %s seconds ---" % (time.time() - start_timestamp))


    def tab3_SRC_dspec_small_update(dspecDFtmp):
        global tab3_SRC_dspec_small, tab3_SRC_dspecvx_small, tab3_SRC_dspecvy_small
        global mean_amp_g, mean_vx, mean_vy, drange_amp_g, drange_vx, drange_vy
        global vmax_amp_g, vmax_vx, vmax_vy, vmin_amp_g, vmin_vx, vmin_vy
        start_timestamp = time.time()
        amp_g = (dspecDFtmp['amp_gaus'].copy()).reshape(tab2_nfreq, tab2_ntim)
        mean_amp_g = np.nanmean(amp_g)
        drange_amp_g = 40.
        vmax_amp_g, vmin_amp_g = mean_amp_g + drange_amp_g * np.asarray([1., -1.])
        amp_g[amp_g > vmax_amp_g] = vmax_amp_g
        amp_g[amp_g < vmin_amp_g] = vmin_amp_g
        tab3_SRC_dspec_small.data['data'] = [amp_g]
        vx = (dspecDFtmp['x_pos'].copy()).reshape(tab2_nfreq, tab2_ntim)
        mean_vx = np.nanmean(vx)
        drange_vx = 40.
        vmax_vx, vmin_vx = mean_vx + drange_vx * np.asarray([1., -1.])
        vx[vx > vmax_vx] = vmax_vx
        vx[vx < vmin_vx] = vmin_vx
        tab3_SRC_dspecvx_small.data['data'] = [vx]
        vy = (dspecDFtmp['y_pos'].copy()).reshape(tab2_nfreq, tab2_ntim)
        mean_vy = np.nanmean(vy)
        drange_vy = 40.
        vmax_vy, vmin_vy = mean_vy + drange_vy * np.asarray([1., -1.])
        vy[vy > vmax_vy] = vmax_vy
        vy[vy < vmin_vy] = vmin_vy
        tab3_SRC_dspecvy_small.data['data'] = [vy]
        print("--- %s seconds ---" % (time.time() - start_timestamp))


    tab3_SRC_dspec_small_init()

    tab3_p_dspec_small.image(image="data", x=tab2_dtim[0], y=tab2_freq[0], dw=tab2_dtim[-1] - tab2_dtim[0],
                             dh=tab2_freq[-1] - tab2_freq[0],
                             palette=bokehpalette_jet, source=tab3_SRC_dspec_small)
    tab3_p_dspecvx_small.image(image="data", x=tab2_dtim[0], y=tab2_freq[0], dw=tab2_dtim[-1] - tab2_dtim[0],
                               dh=tab2_freq[-1] - tab2_freq[0],
                               palette=bokehpalette_jet, source=tab3_SRC_dspecvx_small)
    tab3_p_dspecvy_small.image(image="data", x=tab2_dtim[0], y=tab2_freq[0], dw=tab2_dtim[-1] - tab2_dtim[0],
                               dh=tab2_freq[-1] - tab2_freq[0],
                               palette=bokehpalette_jet, source=tab3_SRC_dspecvy_small)
    tab3_source_idx_line = ColumnDataSource(pd.DataFrame({'time': [], 'freq': []}))
    tab3_r_dspec_small_line = tab3_p_dspec_small.line(x='time', y='freq', line_width=1.5, line_alpha=0.8,
                                                      line_color='white', source=tab3_source_idx_line)
    tab3_p_dspecvx_small.line(x='time', y='freq', line_width=1.5, line_alpha=0.8, line_color='white',
                              source=tab3_source_idx_line)
    tab3_p_dspecvy_small.line(x='time', y='freq', line_width=1.5, line_alpha=0.8, line_color='white',
                              source=tab3_source_idx_line)
    tab2_dspec_selected = None


    def tab2_dspec_selection_change(attrname, old, new):
        global tab2_dspec_selected
        tab2_dspec_selected = tab2_SRC_dspec.selected['1d']['indices']
        if tab2_dspec_selected:
            global dspecDF
            dspecDF = dspecDF0.iloc[tab2_dspec_selected, :]
            dspecDFtmp_init()
            dspecDFtmp.loc[tab2_dspec_selected, 'x_pos'] = dspecDF0.loc[tab2_dspec_selected, 'x_pos']
            dspecDFtmp.loc[tab2_dspec_selected, 'y_pos'] = dspecDF0.loc[tab2_dspec_selected, 'y_pos']
            dspecDFtmp.loc[tab2_dspec_selected, 'amp_gaus'] = dspecDF0.loc[tab2_dspec_selected, 'amp_gaus']
            tab3_SRC_dspec_small_update(dspecDFtmp)
            tab2_SRC_maxfit_centroid_update(dspecDF)


    tab2_SRC_dspec.on_change('selected', tab2_dspec_selection_change)

    tab3_dspec_small_CTRLs_OPT = dict(mean_values=[mean_amp_g, mean_vx, mean_vy],
                                      drange_values=[drange_amp_g, drange_vx, drange_vy],
                                      vmax_values=[vmax_amp_g, vmax_vx, vmax_vy],
                                      vmin_values=[vmin_amp_g, vmin_vx, vmin_vy],
                                      vmax_values_last=[vmax_amp_g, vmax_vx, vmax_vy],
                                      vmin_values_last=[vmin_amp_g, vmin_vx, vmin_vy],
                                      items_dspec_small=['amp_gaus', 'x_pos', 'y_pos'],
                                      labels_dspec_small=["Flux", "X-pos", "Y-pos"], idx_p_dspec_small=0,
                                      radio_button_group_dspec_small_update_flag=False)

    tab3_RBG_dspec_small = RadioButtonGroup(labels=tab3_dspec_small_CTRLs_OPT['labels_dspec_small'], active=0)
    tab3_BUT_dspec_small_reset = Button(label='Reset DRange', width=100)
    tab3_Slider_dspec_small_dmax = Slider(start=mean_amp_g, end=mean_amp_g + 2 * drange_amp_g, value=vmax_amp_g,
                                          step=1,
                                          title='dmax', callback_throttle=250)
    tab3_Slider_dspec_small_dmin = Slider(start=mean_amp_g - 2 * drange_amp_g, end=mean_amp_g, value=vmin_amp_g,
                                          step=1,
                                          title='dmin', callback_throttle=250)


    def tab3_RBG_dspec_small_update(attrname, old, new):
        idx_p_dspec_small = tab3_RBG_dspec_small.active
        global tab3_dspec_small_CTRLs_OPT
        tab3_dspec_small_CTRLs_OPT['idx_p_dspec_small'] = idx_p_dspec_small
        tab3_dspec_small_CTRLs_OPT['radio_button_group_dspec_small_update_flag'] = True
        mean_values = tab3_dspec_small_CTRLs_OPT['mean_values']
        drange_values = tab3_dspec_small_CTRLs_OPT['drange_values']
        vmax_values_last = tab3_dspec_small_CTRLs_OPT['vmax_values_last']
        vmin_values_last = tab3_dspec_small_CTRLs_OPT['vmin_values_last']
        tab3_Slider_dspec_small_dmax.start = mean_values[idx_p_dspec_small] - drange_values[idx_p_dspec_small]
        tab3_Slider_dspec_small_dmax.end = mean_values[idx_p_dspec_small] + 2 * drange_values[idx_p_dspec_small]
        tab3_Slider_dspec_small_dmax.value = vmax_values_last[idx_p_dspec_small]
        tab3_Slider_dspec_small_dmin.start = mean_values[idx_p_dspec_small] - 2 * drange_values[
            idx_p_dspec_small]
        tab3_Slider_dspec_small_dmin.end = mean_values[idx_p_dspec_small] + drange_values[idx_p_dspec_small]
        tab3_Slider_dspec_small_dmin.value = vmin_values_last[idx_p_dspec_small]
        tab3_dspec_small_CTRLs_OPT['radio_button_group_dspec_small_update_flag'] = False


    tab3_RBG_dspec_small.on_change('active', tab3_RBG_dspec_small_update)


    def tab3_BUT_dspec_small_reset_update():
        global dspecDFtmp, tab2_nfreq, tab2_ntim, tab3_dspec_small_CTRLs_OPT
        global tab3_SRC_dspec_small, tab3_SRC_dspecvx_small, tab3_SRC_dspecvy_small
        items_dspec_small = tab3_dspec_small_CTRLs_OPT['items_dspec_small']
        mean_values = tab3_dspec_small_CTRLs_OPT['mean_values']
        drange_values = tab3_dspec_small_CTRLs_OPT['drange_values']
        vmax_values = tab3_dspec_small_CTRLs_OPT['vmax_values']
        vmin_values = tab3_dspec_small_CTRLs_OPT['vmin_values']
        source_list = [tab3_SRC_dspec_small, tab3_SRC_dspecvx_small, tab3_SRC_dspecvy_small]
        for ll, item in enumerate(items_dspec_small):
            TmpData = (dspecDFtmp[item].copy()).reshape(tab2_nfreq, tab2_ntim)
            TmpData[TmpData > vmax_values[ll]] = vmax_values[ll]
            TmpData[TmpData < vmin_values[ll]] = vmin_values[ll]
            source_list[ll].data['data'] = [TmpData]
            print vmax_values[ll], vmin_values[ll]
        idx_p_dspec_small = 0
        tab3_dspec_small_CTRLs_OPT['idx_p_dspec_small'] = idx_p_dspec_small
        tab3_RBG_dspec_small.active = idx_p_dspec_small
        tab3_Slider_dspec_small_dmax.start = mean_values[idx_p_dspec_small] - drange_values[idx_p_dspec_small]
        tab3_Slider_dspec_small_dmax.end = mean_values[idx_p_dspec_small] + 2 * drange_values[idx_p_dspec_small]
        tab3_Slider_dspec_small_dmax.value = vmax_values[idx_p_dspec_small]
        tab3_Slider_dspec_small_dmin.start = mean_values[idx_p_dspec_small] - 2 * drange_values[
            idx_p_dspec_small]
        tab3_Slider_dspec_small_dmin.end = mean_values[idx_p_dspec_small] + drange_values[idx_p_dspec_small]
        tab3_Slider_dspec_small_dmin.value = vmin_values[idx_p_dspec_small]
        tab3_dspec_small_CTRLs_OPT['vmax_values_last'] = [ll for ll in vmax_values]
        tab3_dspec_small_CTRLs_OPT['vmin_values_last'] = [ll for ll in vmin_values]


    tab3_BUT_dspec_small_reset.on_click(tab3_BUT_dspec_small_reset_update)


    def tab3_slider_dspec_small_update(attrname, old, new):
        global dspecDFtmp, tab2_nfreq, tab2_ntim, tab3_dspec_small_CTRLs_OPT
        items_dspec_small = tab3_dspec_small_CTRLs_OPT['items_dspec_small']
        idx_p_dspec_small = tab3_dspec_small_CTRLs_OPT['idx_p_dspec_small']
        dmax = tab3_Slider_dspec_small_dmax.value
        dmin = tab3_Slider_dspec_small_dmin.value
        if not tab3_dspec_small_CTRLs_OPT['radio_button_group_dspec_small_update_flag']:
            tab3_dspec_small_CTRLs_OPT['vmax_values_last'][idx_p_dspec_small] = dmax
            tab3_dspec_small_CTRLs_OPT['vmin_values_last'][idx_p_dspec_small] = dmin
        TmpData = (dspecDFtmp[items_dspec_small[idx_p_dspec_small]].copy()).reshape(tab2_nfreq, tab2_ntim)
        TmpData[TmpData > dmax] = dmax
        TmpData[TmpData < dmin] = dmin
        if idx_p_dspec_small == 0:
            global tab3_SRC_dspec_small
            tab3_SRC_dspec_small.data['data'] = [TmpData]
        elif idx_p_dspec_small == 1:
            global tab3_SRC_dspecvx_small
            tab3_SRC_dspecvx_small.data['data'] = [TmpData]
        elif idx_p_dspec_small == 2:
            global tab3_SRC_dspecvy_small
            tab3_SRC_dspecvy_small.data['data'] = [TmpData]


    tab3_CTRLs_dspec_small = [tab3_Slider_dspec_small_dmax, tab3_Slider_dspec_small_dmin]
    for ctrl in tab3_CTRLs_dspec_small:
        ctrl.on_change('value', tab3_slider_dspec_small_update)

    # todo add the time/freq selection
    tab3_RBG_TimeFreq = RadioButtonGroup(labels=["time", "freq"], active=0)
    tab3_Slider_ANLYS_idx = Slider(start=0, end=tab2_ntim - 1, value=0, step=1, title="time idx", width=400)


    def tab3_slider_ANLYS_idx_update(attrname, old, new):
        global tab2_dtim, tab2_freq, tab2_ntim, SRC_maxfit_centroid
        tab3_Slider_ANLYS_idx.start = next(
            i for i in xrange(tab2_ntim) if tab2_dtim[i] >= tab3_p_dspec_small.x_range.start)
        tab3_Slider_ANLYS_idx.end = next(
            i for i in xrange(tab2_ntim - 1, -1, -1) if tab2_dtim[i] <= tab3_p_dspec_small.x_range.end) + 1
        indices_time = tab3_Slider_ANLYS_idx.value
        tab3_r_dspec_small_line.data_source.data = ColumnDataSource(
            pd.DataFrame({'time': [tab2_dtim[indices_time], tab2_dtim[indices_time]],
                          'freq': [tab2_freq[0], tab2_freq[-1]]})).data
        try:
            tab3_r_aia_submap_oval.visible = True
            tab3_r_aia_submap_oval.data_source.data = SRC_maxfit_centroid[indices_time].data
        except:
            tab3_r_aia_submap_oval.visible = False


    tab3_Slider_ANLYS_idx.on_change('value', tab3_slider_ANLYS_idx_update)

    tab3_Div_Tb = Div(text=""" """, width=400)

    tab3_animate_step = 1


    def tab3_animate_update():
        global tab3_animate_step, tab2_dspec_selected
        if tab2_dspec_selected:
            indices_time = tab3_Slider_ANLYS_idx.value + tab3_animate_step
            if (tab3_animate_step == 1) and (indices_time > tab3_Slider_ANLYS_idx.end):
                indices_time = tab3_Slider_ANLYS_idx.start
            if (tab3_animate_step == -1) and (indices_time < tab3_Slider_ANLYS_idx.start):
                indices_time = tab3_Slider_ANLYS_idx.end
            tab3_Slider_ANLYS_idx.value = indices_time
            tab3_Div_Tb.text = """ """
        else:
            tab3_Div_Tb.text = """<p><b>Warning: Select time and frequency from the Dynamic Spectrum first!!!</b></p>"""


    def tab3_animate():
        global tab2_dspec_selected
        if tab3_BUT_PlayCTRL.label == 'Play':
            if tab2_dspec_selected:
                tab3_BUT_PlayCTRL.label = 'Pause'
                tab3_BUT_PlayCTRL.button_type = 'danger'
                curdoc().add_periodic_callback(tab3_animate_update, 125)
                tab3_Div_Tb.text = """ """
            else:
                tab3_Div_Tb.text = """<p><b>Warning: Select time and frequency from the Dynamic Spectrum first!!!</b></p>"""
        else:
            tab3_BUT_PlayCTRL.label = 'Play'
            tab3_BUT_PlayCTRL.button_type = 'success'
            curdoc().remove_periodic_callback(tab3_animate_update)


    tab3_BUT_PlayCTRL = Button(label='Play', width=80, button_type='success')
    tab3_BUT_PlayCTRL.on_click(tab3_animate)


    def tab3_animate_step_CTRL():
        global tab3_animate_step, tab2_dspec_selected
        if tab2_dspec_selected:
            if tab3_BUT_PlayCTRL.label == 'Pause':
                tab3_BUT_PlayCTRL.label = 'Play'
                tab3_BUT_PlayCTRL.button_type = 'success'
                curdoc().remove_periodic_callback(tab3_animate_update)
            idx = tab3_Slider_ANLYS_idx.value + tab3_animate_step
            if (tab3_animate_step == 1) and (idx > tab3_Slider_ANLYS_idx.end):
                idx = tab3_Slider_ANLYS_idx.start
            elif (tab3_animate_step == -1) and (idx < tab3_Slider_ANLYS_idx.start):
                idx = tab3_Slider_ANLYS_idx.end
            tab3_Slider_ANLYS_idx.value = idx
            tab3_Div_Tb.text = """ """
        else:
            tab3_Div_Tb.text = """<p><b>Warning: Select time and frequency from the Dynamic Spectrum first!!!</b></p>"""


    tab3_BUT_StepCTRL = Button(label='Step', width=80, button_type='primary')
    tab3_BUT_StepCTRL.on_click(tab3_animate_step_CTRL)


    def tab3_animate_FRWD_REVS():
        global tab3_animate_step
        if tab2_dspec_selected:
            if tab3_animate_step == 1:
                tab3_BUT_FRWD_REVS_CTRL.label = 'Reverse'
                tab3_animate_step = -1
            else:
                tab3_BUT_FRWD_REVS_CTRL.label = 'Forward'
                tab3_animate_step = 1
            tab3_Div_Tb.text = """ """
        else:
            tab3_Div_Tb.text = """<p><b>Warning: Select time and frequency from the Dynamic Spectrum first!!!</b></p>"""


    tab3_BUT_FRWD_REVS_CTRL = Button(label='Forward', width=80, button_type='warning')
    tab3_BUT_FRWD_REVS_CTRL.on_click(tab3_animate_FRWD_REVS)

    tab3_SPCR_LFT_BUT_Step = Spacer(width=20, height=10)
    tab3_SPCR_LFT_BUT_REVS_CTRL = Spacer(width=20, height=10)

    # todo add RCP LCP check box
    tab3_CheckboxGroup_pol = CheckboxGroup(labels=["RCP", "LCP"], active=[0, 1])

    # todo add AIA & HMI resolution selection
    tab2_Select_AIA = Select(title="Img resolution:", value="512", options=["512", "1024", "2048", "4096"],
                             width=150)
    # todo add the threshold selection (overplot another gylph)
    # todo add the dmax dmin and reset

    panel2 = column(
        row(gridplot([[tab2_p_aia, tab2_p_hmi, tab2_p_vla]], toolbar_location='right'), tab2_p_dspec_thumb),
        row(column(tab2_p_dspec,
                   row(tab2_p_dspec_xPro, tab2_p_dspec_yPro)),
            widgetbox(tab2_Select_AIA, tab2_BUT_LinkImg_replot, tab2_Select_pol, tab2_Select_bl, tab2_Select_colormap,
                      tab2_panel2_BUT_exit, tab2_panel2_Div_exit, width=150)))

    panel3 = row(tab3_p_aia_submap, column(
        row(gridplot([tab3_p_dspec_small], [tab3_p_dspecvx_small], [tab3_p_dspecvy_small],
                     toolbar_location='right'),
            widgetbox(tab3_RBG_dspec_small, tab3_Slider_dspec_small_dmax, tab3_Slider_dspec_small_dmin,
                      tab3_BUT_dspec_small_reset, tab2_panel3_BUT_exit, tab2_panel3_Div_exit, width=200)), row(
            column(tab3_Slider_ANLYS_idx,
                   row(tab3_BUT_PlayCTRL, tab3_SPCR_LFT_BUT_Step, tab3_BUT_StepCTRL, tab3_SPCR_LFT_BUT_REVS_CTRL,
                       tab3_BUT_FRWD_REVS_CTRL), tab3_Div_Tb),
            widgetbox(tab3_RBG_TimeFreq, tab3_CheckboxGroup_pol, width=200))))
    tab2 = Panel(child=panel2, title="FS View")
    tab3 = Panel(child=panel3, title="ANLYS")

    tabs_top = Tabs(tabs=[tab2, tab3])

    lout = row(tabs_top)

    # def timeout_callback():
    #     print 'timeout'
    #     raise SystemExit


    curdoc().add_root(lout)
    # curdoc().add_timeout_callback(timeout_callback, 2000)
    curdoc().title = "FSview"
else:
    '''FSview2CASA'''
    tab2_panel_Div_exit = Div(
        text="""<p><b>Warning</b>: Click the <b>Exit FSview2CASA</b>
                first before closing the tab</p></b>""", width=150)
    timestrs = []
    for ii in range(len(xx)):
        t0 = xx[ii]  # -0.5*t_int
        timestr0 = jdutil.jd_to_datetime(t0 / 3600. / 24.)
        timestrs.append(timestr0.strftime('%H:%M:%S') + '.{:03d}'.format(int(round(timestr0.microsecond / 1e3))))
    dspecDF = pd.DataFrame({'time': xx - xx[0],
                            'freq': yy,
                            'dspec': tab2_spec_plt.flatten(),
                            'timestr': timestrs})

    rmax, rmin = tab2_spec_plt.max(), tab2_spec_plt.min()
    colors_dspec = [colors.rgb2hex(m) for m in colormap_jet((tab2_spec_plt.flatten() - rmin) / (rmax - rmin))]

    TOOLS = "crosshair,pan,wheel_zoom,tap,box_zoom,reset,save"

    tab2_SRC_dspec = ColumnDataSource(dspecDF)

    '''create the dynamic spectrum plot'''
    tab2_p_dspec = figure(tools=TOOLS, webgl=config_plot['plot_config']['WebGL'],
                          plot_width=config_plot['plot_config']['tab2_2CASA']['dspec_wdth'],
                          plot_height=config_plot['plot_config']['tab2_2CASA']['dspec_hght'],
                          x_range=(tab2_dtim[0], tab2_dtim[-1]), y_range=(tab2_freq[0], tab2_freq[-1]),
                          toolbar_location="above")
    tim0_char = jdutil.jd_to_datetime(xx[0] / 3600. / 24.)
    tim0_char = tim0_char.strftime('%Y-%b-%d %H:%M:%S') + '.{:03d}'.format(int(round(tim0_char.microsecond / 1e3)))
    tab2_p_dspec.axis.visible = True
    tab2_p_dspec.title.text = "Dynamic spectrum"
    tab2_p_dspec.xaxis.axis_label = 'Seconds since ' + tim0_char
    tab2_p_dspec.yaxis.axis_label = 'Frequency [GHz]'
    tab2_SRC_dspec_image = ColumnDataSource(data={'data': [tab2_spec_plt], 'xx': [tab2_dtim], 'yy': [tab2_freq]})
    tab2_p_dspec.image(image="data", x=tab2_dtim[0], y=tab2_freq[0], dw=tab2_dtim[-1] - tab2_dtim[0],
                       dh=tab2_freq[-1] - tab2_freq[0],
                       source=tab2_SRC_dspec_image, palette=bokehpalette_jet)

    # make the plot lasso selectable
    tab2_r_square = tab2_p_dspec.square('time', 'freq', source=tab2_SRC_dspec, fill_color=colors_dspec,
                                        fill_alpha=0.0,
                                        line_color=None, line_alpha=0.0, selection_fill_alpha=0.1,
                                        selection_fill_color='black',
                                        nonselection_fill_alpha=0.0,
                                        selection_line_alpha=0.2, selection_line_color='white',
                                        nonselection_line_alpha=0.0,
                                        size=max(
                                            config_plot['plot_config']['tab2_2CASA']['dspec_wdth'] / float(tab2_ntim),
                                            config_plot['plot_config']['tab2_2CASA']['dspec_hght'] / float(tab2_nfreq)))
    tab2_p_dspec.add_tools(BoxSelectTool())
    tab2_p_dspec.add_tools(LassoSelectTool())
    tab2_p_dspec.select(BoxSelectTool).select_every_mousemove = False
    tab2_p_dspec.select(LassoSelectTool).select_every_mousemove = False
    tab2_p_dspec.border_fill_color = "whitesmoke"
    tab2_p_dspec.axis.major_tick_out = 0
    tab2_p_dspec.axis.major_tick_in = 5
    tab2_p_dspec.axis.minor_tick_out = 0
    tab2_p_dspec.axis.minor_tick_in = 3
    tab2_p_dspec.axis.major_tick_line_color = "white"
    tab2_p_dspec.axis.minor_tick_line_color = "white"

    tab2_dspec_selected = None


    def tab2_dspec_selection_change(attrname, old, new):
        global tab2_dspec_selected
        tab2_dspec_selected = tab2_SRC_dspec.selected['1d']['indices']
        if tab2_dspec_selected:
            print tab2_dspec_selected.indices()[0]
            global dspecDF
            dspecDF = dspecDF0.iloc[tab2_dspec_selected, :]


    tab2_SRC_dspec.on_change('selected', tab2_dspec_selection_change)

    tab2_Select_pol = Select(title="Polarization:", value="LL", options=["RR", "LL", "I", "V"], width=150)
    tab2_Select_bl = Select(title="Baseline:", value=tab2_bl[0], options=tab2_bl, width=150)
    tab2_Select_colormap = Select(title="Colormap:", value="linear", options=["linear", "log"], width=150)

    tab2_p_dspec_xPro = figure(tools='', plot_width=config_plot['plot_config']['tab2_2CASA']['dspec_xPro_wdth'],
                               plot_height=config_plot['plot_config']['tab2_2CASA']['dspec_xPro_hght'],
                               x_range=tab2_p_dspec.x_range, y_range=(spec_plt_min, spec_plt_max),
                               title="Time profile", toolbar_location=None)
    tab2_SRC_dspec_xPro = ColumnDataSource({'x': [], 'y': []})
    tab2_SRC_dspec_xPro_hover = ColumnDataSource({'x': [], 'y': [], 'tooltips': []})
    r_dspec_xPro = tab2_p_dspec_xPro.line(x='x', y='y', alpha=1.0, line_width=1, source=tab2_SRC_dspec_xPro)
    r_dspec_xPro_c = tab2_p_dspec_xPro.circle(x='x', y='y', size=5, fill_alpha=0.2, fill_color='grey',
                                              line_color=None,
                                              source=tab2_SRC_dspec_xPro)
    r_dspec_xPro_hover = tab2_p_dspec_xPro.circle(x='x', y='y', size=5, fill_alpha=0.5, fill_color='firebrick',
                                                  line_color='firebrick', source=tab2_SRC_dspec_xPro_hover)
    tab2_l_dspec_xPro_hover = LabelSet(x='x', y='y', text='tooltips', level='glyph',
                                       source=tab2_SRC_dspec_xPro_hover,
                                       render_mode='canvas')
    tab2_l_dspec_xPro_hover.text_font_size = '5pt'
    tab2_p_dspec_xPro.add_layout(tab2_l_dspec_xPro_hover)
    tab2_p_dspec_xPro.title.text_font_size = '6pt'
    tab2_p_dspec_xPro.background_fill_color = "beige"
    tab2_p_dspec_xPro.background_fill_alpha = 0.4
    tab2_p_dspec_xPro.xaxis.axis_label = 'Seconds since ' + tim0_char
    tab2_p_dspec_xPro.yaxis.axis_label_text_font_size = '5px'
    tab2_p_dspec_xPro.yaxis.axis_label = 'Intensity [sfu]'
    tab2_p_dspec_xPro.border_fill_color = "whitesmoke"
    tab2_p_dspec_xPro.axis.major_tick_out = 0
    tab2_p_dspec_xPro.axis.major_tick_in = 5
    tab2_p_dspec_xPro.axis.minor_tick_out = 0
    tab2_p_dspec_xPro.axis.minor_tick_in = 3
    tab2_p_dspec_xPro.axis.major_tick_line_color = "black"
    tab2_p_dspec_xPro.axis.minor_tick_line_color = "black"

    tab2_p_dspec_yPro = figure(tools='', plot_width=config_plot['plot_config']['tab2_2CASA']['dspec_yPro_wdth'],
                               plot_height=config_plot['plot_config']['tab2_2CASA']['dspec_yPro_hght'],
                               x_range=tab2_p_dspec.y_range, y_range=(spec_plt_min, spec_plt_max),
                               title="Frequency profile", toolbar_location=None)
    tab2_SRC_dspec_yPro = ColumnDataSource({'x': [], 'y': []})
    tab2_SRC_dspec_yPro_hover = ColumnDataSource({'x': [], 'y': [], 'tooltips': []})
    r_dspec_yPro = tab2_p_dspec_yPro.line(x='x', y='y', alpha=1.0, line_width=1, source=tab2_SRC_dspec_yPro)
    r_dspec_yPro_c = tab2_p_dspec_yPro.circle(x='x', y='y', size=5, fill_alpha=0.2, fill_color='grey',
                                              line_color=None,
                                              source=tab2_SRC_dspec_yPro)
    r_dspec_yPro_hover = tab2_p_dspec_yPro.circle(x='x', y='y', size=5, fill_alpha=0.5, fill_color='firebrick',
                                                  line_color='firebrick', source=tab2_SRC_dspec_yPro_hover)
    l_dspec_yPro_hover = LabelSet(x='x', y='y', text='tooltips', level='glyph', source=tab2_SRC_dspec_yPro_hover,
                                  render_mode='canvas')
    l_dspec_yPro_hover.text_font_size = '5pt'
    tab2_p_dspec_yPro.add_layout(l_dspec_yPro_hover)
    tab2_p_dspec_yPro.title.text_font_size = '6pt'
    tab2_p_dspec_yPro.yaxis.visible = False
    tab2_p_dspec_yPro.background_fill_color = "beige"
    tab2_p_dspec_yPro.background_fill_alpha = 0.4
    tab2_p_dspec_yPro.xaxis.axis_label = 'Frequency [GHz]'
    tab2_p_dspec_yPro.yaxis.axis_label_text_font_size = '5px'
    tab2_p_dspec_yPro.border_fill_color = "whitesmoke"
    tab2_p_dspec_yPro.min_border_bottom = 0
    tab2_p_dspec_yPro.min_border_left = 0
    tab2_p_dspec_yPro.border_fill_color = "whitesmoke"
    tab2_p_dspec_yPro.axis.major_tick_out = 0
    tab2_p_dspec_yPro.axis.major_tick_in = 5
    tab2_p_dspec_yPro.axis.minor_tick_out = 0
    tab2_p_dspec_yPro.axis.minor_tick_in = 3
    tab2_p_dspec_yPro.axis.major_tick_line_color = "black"
    tab2_p_dspec_yPro.axis.minor_tick_line_color = "black"


    def tab2_update_dspec_image(attrname, old, new):
        global tab2_spec, tab2_dtim, tab2_freq, tab2_bl
        select_pol = tab2_Select_pol.value
        select_bl = tab2_Select_bl.value
        bl_index = tab2_bl.index(select_bl)
        spec_plt_R = tab2_spec[0, bl_index, :, :]
        spec_plt_L = tab2_spec[1, bl_index, :, :]
        spec_plt_I = (tab2_spec[0, bl_index, :, :] + tab2_spec[1, bl_index, :, :]) / 2.
        spec_plt_V = (tab2_spec[0, bl_index, :, :] - tab2_spec[1, bl_index, :, :]) / 2.
        spec_plt_max_IRL = int(
            max(spec_plt_R.max(), spec_plt_L.max(), spec_plt_I.max())) * 1.2
        spec_plt_min_IRL = (int(min(spec_plt_R.min(), spec_plt_L.min(), spec_plt_I.min())) / 10) * 10
        spec_plt_max_V = max(abs(int(spec_plt_V.max())), abs(int(spec_plt_V.min()))) * 1.2
        spec_plt_min_V = -spec_plt_max_V
        if select_pol == 'RR':
            spec_plt = spec_plt_R
            spec_plt_max = spec_plt_max_IRL
            spec_plt_min = spec_plt_min_IRL
        elif select_pol == 'LL':
            spec_plt = spec_plt_L
            spec_plt_max = spec_plt_max_IRL
            spec_plt_min = spec_plt_min_IRL
        elif select_pol == 'I':
            spec_plt = spec_plt_I
            spec_plt_max = spec_plt_max_IRL
            spec_plt_min = spec_plt_min_IRL
        elif select_pol == 'V':
            spec_plt = spec_plt_V
            spec_plt_max = spec_plt_max_V
            spec_plt_min = spec_plt_min_V
            tab2_Select_colormap.value = 'linear'
        if tab2_Select_colormap.value == 'log' and select_pol != 'V':
            tab2_SRC_dspec_image.data = {'data': [np.log(spec_plt)], 'xx': [tab2_dtim], 'yy': [tab2_freq]}
        else:
            tab2_SRC_dspec_image.data = {'data': [spec_plt], 'xx': [tab2_dtim], 'yy': [tab2_freq]}
        tab2_SRC_dspec.data['dspec'] = spec_plt.flatten()
        tab2_p_dspec_xPro.y_range.start = spec_plt_min
        tab2_p_dspec_xPro.y_range.end = spec_plt_max
        tab2_p_dspec_yPro.y_range.start = spec_plt_min
        tab2_p_dspec_yPro.y_range.end = spec_plt_max


    tab2_ctrls = [tab2_Select_bl, tab2_Select_pol, tab2_Select_colormap]
    for ctrl in tab2_ctrls:
        ctrl.on_change('value', tab2_update_dspec_image)

    url = ""
    tab2_SRC_p_dspec_thumb = ColumnDataSource(
        dict(url=[url], x1=[0], y1=[0], w1=[config_plot['plot_config']['tab2']['dspec_thumb_wdth']],
             h1=[config_plot['plot_config']['tab2']['dspec_thumb_hght']], ))
    tab2_p_dspec_thumb = figure(tools="pan,wheel_zoom,save",
                                plot_width=config_plot['plot_config']['tab2']['dspec_thumb_wdth'],
                                plot_height=config_plot['plot_config']['tab2']['dspec_thumb_hght'],
                                x_range=(0, config_plot['plot_config']['tab2']['dspec_thumb_wdth']),
                                y_range=(0, config_plot['plot_config']['tab2']['dspec_thumb_hght']),
                                title="EVLA thumbnail",
                                toolbar_location="right")
    r_dspec_thumb = tab2_p_dspec_thumb.image_url(url="url", x="x1", y="y1", w="w1", h="h1",
                                                 source=tab2_SRC_p_dspec_thumb, anchor='bottom_left')
    tab2_p_dspec_thumb.xaxis.visible = False
    tab2_p_dspec_thumb.yaxis.visible = False
    tab2_p_dspec_thumb.title.text_font_size = '6pt'
    tab2_p_dspec_thumb.border_fill_color = "whitesmoke"

    # # Add a hover tool
    tooltips = None

    hover_JScode = """
    var nx = %d;
    var ny = %d;
    var data = {'x': [], 'y': []};
    var cdata = rs.get('data');
    var indices = cb_data.index['1d'].indices;
    var idx_offset = indices[0] - (indices[0] %% nx);
    for (i=0; i < nx; i++) {
        data['x'].push(cdata.time[i+idx_offset]);
        data['y'].push(cdata.dspec[i+idx_offset]);
    }
    rdx.set('data', data);
    idx_offset = indices[0] %% nx;
    data = {'x': [], 'y': []};
    for (i=0; i < ny; i++) {
        data['x'].push(cdata.freq[i*nx+idx_offset]);
        data['y'].push(cdata.dspec[i*nx+idx_offset]);
    }
    rdy.set('data', data);
    var time = cdata.timestr[indices[0]]+' '
    var freq = cdata.freq[indices[0]].toFixed(3)+'[GHz] '
    var dspec = cdata.dspec[indices[0]].toFixed(3)+ '[sfu]'
    var tooltips = freq + time + dspec
    data = {'x': [], 'y': [], 'tooltips': []};
    data['x'].push(cdata.time[indices[0]]);
    data['y'].push(cdata.dspec[indices[0]]);
    data['tooltips'].push(tooltips);
    rdx_hover.set('data', data);
    tooltips = time + freq + dspec
    data = {'x': [], 'y': [], 'tooltips': []};
    data['x'].push(cdata.freq[indices[0]]);
    data['y'].push(cdata.dspec[indices[0]]);
    data['tooltips'].push(tooltips);
    rdy_hover.set('data', data);
    """ % (tab2_ntim, tab2_nfreq)

    tab2_p_dspec_hover_callback = CustomJS(
        args={'rs': tab2_r_square.data_source, 'rdx': r_dspec_xPro.data_source, 'rdy': r_dspec_yPro.data_source,
              'rdx_hover': r_dspec_xPro_hover.data_source,
              'rdy_hover': r_dspec_yPro_hover.data_source}, code=hover_JScode)
    tab2_p_dspec_hover = HoverTool(tooltips=tooltips, callback=tab2_p_dspec_hover_callback,
                                   renderers=[tab2_r_square])
    tab2_p_dspec.add_tools(tab2_p_dspec_hover)

    tab2_input_tCLN = TextInput(value="Input the param here", title="Clean task parameters:",
                                width=config_plot['plot_config']['tab2_2CASA']['input_tCLN_wdth'])

    tab2_Div_tCLN = Div(text='', width=config_plot['plot_config']['tab2_2CASA']['tab2_Div_tCLN_wdth'])
    tab2_Div_tCLN2 = Div(text='', width=600)

    timestart = xx[0]


    def tab2_BUT_tCLN_param_add():
        tab2_Div_tCLN2.text = ' '
        txts = tab2_input_tCLN.value.strip()
        txts = txts.split(';')
        for txt in txts:
            txt = txt.strip()
            if txt == 'timerange':
                time0, time1 = dspecDF['time'].min() + timestart, dspecDF['time'].max() + timestart
                date_char = jdutil.jd_to_datetime(timestart / 3600. / 24.)
                date_char = date_char.strftime('%Y/%m/%d')
                t0_char = jdutil.jd_to_datetime(time0 / 3600. / 24.)
                t0_char = t0_char.strftime('%H:%M:%S') + '.{:03d}'.format(int(round(t0_char.microsecond / 1e3)))
                t1_char = jdutil.jd_to_datetime(time1 / 3600. / 24.)
                t1_char = t1_char.strftime('%H:%M:%S') + '.{:03d}'.format(int(round(t1_char.microsecond / 1e3)))
                tab2_tCLN_Param_dict['timerange'] = "'{}/{}~{}/{}'".format(date_char, t0_char, date_char, t1_char)
            elif txt == 'freqrange':
                freq0, freq1 = dspecDF['freq'].min(), dspecDF['freq'].max()
                freqrange = "'{:.3f}~{:.3f} GHz'".format(freq0, freq1)
                tab2_tCLN_Param_dict['freqrange'] = freqrange
            else:
                txt = txt.split('=')
                if len(txt) == 2:
                    key, val = txt
                    tab2_tCLN_Param_dict[key.strip()] = val.strip()
                else:
                    tab2_Div_tCLN2.text = '<p>Input syntax: <b>uvtaper</b>=True; <b>niter</b>=200; ' \
                                          '<b>cell</b>=["5.0arcsec", "5.0arcsec"]. Any spaces will be ignored.</p>'
        tab2_Div_tCLN_text = ' '.join(
            "<p><b>{}</b> = {}</p>".format(key, val) for (key, val) in tab2_tCLN_Param_dict.items())
        tab2_Div_tCLN.text = tab2_Div_tCLN_text


    def tab2_BUT_tCLN_param_delete():
        global tab2_tCLN_Param_dict
        tab2_Div_tCLN2.text = ' '
        txts = tab2_input_tCLN.value.strip()
        txts = txts.split(';')
        for key in txts:
            try:
                tab2_tCLN_Param_dict.pop(key)
            except:
                tab2_Div_tCLN2.text = '<p>Input syntax: <b>uvtaper</b>; <b>niter</b>; ' \
                                      '<b>cell</b>. Any spaces will be ignored.</p>'
        tab2_Div_tCLN_text = ' '.join(
            "<p><b>{}</b> = {}</p>".format(key, val) for (key, val) in tab2_tCLN_Param_dict.items())
        tab2_Div_tCLN.text = tab2_Div_tCLN_text


    def tab2_BUT_tCLN_param_default():
        global tab2_tCLN_Param_dict
        tab2_tCLN_Param_dict = OrderedDict()
        tab2_tCLN_Param_dict['mspath'] = "'/srg/sjyu/20141101/'"
        tab2_tCLN_Param_dict['vis'] = "'/srg/sjyu/20141101/sun_20141101_t191020-191040.50ms.cal.ms'"
        tab2_tCLN_Param_dict['imagedir'] = "'slfcal/{}'".format(struct_id)
        tab2_tCLN_Param_dict['ncpu'] = "8"
        tab2_tCLN_Param_dict['twidth'] = "1"
        tab2_tCLN_Param_dict['doreg'] = "False"
        tab2_tCLN_Param_dict['timerange'] = "''"
        tab2_tCLN_Param_dict['uvrange'] = "''"
        tab2_tCLN_Param_dict['antenna'] = "''"
        tab2_tCLN_Param_dict['ephemfile'] = "'horizons_sun_20141101.radecp'"
        tab2_tCLN_Param_dict['msinfofile'] = "'sun_20141101_t191020-191040.50ms.cal.msinfo.npz'"
        tab2_tCLN_Param_dict['struct_id'] = "'{}'".format(struct_id.replace("/", ""))
        tab2_tCLN_Param_dict['mode'] = "'channel'"
        tab2_tCLN_Param_dict['imagermode'] = "'csclean'"
        tab2_tCLN_Param_dict['weighting'] = "'briggs'"
        tab2_tCLN_Param_dict['gain'] = '0.1'
        tab2_tCLN_Param_dict['psfmode'] = "'clark'"
        tab2_tCLN_Param_dict['imsize'] = ""'[512, 512]'""
        tab2_tCLN_Param_dict['cell'] = "['5.0arcsec', '5.0arcsec']"
        tab2_tCLN_Param_dict['phasecenter'] = "'J2000 14h26m22.7351 -14d29m29.801'"
        tab2_tCLN_Param_dict['mask'] = "' '"
        tab2_tCLN_Param_dict['stokes'] = "'RRLL'"
        tab2_tCLN_Param_dict['uvtaper'] = 'True'
        tab2_tCLN_Param_dict['outertaper'] = "['50arcsec']"
        tab2_tCLN_Param_dict['uvrange'] = "''"
        tab2_tCLN_Param_dict['niter'] = "200"
        tab2_tCLN_Param_dict['usescratch'] = "False"
        tab2_tCLN_Param_dict['interactive'] = "False"
        tab2_Div_tCLN_text = ' '.join(
            "<p><b>{}</b> = {}</p>".format(key, val) for (key, val) in tab2_tCLN_Param_dict.items())
        tab2_Div_tCLN.text = tab2_Div_tCLN_text
        tab2_Div_tCLN2.text = '<p><b>Default parameter Restored.</b></p>'


    tab2_BUT_tCLN_param_default()

    tab2_BUT_tCLN_param_ADD = Button(label='Add to Param', width=100, button_type='primary')
    tab2_BUT_tCLN_param_ADD.on_click(tab2_BUT_tCLN_param_add)
    tab2_BUT_tCLN_param_DEL = Button(label='Delete Param', width=100, button_type='warning')
    tab2_BUT_tCLN_param_DEL.on_click(tab2_BUT_tCLN_param_delete)
    tab2_BUT_tCLN_param_Default = Button(label='Default Param', width=100)
    tab2_BUT_tCLN_param_Default.on_click(tab2_BUT_tCLN_param_default)
    tab2_SPCR_ABV_BUT_tCLN = Spacer(width=50, height=18)
    tab2_SPCR_LFT_BUT_tCLN_param_ADD = Spacer(width=50, height=10)
    tab2_SPCR_LFT_BUT_tCLN_param_DEL = Spacer(width=20, height=10)
    tab2_SPCR_LFT_BUT_tCLN_param_default = Spacer(width=20, height=10)
    tab2_SPCR_LFT_Div_tCLN2 = Spacer(width=50, height=10)


    def tab2_BUT_tCLN_process():
        with open(database_dir + event_id + struct_id + 'CASA_CLN_args.json', 'w') as fp:
            json.dump(tab2_tCLN_Param_dict, fp)
        os.system('cp FSview/script_process.py {}'.format(database_dir + event_id + struct_id))
        tab2_Div_tCLN2.text = '<p>CASA script and arguments config file saved to <b>{}</b>.</p>'.format(
            database_dir + event_id + struct_id)


    tab2_BUT_process = Button(label='Process', width=150, button_type='success')
    tab2_BUT_process.on_click(tab2_BUT_tCLN_process)


    def tab2_panel2_exit():
        tab2_panel_Div_exit.text = """<p><b>You may close the tab anytime you like.</b></p>"""
        raise SystemExit


    tab2_panel2_BUT_exit = Button(label='Exit FSview2CASA', width=150, button_type='danger')
    tab2_panel2_BUT_exit.on_click(tab2_panel2_exit)
    panel2 = column(tab2_p_dspec, row(column(row(tab2_p_dspec_xPro, tab2_p_dspec_yPro), row(tab2_input_tCLN, column(
        tab2_SPCR_ABV_BUT_tCLN, column(
            row(tab2_SPCR_LFT_BUT_tCLN_param_ADD, tab2_BUT_tCLN_param_ADD, tab2_SPCR_LFT_BUT_tCLN_param_DEL,
                tab2_BUT_tCLN_param_DEL, tab2_SPCR_LFT_BUT_tCLN_param_default, tab2_BUT_tCLN_param_Default),
            row(tab2_SPCR_LFT_Div_tCLN2, tab2_Div_tCLN2)))), tab2_Div_tCLN),
                                      widgetbox(tab2_Select_pol, tab2_Select_bl, tab2_Select_colormap, tab2_BUT_process,
                                                tab2_panel2_BUT_exit, tab2_panel_Div_exit, width=150)))

    curdoc().add_root(panel2)
    curdoc().title = "FSview2CASA"  # except:
    #     print 'prepare the data first'
    #     raise SystemExit
