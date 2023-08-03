import re
import pytz
from decimal import Decimal

from django.db import transaction
# from ledger.accounts.models import EmailUser
from ledger_api_client.ledger_models import EmailUserRO as EmailUser

from mooringlicensing import settings
import json
from mooringlicensing.components.main.utils import get_dot_vessel_information
from mooringlicensing.components.main.models import GlobalSettings, TemporaryDocumentCollection
from mooringlicensing.components.main.process_document import save_default_document_obj, save_vessel_registration_document_obj
from mooringlicensing.components.main.decorators import (
        basic_exception_handler, 
        timeit, 
        query_debugger
        )
from mooringlicensing.components.proposals.models import (
    WaitingListApplication,
    AnnualAdmissionApplication,
    AuthorisedUserApplication,
    MooringLicenceApplication,
    Vessel,
    VesselOwnership,
    Owner,
    Proposal,
    Company,
    CompanyOwnership,
    Mooring, ProposalApplicant, VesselRegistrationDocument
)
from mooringlicensing.components.proposals.serializers import (
    SaveVesselDetailsSerializer,
    SaveVesselOwnershipSerializer,
    SaveCompanyOwnershipSerializer,
    SaveDraftProposalVesselSerializer,
    #SaveProposalSerializer,
    SaveWaitingListApplicationSerializer,
    SaveMooringLicenceApplicationSerializer,
    SaveAuthorisedUserApplicationSerializer,
    SaveAnnualAdmissionApplicationSerializer,
    VesselSerializer,
    VesselOwnershipSerializer,
    VesselDetailsSerializer, CompanyOwnershipSerializer,
)

from mooringlicensing.components.approvals.models import (
    ApprovalHistory,
    MooringLicence,
    AnnualAdmissionPermit,
    WaitingListAllocation,
    AuthorisedUserPermit, Approval
)
from mooringlicensing.components.users.serializers import UserSerializer
from mooringlicensing.ledger_api_utils import get_invoice_payment_status
from mooringlicensing.settings import PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_RENEWAL, PROPOSAL_TYPE_NEW
import traceback
import os
from copy import deepcopy
from datetime import datetime
import time
from rest_framework import serializers

import logging
from django.db.models import Q


# logger = logging.getLogger('mooringlicensing')
logger = logging.getLogger(__name__)


def create_data_from_form(schema, post_data, file_data, post_data_index=None,special_fields=[],assessor_data=False):
    data = {}
    special_fields_list = []
    assessor_data_list = []
    comment_data_list = {}
    special_fields_search = SpecialFieldsSearch(special_fields)
    if assessor_data:
        assessor_fields_search = AssessorDataSearch()
        comment_fields_search = CommentDataSearch()
    try:
        for item in schema:
            data.update(_create_data_from_item(item, post_data, file_data, 0, ''))
            special_fields_search.extract_special_fields(item, post_data, file_data, 0, '')
            if assessor_data:
                assessor_fields_search.extract_special_fields(item, post_data, file_data, 0, '')
                comment_fields_search.extract_special_fields(item, post_data, file_data, 0, '')
        special_fields_list = special_fields_search.special_fields
        if assessor_data:
            assessor_data_list = assessor_fields_search.assessor_data
            comment_data_list = comment_fields_search.comment_data
    except:
        traceback.print_exc()
    if assessor_data:
        return [data],special_fields_list,assessor_data_list,comment_data_list

    return [data],special_fields_list


def _extend_item_name(name, suffix, repetition):
    return '{}{}-{}'.format(name, suffix, repetition)

def _create_data_from_item(item, post_data, file_data, repetition, suffix):
    item_data = {}

    if 'name' in item:
        extended_item_name = item['name']
    else:
        raise Exception('Missing name in item %s' % item['label'])

    if 'children' not in item:
        if item['type'] in ['checkbox' 'declaration']:
            item_data[item['name']] = extended_item_name in post_data
        elif item['type'] == 'file':
            if extended_item_name in file_data:
                item_data[item['name']] = str(file_data.get(extended_item_name))
                # TODO save the file here
            elif extended_item_name + '-existing' in post_data and len(post_data[extended_item_name + '-existing']) > 0:
                item_data[item['name']] = post_data.get(extended_item_name + '-existing')
            else:
                item_data[item['name']] = ''
        else:
            if extended_item_name in post_data:
                if item['type'] == 'multi-select':
                    item_data[item['name']] = post_data.getlist(extended_item_name)
                else:
                    item_data[item['name']] = post_data.get(extended_item_name)
    else:
        if 'repetition' in item:
            item_data = generate_item_data(extended_item_name,item,item_data,post_data,file_data,len(post_data[item['name']]),suffix)
        else:
            item_data = generate_item_data(extended_item_name, item, item_data, post_data, file_data,1,suffix)


    if 'conditions' in item:
        for condition in item['conditions'].keys():
            for child in item['conditions'][condition]:
                item_data.update(_create_data_from_item(child, post_data, file_data, repetition, suffix))

    return item_data

def generate_item_data(item_name,item,item_data,post_data,file_data,repetition,suffix):
    item_data_list = []
    for rep in xrange(0, repetition):
        child_data = {}
        for child_item in item.get('children'):
            child_data.update(_create_data_from_item(child_item, post_data, file_data, 0,
                                                     '{}-{}'.format(suffix, rep)))
        item_data_list.append(child_data)

        item_data[item['name']] = item_data_list
    return item_data

