import datetime
import logging

import ledger_api_client.utils
# from ledger.checkout.utils import calculate_excl_gst
import pytz
import json

from rest_framework.views import APIView

from mooringlicensing.ledger_api_utils import retrieve_email_userro, get_invoice_payment_status
# from ledger.settings_base import TIME_ZONE
from mooringlicensing.settings import TIME_ZONE
from decimal import *
# from ledger.payments.bpoint.models import BpointTransaction
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from mooringlicensing.components.main.models import ApplicationType
# from mooringlicensing.components.payments_ml.invoice_pdf import create_invoice_pdf_bytes
from rest_framework.response import Response

import dateutil.parser
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect
# from django.core.urlresolvers import reverse
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, render, redirect
from django.views import View
from django.views.generic import TemplateView
# <<<<<<< HEAD
# from ledger.basket.models import Basket
# from ledger.payments.invoice.models import Invoice
from ledger_api_client.ledger_models import Invoice, Basket
# from ledger.payments.utils import update_payments
from ledger_api_client.utils import update_payments, calculate_excl_gst
# from oscar.apps.order.models import Order
from ledger_api_client.order import Order
# ||||||| 741adce2
# from ledger.basket.models import Basket
# from ledger.payments.invoice.models import Invoice
# from ledger.payments.utils import update_payments
# from oscar.apps.order.models import Order
# =======
# from ledger.basket.models import Basket
# from ledger.payments.invoice.models import Invoice
# from ledger.payments.utils import update_payments
#from oscar.apps.order.models import Order
# from ledger.order.models import Order
# >>>>>>> main

from mooringlicensing import settings
from mooringlicensing.components.approvals.models import DcvPermit, DcvAdmission, Approval, StickerActionDetail, Sticker
from mooringlicensing.components.payments_ml.email import send_application_submit_confirmation_email
from mooringlicensing.components.approvals.email import send_dcv_permit_mail, send_dcv_admission_mail, \
    send_sticker_replacement_email
from mooringlicensing.components.payments_ml.models import ApplicationFee, DcvPermitFee, \
    DcvAdmissionFee, FeeItem, StickerActionFee, FeeItemStickerReplacement, FeeItemApplicationFee, FeeCalculation
from mooringlicensing.components.payments_ml.utils import checkout, set_session_application_invoice, set_session_dcv_admission_invoice, get_session_sticker_action_invoice, delete_session_sticker_action_invoice
from mooringlicensing.components.proposals.models import Proposal, ProposalUserAction, \
    AuthorisedUserApplication, MooringLicenceApplication, WaitingListApplication, AnnualAdmissionApplication, \
    VesselDetails
from mooringlicensing.settings import PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_RENEWAL, LEDGER_SYSTEM_ID
from rest_framework import status
from ledger_api_client import utils

# logger = logging.getLogger('mooringlicensing')
logger = logging.getLogger(__name__)


class DcvAdmissionFeeView(TemplateView):

    def get_object(self):
        return get_object_or_404(DcvAdmission, id=self.kwargs['dcv_admission_pk'])

    def post(self, request, *args, **kwargs):
        dcv_admission = self.get_object()
        dcv_admission_fee = DcvAdmissionFee.objects.create(dcv_admission=dcv_admission, created_by=dcv_admission.submitter, payment_type=DcvAdmissionFee.PAYMENT_TYPE_TEMPORARY)

        try:
            with transaction.atomic():
                set_session_dcv_admission_invoice(request.session, dcv_admission_fee)

                lines, db_processes = dcv_admission.create_fee_lines()

                # request.session['db_processes'] = db_processes_after_success
                new_fee_calculation = FeeCalculation.objects.create(uuid=dcv_admission_fee.uuid, data=db_processes)
                checkout_response = checkout(
                    request,
                    dcv_admission.submitter_obj,
                    lines,
                    # return_url_ns='dcv_admission_fee_success',
                    # return_preload_url_ns='dcv_admission_fee_success',
                    # request.build_absolute_uri(reverse('dcv_admission_fee_success')),
                    # request.build_absolute_uri(reverse('dcv_admission_fee_success')),
                    return_url=request.build_absolute_uri(reverse('dcv_admission_fee_success', kwargs={"uuid": dcv_admission_fee.uuid})),
                    # return_preload_url=request.build_absolute_uri(reverse("dcv_admission_fee_success_preload", kwargs={"uuid": dcv_admission_fee.uuid})),
                    return_preload_url=settings.MOORING_LICENSING_EXTERNAL_URL + reverse("dcv_admission_fee_success_preload", kwargs={"uuid": dcv_admission_fee.uuid}),
                    booking_reference=str(dcv_admission_fee.uuid),
                    invoice_text='DCV Admission Fee',
                )

                logger.info('{} built payment line item {} for DcvAdmission Fee and handing over to payment gateway'.format(dcv_admission.submitter, dcv_admission.id))
                return checkout_response

        except Exception as e:
            logger.error('Error Creating DcvAdmission Fee: {}'.format(e))
            if dcv_admission_fee:
                dcv_admission_fee.delete()
            raise


class DcvPermitFeeView(TemplateView):

    def get_object(self):
        return get_object_or_404(DcvPermit, id=self.kwargs['dcv_permit_pk'])

    def post(self, request, *args, **kwargs):
        dcv_permit = self.get_object()
        created_by = None if request.user.is_anonymous else request.user.id
        dcv_permit_fee = DcvPermitFee.objects.create(dcv_permit=dcv_permit, created_by=created_by, payment_type=DcvPermitFee.PAYMENT_TYPE_TEMPORARY)

        try:
            with transaction.atomic():
                # set_session_dcv_permit_invoice(request.session, dcv_permit_fee)

                # lines, db_processes_after_success = create_fee_lines(dcv_permit)
                lines, db_processes = dcv_permit.create_fee_lines()

                # request.session['db_processes'] = db_processes_after_success
                new_fee_calculation = FeeCalculation.objects.create(uuid=dcv_permit_fee.uuid, data=db_processes)

                checkout_response = checkout(
                    request,
                    dcv_permit.submitter_obj,
                    lines,
                    # request.build_absolute_uri(reverse('dcv_permit_fee_success')),  # return url
                    # request.build_absolute_uri(reverse('dcv_permit_fee_success')),  # return preload url
                    return_url=request.build_absolute_uri(reverse('dcv_permit_fee_success', kwargs={"uuid": dcv_permit_fee.uuid})),
                    # return_preload_url=request.build_absolute_uri(reverse("dcv_permit_fee_success_preload", kwargs={"uuid": dcv_permit_fee.uuid})),
                    return_preload_url=settings.MOORING_LICENSING_EXTERNAL_URL + reverse("dcv_permit_fee_success_preload", kwargs={"uuid": dcv_permit_fee.uuid}),
                    booking_reference=str(dcv_permit_fee.uuid),
                    invoice_text='DCV Permit Fee',
                )

                logger.info('{} built payment line item {} for DcvPermit Fee and handing over to payment gateway'.format(request.user, dcv_permit.id))
                return checkout_response

        except Exception as e:
            logger.error('Error Creating DcvPermit Fee: {}'.format(e))
            if dcv_permit_fee:
                dcv_permit_fee.delete()
            raise


