import traceback
# import base64
# import geojson
# from six.moves.urllib.parse import urlparse
# from wsgiref.util import FileWrapper
from django.db.models import Q, Min
from django.db import transaction
# from django.http import HttpResponse
# from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
# from django.conf import settings
# from django.contrib import messages
# from django.views.decorators.http import require_http_methods
# from django.views.decorators.csrf import csrf_exempt
# from django.utils import timezone
from rest_framework import viewsets, serializers, status, generics, views
# from rest_framework.decorators import detail_route, list_route,renderer_classes
from rest_framework.decorators import action as detail_route
from rest_framework.decorators import action as list_route
from rest_framework.decorators import renderer_classes
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
# from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser, BasePermission
# from rest_framework.pagination import PageNumberPagination
# from datetime import datetime, timedelta
# from collections import OrderedDict
# from django.core.cache import cache
# from ledger.accounts.models import EmailUser,OrganisationAddress
from ledger_api_client.ledger_models import EmailUserRO as Emailuser
# from ledger.address.models import Country
# from datetime import datetime,timedelta, date
from mooringlicensing.helpers import is_customer, is_internal
from mooringlicensing.components.organisations.models import (
                                    Organisation,
                                    # OrganisationContact,
                                    OrganisationRequest,
                                    OrganisationRequestUserAction,
                                    OrganisationContact,
                                    OrganisationAccessGroup,
                                    # OrganisationRequestLogEntry,
                                    # OrganisationAction,
                                    # ledger_organisation,
                                )

from mooringlicensing.components.organisations.serializers import (
                                        OrganisationSerializer,
                                        OrganisationAddressSerializer,
                                        DetailsSerializer,
                                        SaveDiscountSerializer,
                                        OrganisationRequestSerializer,
                                        OrganisationRequestDTSerializer,
                                        OrganisationContactSerializer,
                                        OrganisationCheckSerializer,
                                        OrganisationPinCheckSerializer,
                                        OrganisationRequestActionSerializer,
                                        OrganisationActionSerializer,
                                        OrganisationRequestCommsSerializer,
                                        OrganisationCommsSerializer,
                                        OrganisationUnlinkUserSerializer,
                                        OrgUserAcceptSerializer,
                                        MyOrganisationsSerializer,
                                        OrganisationCheckExistSerializer,
                                        LedgerOrganisationFilterSerializer,
                                        OrganisationLogEntrySerializer,
                                        OrganisationRequestLogEntrySerializer,
                                    )
#from mooringlicensing.components.applications.serializers import (
#                                        BaseApplicationSerializer,
#                                    )

# from mooringlicensing.components.organisations.emails import (
# 						send_organisation_address_updated_email_notification,
# 						send_organisation_id_upload_email_notification,
# 						send_organisation_request_email_notification,
# 					)


#from wildlifecompliance.components.applications.models import (
#                                        Application,
#                                        Assessment,
#                                        ApplicationRequest,
#                                        ApplicationGroupType
#                                    )