class AssessorDataSearch(object):

    def __init__(self,lookup_field='canBeEditedByAssessor'):
        self.lookup_field = lookup_field
        self.assessor_data = []

    def extract_assessor_data(self,item,post_data):
        values = []
        res = {
            'name': item,
            'assessor': '',
            'referrals':[]
        }
        for k in post_data:
            if re.match(item,k):
                values.append({k:post_data[k]})
        if values:
            for v in values:
                for k,v in v.items():
                    parts = k.split('{}-'.format(item))
                    if len(parts) > 1:
                        # split parts to see if referall
                        ref_parts = parts[1].split('Referral-')
                        if len(ref_parts) > 1:
                            # Referrals
                            res['referrals'].append({
                                'value':v,
                                'email':ref_parts[1],
                                'full_name': EmailUser.objects.get(email=ref_parts[1].lower()).get_full_name()
                            })
                        elif k.split('-')[-1].lower() == 'assessor':
                            # Assessor
                            res['assessor'] = v

        return res

    def extract_special_fields(self,item, post_data, file_data, repetition, suffix):
        item_data = {}
        if 'name' in item:
            extended_item_name = item['name']
        else:
            raise Exception('Missing name in item %s' % item['label'])

        if 'children' not in item:
            if 'conditions' in item:
                for condition in item['conditions'].keys():
                    for child in item['conditions'][condition]:
                        item_data.update(self.extract_special_fields(child, post_data, file_data, repetition, suffix))

            if item.get(self.lookup_field):
                self.assessor_data.append(self.extract_assessor_data(extended_item_name,post_data))

        else:
            if 'repetition' in item:
                item_data = self.generate_item_data_special_field(extended_item_name,item,item_data,post_data,file_data,len(post_data[item['name']]),suffix)
            else:
                item_data = self.generate_item_data_special_field(extended_item_name, item, item_data, post_data, file_data,1,suffix)

            if 'conditions' in item:
                for condition in item['conditions'].keys():
                    for child in item['conditions'][condition]:
                        item_data.update(self.extract_special_fields(child, post_data, file_data, repetition, suffix))

        return item_data

    def generate_item_data_special_field(self,item_name,item,item_data,post_data,file_data,repetition,suffix):
        item_data_list = []
        for rep in xrange(0, repetition):
            child_data = {}
            for child_item in item.get('children'):
                child_data.update(self.extract_special_fields(child_item, post_data, file_data, 0,
                                                         '{}-{}'.format(suffix, rep)))
            item_data_list.append(child_data)

            item_data[item['name']] = item_data_list
        return item_data

class CommentDataSearch(object):

    def __init__(self,lookup_field='canBeEditedByAssessor'):
        self.lookup_field = lookup_field
        self.comment_data = {}

    def extract_comment_data(self,item,post_data):
        res = {}
        values = []
        for k in post_data:
            if re.match(item,k):
                values.append({k:post_data[k]})
        if values:
            for v in values:
                for k,v in v.items():
                    parts = k.split('{}'.format(item))
                    if len(parts) > 1:
                        ref_parts = parts[1].split('-comment-field')
                        if len(ref_parts) > 1:
                            res = {'{}'.format(item):v}
        return res

    def extract_special_fields(self,item, post_data, file_data, repetition, suffix):
        item_data = {}
        if 'name' in item:
            extended_item_name = item['name']
        else:
            raise Exception('Missing name in item %s' % item['label'])

        if 'children' not in item:
            self.comment_data.update(self.extract_comment_data(extended_item_name,post_data))

        else:
            if 'repetition' in item:
                item_data = self.generate_item_data_special_field(extended_item_name,item,item_data,post_data,file_data,len(post_data[item['name']]),suffix)
            else:
                item_data = self.generate_item_data_special_field(extended_item_name, item, item_data, post_data, file_data,1,suffix)


        if 'conditions' in item:
            for condition in item['conditions'].keys():
                for child in item['conditions'][condition]:
                    item_data.update(self.extract_special_fields(child, post_data, file_data, repetition, suffix))

        return item_data

    def generate_item_data_special_field(self,item_name,item,item_data,post_data,file_data,repetition,suffix):
        item_data_list = []
        for rep in xrange(0, repetition):
            child_data = {}
            for child_item in item.get('children'):
                child_data.update(self.extract_special_fields(child_item, post_data, file_data, 0,
                                                         '{}-{}'.format(suffix, rep)))
            item_data_list.append(child_data)

            item_data[item['name']] = item_data_list
        return item_data

class SpecialFieldsSearch(object):

    def __init__(self,lookable_fields):
        self.lookable_fields = lookable_fields
        self.special_fields = {}

    def extract_special_fields(self,item, post_data, file_data, repetition, suffix):
        item_data = {}
        if 'name' in item:
            extended_item_name = item['name']
        else:
            raise Exception('Missing name in item %s' % item['label'])

        if 'children' not in item:
            for f in self.lookable_fields:
                if item['type'] in ['checkbox' 'declaration']:
                    val = None
                    val = item.get(f,None)
                    if val:
                        item_data[f] = extended_item_name in post_data
                        self.special_fields.update(item_data)
                else:
                    if extended_item_name in post_data:
                        val = None
                        val = item.get(f,None)
                        if val:
                            if item['type'] == 'multi-select':
                                item_data[f] = ','.join(post_data.getlist(extended_item_name))
                            else:
                                item_data[f] = post_data.get(extended_item_name)
                            self.special_fields.update(item_data)
        else:
            if 'repetition' in item:
                item_data = self.generate_item_data_special_field(extended_item_name,item,item_data,post_data,file_data,len(post_data[item['name']]),suffix)
            else:
                item_data = self.generate_item_data_special_field(extended_item_name, item, item_data, post_data, file_data,1,suffix)


        if 'conditions' in item:
            for condition in item['conditions'].keys():
                for child in item['conditions'][condition]:
                    item_data.update(self.extract_special_fields(child, post_data, file_data, repetition, suffix))

        return item_data

    def generate_item_data_special_field(self,item_name,item,item_data,post_data,file_data,repetition,suffix):
        item_data_list = []
        for rep in xrange(0, repetition):
            child_data = {}
            for child_item in item.get('children'):
                child_data.update(self.extract_special_fields(child_item, post_data, file_data, 0,
                                                         '{}-{}'.format(suffix, rep)))
            item_data_list.append(child_data)

            item_data[item['name']] = item_data_list
        return item_data

def save_proponent_data(instance, request, viewset):
    if viewset.action == 'submit':
        logger.info('Proposal {} has been submitted'.format(instance.lodgement_number))
    if type(instance.child_obj) == WaitingListApplication:
        save_proponent_data_wla(instance, request, viewset)
    elif type(instance.child_obj) == AnnualAdmissionApplication:
        save_proponent_data_aaa(instance, request, viewset)
    elif type(instance.child_obj) == AuthorisedUserApplication:
        save_proponent_data_aua(instance, request, viewset)
    elif type(instance.child_obj) == MooringLicenceApplication:
        save_proponent_data_mla(instance, request, viewset)

    # Save request.user details in a JSONField not to overwrite the details of it.
    serializer = UserSerializer(request.user, context={'request':request})
    if instance:
        instance.personal_details = serializer.data
        instance.save()