class ConfirmationView(TemplateView):
    template_name = 'mooringlicensing/payments_ml/success_submit.html'

    def get_object(self):
        return get_object_or_404(Proposal, id=self.kwargs['proposal_pk'])

    def post(self, request, *args, **kwargs):
        proposal = self.get_object()

        if proposal.application_type.code in (WaitingListApplication.code, AnnualAdmissionApplication.code,):
            self.send_confirmation_mail(proposal, request)
        else:
            pass
            # Confirmation email has been sent in the instance.process_after_submit()

        context = {
            'proposal': proposal,
            'submitter': proposal.submitter_obj,
        }
        return render(request, self.template_name, context)

    @staticmethod
    def send_confirmation_mail(proposal, request):
        # Send invoice
        to_email_addresses = proposal.submitter_obj.email
        email_data = send_application_submit_confirmation_email(request, proposal, [to_email_addresses, ])


# class ApplicationFeeExistingView(TemplateView):
class ApplicationFeeExistingView(APIView):
    def get_object(self):
        return get_object_or_404(Invoice, reference=self.kwargs['invoice_reference'])

    def get(self, request, *args, **kwargs):
        invoice = self.get_object()
        logger.info(f'Getting payment screen for the future invoice: [{invoice}] ...')

        application_fee = ApplicationFee.objects.get(invoice_reference=invoice.reference)

        # if application_fee.paid:
        #     return redirect('application_fee_already_paid', proposal_pk=proposal.id)
        if get_invoice_payment_status(invoice.id) in ['paid', 'over_paid',]:
            return redirect('application_fee_already_paid', proposal_pk=application_fee.proposal.id)

        try:
            with transaction.atomic():
                db_processes = {
                    'for_existing_invoice': True,
                    'fee_item_application_fee_ids': [],
                }
                fee_item_application_fees = FeeItemApplicationFee.objects.filter(application_fee=application_fee)
                for fee_item_application_fee in fee_item_application_fees:
                    db_processes['fee_item_application_fee_ids'].append(fee_item_application_fee.id)

                new_fee_calculation = FeeCalculation.objects.create(uuid=application_fee.uuid, data=db_processes)

                return_url = request.build_absolute_uri(reverse('fee_success', kwargs={"uuid": application_fee.uuid}))
                fallback_url = request.build_absolute_uri(reverse("external"))
                payment_session = ledger_api_client.utils.generate_payment_session(request, invoice.reference, return_url, fallback_url)
                return HttpResponseRedirect(payment_session['payment_url'])

        except Exception as e:
            logger.error('Error Creating Application Fee: {}'.format(e))
            raise


class StickerReplacementFeeView(TemplateView):
    def get_object(self):
        if 'approval_pk' in self.kwargs:
            return get_object_or_404(Approval, id=self.kwargs['approval_pk'])
        elif 'sticker_id' in self.kwargs:
            return get_object_or_404(Sticker, id=self.kwargs['sticker_id'])
        else:
            # Should not reach here
            pass

    def post(self, request, *args, **kwargs):
        # approval = self.get_object()
        data = request.POST.get('data')
        data = json.loads(data)
        ids = data['sticker_action_detail_ids']

        # 1. Validate data
        # raise forms.ValidationError('Validation error')

        # 2. Store detais in the session
        sticker_action_fee = StickerActionFee.objects.create(created_by=request.user.id, payment_type=StickerActionFee.PAYMENT_TYPE_TEMPORARY)
        current_datetime = datetime.datetime.now(pytz.timezone(TIME_ZONE))

        try:
            with transaction.atomic():
                sticker_action_details = StickerActionDetail.objects.filter(id__in=ids)
                sticker_action_details.update(sticker_action_fee=sticker_action_fee)

                # set_session_sticker_action_invoice(request.session, sticker_action_fee)

                target_datetime_str = current_datetime.astimezone(pytz.timezone(TIME_ZONE)).strftime('%d/%m/%Y %I:%M %p')
                application_type = ApplicationType.objects.get(code=settings.APPLICATION_TYPE_REPLACEMENT_STICKER['code'])
                fee_item = FeeItemStickerReplacement.get_fee_item_by_date(current_datetime.date())

                lines = []
                for sticker_action_detail in sticker_action_details:
                    line = {
                        'ledger_description': 'Sticker Replacement Fee, sticker: {} @{}'.format(sticker_action_detail.sticker, target_datetime_str),
                        'oracle_code': application_type.get_oracle_code_by_date(current_datetime.date()),
                        'price_incl_tax': fee_item.amount,
                        'price_excl_tax': ledger_api_client.utils.calculate_excl_gst(fee_item.amount) if fee_item.incur_gst else fee_item.amount,
                        'quantity': 1,
                    }
                    lines.append(line)

                checkout_response = checkout(
                    request,
                    request.user,
                    lines,
                    # request.build_absolute_uri(reverse('sticker_replacement_fee_success')),
                    # request.build_absolute_uri(reverse('sticker_replacement_fee_success')),
                    return_url=request.build_absolute_uri(reverse('sticker_replacement_fee_success', kwargs={"uuid": sticker_action_fee.uuid})),
                    # return_preload_url=request.build_absolute_uri(reverse("sticker_replacement_fee_success_preload", kwargs={"uuid": sticker_action_fee.uuid})),
                    return_preload_url=settings.MOORING_LICENSING_EXTERNAL_URL + reverse("sticker_replacement_fee_success_preload", kwargs={"uuid": sticker_action_fee.uuid}),
                    booking_reference=str(sticker_action_fee.uuid),
                    invoice_text='{}'.format(application_type.description),
                )

                logger.info('{} built payment line item(s) {} for Sticker Replacement Fee and handing over to payment gateway'.format('User {} with id {}'.format(request.user.get_full_name(), request.user.id), sticker_action_fee))
                return checkout_response

        except Exception as e:
            logger.error('Error handling StickerActionFee: {}'.format(e))
            if sticker_action_fee:
                sticker_action_fee.delete()
            raise


class StickerReplacementFeeSuccessViewPreload(APIView):

    def get(self, request, uuid, format=None):
        logger.info(f'{StickerReplacementFeeSuccessViewPreload.__name__} get method is called.')

        if uuid:  # and invoice_reference:
            if not StickerActionFee.objects.filter(uuid=uuid).exists():
                logger.info(f'StickerActionFee with uuid: {uuid} does not exist.  Redirecting user to dashboard page.')
                return redirect(reverse('external'))
            else:
                logger.info(f'StickerActionFee with uuid: {uuid} exists.')
            sticker_action_fee = StickerActionFee.objects.get(uuid=uuid)
            sticker_action_details = sticker_action_fee.sticker_action_details

            invoice_reference = request.GET.get("invoice", "")
            logger.info(f"Invoice reference: {invoice_reference} and uuid: {uuid}.",)
            if not Invoice.objects.filter(reference=invoice_reference).exists():
                logger.info(f'Invoice with invoice_reference: {invoice_reference} does not exist.  Redirecting user to dashboard page.')
                return redirect(reverse('external'))
            else:
                logger.info(f'Invoice with invoice_reference: {invoice_reference} exist.')
            invoice = Invoice.objects.get(reference=invoice_reference)

            sticker_action_fee.invoice_reference = invoice.reference
            sticker_action_fee.save()

            if sticker_action_fee.payment_type == StickerActionFee.PAYMENT_TYPE_TEMPORARY:
                # if fee_inv:
                sticker_action_fee.payment_type = ApplicationFee.PAYMENT_TYPE_INTERNET
                sticker_action_fee.expiry_time = None
                sticker_action_fee.save()

                # for sticker_action_detail in sticker_action_details.all():
                #     old_sticker = sticker_action_detail.sticker
                #     new_sticker = old_sticker.request_replacement(Sticker.STICKER_STATUS_LOST)
                sticker_action_detail = sticker_action_details.first()
                old_sticker = sticker_action_detail.sticker
                new_sticker = old_sticker.request_replacement(Sticker.STICKER_STATUS_LOST)

                # Send email with the invoice
                send_sticker_replacement_email(request, old_sticker, new_sticker, invoice.reference)

            logger.info(
                "Returning status.HTTP_200_OK. Order created successfully.",
            )
            # this end-point is called by an unmonitored get request in ledger so there is no point having a
            # a response body however we will return a status in case this is used on the ledger end in future
            # return Response(status=status.HTTP_204_NO_CONTENT)
            return Response(status=status.HTTP_200_OK)


