# # add to crontab file
# # cronjob to convert UDB data to CASA Measurement Sets every 10 minutes
# */10 * * * * cd /home/user/workdir; >/dev/null 2>&1


from datetime import datetime as dt
import glob
import os

tnow = dt.now()
yy = tnow.strftime("%Y")
ymd = tnow.strftime("%Y%m%d")
inpath = '/data1/eovsa/fits/UDB/{}/'.format(yy)
idbfiles = [os.path.basename(ll) for ll in glob.glob('{}UDB{}*'.format(inpath, ymd))]


outpath = '/data1/eovsa/fits/UDBms/{}/'.format(yy)
if not os.path.exists(outpath):
    os.makedirs(outpath)
msfiles = [os.path.basename(ll).split('-')[0] for ll in glob.glob('{}UDB{}*'.format(outpath, ymd))]

files2import = [inpath + ll for ll in list(set(idbfiles) - set(msfiles))]
if files2import:
	importeovsa(idbfiles=files2import, timebin="0s", width=1,
	            visprefix=outpath, nocreatms=False, doconcat=False, modelms="")