def save_proponent_data_aaa(instance, request, viewset):
    print(request.data)
    # vessel
    vessel_data = deepcopy(request.data.get("vessel"))
    if vessel_data:
        if viewset.action == 'submit':
            submit_vessel_data(instance, request, vessel_data)
        elif instance.processing_status == 'draft':
            save_vessel_data(instance, request, vessel_data)
    # proposal
    proposal_data = request.data.get('proposal') if request.data.get('proposal') else {}
    serializer = SaveAnnualAdmissionApplicationSerializer(
            instance, 
            data=proposal_data, 
            context={
                "action": viewset.action,
                "proposal_id": instance.id
                #"ignore_insurance_check": request.data.get("ignore_insurance_check")
                }
    )
    serializer.is_valid(raise_exception=True)
    instance = serializer.save()
    logger.info(f'Update the Proposal: [{instance}] with the data: [{proposal_data}].')

    if viewset.action == 'submit':
        # if instance.invoice and instance.invoice.payment_status in ['paid', 'over_paid']:
        if instance.invoice and get_invoice_payment_status(instance.id) in ['paid', 'over_paid']:
            # Save + Submit + Paid ==> We have to update the status
            # Probably this is the case that assessor put back this application to external and then external submit this.
            logger.info('Proposal {} has been submitted but already paid.  Update the status of it to {}'.format(instance.lodgement_number, Proposal.PROCESSING_STATUS_WITH_ASSESSOR))
            instance.processing_status = Proposal.PROCESSING_STATUS_WITH_ASSESSOR
            instance.save()


def save_proponent_data_wla(instance, request, viewset):
    print(request.data)
    # vessel
    vessel_data = deepcopy(request.data.get("vessel"))
    if vessel_data:
        if viewset.action == 'submit':
            submit_vessel_data(instance, request, vessel_data)
        elif instance.processing_status == 'draft':
            save_vessel_data(instance, request, vessel_data)
    # proposal
    proposal_data = request.data.get('proposal') if request.data.get('proposal') else {}
    serializer = SaveWaitingListApplicationSerializer(
            instance, 
            data=proposal_data, 
            context={
                "action": viewset.action,
                "proposal_id": instance.id
                }
    )
    serializer.is_valid(raise_exception=True)
    instance = serializer.save()
    logger.info(f'Update the Proposal: [{instance}] with the data: [{proposal_data}].')

    if viewset.action == 'submit':
        # if instance.invoice and instance.invoice.payment_status in ['paid', 'over_paid']:
        if instance.invoice and get_invoice_payment_status(instance.invoice.id) in ['paid', 'over_paid']:
            # Save + Submit + Paid ==> We have to update the status
            # Probably this is the case that assessor put back this application to external and then external submit this.
            logger.info('Proposal {} has been submitted but already paid.  Update the status of it to {}'.format(instance.lodgement_number, Proposal.PROCESSING_STATUS_WITH_ASSESSOR))
            instance.processing_status = Proposal.PROCESSING_STATUS_WITH_ASSESSOR
            instance.save()


def save_proponent_data_mla(instance, request, viewset):
    print(request.data)
    # vessel
    vessel_data = deepcopy(request.data.get("vessel"))
    if vessel_data:
        if viewset.action == 'submit':
            submit_vessel_data(instance, request, vessel_data)
        elif instance.processing_status == 'draft':
            save_vessel_data(instance, request, vessel_data)
    # proposal
    proposal_data = request.data.get('proposal') if request.data.get('proposal') else {}
    serializer = SaveMooringLicenceApplicationSerializer(
            instance, 
            data=proposal_data, 
            context={
                "action": viewset.action,
                "proposal_id": instance.id
                #"ignore_insurance_check":request.data.get("ignore_insurance_check")
                }
    )
    serializer.is_valid(raise_exception=True)
    #instance = serializer.save()
    serializer.save()
    logger.info(f'Update the Proposal: [{instance}] with the data: [{proposal_data}].')

    if viewset.action == 'submit':
        instance.child_obj.process_after_submit(request)
        instance.refresh_from_db()


def save_proponent_data_aua(instance, request, viewset):
    print(request.data)
    # vessel
    vessel_data = deepcopy(request.data.get("vessel"))
    if vessel_data:
        if viewset.action == 'submit':
            submit_vessel_data(instance, request, vessel_data)
        elif instance.processing_status == Proposal.PROCESSING_STATUS_DRAFT:
            save_vessel_data(instance, request, vessel_data)
    # proposal
    proposal_data = request.data.get('proposal') if request.data.get('proposal') else {}
    serializer = SaveAuthorisedUserApplicationSerializer(
            instance, 
            data=proposal_data, 
            context={
                "action": viewset.action,
                "proposal_id": instance.id
                #"ignore_insurance_check":request.data.get("ignore_insurance_check")
                }
    )
    serializer.is_valid(raise_exception=True)
    #instance = serializer.save()
    serializer.save()
    logger.info(f'Update the Proposal: [{instance}] with the data: [{proposal_data}].')

    if viewset.action == 'submit':
        instance.child_obj.process_after_submit(request)
        instance.refresh_from_db()


# draft and submit
def save_vessel_data(instance, request, vessel_data):
    logger.info(f'save_vessel_data is called with the vessel_data: {vessel_data}')

    vessel_details_data = {}
    vessel_id = vessel_data.get('id')
    vessel_details_data = vessel_data.get("vessel_details")

    # update vessel details to vessel_data
    for key in vessel_details_data.keys():
        vessel_data.update({key: vessel_details_data.get(key)})
    if vessel_id:
        vessel_data.update({"vessel_id": vessel_id})

    vessel_ownership_data = vessel_data.get("vessel_ownership")
    if vessel_ownership_data.get('company_ownership'):
        company_ownership_percentage = vessel_ownership_data.get('company_ownership', {}).get('percentage')
        company_ownership_name = vessel_ownership_data.get('company_ownership', {}).get('company', {}).get('name')
        vessel_data.update({"company_ownership_percentage": company_ownership_percentage})
        vessel_data.update({"company_ownership_name": company_ownership_name})
    if 'company_ownership' in vessel_ownership_data.keys():
        vessel_ownership_data.pop('company_ownership', None)

    # copy VesselOwnership fields to vessel_data
    for key in vessel_ownership_data.keys():
        vessel_data.update({key: vessel_ownership_data.get(key)})

    # overwrite vessel_data.id with correct value
    if type(instance.child_obj) == MooringLicenceApplication and vessel_data.get('readonly'):
        # do not write vessel_data to proposal
        pass
    else:
        serializer = SaveDraftProposalVesselSerializer(instance, vessel_data)
        serializer.is_valid(raise_exception=True)
        print(serializer.validated_data)
        serializer.save()
        logger.info(f'Proposal: [{instance}] has been updated with the vessel data: [{vessel_data}]')