class StickerReplacementFeeSuccessView(TemplateView):
    template_name = 'mooringlicensing/payments_ml/success_sticker_action_fee.html'
    LAST_STICKER_ACTION_FEE_ID = 'mooringlicensing_last_dcv_admission_invoice'

    def get(self, request, uuid):
        logger.info(f'{StickerReplacementFeeSuccessView.__name__} get method is called.')

        try:
            sticker_action_fee = StickerActionFee.objects.get(uuid=uuid)
            invoice = Invoice.objects.get(reference=sticker_action_fee.invoice_reference)
            # invoice_url = get_invoice_url(invoice.reference, request)
            # api_key = settings.LEDGER_API_KEY
            # invoice_url = settings.LEDGER_API_URL+'/ledgergw/invoice-pdf/'+api_key+'/' + self.invoice.reference
            invoice_url = f'/ledger-toolkit-api/invoice-pdf/{self.invoice.reference}/'
            # invoice_pdf = requests.get(url=url)
            submitter = retrieve_email_userro(sticker_action_fee.created_by) if sticker_action_fee.created_by else ''

            context = {
                'submitter': submitter,
                'fee_invoice': sticker_action_fee,
                'invoice': invoice,
                'invoice_url': invoice_url,
            }
            return render(request, self.template_name, context)

        except Exception as e:
            # Should not reach here
            msg = 'Failed to process the payment. {}'.format(str(e))
            logger.error(msg)
            raise Exception(msg)


class ApplicationFeeView(TemplateView):

    def get_object(self):
        return get_object_or_404(Proposal, id=self.kwargs['proposal_pk'])

    def get(self, request, *args, **kwargs):
        pass

    def post(self, request, *args, **kwargs):
        proposal = self.get_object()
        application_fee = ApplicationFee.objects.create(proposal=proposal, created_by=request.user.id, payment_type=ApplicationFee.PAYMENT_TYPE_TEMPORARY)
        logger.info('ApplicationFee.id: {} has been created for the Proposal: {}'.format(application_fee.id, proposal))

        try:
            with transaction.atomic():
                set_session_application_invoice(request.session, application_fee)

                try:
                    lines, db_processes_after_success = proposal.child_obj.create_fee_lines()  # Accessed by WL and AA
                except Exception as e:
                    # return HttpResponseRedirect(reverse('external-proposal-detail', kwargs={'proposal_pk': proposal.id}))
                    # return HttpResponse({'error': e})

                    self.template_name = 'mooringlicensing/payments_ml/fee_calculation_error.html'
                    context = {
                        'error_message': str(e),
                    }
                    return render(request, self.template_name, context)

                # request.session['db_processes'] = db_processes_after_success
                new_fee_calculation = FeeCalculation.objects.create(uuid=application_fee.uuid, data=db_processes_after_success)

                return_url = request.build_absolute_uri(reverse('fee_success', kwargs={"uuid": application_fee.uuid}))
                # return_preload_url = request.build_absolute_uri(reverse("ledger-api-success-callback", kwargs={"uuid": application_fee.uuid}))
                return_preload_url = settings.MOORING_LICENSING_EXTERNAL_URL + reverse("ledger-api-success-callback", kwargs={"uuid": application_fee.uuid})
                reference = proposal.previous_application.lodgement_number if proposal.previous_application else proposal.lodgement_number
                checkout_response = checkout(
                    request,
                    proposal.submitter_obj,
                    lines,
                    return_url,
                    return_preload_url,
                    # booking_reference=str(application_fee.uuid),
                    booking_reference=reference,
                    invoice_text='{} ({})'.format(proposal.application_type.description, proposal.proposal_type.description),
                )

                user = proposal.submitter_obj

                logger.info('{} built payment line item {} for Application Fee and handing over to payment gateway'.format('User {} with id {}'.format(user.get_full_name(), user.id), proposal.id))
                return checkout_response

        except Exception as e:
            logger.error('Error while checking out for the proposal: {}\n{}'.format(proposal.lodgement_number, str(e)))
            if application_fee:
                application_fee.delete()
                logger.info('ApplicationFee: {} has been deleted'.format(application_fee))
            raise


