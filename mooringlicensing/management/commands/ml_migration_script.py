from django.core.management.base import BaseCommand
from django.conf import settings
from mooringlicensing.utils.ml_migrate import MooringLicenceReader
import time

import logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Run the MooringLicensing Migration Script \n' \
           'python manage_ml.py ml_migration_script --path shared/utils/csv/clean/'

    def add_arguments(self, parser):
        parser.add_argument('--path', type=str)

    def handle(self, *args, **options):
        path = options['path']
        t_start = time.time()

        mlr=MooringLicenceReader('PersonDets.txt', 'MooringDets.txt', 'VesselDets.txt', 'UserDets.txt', 'ApplicationDets.txt','annual_admissions_booking_report.csv', path=path)

        mlr.create_users()
        mlr.create_vessels()
        mlr.create_mooring_licences()
        mlr.create_authuser_permits()
        mlr.create_waiting_list()
        mlr.create_dcv()
        mlr.create_annual_admissions()

        MooringLicenceReader.create_pdf_ml()
        MooringLicenceReader.create_pdf_aup()
        MooringLicenceReader.create_pdf_wl()
        MooringLicenceReader.create_pdf_dcv()
        MooringLicenceReader.create_pdf_aa()

        t_end = time.time()
        logger.info('TIME TAKEN: {}'.format(t_end - t_start))