def dot_check_wrapper(request, payload, vessel_lookup_errors, vessel_data):
    json_string = json.dumps(payload)
    dot_response_str = get_dot_vessel_information(request, json_string)
    try:
        dot_response_json = json.loads(dot_response_str)
    except Exception as e:
        raise serializers.ValidationError("Cannot load as JSON: {}".format(dot_response_str))
    logger.info("dot_response_json")
    logger.info(dot_response_json)
    logger.info(dot_response_json.get("status"))
    if dot_response_json.get("status") and not dot_response_json.get("status") == 200:
        raise serializers.ValidationError("DoT Service Unavailable")
    dot_response = dot_response_json.get("data")
    dot_boat_length = dot_response.get("boatLength")
    boat_found = True if dot_response.get("boatFound") == "Y" else False
    boat_owner_match = True if dot_response.get("boatOwnerMatch") else False
    ml_boat_length = vessel_data.get("vessel_details", {}).get("vessel_length")
    if not boat_found or not boat_owner_match or not dot_boat_length == float(ml_boat_length):
        vessel_lookup_errors[vessel_data.get("rego_no")] = "The provided details do not match those recorded with the Department of Transport"

#def delete_draft_vessel_data(instance):
#    instance.rego_no = ''
#    instance.vessel_id = None
#    instance.vessel_type = ''
#    instance.vessel_name = ''
#    instance.vessel_length = '0.00'
#    instance.vessel_draft = '0.00'
#    instance.vessel_beam = '0.00'
#    instance.vessel_weight = '0.00'
#    instance.berth_mooring = ''
#    instance.percentage = None
#    instance.individual_owner = None
#    instance.company_ownership_percentage = None
#    instance.company_ownership_name = ''
#    instance.dot_name = ''
#    instance.temporary_document_collection_id = None
#    instance.save()