class DcvAdmissionFeeSuccessView(TemplateView):
    template_name = 'mooringlicensing/payments_ml/success_dcv_admission_fee.html'
    LAST_DCV_ADMISSION_FEE_ID = 'mooringlicensing_last_dcv_admission_invoice'

    def get(self, request, uuid, *args, **kwargs):
        logger.info(f'{DcvAdmissionFeeSuccessView.__name__} get method is called.')

        if uuid:
            if not DcvAdmissionFee.objects.filter(uuid=uuid).exists():
                logger.info(f'DcvAdmissionFee with uuid: {uuid} does not exist.  Redirecting user to dashboard page.')
                return redirect(reverse('external'))
            else:
                logger.info(f'DcvAdmissionFee with uuid: {uuid} exists.')
            dcv_admission_fee = DcvAdmissionFee.objects.get(uuid=uuid)
            dcv_admission = dcv_admission_fee.dcv_admission

            invoice_url = f'/ledger-toolkit-api/invoice-pdf/{dcv_admission_fee.invoice_reference}/'
            context = {
                'dcv_admission': dcv_admission,
                'submitter': dcv_admission.submitter_obj,
                'fee_invoice': dcv_admission_fee,
                'invoice_url': invoice_url,
                'admission_urls': dcv_admission.get_admission_urls(),
            }
            return render(request, self.template_name, context)
    # def get(self, request, *args, **kwargs):
    # proposal = None
        # submitter = None
        # invoice = None
        #
        # try:
        #     dcv_admission_fee = get_session_dcv_admission_invoice(request.session)  # This raises an exception when accessed 2nd time?
        #
        #     # Retrieve db processes stored when calculating the fee, and delete the session
        #     db_operations = request.session['db_processes']
        #     del request.session['db_processes']
        #
        #     dcv_admission = dcv_admission_fee.dcv_admission
        #     # recipient = dcv_permit.applicant_email
        #     submitter = dcv_admission.submitter
        #
        #     if self.request.user.is_authenticated():
        #         basket = Basket.objects.filter(status='Submitted', owner=request.user).order_by('-id')[:1]
        #     else:
        #         basket = Basket.objects.filter(status='Submitted', owner=dcv_admission.submitter).order_by('-id')[:1]
        #
        #     order = Order.objects.get(basket=basket[0])
        #     invoice = Invoice.objects.get(order_number=order.number)
        #     invoice_ref = invoice.reference
        #
        #     # Update the application_fee object
        #     dcv_admission_fee.invoice_reference = invoice_ref
        #     dcv_admission_fee.save()
        #
        #     if dcv_admission_fee.payment_type == ApplicationFee.PAYMENT_TYPE_TEMPORARY:
        #         try:
        #             inv = Invoice.objects.get(reference=invoice_ref)
        #             order = Order.objects.get(number=inv.order_number)
        #             order.user = submitter
        #             order.save()
        #         except Invoice.DoesNotExist:
        #             logger.error('{} tried paying an dcv_admission fee with an incorrect invoice'.format('User {} with id {}'.format(dcv_admission.submitter_obj.get_full_name(), dcv_admission.submitter_obj.id) if dcv_admission.submitter else 'An anonymous user'))
        #             return redirect('external-dcv_admission-detail', args=(dcv_admission.id,))
        #         if inv.system not in [PAYMENT_SYSTEM_PREFIX,]:
        #             logger.error('{} tried paying an dcv_admission fee with an invoice from another system with reference number {}'.format('User {} with id {}'.format(dcv_admission.submitter_obj.get_full_name(), dcv_admission.submitter_obj.id) if dcv_admission.submitter else 'An anonymous user',inv.reference))
        #             return redirect('external-dcv_admission-detail', args=(dcv_admission.id,))
        #
        #         dcv_admission_fee.payment_type = ApplicationFee.PAYMENT_TYPE_INTERNET
        #         dcv_admission_fee.expiry_time = None
        #         # update_payments(invoice_ref)
        #
        #         # if dcv_admission and invoice.payment_status in ('paid', 'over_paid',):
        #         if dcv_admission and get_invoice_payment_status(invoice.id) in ('paid', 'over_paid',):
        #             self.adjust_db_operations(dcv_admission, db_operations)
        #             dcv_admission.generate_dcv_admission_doc()
        #         else:
        #             logger.error('Invoice payment status is {}'.format(get_invoice_payment_status(invoice.id)))
        #             raise
        #
        #         dcv_admission_fee.save()
        #         request.session[self.LAST_DCV_ADMISSION_FEE_ID] = dcv_admission_fee.id
        #         delete_session_dcv_admission_invoice(request.session)
        #
        #         email_data = send_dcv_admission_mail(dcv_admission, invoice, request)
        #         context = {
        #             'dcv_admission': dcv_admission,
        #             'submitter': submitter,
        #             'fee_invoice': dcv_admission_fee,
        #             'invoice': invoice,
        #             'admission_urls': dcv_admission.get_admission_urls(),
        #         }
        #         return render(request, self.template_name, context)
        #
        # except Exception as e:
        #     if (self.LAST_DCV_ADMISSION_FEE_ID in request.session) and DcvAdmissionFee.objects.filter(id=request.session[self.LAST_DCV_ADMISSION_FEE_ID]).exists():
        #         dcv_admission_fee = DcvAdmissionFee.objects.get(id=request.session[self.LAST_DCV_ADMISSION_FEE_ID])
        #         dcv_admission = dcv_admission_fee.dcv_admission
        #         submitter = dcv_admission.submitter
        #
        #     else:
        #         return redirect('home')
        #
        # invoice = Invoice.objects.get(reference=dcv_admission_fee.invoice_reference)
        # context = {
        #     'dcv_admission': dcv_admission,
        #     'submitter': submitter,
        #     'fee_invoice': dcv_admission_fee,
        #     'invoice': invoice,
        #     'admission_urls': dcv_admission.get_admission_urls(),
        # }
        # return render(request, self.template_name, context)

    # @staticmethod
    # def adjust_db_operations(dcv_admission, db_operations):
    #     dcv_admission.lodgement_datetime = dateutil.parser.parse(db_operations['datetime_for_calculating_fee'])
    #     dcv_admission.save()


class DcvAdmissionFeeSuccessViewPreload(APIView):

    @staticmethod
    def adjust_db_operations(dcv_admission, db_operations):
        dcv_admission.lodgement_datetime = dateutil.parser.parse(db_operations['datetime_for_calculating_fee'])
        dcv_admission.save()

    def get(self, request, uuid, format=None):
        logger.info(f'{DcvAdmissionFeeSuccessViewPreload.__name__} get method is called.')

        if uuid:  # and invoice_reference:
            if not DcvAdmissionFee.objects.filter(uuid=uuid).exists():
                logger.info(f'DcvAdmissionFee with uuid: {uuid} does not exist.  Redirecting user to dashboard page.')
                return redirect(reverse('external'))
            else:
                logger.info(f'DcvAdmissionFee with uuid: {uuid} exists.')
            dcv_admission_fee = DcvAdmissionFee.objects.get(uuid=uuid)
            dcv_admission = dcv_admission_fee.dcv_admission

            invoice_reference = request.GET.get("invoice", "")
            logger.info(f"Invoice reference: {invoice_reference} and uuid: {uuid}.",)
            if not Invoice.objects.filter(reference=invoice_reference).exists():
                logger.info(f'Invoice with invoice_reference: {invoice_reference} does not exist.  Redirecting user to dashboard page.')
                return redirect(reverse('external'))
            else:
                logger.info(f'Invoice with invoice_reference: {invoice_reference} exist.')
            invoice = Invoice.objects.get(reference=invoice_reference)

            if not FeeCalculation.objects.filter(uuid=uuid).exists():
                logger.info(f'FeeCalculation with uuid: {uuid} does not exist.  Redirecting user to dashboard page.')
                return redirect(reverse('external'))
            else:
                logger.info(f'FeeCalculation with uuid: {uuid} exist.')
            fee_calculation = FeeCalculation.objects.get(uuid=uuid)
            db_operations = fee_calculation.data

            if dcv_admission_fee.payment_type == ApplicationFee.PAYMENT_TYPE_TEMPORARY:
                if invoice.system not in [LEDGER_SYSTEM_ID, ]:
                    logger.error('{} tried paying an dcv_admission fee with an invoice from another system with reference number {}'.format('User {} with id {}'.format(dcv_admission.submitter_obj.get_full_name(), dcv_admission.submitter_obj.id) if dcv_admission.submitter else 'An anonymous user',inv.reference))
                    return redirect('external-dcv_admission-detail', args=(dcv_admission.id,))

                dcv_admission_fee.payment_type = ApplicationFee.PAYMENT_TYPE_INTERNET
                dcv_admission_fee.expiry_time = None
                # update_payments(invoice_ref)

                if 'fee_item_ids' in db_operations:
                    for item_id in db_operations['fee_item_ids']:
                        fee_item = FeeItem.objects.get(id=item_id)
                        dcv_admission_fee.fee_items.add(fee_item)

                # if dcv_admission and invoice.payment_status in ('paid', 'over_paid',):
                if dcv_admission and get_invoice_payment_status(invoice.id) in ('paid', 'over_paid',):
                    self.adjust_db_operations(dcv_admission, db_operations)
                    dcv_admission.generate_dcv_admission_doc()
                else:
                    logger.error('Invoice payment status is {}'.format(get_invoice_payment_status(invoice.id)))
                    raise

                dcv_admission_fee.invoice_reference = invoice_reference
                dcv_admission_fee.save()

                email = send_dcv_admission_mail(dcv_admission, invoice, request)
            logger.info(
                "Returning status.HTTP_200_OK. Order created successfully.",
            )
            # this end-point is called by an unmonitored get request in ledger so there is no point having a
            # a response body however we will return a status in case this is used on the ledger end in future
            # return Response(status=status.HTTP_204_NO_CONTENT)
            return Response(status=status.HTTP_200_OK)


