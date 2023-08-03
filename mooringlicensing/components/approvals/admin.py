from django.contrib import admin

from mooringlicensing.components.approvals import models
from mooringlicensing.ledger_api_utils import retrieve_email_userro


@admin.register(models.Sticker)
class StickerAdmin(admin.ModelAdmin):
    list_display = ['id', 'number', 'status', 'approval', 'dcv_permit', 'printing_date', 'mailing_date', 'fee_season',]
    search_fields = ['id', 'number', 'approval__lodgement_number',]
    list_filter = ['status',]
    list_display_links = ['id', 'number',]
    ordering = ['-id', ]


@admin.register(models.Approval)
class ApprovalAdmin(admin.ModelAdmin):
    list_display = [
        'lodgement_number',
        'status',
        'get_submitter',
        'issue_date',
        'start_date',
        'expiry_date',
        'current_proposal',
        'replaced_by',
        'applicant',
    ]
    search_fields = ['lodgement_number',]
    list_filter = ('status',)

    def get_submitter(self, obj):
        if obj.submitter:
            return retrieve_email_userro(obj.submitter)
        else:
            return ''

    get_submitter.short_description = 'submitter'  # Rename column header