def submit_vessel_data(instance, request, vessel_data):
    logger.info(f'submit_vessel_data() is called with the vessel_data: {vessel_data}')

    # Dot vessel rego lookup
    if settings.DO_DOT_CHECK:
        logger.info('Performing DoT check...')
        vessel_lookup_errors = {}
        # Mooring Licence vessel history
        if type(instance.child_obj) == MooringLicenceApplication and instance.approval:
            for vo in instance.approval.child_obj.vessel_ownership_list:
                dot_name = vo.dot_name
                owner_str = dot_name.replace(" ", "%20")
                payload = {
                        "boatRegistrationNumber": vo.vessel.rego_no,
                        "owner": owner_str,
                        "userId": str(request.user.id)
                        }
                dot_check_wrapper(request, payload, vessel_lookup_errors, vessel_data)

        # current proposal vessel check
        if vessel_data.get("rego_no"):
            dot_name = vessel_data.get("vessel_ownership", {}).get("dot_name", "")
            owner_str = dot_name.replace(" ", "%20")
            payload = {
                    "boatRegistrationNumber": vessel_data.get("rego_no"),
                    "owner": owner_str,
                    "userId": str(request.user.id)
                    }
            dot_check_wrapper(request, payload, vessel_lookup_errors, vessel_data)

        if vessel_lookup_errors:
            raise serializers.ValidationError(vessel_lookup_errors)

    min_vessel_size_str = GlobalSettings.objects.get(key=GlobalSettings.KEY_MINIMUM_VESSEL_LENGTH).value
    min_mooring_vessel_size_str = GlobalSettings.objects.get(key=GlobalSettings.KEY_MINUMUM_MOORING_VESSEL_LENGTH).value
    min_vessel_size = float(min_vessel_size_str)
    min_mooring_vessel_size = float(min_mooring_vessel_size_str)

    #if (not vessel_data.get('rego_no') and instance.proposal_type.code in [PROPOSAL_TYPE_RENEWAL, PROPOSAL_TYPE_AMENDMENT] and
     #       type(instance.child_obj) in [WaitingListApplication, MooringLicenceApplication, AnnualAdmissionApplication]):
      #  return
    if not vessel_data.get('rego_no'):
        if instance.proposal_type.code in [PROPOSAL_TYPE_RENEWAL, PROPOSAL_TYPE_AMENDMENT,]:
            if type(instance.child_obj) in [MooringLicenceApplication, WaitingListApplication,]:
                return
        else:
            raise serializers.ValidationError("Application cannot be submitted without a vessel listed")

    ## save vessel data into proposal first
    save_vessel_data(instance, request, vessel_data)
    vessel, vessel_details = store_vessel_data(request, vessel_data)

    # associate vessel_details with proposal
    instance.vessel_details = vessel_details
    instance.save()

    ## vessel min length requirements - cannot use serializer validation due to @property vessel_applicable_length
    if type(instance.child_obj) == AnnualAdmissionApplication:
        if instance.vessel_details.vessel_applicable_length < min_vessel_size:
            logger.error("Proposal {}: Vessel must be at least {}m in length".format(instance, min_vessel_size_str))
            raise serializers.ValidationError("Vessel must be at least {}m in length".format(min_vessel_size_str))
    elif type(instance.child_obj) == AuthorisedUserApplication:
        if instance.vessel_details.vessel_applicable_length < min_vessel_size:
            logger.error("Proposal {}: Vessel must be at least {}m in length".format(instance, min_vessel_size_str))
            raise serializers.ValidationError("Vessel must be at least {}m in length".format(min_vessel_size_str))
        # check new site licensee mooring
        proposal_data = request.data.get('proposal') if request.data.get('proposal') else {}
        mooring_id = proposal_data.get('mooring_id')
        if mooring_id and proposal_data.get('site_licensee_email'):
            mooring = Mooring.objects.get(id=mooring_id)
            if (instance.vessel_details.vessel_applicable_length > mooring.vessel_size_limit or
            instance.vessel_details.vessel_draft > mooring.vessel_draft_limit):
                logger.error("Proposal {}: Vessel unsuitable for mooring".format(instance))
                raise serializers.ValidationError("Vessel unsuitable for mooring")
        ## amend / renewal
        #if instance.approval:
        #    # check existing moorings against current vessel dimensions
        #    for moa in instance.approval.mooringonapproval_set.filter(end_date__isnull=True):
        #        mooring = Mooring.objects.get(id=moa.mooring_id)
        #        if (instance.vessel_details.vessel_applicable_length > mooring.vessel_size_limit or
        #        instance.vessel_details.vessel_draft > mooring.vessel_draft_limit):
        #            logger.error("Proposal {}: Vessel unsuitable for one or more moorings".format(instance))
        #            raise serializers.ValidationError("Vessel unsuitable for one or more moorings")

    elif type(instance.child_obj) == WaitingListApplication:
        if instance.vessel_details.vessel_applicable_length < min_mooring_vessel_size:
            logger.error("Proposal {}: Vessel must be at least {}m in length".format(instance, min_mooring_vessel_size_str))
            raise serializers.ValidationError("Vessel must be at least {}m in length".format(min_mooring_vessel_size_str))
    else:
        ## Mooring Licence Application
        if instance.proposal_type.code in [PROPOSAL_TYPE_RENEWAL, PROPOSAL_TYPE_AMENDMENT] and instance.vessel_details.vessel_applicable_length < min_vessel_size:
            logger.error("Proposal {}: Vessel must be at least {}m in length".format(instance, min_vessel_size_str))
            raise serializers.ValidationError("Vessel must be at least {}m in length".format(min_vessel_size_str))
        elif instance.vessel_details.vessel_applicable_length < min_mooring_vessel_size:
            logger.error("Proposal {}: Vessel must be at least {}m in length".format(instance, min_mooring_vessel_size_str))
            raise serializers.ValidationError("Vessel must be at least {}m in length".format(min_mooring_vessel_size_str))
        elif instance.proposal_type.code in [PROPOSAL_TYPE_RENEWAL, PROPOSAL_TYPE_AMENDMENT] and (
                instance.vessel_details.vessel_applicable_length > instance.approval.child_obj.mooring.vessel_size_limit or
                instance.vessel_details.vessel_draft > instance.approval.child_obj.mooring.vessel_draft_limit
                ):
            logger.error("Proposal {}: Vessel unsuitable for mooring".format(instance))
            raise serializers.ValidationError("Vessel unsuitable for mooring")

    # record ownership data
    vessel_ownership = store_vessel_ownership(request, vessel, instance)

    # associate vessel_ownership with proposal
    instance.vessel_ownership = vessel_ownership
    instance.save()

    association_fail = False
    proposals = [proposal.child_obj for proposal in Proposal.objects.filter(vessel_details__vessel=vessel).exclude(id=instance.id)]
    proposals_wla = []
    proposals_mla = []
    proposals_aaa = []
    proposals_aua = []
    # 20220311 - add exclusion for amendment applications
    approvals = [ah.approval for ah in ApprovalHistory.objects.filter(end_date=None, vessel_ownership__vessel=vessel).exclude(approval_id=instance.approval_id)]
    approvals = list(dict.fromkeys(approvals))  # remove duplicates
    approvals_wla = []
    approvals_ml = []
    approvals_ml_sus = []
    approvals_aap = []
    approvals_aup = []
    approvals_aup_sus = []
    for proposal in proposals:
        # if type(proposal) == WaitingListApplication and proposal.processing_status not in ['approved', 'declined', 'discarded']:
        if proposal.processing_status not in [Proposal.PROCESSING_STATUS_APPROVED, Proposal.PROCESSING_STATUS_DECLINED, Proposal.PROCESSING_STATUS_DISCARDED,]:
            if type(proposal) == WaitingListApplication:
                proposals_wla.append(proposal)
            if type(proposal) == MooringLicenceApplication:
                proposals_mla.append(proposal)
            if type(proposal) == AnnualAdmissionApplication:
                proposals_aaa.append(proposal)
            if type(proposal) == AuthorisedUserApplication:
                proposals_aua.append(proposal)
    for approval in approvals:
        if approval.status in settings.APPROVED_APPROVAL_STATUS:
            if type(approval.child_obj) == WaitingListAllocation:
                approvals_wla.append(approval)
            if type(approval.child_obj) == MooringLicence:
                approvals_ml.append(approval)
            if type(approval.child_obj) == AnnualAdmissionPermit:
                approvals_aap.append(approval)
            if type(approval.child_obj) == AuthorisedUserPermit:
                approvals_aup.append(approval)

    wl_applications = WaitingListApplication.get_intermediate_proposals(instance.submitter).exclude(id=instance.id)
    wl_allocations = WaitingListAllocation.get_intermediate_approvals(instance.submitter).exclude(approval=instance.approval)
    ml_applications = MooringLicenceApplication.get_intermediate_proposals(instance.submitter)
    ml_approvals = MooringLicence.get_valid_approvals(instance.submitter)

    # apply rules
    if type(instance.child_obj) == WaitingListApplication and (proposals_wla or approvals_wla or proposals_mla or approvals_ml):
        raise serializers.ValidationError("The vessel in the application is already listed in " +
        ", ".join(['{} {} '.format(proposal.description, proposal.lodgement_number) for proposal in proposals_wla]) +
        ", ".join(['{} {} '.format(approval.description, approval.lodgement_number) for approval in approvals_wla])
        )
    # Person can have only one WLA, Waiting Liast application, Mooring Licence and Mooring Licence application
    elif (type(instance.child_obj) == WaitingListApplication and (
            WaitingListApplication.get_intermediate_proposals(instance.submitter).exclude(id=instance.id) or
            WaitingListAllocation.get_intermediate_approvals(instance.submitter).exclude(approval=instance.approval) or
            MooringLicenceApplication.get_intermediate_proposals(instance.submitter) or
            MooringLicence.get_valid_approvals(instance.submitter))
        ):
        raise serializers.ValidationError("Person can have only one WLA, Waiting List application, Mooring Site Licence and Mooring Site Licence application")
    elif (type(instance.child_obj) == AnnualAdmissionApplication and (proposals_aaa or approvals_aap or
            proposals_aua or approvals_aup or proposals_mla or approvals_ml)):
        list_sum = proposals_aaa + proposals_aua + proposals_mla + approvals_aap + approvals_aup + approvals_ml
        raise serializers.ValidationError("The vessel in the application is already listed in " +
        ", ".join(['{} {} '.format(item.description, item.lodgement_number) for item in list_sum]))
    elif type(instance.child_obj) == AuthorisedUserApplication and (proposals_aua or approvals_aup):
        #association_fail = True
        raise serializers.ValidationError("The vessel in the application is already listed in " +  
        ", ".join(['{} {} '.format(proposal.description, proposal.lodgement_number) for proposal in proposals_aua]) +
        ", ".join(['{} {} '.format(approval.description, approval.lodgement_number) for approval in approvals_aup])
        )
    elif type(instance.child_obj) == MooringLicenceApplication and (proposals_mla or approvals_ml):
        #association_fail = True
        raise serializers.ValidationError("The vessel in the application is already listed in " +  
        ", ".join(['{} {} '.format(proposal.description, proposal.lodgement_number) for proposal in proposals_mla]) +
        ", ".join(['{} {} '.format(approval.description, approval.lodgement_number) for approval in approvals_ml])
        )
    #if association_fail:
     #   raise serializers.ValidationError("This vessel is already part of another application/permit/licence")

    ## vessel ownership cannot be greater than 100%
    ownership_percentage_validation(vessel_ownership, instance)
    #delete_draft_vessel_data(instance)

