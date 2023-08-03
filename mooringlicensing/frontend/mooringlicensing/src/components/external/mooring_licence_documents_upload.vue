<template>
    <div :class="wrapping_class_name">
        <FormSection
            :formCollapse="false"
            label="Other documents"
            Index="other_documents"
        >
            <div class="row form-group" v-if="!readonly">
                <label for="" class="col-sm-12 control-label">Attach the following documents and submit them to the Rottnest Island Authority</label>
            </div>

            <div class="row form-group">
                <label for="" class="col-sm-5 control-label">Copy of current mooring report</label>
                <div class="col-sm-7">
                    <FileField
                        :readonly="readonly"
                        ref="mooring_report_documents"
                        name="mooring-report-documents"
                        :isRepeatable="true"
                        :documentActionUrl="mooring_report_url"
                        :replace_button_by_text="true"
                    />
                </div>
            </div>

            <div class="row form-group">
                <label for="" class="col-sm-5 control-label">Written proof of finalisation concerning the ownership of the mooring apparatus between you and the previous licensee</label>
                <div class="col-sm-7">
                    <FileField
                        :readonly="readonly"
                        ref="written_proof_documents"
                        name="written-proof-documents"
                        :isRepeatable="true"
                        :documentActionUrl="written_proof_url"
                        :replace_button_by_text="true"
                    />
                </div>
            </div>

            <div class="row form-group">
                <label for="" class="col-sm-5 control-label">Signed licence agreement</label>
                <div class="col-sm-7">
                    <FileField
                        :readonly="readonly"
                        ref="signed_licence_agreement_documents"
                        name="signed-licence-agreement-documents"
                        :isRepeatable="true"
                        :documentActionUrl="signed_licence_agreement_documents_url"
                        :replace_button_by_text="true"
                    />
                </div>
            </div>

            <div class="row form-group">
                <label for="" class="col-sm-5 control-label">Proof of Identity</label>
                <div class="col-sm-7">
                    <FileField
                        :readonly="readonly"
                        ref="proof_of_identity_documents"
                        name="proof-of-identity-documents"
                        :isRepeatable="true"
                        :documentActionUrl="proof_of_identity_documents_url"
                        :replace_button_by_text="true"
                    />
                </div>
            </div>
        </FormSection>

        <div>
            <input type="hidden" name="csrfmiddlewaretoken" :value="csrf_token"/>
            <div class="row" style="margin-bottom: 50px">
                <div  class="container">
                    <div class="row" style="margin-bottom: 50px">
                        <div class="navbar navbar-fixed-bottom"  style="background-color: #f5f5f5;">
                            <div class="navbar-inner">
                                <div class="container">
                                    <p class="pull-right" style="margin-top:5px">
                                        <button v-if="submitting" type="button" class="btn btn-primary" disabled>Submit&nbsp;<i class="fa fa-circle-o-notch fa-spin fa-fw"></i></button>
                                        <input v-else type="button" @click.prevent="submit" class="btn btn-primary" value="Submit" :disabled="submitting"/>
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import FormSection from "@/components/forms/section_toggle.vue"
import FileField from '@/components/forms/filefield_immediate.vue'
import { api_endpoints, helpers } from '@/utils/hooks'

export default {
    name: 'OtherDocuments',
    props: {
        uuid_props:{
            type: String,
            default: '',
        },
        readonly: {
            type: Boolean,
            default: false,
        },
        wrapping_class_name: {
            type: String,
            default: 'container',
        }
    },
    data() {
        let vm = this;
        return {
            uuid: '',
            submitting: false,
        }
    },
    components:{
        FormSection,
        FileField,
    },
    computed: {
        csrf_token: function() {
            return helpers.getCookie('csrftoken')
        },
        unique_id: function(){
            if (this.uuid){
                return this.uuid
            } else if (this.uuid_props){
                return this.uuid_props
            } else {
                return ''
            }
        },
        mooring_report_url: function() {
            let url = '';
            if (this.unique_id){
                url = helpers.add_endpoint_join(
                    api_endpoints.proposal_by_uuid,
                    this.unique_id + '/process_mooring_report_document/'
                )
            }
            return url;
        },
        written_proof_url: function() {
            let url = '';
            if (this.unique_id){
                url = helpers.add_endpoint_join(
                    api_endpoints.proposal_by_uuid,
                    this.unique_id + '/process_written_proof_document/'
                )
            }
            return url;
        },
        signed_licence_agreement_documents_url: function(){
            let url = '';
            if (this.unique_id){
                url = helpers.add_endpoint_join(
                    api_endpoints.proposal_by_uuid,
                    this.unique_id + '/process_signed_licence_agreement_document/'
                )
            }
            return url;
        },
        proof_of_identity_documents_url: function(){
            let url = '';
            if (this.unique_id){
                url = helpers.add_endpoint_join(
                    api_endpoints.proposal_by_uuid,
                    this.unique_id + '/process_proof_of_identity_document/'
                )
            }
            return url;
        },
        submit_url: function(){
            let url = '';
            if (this.unique_id){
                url = helpers.add_endpoint_join(
                    api_endpoints.proposal_by_uuid,
                    this.unique_id + '/submit/'
                )
            }
            return url;
        }
    },
    methods: {
        submit: function(){
            let vm = this
            vm.submitting = true;

            swal({
                title: "Other Documents for Mooring Site Licence Application",
                text: "Are you sure you want to submit the documents?",
                type: "question",
                showCancelButton: true,
                confirmButtonText: "Submit",
            }).then(
                (res)=>{
                    let ret = vm.perform_submit();
                    ret.then(data=>{
                        this.$router.push({ name: 'external-dashboard' })
                    })
                    this.submitting = false
                },
                (res)=>{
                    this.submitting = false
                },
            )
        },
        perform_submit: async function(){
            try{
                const res = await this.$http.post(this.submit_url)
                return res;
            } catch(err){
                helpers.processError(err)
            }
        }
    },
    mounted: function(){
        this.uuid = this.$route.params.uuid
    },
}
</script>
