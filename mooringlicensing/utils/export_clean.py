import csv
import os

def clean(srcpath='/var/www/ml_seg/mooringlicensing/utils/csv/clean_31Jul2023_renamed', outpath='/var/www/ml_seg/mooringlicensing/utils/csv/clean'):
    '''
    from mooringlicensing.utils.export_clean import clean
    clean()
    '''

    isExist = os.path.exists(outpath)
    if not isExist:
        os.makedirs(outpath)

    files = []
    lines = []
    #import ipdb; ipdb.set_trace()
    for file in os.listdir(srcpath):
        if file.endswith(".txt"):
            files.append(file)

#    for filename in files:
#        #with open('/home/jawaidm/Documents/ML_Excel/Lotus_Notes_extracts/EmergencyDets20221201-083245.txt', encoding="cp1252") as f:
#        with open(srcpath + os.sep + filename, encoding="cp1252") as inf:
#            #lines = [line.strip()[1:-1] for line in inf]
#            lines = [line.strip().replace('"', '').strip().replace('"', '') for line in inf]
#            #import ipdb; ipdb.set_trace()
#
#        out_filename = filename.split('/')[-1]
#        with open(outpath + os.sep + out_filename, 'w') as outf:
#            wr = csv.writer(outf) #, delimiter ='|', quotechar = '"')
#            for line in lines:
#                #wr.writerow(line.strip('"').split('|'))
#                #wr.writerow([line.strip('"')])
#                wr.writerow([line])


    for filename in files:
        out_filename = filename.split('/')[-1]
        with open(srcpath + os.sep + filename, 'r', encoding="cp1252") as infile, open(outpath + os.sep + out_filename, 'w') as outfile:
            temp = infile.read().replace('"','')
            outfile.write(temp)