def store_vessel_data(request, vessel_data):
    logger.info(f'store_vessel_data() is called with the vessel_data: {vessel_data}')

    if not vessel_data.get('rego_no'):
        raise serializers.ValidationError({"Missing information": "You must supply a Vessel Registration Number"})
    rego_no = vessel_data.get('rego_no').replace(" ", "").strip().lower() # successfully avoiding dupes?
    vessel, created = Vessel.objects.get_or_create(rego_no=rego_no)
    if created:
        logger.info(f'New Vessel: [{vessel}] has been created.')
    
    vessel_details_data = vessel_data.get("vessel_details")
    # add vessel to vessel_details_data
    vessel_details_data["vessel"] = vessel.id

    ## Vessel Details
    existing_vessel_details = vessel.latest_vessel_details
    ## we no longer use a read_only flag, so must compare incoming data to existing
    existing_vessel_details_data = VesselDetailsSerializer(existing_vessel_details).data
    #print(existing_vessel_details_data.keys())
    create_vessel_details = False
    for key in existing_vessel_details_data.keys():
        if key in vessel_details_data and existing_vessel_details_data[key] != vessel_details_data[key]:
            # Value is different between the existing and new --> We create new vessel details rather than updating the existing
            create_vessel_details = True
            break

    if create_vessel_details:
        serializer = SaveVesselDetailsSerializer(data=vessel_details_data)
        serializer.is_valid(raise_exception=True)
        vessel_details = serializer.save()
        logger.info(f'New VesselDetails: [{vessel_details}] has been created.')
    else:
        serializer = SaveVesselDetailsSerializer(existing_vessel_details, vessel_details_data)
        serializer.is_valid(raise_exception=True)
        vessel_details = serializer.save()
        logger.info(f'VesselDetails: [{vessel_details}] has been updated.')

    return vessel, vessel_details