class DcvPermitFeeSuccessView(TemplateView):
    template_name = 'mooringlicensing/payments_ml/success_dcv_permit_fee.html'
    LAST_DCV_PERMIT_FEE_ID = 'mooringlicensing_last_dcv_permit_invoice'

    def get(self, request, uuid, *args, **kwargs):
        logger.info(f'{DcvPermitFeeSuccessView.__name__} get method is called.')

        if uuid:
            if not DcvPermitFee.objects.filter(uuid=uuid).exists():
                logger.info(f'DcvPermitFee with uuid: {uuid} does not exist.  Redirecting user to dashboard page.')
                return redirect(reverse('external'))
            else:
                logger.info(f'DcvPermitFee with uuid: {uuid} exists.')
            dcv_permit_fee = DcvPermitFee.objects.get(uuid=uuid)

            dcv_permit = dcv_permit_fee.dcv_permit
            # invoice_url = get_invoice_url(dcv_permit_fee.invoice_reference, request)
            api_key = settings.LEDGER_API_KEY
            invoice_url = settings.LEDGER_API_URL+'/ledgergw/invoice-pdf/'+api_key+'/' + dcv_permit_fee.invoice_reference
            # invoice_pdf = requests.get(url=url)

            context = {
                'dcv_permit': dcv_permit,
                'submitter': dcv_permit.submitter_obj,
                'fee_invoice': dcv_permit_fee,
                'invoice_url': invoice_url,
            }
            return render(request, self.template_name, context)


class DcvPermitFeeSuccessViewPreload(APIView):
    @staticmethod
    def adjust_db_operations(dcv_permit, db_operations):
        dcv_permit.start_date = datetime.datetime.strptime(db_operations['season_start_date'], '%Y-%m-%d').date()
        dcv_permit.end_date = datetime.datetime.strptime(db_operations['season_end_date'], '%Y-%m-%d').date()
        dcv_permit.lodgement_datetime = dateutil.parser.parse(db_operations['datetime_for_calculating_fee'])
        dcv_permit.save()

    def get(self, request, uuid, format=None):
        logger.info(f'{DcvPermitFeeSuccessViewPreload.__name__} get method is called.')

        if uuid:  # and invoice_reference:
            if not DcvPermitFee.objects.filter(uuid=uuid).exists():
                logger.info(f'DcvPermitFee with uuid: {uuid} does not exist.  Redirecting user to dashboard page.')
                return redirect(reverse('external'))
            else:
                logger.info(f'DcvPermitFee with uuid: {uuid} exists.')
            dcv_permit_fee = DcvPermitFee.objects.get(uuid=uuid)

            invoice_reference = request.GET.get("invoice", "")
            logger.info(f"Invoice reference: {invoice_reference} and uuid: {uuid}.",)
            if not Invoice.objects.filter(reference=invoice_reference).exists():
                logger.info(f'Invoice with invoice_reference: {invoice_reference} does not exist.  Redirecting user to dashboard page.')
                return redirect(reverse('external'))
            else:
                logger.info(f'Invoice with invoice_reference: {invoice_reference} exist.')
            invoice = Invoice.objects.get(reference=invoice_reference)

            if not FeeCalculation.objects.filter(uuid=uuid).exists():
                logger.info(f'FeeCalculation with uuid: {uuid} does not exist.  Redirecting user to dashboard page.')
                return redirect(reverse('external'))
            else:
                logger.info(f'FeeCalculation with uuid: {uuid} exist.')
            fee_calculation = FeeCalculation.objects.get(uuid=uuid)
            db_operations = fee_calculation.data

            fee_item = FeeItem.objects.get(id=db_operations['fee_item_id'])
            try:
                fee_item_additional = FeeItem.objects.get(id=db_operations['fee_item_additional_id'])
            except:
                fee_item_additional = None

            # Update the application_fee object
            dcv_permit = dcv_permit_fee.dcv_permit
            dcv_permit_fee.invoice_reference = invoice_reference
            dcv_permit_fee.save()
            dcv_permit_fee.fee_items.add(fee_item)
            if fee_item_additional:
                dcv_permit_fee.fee_items.add(fee_item_additional)

            if dcv_permit_fee.payment_type == DcvPermitFee.PAYMENT_TYPE_TEMPORARY:
                # try:
                #     inv = Invoice.objects.get(reference=invoice_reference)
                #     order = Order.objects.get(number=inv.order_number)
                #     order.user = request.user
                #     order.save()
                # except Invoice.DoesNotExist:
                #     logger.error('{} tried paying an dcv_permit fee with an incorrect invoice'.format('User {} with id {}'.format(dcv_permit.submitter_obj.get_full_name(), dcv_permit.submitter_obj.id) if dcv_permit.submitter else 'An anonymous user'))
                #     return redirect('external-dcv_permit-detail', args=(dcv_permit.id,))
                # if inv.system not in [PAYMENT_SYSTEM_PREFIX,]:
                #     logger.error('{} tried paying an dcv_permit fee with an invoice from another system with reference number {}'.format('User {} with id {}'.format(dcv_permit.submitter_obj.get_full_name(), dcv_permit.submitter_obj.id) if dcv_permit.submitter else 'An anonymous user',inv.reference))
                #     return redirect('external-dcv_permit-detail', args=(dcv_permit.id,))

                dcv_permit_fee.payment_type = ApplicationFee.PAYMENT_TYPE_INTERNET
                dcv_permit_fee.expiry_time = None
                # update_payments(invoice_reference)

                # if dcv_permit and invoice.payment_status in ('paid', 'over_paid',):
                if dcv_permit and get_invoice_payment_status(invoice.id):
                    self.adjust_db_operations(dcv_permit, db_operations)
                    dcv_permit.generate_dcv_permit_doc()
                else:
                    # logger.error('Invoice payment status is {}'.format(invoice.payment_status))
                    logger.error('Invoice payment status is {}'.format(get_invoice_payment_status(invoice.id)))
                    raise

                dcv_permit_fee.save()
                # request.session[self.LAST_DCV_PERMIT_FEE_ID] = dcv_permit_fee.id
                # delete_session_dcv_permit_invoice(request.session)

                send_dcv_permit_mail(dcv_permit, invoice, request)

                # context = {
                #     'dcv_permit': dcv_permit,
                #     'submitter': submitter,
                #     'fee_invoice': dcv_permit_fee,
                # }
                # return render(request, self.template_name, context)

            logger.info(
                "Returning status.HTTP_200_OK. Order created successfully.",
            )
            # this end-point is called by an unmonitored get request in ledger so there is no point having a
            # a response body however we will return a status in case this is used on the ledger end in future
            # return Response(status=status.HTTP_204_NO_CONTENT)
            return Response(status=status.HTTP_200_OK)