class OrganisationViewSet(viewsets.ModelViewSet):
    queryset = Organisation.objects.all()
    serializer_class = OrganisationSerializer

    def _get_queryset(self):
        user = self.request.user
        if is_internal(self.request):
            return Organisation.objects.all()
        elif is_customer(self.request):
            return user.mooringlicensing_organisations.all()
        return Organisation.objects.none()

    @detail_route(methods=['GET',], detail=True)
    def contacts(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = OrganisationContactSerializer(instance.contacts.exclude(user_status='pending'),many=True)
            return Response(serializer.data);
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    @detail_route(methods=['GET',], detail=True)
    def contacts_linked(self, request, *args, **kwargs):
        try:
            qs = self.get_queryset()
            serializer = OrganisationContactSerializer(qs,many=True)
            return Response(serializer.data)
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    @detail_route(methods=['GET',], detail=True)
    def contacts_exclude(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            qs = instance.contacts.exclude(user_status='draft')
            serializer = OrganisationContactSerializer(qs,many=True)
            return Response(serializer.data)
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))


    @detail_route(methods=['POST',], detail=True)
    def validate_pins(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = OrganisationPinCheckSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            ret = instance.validate_pins(serializer.validated_data['pin1'],serializer.validated_data['pin2'],request)

            if ret == None:
                # user has already been to this organisation - don't add again
                data = {'valid': ret}
                return Response({'valid' : 'User already exists'})

            data = {'valid': ret}
            if data['valid']:
                # Notify each Admin member of request.
                instance.send_organisation_request_link_notification(request)
            return Response(data)
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    @detail_route(methods=['POST', ], detail=True)
    def accept_user(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = OrgUserAcceptSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user_obj = EmailUser.objects.get(
                email=serializer.validated_data['email'].lower()
            )
            instance.accept_user(user_obj, request)
            serializer = self.get_serializer(instance)
            return Response(serializer.data);
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    @detail_route(methods=['POST', ], detail=True)
    def accept_declined_user(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = OrgUserAcceptSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user_obj = EmailUser.objects.get(
                email=serializer.validated_data['email'].lower()
            )
            instance.accept_declined_user(user_obj, request)
            serializer = self.get_serializer(instance)
            return Response(serializer.data);
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            if hasattr(e,'error_dict'):
                raise serializers.ValidationError(repr(e.error_dict))
            else:
                if hasattr(e,'message'):
                    raise serializers.ValidationError(e.message)
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))


    @detail_route(methods=['POST',], detail=True)
    def decline_user(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = OrgUserAcceptSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user_obj = EmailUser.objects.get(
                email = serializer.validated_data['email'].lower()
                )
            instance.decline_user(user_obj,request)
            serializer = self.get_serializer(instance)
            return Response(serializer.data);
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))


    @detail_route(methods=['POST',], detail=True)
    def unlink_user(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = OrgUserAcceptSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user_obj = EmailUser.objects.get(
                email = serializer.validated_data['email'].lower()
                )
            instance.unlink_user(user_obj,request)
            serializer = self.get_serializer(instance)
            return Response(serializer.data);
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            if hasattr(e,'error_dict'):
                raise serializers.ValidationError(repr(e.error_dict))
            else:
                if hasattr(e,'message'):
                    raise serializers.ValidationError(e.message)
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))




    @detail_route(methods=['POST',], detail=True)
    def make_admin_user(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = OrgUserAcceptSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user_obj = EmailUser.objects.get(
                email = serializer.validated_data['email'].lower()
                )
            instance.make_admin_user(user_obj,request)
            serializer = self.get_serializer(instance)
            return Response(serializer.data);
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            if hasattr(e,'error_dict'):
                raise serializers.ValidationError(repr(e.error_dict))
            else:
                if hasattr(e,'message'):
                    raise serializers.ValidationError(e.message)
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    @detail_route(methods=['POST',], detail=True)
    def make_user(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = OrgUserAcceptSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user_obj = EmailUser.objects.get(
                email = serializer.validated_data['email'].lower()
                )
            instance.make_user(user_obj,request)
            serializer = self.get_serializer(instance)
            return Response(serializer.data);
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            if hasattr(e,'error_dict'):
                raise serializers.ValidationError(repr(e.error_dict))
            else:
                if hasattr(e,'message'):
                    raise serializers.ValidationError(e.message)
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    @detail_route(methods=['POST',], detail=True)
    def make_consultant(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = OrgUserAcceptSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user_obj = EmailUser.objects.get(
                email = serializer.validated_data['email'].lower()
                )
            instance.make_consultant(user_obj,request)
            serializer = self.get_serializer(instance)
            return Response(serializer.data);
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))


    @detail_route(methods=['POST',], detail=True)
    def suspend_user(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = OrgUserAcceptSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user_obj = EmailUser.objects.get(
                email = serializer.validated_data['email'].lower()
                )
            instance.suspend_user(user_obj,request)
            serializer = self.get_serializer(instance)
            return Response(serializer.data);
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            if hasattr(e,'error_dict'):
                raise serializers.ValidationError(repr(e.error_dict))
            else:
                if hasattr(e,'message'):
                    raise serializers.ValidationError(e.message)
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))


    @detail_route(methods=['POST',], detail=True)
    def reinstate_user(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = OrgUserAcceptSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user_obj = EmailUser.objects.get(
                email = serializer.validated_data['email'].lower()
                )
            instance.reinstate_user(user_obj,request)
            serializer = self.get_serializer(instance)
            return Response(serializer.data);
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            if hasattr(e,'error_dict'):
                raise serializers.ValidationError(repr(e.error_dict))
            else:
                if hasattr(e,'message'):
                    raise serializers.ValidationError(e.message)
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))


    @detail_route(methods=['POST',], detail=True)
    def relink_user(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = OrgUserAcceptSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user_obj = EmailUser.objects.get(
                email = serializer.validated_data['email'].lower()
                )
            instance.relink_user(user_obj,request)
            serializer = self.get_serializer(instance)
            return Response(serializer.data);
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            if hasattr(e,'error_dict'):
                raise serializers.ValidationError(repr(e.error_dict))
            else:
                if hasattr(e,'message'):
                    raise serializers.ValidationError(e.message)
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))



    @detail_route(methods=['GET',], detail=True)
    def action_log(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            qs = instance.action_logs.all()
            serializer = OrganisationActionSerializer(qs,many=True)
            return Response(serializer.data)
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

#    @detail_route(methods=['GET',])
#    def applications(self, request, *args, **kwargs):
#        try:
#            instance = self.get_object()
#            qs = instance.org_applications.all()
#            serializer = BaseApplicationSerializer(qs,many=True)
#            return Response(serializer.data)
#        except serializers.ValidationError:
#            print(traceback.print_exc())
#            raise
#        except ValidationError as e:
#            print(traceback.print_exc())
#            raise serializers.ValidationError(repr(e.error_dict))
#        except Exception as e:
#            print(traceback.print_exc())
#            raise serializers.ValidationError(str(e))

    @detail_route(methods=['GET',], detail=True)
    def comms_log(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            qs = instance.comms_logs.all()
            serializer = OrganisationCommsSerializer(qs,many=True)
            return Response(serializer.data)
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))


    @detail_route(methods=['POST',], detail=True)
    @renderer_classes((JSONRenderer,))
    def add_comms_log(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                instance = self.get_object()
                mutable=request.data._mutable
                request.data._mutable=True
                request.data['organisation'] = u'{}'.format(instance.id)
                request.data['staff'] = u'{}'.format(request.user.id)
                request.data._mutable=mutable
                serializer = OrganisationLogEntrySerializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                comms = serializer.save()
                # Save the files
                for f in request.FILES:
                    document = comms.documents.create()
                    document.name = str(request.FILES[f])
                    document._file = request.FILES[f]
                    document.save()
                # End Save Documents

                return Response(serializer.data)
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    @list_route(methods=['POST',], detail=False)
    def existance(self, request, *args, **kwargs):
        try:
            serializer = OrganisationCheckSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = Organisation.existance(serializer.validated_data['abn'])
            # Check request user cannot be relinked to org.
            data.update([('user', request.user.id)])
            data.update([('abn', request.data['abn'])])
            serializer = OrganisationCheckExistSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            return Response(serializer.data)
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    @detail_route(methods=['POST',], detail=True)
    def update_details(self, request, *args, **kwargs):
        try:
            org = self.get_object()
            instance = org.organisation
            data=request.data
            serializer = DetailsSerializer(instance,data=data, context={'request':request})
            serializer.is_valid(raise_exception=True)
            instance = serializer.save()
            #serializer = self.get_serializer(org)

            if is_internal(request) and 'apply_application_discount' in request.data:
                data = request.data
                if not data['apply_application_discount']:
                    data['application_discount'] = 0
                if not data['apply_licence_discount']:
                    data['licence_discount'] = 0

                if data['application_discount'] == 0:
                    data['apply_application_discount'] = False
                if data['licence_discount']  == 0:
                    data['apply_licence_discount'] = False

                serializer = SaveDiscountSerializer(org,data=data)
                serializer.is_valid(raise_exception=True)
                instance = serializer.save()

            serializer = self.get_serializer(org)
            return Response(serializer.data);
        except serializers.ValidationError as e:
            print(e.get_full_details())
            #raise serializers.ValidationError(str( e.get_full_details() ))
            raise
        except ValidationError as e:
            if hasattr(e,'error_dict'):
                raise serializers.ValidationError(repr(e.error_dict))
            if hasattr(e,'message'):
                    raise serializers.ValidationError(e.message)
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    @detail_route(methods=['POST',], detail=True)
    def update_address(self, request, *args, **kwargs):
        try:
            org = self.get_object()
            instance = org.organisation
            serializer = OrganisationAddressSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            # TODO: Update address
            # address, created = OrganisationAddress.objects.get_or_create(
            # 	line1 = serializer.validated_data['line1'],
            # 	locality = serializer.validated_data['locality'],
            # 	state = serializer.validated_data['state'],
            # 	country = serializer.validated_data['country'],
            # 	postcode = serializer.validated_data['postcode'],
            # 	organisation = instance
            # )
            # instance.postal_address = address
            instance.save()
            #send_organisation_address_updated_email_notification(request.user, instance, org, request)
            serializer = self.get_serializer(org)
            return Response(serializer.data);
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    @detail_route(methods=['POST',], detail=True)
    def upload_id(self, request, *args, **kwargs):
        pass
#        try:
#            instance = self.get_object()
#            instance.organisation.upload_identification(request)
#            with transaction.atomic():
#                instance.save()
#                instance.log_user_action(OrganisationAction.ACTION_ID_UPDATE.format(
#                '{} ({})'.format(instance.name, instance.abn)), request)
#
#            _applications = Application.objects.filter(org_applicant=instance.organisation.id)
#            # Notify internal users new ID uploaded.
#            if _applications:
#                emails = set()
#                for _application in _applications:
#                    # Officer assigned to the application
#                    if _application.assigned_officer_id:
#                        emails.add(EmailUser.objects.get(id=_application.assigned_officer_id).email)
#                    # Officer belonging to a group assigned to the application
#                    if ApplicationRequest.objects.filter(application_id=_application.id).exists():
#                        _requests = ApplicationRequest.objects.filter(application_id=_application.id)
#                        for _request in _requests:
#                            if Assessment.objects.filter(id=_request.id).exists():
#                                _group = Assessment.objects.filter(id=_request.id).first()
#                                if _group.assessor_group_id:
#                                    _group_type = ApplicationGroupType.objects\
#                                                .filter(id=_group.assessor_group_id).first()
#                                    _group_emails = _group_type.members.values_list('email', flat=True)
#                                    for _email in _group_emails:
#                                        emails.add(EmailUser.objects.get(email=_email).email)
#                contact = OrganisationContact.objects.get(organisation=instance).email
#                contact_email = EmailUser.objects.filter(email=request.user).first()
#                if EmailUser.objects.filter(email=contact).first():
#                    contact_email = EmailUser.objects.filter(email=contact).first()
#                send_organisation_id_upload_email_notification(emails, instance, contact_email, request)
#
#            serializer = OrganisationSerializer(instance, partial=True)
#            return Response(serializer.data)
#        except serializers.ValidationError:
#            print(traceback.print_exc())
#            raise
#        except ValidationError as e:
#            print(traceback.print_exc())
#            raise serializers.ValidationError(repr(e.error_dict))
#        except Exception as e:
#            print(traceback.print_exc())
#            raise serializers.ValidationError(str(e))

from rest_framework import filters
class OrganisationListFilterView(generics.ListAPIView):
    """ https://cop-internal.dbca.wa.gov.au/api/filtered_organisations?search=Org1
    """
    pass
    # queryset = ledger_organisation.objects.none()
    # serializer_class = LedgerOrganisationFilterSerializer
    # filter_backends = (filters.SearchFilter,)
    # search_fields = ('name',)
    #
    # def get_queryset(self):
    # 	org_list = Organisation.objects.all().values_list('organisation_id', flat=True)
    # 	return ledger_organisation.objects.filter(id__in=org_list)

class OrganisationRequestsViewSet(viewsets.ModelViewSet):
    queryset = OrganisationRequest.objects.all()
    serializer_class = OrganisationRequestSerializer

    def get_queryset(self):
        user = self.request.user
        if is_internal(self.request):
            return OrganisationRequest.objects.all()
        elif is_customer(self.request):
            # return user.organisationrequest_set.all()
            # user_id = user.id
            # print(user_id)
            org_requests = OrganisationRequest.objects.filter(requester=user.id)
            return org_requests
        return OrganisationRequest.objects.none()

    @list_route(methods=['GET',], detail=False)
    def datatable_list(self, request, *args, **kwargs):
        try:
            qs = self.get_queryset()
            serializer = OrganisationRequestDTSerializer(qs,many=True)
            return Response(serializer.data)
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    # @list_route(methods=['GET',])
    # def user_organisation_request_list(self, request, *args, **kwargs):
    #     try:
    #         queryset = self.get_queryset()
    #         queryset = queryset.filter(requester = request.user)

    #         # instance = OrganisationRequest.objects.get(requester = request.user)
    #         serializer = self.get_serializer(queryset, many=True)
    #         return Response(serializer.data)
    #     except serializers.ValidationError:
    #         print(traceback.print_exc())
    #         raise
    #     except ValidationError as e:
    #         print(traceback.print_exc())
    #         raise serializers.ValidationError(repr(e.error_dict))
    #     except Exception as e:
    #         print(traceback.print_exc())
    #         raise serializers.ValidationError(str(e))

    @list_route(methods=['GET', ], detail=False)
    def get_pending_requests(self, request, *args, **kwargs):
        try:
            qs = self.get_queryset().filter(requester=request.user.id, status='with_assessor')
            serializer = OrganisationRequestDTSerializer(qs, many=True)
            return Response(serializer.data)
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    @list_route(methods=['GET', ], detail=False)
    def get_amendment_requested_requests(self, request, *args, **kwargs):
        try:
            qs = self.get_queryset().filter(requester=request.user, status='amendment_requested')
            serializer = OrganisationRequestDTSerializer(qs, many=True)
            return Response(serializer.data)
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    @detail_route(methods=['GET',], detail=True)
    def assign_request_user(self, request, *args, **kwargs):
        try:
            instance = self.get_object(requester =request.user)
            serializer = OrganisationRequestSerializer(instance)
            return Response(serializer.data)
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    @detail_route(methods=['GET',], detail=True)
    def unassign(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            instance.unassign(request)
            serializer = OrganisationRequestSerializer(instance)
            return Response(serializer.data)
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    @detail_route(methods=['GET',], detail=True)
    def accept(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            instance.accept(request)
            serializer = OrganisationRequestSerializer(instance)
            return Response(serializer.data)
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            # print(traceback.print_exc())
            # raise serializers.ValidationError(repr(e.error_dict))
            if hasattr(e,'error_dict'):
                raise serializers.ValidationError(repr(e.error_dict))
            else:
                if hasattr(e,'message'):
                    raise serializers.ValidationError(e.message)
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    @detail_route(methods=['GET',], detail=True)
    def amendment_request(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            instance.amendment_request(request)
            serializer = OrganisationRequestSerializer(instance)
            return Response(serializer.data)
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    @detail_route(methods=['PUT',], detail=True)
    def reupload_identification_amendment_request(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            instance.reupload_identification_amendment_request(request)
            serializer = OrganisationRequestSerializer(instance, partial=True)
            return Response(serializer.data)
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    @detail_route(methods=['GET',], detail=True)
    def decline(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            reason = ''
            instance.decline(reason, request)
            serializer = OrganisationRequestSerializer(instance)
            return Response(serializer.data)
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    @detail_route(methods=['POST',], detail=True)
    def assign_to(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            user_id = request.data.get('user_id',None)
            user = None
            if not user_id:
                raise serializers.ValiationError('A user id is required')
            try:
                user = EmailUser.objects.get(id=user_id)
            except EmailUser.DoesNotExist:
                raise serializers.ValidationError('A user with the id passed in does not exist')
            instance.assign_to(user,request)
            serializer = OrganisationRequestSerializer(instance)
            return Response(serializer.data)
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    @detail_route(methods=['GET',], detail=True)
    def action_log(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            qs = instance.action_logs.all()
            serializer = OrganisationRequestActionSerializer(qs,many=True)
            return Response(serializer.data)
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    @detail_route(methods=['GET',], detail=True)
    def comms_log(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            qs = instance.comms_logs.all()
            serializer = OrganisationRequestCommsSerializer(qs,many=True)
            return Response(serializer.data)
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

    @detail_route(methods=['POST',], detail=True)
    @renderer_classes((JSONRenderer,))
    def add_comms_log(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                instance = self.get_object()
                mutable=request.data._mutable
                request.data._mutable=True
                request.data['organisation'] = u'{}'.format(instance.id)
                request.data['request'] = u'{}'.format(instance.id)
                request.data['staff'] = u'{}'.format(request.user.id)
                request.data._mutable=mutable
                serializer = OrganisationRequestLogEntrySerializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                comms = serializer.save()
                # Save the files
                for f in request.FILES:
                    document = comms.documents.create()
                    document.name = str(request.FILES[f])
                    document._file = request.FILES[f]
                    document.save()
                # End Save Documents

                return Response(serializer.data)
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))


    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.validated_data['requester'] = request.user
            if request.data['role'] == 'consultant':
                # Check if consultant can be relinked to org.
                data = Organisation.existance(request.data['abn'])
                data.update([('user', request.user.id)])
                data.update([('abn', request.data['abn'])])
                existing_org = OrganisationCheckExistSerializer(data=data)
                existing_org.is_valid(raise_exception=True)
            with transaction.atomic():
                instance = serializer.save()
                instance.log_user_action(OrganisationRequestUserAction.ACTION_LODGE_REQUEST.format(instance.id),request)
                instance.send_organisation_request_email_notification(request)
            return Response(serializer.data)
        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(repr(e.error_dict))
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))

class OrganisationAccessGroupMembers(views.APIView):

    renderer_classes = [JSONRenderer,]
    def get(self,request, format=None):
        members = []
        if is_internal(request):
            group = OrganisationAccessGroup.objects.first()
            if group:
                for m in group.all_members:
                    members.append({'name': m.get_full_name(),'id': m.id})
            else:
                for m in EmailUser.objects.filter(is_superuser=True,is_staff=True,is_active=True):
                    members.append({'name': m.get_full_name(),'id': m.id})
        return Response(members)


class OrganisationContactViewSet(viewsets.ModelViewSet):
    serializer_class = OrganisationContactSerializer
    queryset = OrganisationContact.objects.all()

    def get_queryset(self):
        user = self.request.user
        if is_internal(self.request):
            return OrganisationContact.objects.all()
        elif is_customer(self.request):
            user_orgs = [org.id for org in user.mooringlicensing_organisations.all()]
            return OrganisationContact.objects.filter( Q(organisation_id__in = user_orgs) )
        return OrganisationContact.objects.none()

class MyOrganisationsViewSet(viewsets.ModelViewSet):
    queryset = Organisation.objects.all()
    serializer_class = MyOrganisationsSerializer

    def get_queryset(self):
        user = self.request.user
        if is_internal(self.request):
            return Organisation.objects.all()
        elif is_customer(self.request):
            return user.mooringlicensing_organisations.all()
        return Organisation.objects.none()