def store_vessel_ownership(request, vessel, instance=None):
    logger.info(f'Storing vessel_ownership with the vessel: [{vessel}], proposal: [{instance}] ...')

    ## Get Vessel
    ## we cannot use vessel_data, because this dict has been modified in store_vessel_data()
    vessel_ownership_data = deepcopy(request.data.get('vessel').get("vessel_ownership"))
    if vessel_ownership_data.get('individual_owner') is None:
        raise serializers.ValidationError({"Missing information": "You must select a Vessel Owner"})
    elif (not vessel_ownership_data.get('individual_owner') and not 
            vessel_ownership_data.get("company_ownership", {}).get("company", {}).get("name")
            ):
        raise serializers.ValidationError({"Missing information": "You must supply the company name"})

    individual_owner = vessel_ownership_data.get('individual_owner')

    company_ownership = None
    if individual_owner:
        # This proposal is for individual owner
        logger.info(f'This proposal: [{instance}] is for individual owner.')
    else:
        # This proposal is for company owner
        logger.info(f'This proposal: [{instance}] is for company owner.')

        company_name = vessel_ownership_data.get("company_ownership").get("company").get("name")
        company, created = Company.objects.get_or_create(name=company_name)
        if created:
            logger.info(f'New Company: [{company}] has been created.')

        ## CompanyOwnership
        company_ownership_data = vessel_ownership_data.get("company_ownership")
        company_ownership_set = CompanyOwnership.objects.filter(
            company=company,
            vessel=vessel,
        )

        # Check if we need to create a new CO record
        create_company_ownership = False
        edit_company_ownership = True
        if company_ownership_set.filter(status="draft"):
            company_ownership = company_ownership_set.filter(status="draft")[0]
            ## cannot edit draft record with blocking_proposal
            if company_ownership.blocking_proposal:
                edit_company_ownership = False
        elif company_ownership_set.filter(status="approved"):
            company_ownership = company_ownership_set.filter(status="approved")[0]
            existing_company_ownership_data = CompanyOwnershipSerializer(company_ownership).data
            for key in existing_company_ownership_data.keys():
                if key in company_ownership_data and existing_company_ownership_data[key] != company_ownership_data[key]:
                    # At least one field has a different value.
                    create_company_ownership = True
        else:
            create_company_ownership = True

        # update company key from dict to pk
        company_ownership_data.update({"company": company.id})

        # add vessel to company_ownership_data
        company_ownership_data.update({"vessel": vessel.id})

        if create_company_ownership:
            serializer = SaveCompanyOwnershipSerializer(data=company_ownership_data)
            serializer.is_valid(raise_exception=True)
            company_ownership = serializer.save()

            logger.info(f'New CompanyOwnership: [{company_ownership}] has been created')

        elif edit_company_ownership:
            serializer = SaveCompanyOwnershipSerializer(company_ownership, company_ownership_data)
            serializer.is_valid(raise_exception=True)
            company_ownership = serializer.save()

            logger.info(f'CompanyOwnership: [{company_ownership}] has been updated')

    ## add to vessel_ownership_data
    if company_ownership and company_ownership.id:
        vessel_ownership_data['company_ownership'] = company_ownership.id
        if instance:
            ## set blocking_proposal
            company_ownership.blocking_proposal = instance
            company_ownership.save()

            logger.info(f'BlockingProposal: [{instance.lodgement_number}] has been set to the CompanyOwnership: [{company_ownership}]')
    else:
        vessel_ownership_data['company_ownership'] = None
    vessel_ownership_data['vessel'] = vessel.id

    owner, created = Owner.objects.get_or_create(emailuser=request.user.id)  # Is owner accessing user...??? Correct???
    if created:
        logger.info(f'New Owner: [{owner}] has been created.')
    else:
        logger.info(f'Existing Owner: [{owner}] has been retrieved.')

    vessel_ownership_data['owner'] = owner.id

    # Create/Retrieve vessel_ownership
    vo_created = False
    q_for_approvals_check = Q()  # We want to check if there is a current approval which links to the vessel_ownership retrieved below
    if instance.proposal_type.code in [PROPOSAL_TYPE_NEW,]:
        vessel_ownership, vo_created = VesselOwnership.objects.get_or_create(
            owner=owner,  # Owner is actually the accessing user (request.user) as above.
            vessel=vessel,
            company_ownership=company_ownership
        )
    elif instance.proposal_type.code in [PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_RENEWAL,]:
        # Retrieve a vessel_ownership from the previous proposal
        vessel_ownership = instance.previous_application.vessel_ownership

        vessel_ownership_to_be_created = False
        if vessel_ownership.end_date:
            logger.info(f'Existing VesselOwnership: [{vessel_ownership}] has been retrieved, but the vessel is sold.  This vessel ownership cannot be used.')
            vessel_ownership_to_be_created = True

        keep_existing_vessel = request.data.get('proposal', {}).get('keep_existing_vessel', True)
        if not keep_existing_vessel:
            if instance.application_type.code in [MooringLicenceApplication.code,]:
                logger.info(f'New vessel: [{vessel}] is going to be added to the ML application: [{instance}].')
                vessel_ownership_to_be_created = True
            if instance.application_type.code in [AuthorisedUserApplication.code,]:
                logger.info(f'New vessel: [{vessel}] is going to replace the existing vessel of the AU application: [{instance}].')
                vessel_ownership_to_be_created = True

        if vessel_ownership_to_be_created:
            vessel_ownership = VesselOwnership.objects.create(
                owner=owner,  # Owner is actually the accessing user (request.user) as above.
                vessel=vessel,
                company_ownership=company_ownership
            )
            vo_created = True

        q_for_approvals_check &= ~Q(id=instance.approval.id)  # We want to exclude the approval we are currently processing for
    else:
        msg = f'Proposal: [{instance}] does not have correct proposal type.'
        logger.error(msg)
        raise Exception(msg)

    q_for_approvals_check &= Q(current_proposal__vessel_ownership=vessel_ownership)
    q_for_approvals_check &= Q(status__in=[Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED, Approval.APPROVAL_STATUS_FULFILLED,])

    # Other approvals which have the link to the vessel_ownership
    approvals = Approval.objects.filter(q_for_approvals_check)

    if vo_created:
        logger.info(f'New VesselOwnership: [{vessel_ownership}] has been created.')
    else:
        logger.info(f'Existing VesselOwnership: [{vessel_ownership}] has been retrieved.')

    if approvals.count() == 1:
        logger.warning(f'This VesselOwnership: [{vessel_ownership}] is also used with another active approval: [{approvals[0]}].')
    elif approvals:
        logger.warning(f'This VesselOwnership: [{vessel_ownership}] is also used with other active approvals: [{approvals}].')
    else:
        logger.info(f'This VesselOwnership: [{vessel_ownership}] is not used with any other active approvals.')

    # Update the vessel_ownership
    serializer = SaveVesselOwnershipSerializer(vessel_ownership, vessel_ownership_data)
    serializer.is_valid(raise_exception=True)
    vessel_ownership = serializer.save()
    logger.info(f'VesselOwnership: [{vessel_ownership}] has been updated with the data: [{vessel_ownership_data}].')

    # check and set blocking_owner
    if instance:
        vessel.check_blocking_ownership(vessel_ownership, instance)

    # save temp doc if exists
    handle_vessel_registrarion_documents_in_limbo(instance.id, vessel_ownership)

    # Vessel docs
    if vessel_ownership.company_ownership and not vessel_ownership.vessel_registration_documents.all():
        raise serializers.ValidationError({"Vessel Registration Papers": "Please attach"})
    return vessel_ownership

def handle_vessel_registrarion_documents_in_limbo(proposal_id, vessel_ownership):
    # VesselRegistrationDocument object with proposal is the documents stored for the draft proposal
    documents_in_limbo = VesselRegistrationDocument.objects.filter(proposal_id=proposal_id)

    for doc in documents_in_limbo:
        doc.vessel_ownership = vessel_ownership  # Link to the vessel_ownership
        doc.proposal = None  # Unlink to the proposal.  This link is used when proposal is draft and vessel_ownership is unknown.
        doc.save()

        logger.info(f'VesselRegistrationFile: {doc} has had a link to the vessel_ownership: {vessel_ownership}')


def handle_document(instance, vessel_ownership, request_data, *args, **kwargs):
    print("handle document")
    temporary_document_collection_id = request_data.get('proposal', {}).get('temporary_document_collection_id')
    if temporary_document_collection_id:
        temp_doc_collection = None
        if TemporaryDocumentCollection.objects.filter(id=temporary_document_collection_id):
            temp_doc_collection = TemporaryDocumentCollection.objects.filter(id=temporary_document_collection_id)[0]
        if temp_doc_collection:
            for doc in temp_doc_collection.documents.all():
                save_vessel_registration_document_obj(vessel_ownership, doc)
            temp_doc_collection.delete()
            instance.temporary_document_collection_id = None
            instance.save()