class ApplicationFeeAlreadyPaid(TemplateView):
    template_name = 'mooringlicensing/payments_ml/application_fee_already_paid.html'

    def get(self, request, *args, **kwargs):
        proposal = get_object_or_404(Proposal, id=self.kwargs['proposal_pk'])
        application_fee = proposal.get_main_application_fee()
        invoice = Invoice.objects.get(reference=application_fee.invoice_reference)

        context = {
            'proposal': proposal,
            'submitter': proposal.submitter_obj,
            'application_fee': application_fee,
            'invoice': invoice,
        }
        return render(request, self.template_name, context)


class ApplicationFeeSuccessViewPreload(APIView):
    def get(self, request, uuid, format=None):
        logger.info(f'{ApplicationFeeSuccessViewPreload.__name__} get method is called.')

        if uuid:  # and invoice_reference:
            if not ApplicationFee.objects.filter(uuid=uuid).exists():
                logger.info(f'ApplicationFee with uuid: {uuid} does not exist.  Redirecting user to dashboard page.')
                return redirect(reverse('external'))
            else:
                logger.info(f'ApplicationFee with uuid: {uuid} exist.')
            application_fee = ApplicationFee.objects.get(uuid=uuid)

            # invoice_reference is set in the URL when normal invoice,
            # invoice_reference is not set in the URL when future invoice, but it is set in the application_fee on creation.
            invoice_reference = request.GET.get("invoice", "")
            invoice_reference = application_fee.invoice_reference if not invoice_reference else invoice_reference
            logger.info(f"Invoice reference: {invoice_reference} and uuid: {uuid}.",)
            if not Invoice.objects.filter(reference=invoice_reference).exists():
                logger.info(f'Invoice with invoice_reference: {invoice_reference} does not exist.  Redirecting user to dashboard page.')
                return redirect(reverse('external'))
            else:
                logger.info(f'Invoice with invoice_reference: {invoice_reference} exist.')
            invoice = Invoice.objects.get(reference=invoice_reference)

            if not FeeCalculation.objects.filter(uuid=uuid).exists():
                logger.info(f'FeeCalculation with uuid: {uuid} does not exist.  Redirecting user to dashboard page.')
                return redirect(reverse('external'))
            else:
                logger.info(f'FeeCalculation with uuid: {uuid} exist.')
            fee_calculation = FeeCalculation.objects.get(uuid=uuid)

            db_operations = fee_calculation.data
            proposal = application_fee.proposal

            if 'for_existing_invoice' in db_operations and db_operations['for_existing_invoice']:
                # For existing invoices, fee_item_application_fee.amount_paid should be updated, once paid
                for idx in db_operations['fee_item_application_fee_ids']:
                    fee_item_application_fee = FeeItemApplicationFee.objects.get(id=int(idx))
                    fee_item_application_fee.amount_paid = fee_item_application_fee.amount_to_be_paid
                    fee_item_application_fee.save()
            else:
                # Update the application_fee object
                # For the AUA and MLA's new/amendment application, the application_fee already has relations to fee_item(s) created after creating lines.
                # In that case, there are no 'fee_item_id' and/or 'fee_item_additional_id' keys in the db_operations
                if 'fee_item_id' in db_operations:
                    fee_items = FeeItem.objects.filter(id=db_operations['fee_item_id'])
                    if fee_items:
                        amount_paid = None
                        amount_to_be_paid = None
                        if 'fee_amount_adjusted' in db_operations:
                            # Because of business rules, fee_item.amount is not always the same as the actual amount paid.
                            # Therefore we want to store the amount paid too as well as fee_item.
                            fee_amount_adjusted = db_operations['fee_amount_adjusted']
                            amount_to_be_paid = Decimal(fee_amount_adjusted)
                            amount_paid = amount_to_be_paid
                            fee_item = fee_items.first()
                        fee_item_application_fee = FeeItemApplicationFee.objects.create(
                            fee_item=fee_item,
                            application_fee=application_fee,
                            vessel_details=proposal.vessel_details,
                            amount_to_be_paid=amount_to_be_paid,
                            amount_paid=amount_paid,
                        )
                        logger.info(f'FeeItemApplicationFee: {fee_item_application_fee} created')
                if isinstance(db_operations, list):
                    # This is used for AU/ML's auto renewal
                    for item in db_operations:
                        fee_item = FeeItem.objects.get(id=item['fee_item_id'])
                        fee_amount_adjusted = item['fee_amount_adjusted']
                        amount_to_be_paid = Decimal(fee_amount_adjusted)
                        amount_paid = amount_to_be_paid
                        vessel_details_id = item['vessel_details_id']  # This could be '' when null vessel application
                        vessel_details = VesselDetails.objects.get(id=vessel_details_id) if vessel_details_id else None
                        FeeItemApplicationFee.objects.create(
                            fee_item=fee_item,
                            application_fee=application_fee,
                            vessel_details=vessel_details,
                            amount_to_be_paid=amount_to_be_paid,
                            amount_paid=amount_paid,
                        )

            application_fee.invoice_reference = invoice_reference
            application_fee.save()

            if application_fee.payment_type == ApplicationFee.PAYMENT_TYPE_TEMPORARY:
                try:
                    inv = Invoice.objects.get(reference=invoice_reference)
                    # order = Order.objects.get(number=inv.order_number)
                    # order.user = request.user
                    # order.save()
                except Invoice.DoesNotExist:
                    logger.error('{} tried paying an application fee with an incorrect invoice'.format('User {} with id {}'.format(proposal.submitter_obj.get_full_name(), proposal.submitter_obj.id) if proposal.submitter else 'An anonymous user'))
                    return redirect('external-proposal-detail', args=(proposal.id,))
                if inv.system not in [LEDGER_SYSTEM_ID, ]:
                    logger.error('{} tried paying an application fee with an invoice from another system with reference number {}'.format('User {} with id {}'.format(proposal.submitter_obj.get_full_name(), proposal.submitter_obj.id) if proposal.submitter else 'An anonymous user',inv.reference))
                    return redirect('external-proposal-detail', args=(proposal.id,))

                application_fee.payment_type = ApplicationFee.PAYMENT_TYPE_INTERNET
                application_fee.expiry_time = None
                # update_payments(invoice_ref)

                # if proposal and invoice.payment_status in ('paid', 'over_paid',):
                # inv_props = utils.get_invoice_properties(inv.id)
                # invoice_payment_status = inv_props['data']['invoice']['payment_status']
                invoice_payment_status = get_invoice_payment_status(inv.id)
                if proposal and invoice_payment_status in ('paid', 'over_paid',):
                    logger.info('The fee for the proposal: {} has been fully paid'.format(proposal.lodgement_number))

                    if proposal.application_type.code in (AuthorisedUserApplication.code, MooringLicenceApplication.code):
                        # For AUA or MLA, as payment has been done, create approval
                        approval, created = proposal.child_obj.update_or_create_approval(datetime.datetime.now(pytz.timezone(TIME_ZONE)), request)
                    else:
                        # When WLA / AAA
                        if proposal.application_type.code in [WaitingListApplication.code, AnnualAdmissionApplication.code]:
                            proposal.lodgement_date = datetime.datetime.now(pytz.timezone(TIME_ZONE))
                            proposal.log_user_action(ProposalUserAction.ACTION_LODGE_APPLICATION.format(proposal.id), request)

                            proposal.child_obj.send_emails_after_payment_success(request)
                            # ret1 = proposal.child_obj.send_emails_after_payment_success(request)
                            # if not ret1:
                            #     raise ValidationError('An error occurred while submitting proposal (Submit email notifications failed)')
                            proposal.save()

                        proposal.processing_status = Proposal.PROCESSING_STATUS_WITH_ASSESSOR
                        proposal.save()
                        logger.info(f'Processing status: [{Proposal.PROCESSING_STATUS_WITH_ASSESSOR}] has been set to the proposal: [{proposal}]')

                else:
                    # msg = 'Invoice: {} payment status is {}.  It should be either paid or over_paid'.format(invoice.reference, invoice.payment_status)
                    msg = 'Invoice: {} payment status is {}.  It should be either paid or over_paid'.format(invoice.reference, get_invoice_payment_status(invoice.id))
                    logger.error(msg)
                    raise Exception(msg)

                application_fee.save()
                # request.session[self.LAST_APPLICATION_FEE_ID] = application_fee.id
                # delete_session_application_invoice(request.session)
                #
                # wla_or_aaa = True if proposal.application_type.code in [WaitingListApplication.code, AnnualAdmissionApplication.code,] else False
                # context = {
                #     'proposal': proposal,
                #     'submitter': submitter,
                #     'fee_invoice': application_fee,
                #     'is_wla_or_aaa': wla_or_aaa,
                #     'invoice': invoice,
                # }
                # return render(request, self.template_name, context)

            logger.info(
                "Returning status.HTTP_200_OK. Order created successfully.",
            )
            # this end-point is called by an unmonitored get request in ledger so there is no point having a
            # a response body however we will return a status in case this is used on the ledger end in future
            # return Response(status=status.HTTP_204_NO_CONTENT)
            return Response(status=status.HTTP_200_OK)


