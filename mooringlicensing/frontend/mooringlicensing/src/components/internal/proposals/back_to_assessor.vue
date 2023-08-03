
<template lang="html">
    <div id="internal-proposal-amend">
        <modal transition="modal fade" @ok="ok()" @cancel="cancel()" title="Back To Assessor" large>
            <div class="container-fluid">
                <div class="row">
                    <form class="form-horizontal" name="backToAssessorForm">
                        <alert :show.sync="showError" type="danger"><strong>{{errorString}}</strong></alert>
                        <div class="col-sm-12">
                            <div class="row">
                                <div class="form-group">
                                    <div class="col-sm-3">
                                        <label class="control-label pull-right" for="back_to_assessor_details">Details</label>
                                    </div>
                                    <div class="col-sm-6">
                                        <textarea class="form-control" name="details" v-model="back_to_assessor.details" id="back_to_assessor_details"></textarea>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </form>
                </div>
            </div>
        </modal>
    </div>
</template>

<script>
import Vue from 'vue'
import modal from '@vue-utils/bootstrap-modal.vue'
import alert from '@vue-utils/alert.vue'
import {helpers, api_endpoints} from "@/utils/hooks.js"

export default {
    name:'BackToAssessor',
    components:{
        modal,
        alert,
    },
    props: {
        proposal: {
            type: Object,
            default: null,
        },
    },
    data:function () {
        let vm = this;
        return {
            isModalOpen:false,
            form: null,
            back_to_assessor: {
                details: '',
                proposal: vm.proposal,
            },
            errors: false,
            errorString: '',
            validation_form: null,
        }
    },
    methods: {
        addFormValidations: function() {
            let vm = this;
            vm.validation_form = $(vm.form).validate({
                rules: {
                    details: {
                        required: true,
                    }
                },
                messages: {
                    details: {
                        required:"field is required",
                    }
                },
                showErrors: function(errorMap, errorList) {
                    $.each(this.validElements(), function(index, element) {
                        var $element = $(element);
                        $element.attr("data-original-title", "").parents('.form-group').removeClass('has-error');
                    });
                    // destroy tooltips on valid elements
                    $("." + this.settings.validClass).tooltip("destroy");
                    // add or update tooltips
                    for (var i = 0; i < errorList.length; i++) {
                        var error = errorList[i];
                        $(error.element)
                            .tooltip({
                                trigger: "focus"
                            })
                            .attr("data-original-title", error.message)
                            .parents('.form-group').addClass('has-error');
                    }
                }
            });
        },
        ok:function () {
            let vm =this;
            if($(vm.form).valid()){
                vm.sendData();
            }
        },
        cancel:function () {
            let vm = this;
            vm.close();
        },
        sendData: function(){
            console.log('in sendData')
            let vm = this;
            vm.errors = false;
            // vm.back_to_assessor.proposal = vm.proposal

            let data = {'status': 'with_assessor_requirements', 'approver_comment': vm.back_to_assessor.details}
            vm.$http.post(helpers.add_endpoint_json(api_endpoints.proposal, (vm.proposal.id + '/switch_status')), JSON.stringify(data),{
                emulateJSON:true,
            })
            .then(
                (res) => {
                    // vm.proposal = res.body;
                    // vm.original_proposal = helpers.copyObject(res.body);
                    vm.close()
                    vm.$router.push({ path: '/internal' }); //Navigate to dashboard after creating Amendment request
                }, 
                (err) => {
                    // vm.proposal = helpers.copyObject(vm.original_proposal)
                    //vm.proposal.applicant.address = vm.proposal.applicant.address != null ? vm.proposal.applicant.address : {};
                    swal(
                        'Proposal Error',
                        helpers.apiVueResourceError(err),
                        'error'
                    )
                }
            );

// 
            // vm.$http.post('/api/back_to_assessor.json', vm.back_to_assessor).then(
            //     response => {
            //         //vm.$parent.loading.splice('processing contact',1);
            //         swal(
            //              'Sent',
            //              'An email has been sent to the applicant with the request to amend this application',
            //              'success'
            //         );
            //         vm.amendingProposal = true;
            //         vm.close();
            //         //vm.$emit('refreshFromResponse',response);
            //         Vue.http.get(`/api/proposal/${vm.proposal.id}/internal_proposal.json`).then(
            //             response => {
            //                 vm.$emit('refreshFromResponse', response);
            //             }, error => {
            //                 console.log(error);
            //             }
            //         );
            //         vm.$router.push({ path: '/internal' }); //Navigate to dashboard after creating Amendment request
            //     }, 
            //     error => {
            //         console.log(error);
            //         vm.errors = true;
            //         vm.errorString = helpers.apiVueResourceError(error);
            //         vm.amendingProposal = true;

            //     }
            // );

        },
        close: function(){
            this.isModalOpen = false;
            this.back_to_assessor = {
                details: '',
                proposal: {},
            };
            this.errors = false;
            $(this.$refs.details).val(null).trigger('change');
            $('.has-error').removeClass('has-error');

            this.validation_form.resetForm();

        },
    },
    computed: {
        showError: function() {
            return this.errors;
        },
    },
    mounted:function () {
        this.form = document.forms.backToAssessorForm;
        this.addFormValidations();
        this.$nextTick(()=>{
            // vm.eventListerners();
        });
    },
}
</script>