def ownership_percentage_validation(vessel_ownership, proposal):
    logger.info(f'Calculating the total vessel ownership percentage of the vessel: [{vessel_ownership.vessel}]...')

    individual_ownership_id = None
    company_ownership_id = None
    min_percent_fail = False
    vessel_ownership_percentage = 0
    ## First ensure applicable % >= 25
    if hasattr(vessel_ownership.company_ownership, 'id'):
        company_ownership_id = vessel_ownership.company_ownership.id
        if not vessel_ownership.company_ownership.percentage:
            raise serializers.ValidationError({
                "Ownership Percentage": "You must specify a percentage"
                })
        else:
            if vessel_ownership.company_ownership.percentage < 25:
                min_percent_fail = True
            else:
                vessel_ownership_percentage = vessel_ownership.company_ownership.percentage
    elif not vessel_ownership.percentage:
        raise serializers.ValidationError({
            "Ownership Percentage": "You must specify a percentage"
            })
    else:
        individual_ownership_id = vessel_ownership.id
        if vessel_ownership.percentage < 25:
            min_percent_fail = True
        else:
            vessel_ownership_percentage = vessel_ownership.percentage
    if min_percent_fail:
        raise serializers.ValidationError({
            "Ownership Percentage": "Minimum of 25 percent"
            })

    ## Calc total existing
    vessel_ownerships_to_excluded = proposal.get_previous_vessel_ownerships()
    logger.info(f'Vessel ownerships to be excluded from the calculation: {vessel_ownerships_to_excluded}')

    total_percent = vessel_ownership_percentage
    vessel = vessel_ownership.vessel
    for vo in vessel.filtered_vesselownership_set.all():
        if vo in vessel_ownerships_to_excluded:
            continue
        if hasattr(vo.company_ownership, 'id'):
            if (vo.company_ownership.id != company_ownership_id and 
                    vo.company_ownership.percentage and
                    vo.company_ownership.blocking_proposal
                    ):
                total_percent += vo.company_ownership.percentage
                logger.info(f'Vessel ownership to be taken into account in the calculation: {vo.company_ownership}')
        elif vo.percentage and vo.id != individual_ownership_id:
            total_percent += vo.percentage
            logger.info(f'Vessel ownership to be taken into account in the calculation: {vo}')

    logger.info(f'Total ownership percentage of the vessel: [{vessel}] is {total_percent}%')

    if total_percent > 100:
        raise serializers.ValidationError({
            "Ownership Percentage": "Total of 100 percent exceeded"
            })


def get_fee_amount_adjusted(proposal, fee_item_being_applied, vessel_length):
    # Retrieve all the fee_items for this vessel

    if fee_item_being_applied:
        logger.info('Adjusting the fee amount for proposal: [{}], fee_item: [{}], vessel_length: [{}]'.format(
            proposal.lodgement_number, fee_item_being_applied, vessel_length
        ))

        fee_amount_adjusted = fee_item_being_applied.get_absolute_amount(vessel_length)

        # Retrieve all the fee items paid for this vessel (through proposal.vessel_ownership)
        fee_items_already_paid = proposal.vessel_ownership.get_fee_items_paid()
        if proposal.approval and proposal.approval.status in (Approval.APPROVAL_STATUS_CURRENT, Approval.APPROVAL_STATUS_SUSPENDED,):
            # Retrieve all the fee items paid for the approval this proposal is for (through proposal.approval)
            for item in proposal.approval.get_fee_items():
                if item not in fee_items_already_paid:
                    fee_items_already_paid.append(item)

        if fee_item_being_applied in fee_items_already_paid:
            # Fee item being applied has been paid already
            # We don't charge this fee_item_being_applied
            return Decimal('0.0')
        else:
            for fee_item in fee_items_already_paid:
                if fee_item.fee_period.fee_season == fee_item_being_applied.fee_period.fee_season and \
                        fee_item.fee_constructor.application_type == fee_item_being_applied.fee_constructor.application_type:
                    # Found fee_item which has the same fee_season and the same application_type of fee_item_being_applied
                    # This fee_item's fee_period and vessel_size_category might be different from those of the fee_item_being_applied

                    if fee_item.fee_period.start_date <= fee_item_being_applied.fee_period.start_date:
                        # Find the fee_item which can be considered as already paid for this period
                        target_fee_period = fee_item_being_applied.fee_period
                        target_proposal_type = fee_item_being_applied.proposal_type
                        target_vessel_size_category = fee_item.vessel_size_category

                        target_fee_constructor = fee_item_being_applied.fee_constructor
                        fee_item_considered_paid = target_fee_constructor.get_fee_item_for_adjustment(
                            target_vessel_size_category,
                            target_fee_period,
                            proposal_type=target_proposal_type,  # Find the fee_item with same proposal type (always 'amendment')
                            age_group=None,
                            admission_type=None
                        )

                        # Applicant already partially paid for this fee item.  Deduct it.
                        if fee_item_considered_paid:
                            logger.info(f'Deduct fee item: [{fee_item_considered_paid}] from [{fee_amount_adjusted}].')
                            fee_amount_adjusted -= fee_item_considered_paid.get_absolute_amount(vessel_length)
                            logger.info(f'Result amount: $[{fee_amount_adjusted}].')

        fee_amount_adjusted = 0 if fee_amount_adjusted <= 0 else fee_amount_adjusted
    else:
        if proposal.does_accept_null_vessel:
            # TODO: We don't charge for this application but when new replacement vessel details are provided,calculate fee and charge it
            fee_amount_adjusted = 0
        else:
            msg = 'The application fee admin data might have not been set up correctly.  Please contact the Rottnest Island Authority.'
            raise Exception(msg)

    return fee_amount_adjusted


def make_proposal_applicant_ready(proposal, request):
    proposal_applicant, created = ProposalApplicant.objects.get_or_create(proposal=proposal)
    if created:
        proposal_applicant.first_name = request.user.first_name
        proposal_applicant.last_name = request.user.last_name
        proposal_applicant.dob = request.user.dob

        proposal_applicant.residential_line1 = request.user.residential_address.line1
        proposal_applicant.residential_line2 = request.user.residential_address.line2
        proposal_applicant.residential_line3 = request.user.residential_address.line3
        proposal_applicant.residential_locality = request.user.residential_address.locality
        proposal_applicant.residential_state = request.user.residential_address.state
        proposal_applicant.residential_country = request.user.residential_address.country
        proposal_applicant.residential_postcode = request.user.residential_address.postcode

        proposal_applicant.postal_same_as_residential = request.user.postal_same_as_residential
        proposal_applicant.postal_line1 = request.user.postal_address.line1
        proposal_applicant.postal_line2 = request.user.postal_address.line2
        proposal_applicant.postal_line3 = request.user.postal_address.line3
        proposal_applicant.postal_locality = request.user.postal_address.locality
        proposal_applicant.postal_state = request.user.postal_address.state
        proposal_applicant.postal_country = request.user.postal_address.country
        proposal_applicant.postal_postcode = request.user.postal_address.postcode

        proposal_applicant.email = request.user.email
        proposal_applicant.phone_number = request.user.phone_number
        proposal_applicant.mobile_number = request.user.mobile_number

        proposal_applicant.save()


def make_ownership_ready(proposal, request):
    vessel_ownership = VesselOwnership.objects.create()
    proposal.vessel_ownership = vessel_ownership
    proposal.save()
    logger.info(f'New vessel_ownership {vessel_ownership} has been created and linked to {proposal}')