class ApplicationFeeSuccessView(TemplateView):
    template_name = 'mooringlicensing/payments_ml/success_application_fee.html'
    LAST_APPLICATION_FEE_ID = 'mooringlicensing_last_app_invoice'

    def get(self, request, uuid, *args, **kwargs):
        logger.info(f'{ApplicationFeeSuccessView.__name__} get method is called.')

        try:
            application_fee = ApplicationFee.objects.get(uuid=uuid)
            proposal = application_fee.proposal
            submitter = proposal.submitter_obj
            if type(proposal.child_obj) in [WaitingListApplication, AnnualAdmissionApplication]:
                #proposal.auto_approve_check(request)
                if proposal.auto_approve:
                    proposal.final_approval_for_WLA_AAA(request, details={})

            wla_or_aaa = True if proposal.application_type.code in [WaitingListApplication.code, AnnualAdmissionApplication.code,] else False
            invoice = Invoice.objects.get(reference=application_fee.invoice_reference)
            invoice_url = f'/ledger-toolkit-api/invoice-pdf/{invoice.reference}/'
            context = {
                'proposal': proposal,
                'submitter': submitter,
                'fee_invoice': application_fee,
                'is_wla_or_aaa': wla_or_aaa,
                'invoice': invoice,
                'invoice_url': invoice_url,
            }
            return render(request, self.template_name, context)

        except Exception as e:
            # Should not reach here
            msg = 'Failed to process the payment. {}'.format(str(e))
            logger.error(msg)
            raise Exception(msg)


class DcvAdmissionPDFView(View):
    def get(self, request, *args, **kwargs):
        try:
            dcv_admission = get_object_or_404(DcvAdmission, id=self.kwargs['id'])
            response = HttpResponse(content_type='application/pdf')
            if dcv_admission.admissions.count() < 1:
                logger.warning('DcvAdmission: {} does not have any admission document.'.format(dcv_admission))
                return response
            elif dcv_admission.admissions.count() == 1:
                response.write(dcv_admission.admissions.first()._file.read())
                return response
            else:
                logger.warning('DcvAdmission: {} has more than one admissions.'.format(dcv_admission))
                return response
        except DcvAdmission.DoesNotExist:
            raise
        except Exception as e:
            logger.error('Error accessing the DcvAdmission :{}'.format(e))
            raise


class DcvPermitPDFView(View):
    def get(self, request, *args, **kwargs):
        try:
            dcv_permit = get_object_or_404(DcvPermit, id=self.kwargs['id'])
            response = HttpResponse(content_type='application/pdf')
            if dcv_permit.permits.count() < 1:
                logger.warning('DcvPermit: {} does not have any permit document.'.format(dcv_permit))
                return response
            elif dcv_permit.permits.count() == 1:
                response.write(dcv_permit.permits.first()._file.read())
                return response
            else:
                logger.warning('DcvPermit: {} has more than one permits.'.format(dcv_permit))
                return response
        except DcvPermit.DoesNotExist:
            raise
        except Exception as e:
            logger.error('Error accessing the DcvPermit :{}'.format(e))
            raise


class InvoicePDFView(View):
    def get(self, request, *args, **kwargs):
        raise Exception('Use ledger_api_utils.get_invoice_url() instead.')
        # try:
        #     invoice = get_object_or_404(Invoice, reference=self.kwargs['reference'])
        #
        #     response = HttpResponse(content_type='application/pdf')
        #     response.write(create_invoice_pdf_bytes('invoice.pdf', invoice,))
        #     return response
        # except Invoice.DoesNotExist:
        #     raise
        # except Exception as e:
        #     logger.error('Error accessing the Invoice :{}'.format(e))
        #     raise

    def get_object(self):
        return get_object_or_404(Invoice, reference=self.kwargs['reference'])


class RefundProposalHistoryView(LoginRequiredMixin, TemplateView):
#class RefundProposalHistory(LoginRequiredMixin, TemplateView):
    template_name = 'mooringlicensing/payments_ml/proposal_refund_history.html'

    def get(self, request, *args, **kwargs):
        booking_id = kwargs['pk']
        booking = None
        print ("LOADED")
        if request.user.is_superuser or request.user.groups.filter(name__in=['Mooring Licensing - Payment Officers']).exists():
#            booking = Proposal.objects.get(customer=request.user, booking_type__in=(0, 1), is_canceled=False, pk=booking_id)
             booking = Proposal.objects.get(pk=booking_id)
             newest_booking = booking_id #self.get_newest_booking(booking_id)
             booking_history = self.get_history(newest_booking, booking_array=[])
             invoice_line_items = self.get_history_line_items(booking_history)
             context = {
                'booking_id': booking_id,
                'booking': booking,
                'newest_booking': newest_booking,
                'booking_history' : booking_history,
                'invoice_line_items' : invoice_line_items,
                'oracle_code_refund_allocation_pool': settings.UNALLOCATED_ORACLE_CODE,
                'GIT_COMMIT_DATE' : settings.GIT_COMMIT_DATE,
                'GIT_COMMIT_HASH' : settings.GIT_COMMIT_HASH,
                'API_URL' : '/api/refund_oracle',
                'booking_class_type' : booking.__class__.__name__

             }
             return render(request, self.template_name,context)
        else:
             messages.error(self.request, 'Permission denied.')
             return HttpResponseRedirect(reverse('home')) 

    #def get_newest_booking(self, booking_id):
    #    latest_id = booking_id
    #    if Proposal.objects.filter(old_booking=booking_id).exclude(booking_type=3).count() > 0:
    #        booking = Proposal.objects.filter(old_booking=booking_id)[0]
    #        latest_id = self.get_newest_booking(booking.id)
    #    return latest_id

    def get_history_line_items(self, booking_history):

        invoice_line_items = []
        invoice_line_items_array = []
        invoice_bpoint = []
        rolling_total = Decimal('0.00')
        bpoint_trans_totals = {}
        unique_oracle_code_on_booking = {}
        total_booking_allocation_pool = Decimal('0.00')
        total_bpoint_amount_available = Decimal('0.00')
        entry_count = 0
        for bi in booking_history:
            booking = Proposal.objects.get(pk=bi['booking'].id)
            booking.invoices =()
            #booking.invoices = ApplicationFee.objects.filter(booking=booking)

            booking_invoices= ApplicationFee.objects.filter(proposal=booking)
            for i in booking_invoices:
                 bp = BpointTransaction.objects.filter(crn1=i.invoice_reference)
                 for trans in bp:
                     if trans.action == 'payment':
                            if trans.txn_number not in bpoint_trans_totals:
                                   bpoint_trans_totals[trans.txn_number] = {'crn1': '', 'amount': Decimal('0.00')}
                             
                            total_bpoint_amount_available = total_bpoint_amount_available + trans.amount
                            bpoint_trans_totals[trans.txn_number]['amount'] = bpoint_trans_totals[trans.txn_number]['amount'] + trans.amount 
                            bpoint_trans_totals[trans.txn_number]['crn1'] = trans.crn1
                     if trans.action == 'refund':
                            if trans.original_txn not in bpoint_trans_totals:
                                   bpoint_trans_totals[trans.original_txn] = {'crn': '', 'amount': Decimal('0.00')}
                            bpoint_trans_totals[trans.original_txn]['amount'] = bpoint_trans_totals[trans.original_txn]['amount'] - trans.amount
                            total_bpoint_amount_available = total_bpoint_amount_available - trans.amount
                     invoice_bpoint.append(trans)

                 iv = Invoice.objects.filter(reference=i.invoice_reference)
                 for b in iv:
                    o = Order.objects.get(number=b.order_number)
                    for ol in o.lines.all():
                        if ol.oracle_code == settings.UNALLOCATED_ORACLE_CODE:
                             total_booking_allocation_pool = total_booking_allocation_pool + ol.line_price_incl_tax
                        #rolling_total = rolling_total + ol.line_price_incl_tax
                        entry_count = entry_count + 1
                        invoice_line_items_array.append({'line_id': ol.id, 'order_number': ol.order.number, 'title': ol.title.replace(':','\n',1), 'oracle_code': ol.oracle_code, 'line_price_incl_tax': ol.line_price_incl_tax, 'order_date_placed': ol.order.date_placed, 'rolling_total': '0.00' ,'entry_count': entry_count })
                        invoice_line_items.append(ol)

                        if ol.oracle_code == settings.UNALLOCATED_ORACLE_CODE:
                             pass
                        else:
                             if ol.oracle_code not in unique_oracle_code_on_booking:
                                 unique_oracle_code_on_booking[ol.oracle_code] = Decimal('0.00') 

                             unique_oracle_code_on_booking[ol.oracle_code] = unique_oracle_code_on_booking[ol.oracle_code] + Decimal(ol.line_price_incl_tax)
#                             unique_oracle_code_on_booking[ol.oracle_code] = float("%.2f".format(str(unique_oracle_code_on_booking[ol.oracle_code])))
#                            unique_oracle_code_on_booking.append(ol.oracle_code)
        for ocb in unique_oracle_code_on_booking:
                unique_oracle_code_on_booking[ocb] = str(unique_oracle_code_on_booking[ocb])

        for btt in bpoint_trans_totals:
             bpoint_trans_totals[btt]['amount'] = str(bpoint_trans_totals[btt]['amount'])
        #UNALLOCATED_ORACLE_CODE

        invoice_line_items_array.sort(key=lambda item:item['order_date_placed'], reverse=False)
       
        for il in invoice_line_items_array:
            rolling_total = Decimal(rolling_total) + Decimal(il['line_price_incl_tax'])
            il['rolling_total'] = rolling_total
        
        booking_balance_issue = False
        if rolling_total < 0:
            booking_balance_issue = True

        return {'invoice_line_items': invoice_line_items, 'invoice_line_items_array':  invoice_line_items_array, 'booking_balance_issue': booking_balance_issue,'total_booking_allocation_pool': total_booking_allocation_pool, 'invoice_bpoint': invoice_bpoint,'total_bpoint_amount_available': total_bpoint_amount_available, 'unique_oracle_code_on_booking': json.dumps(unique_oracle_code_on_booking),'bpoint_trans_totals': json.dumps(bpoint_trans_totals)}

    def get_history(self, booking_id, booking_array=[]):
        booking = Proposal.objects.get(pk=booking_id)
        booking.invoices =()
        booking_invoices= ApplicationFee.objects.filter(proposal=booking)
        booking_array.append({'booking': booking, 'invoices': booking_invoices})
 
        #if booking.old_booking:
         #    self.get_history(booking.old_booking.id, booking_array)
        return booking_array

# include LoginRequiredMixin
class ProposalPaymentHistoryView(LoginRequiredMixin, TemplateView):
    template_name = 'mooringlicensing/payments_ml/proposal_payments_history.html'

    def get(self, request, *args, **kwargs):
        booking_id = kwargs['pk']
        booking = None

        if request.user.is_staff or request.user.is_superuser or Proposal.objects.filter(submitter=request.user,pk=booking_id).count() == 1:
             booking = Proposal.objects.get(pk=booking_id)
             #newest_booking = self.get_newest_booking(booking_id)
             newest_booking = booking_id
             booking_history = self.get_history(newest_booking, booking_array=[])
             #print vars(booking_history['bookings'])

        context = {
           'booking_id': booking_id,
           'booking': booking,
           'booking_history' : booking_history,
           'GIT_COMMIT_DATE' : settings.GIT_COMMIT_DATE,
           'GIT_COMMIT_HASH' : settings.GIT_COMMIT_HASH,
        }

        return render(request, self.template_name,context)

    #def get_newest_booking(self, booking_id):
    #    latest_id = booking_id
    #    if Booking.objects.filter(old_booking=booking_id).exclude(booking_type=3).count() > 0:
    #        booking = Booking.objects.filter(old_booking=booking_id)[0]   
    #        latest_id = self.get_newest_booking(booking.id)
    #    return latest_id

    def get_history(self, booking_id, booking_array=[]):
        booking = Proposal.objects.get(pk=booking_id)
        booking.invoices =()
        #booking.invoices = BookingInvoice.objects.filter(booking=booking)
        booking_invoices= ApplicationFee.objects.filter(proposal=booking) 
#        for bi in booking_invoices:
#            print bi
#            booking.invoices.add(bi)

        booking_array.append({'booking': booking, 'invoices': booking_invoices})
        #if booking.old_booking:
         #    self.get_history(booking.old_booking.id, booking_array)
        return booking_array

