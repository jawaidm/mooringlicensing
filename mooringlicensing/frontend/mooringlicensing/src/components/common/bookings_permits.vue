<template lang="html">
    <!--div class="container" id="bookingsPermits"-->
    <div id="bookingsPermits">
        <!--table style="width:100%"-->
        <div class="row form-group">
            <div class="col-sm-12">
                <label for="" class="col-sm-2 control-label">Date</label>
                <div class="col-sm-3 input-group date" ref="datePicker">
                    <input type="text" class="form-control text-center" placeholder="DD/MM/YYYY" v-model="selectedDate" id="dateField"/>
                    <span class="input-group-addon">
                        <span class="glyphicon glyphicon-calendar"></span>
                    </span>
                </div>
            </div>
        </div>
        <div class="row form-group">
            <div class="col-sm-12">
                <div id="spinnerLoader" v-if="dataLoading">
                    <i class="fa fa-4x fa-spinner fa-spin"></i>
                </div>
                <div v-else>
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Entity type</th>
                                <th>Number</th>
                                <th>Action</th>
                                <th>Contact number</th>
                                <th>View</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="approval in approvals">
                                <td>{{ approval.approval_type_dict.description }}</td>
                                <td>{{ approval.lodgement_number }}</td>
                                <!--td>View</td-->
                                <td></td>
                                <td>{{ approval.submitter_phone_number }}</td>
                                <td><a :href=approval.url>View</a></td>
                                <!--td>{{approval.url}}</td-->
                                <td>
                                    <table class="table">
                                        <thead>
                                            <tr>
                                                <th>Registration number</th>
                                                <th>Vessel Name</th>
                                            </tr>
                                        </thead>
                                        <tr v-for="vessel in approval.vessel_data">
                                            <td><a :href="'/internal/vessel/' + vessel.id">{{ vessel.rego_no }}</a></td>
                                            <td>{{ vessel.vessel_name }}</td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>
                            <tr v-for="booking in bookings">
                                <td>Booking</td>
                                <td>{{ booking.booking_id_pf }}</td>
                                <td></td>
                                <td>{{ booking.customer_phone_number }}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import FormSection from '@/components/forms/section_toggle.vue'
import {
  api_endpoints,
  helpers
}
from '@/utils/hooks'
    export default {
        name:'BookingsPermits',
        components:{
            FormSection,
        },
        props: {
            entity: {
                type: Object,
                required: true,
            },
        },
        data:function () {
            let vm = this;
            return {
                approvals: [],
                bookings: [],
                selectedDate: null,
                dataLoading: false,
             }
        },
        /*
        watch: {
            selectedDate: async function() {
                if (this.selectedDate) {
                    console.log("watch date")
                    //await this.retrieveIndividualOwner();
                }
            },
        },
        */
        computed: {
        },
        methods:{
            addEventListeners: async function () {
                let vm = this;
                let el_fr = $(vm.$refs.datePicker);
                let options = {
                    format: "DD/MM/YYYY",
                    showClear: true ,
                    //useCurrent: false,
                };

                el_fr.datetimepicker(options);

                el_fr.on("dp.change", function(e) {
                    //let selected_date = null;
                    if (e.date) {
                        // Date selected
                        vm.selectedDate = e.date.format('DD/MM/YYYY')  // e.date is moment object
                        //vm.arrival.arrival_date = selected_date;
                    } else {
                        // Date not selected
                        //vm.arrival.arrival_date = selected_date;
                        vm.selectedDate = null;
                    }
                });
                $("#dateField").on("blur", async function(e) {
                    //console.log("watch date")
                    vm.lookupEntities();
                });
            },
            lookupEntities: async function() {
                this.$nextTick(async () => {
                    console.log("lookupEntities");
                    this.dataLoading = true;
                    let payload = {
                        "selected_date": this.selectedDate,
                    }
                    // Approvals
                    if (this.entity.type === "vessel") {
                        const res = await this.$http.post(`/api/vessel/${this.entity.id}/find_related_approvals.json`, payload);
                        this.approvals = [];
                        for (let approval of res.body) {
                            this.approvals.push(approval);
                        }
                    } else if (this.entity.type === "mooring") {
                        const res = await this.$http.post(`/api/mooring/${this.entity.id}/find_related_approvals.json`, payload);
                        this.approvals = [];
                        for (let approval of res.body) {
                            this.approvals.push(approval);
                        }
                    }
                    // Bookings
                    // TODO: separate vue component may be required
                    if (this.entity.type === "vessel") {
                        const res = await this.$http.post(`/api/vessel/${this.entity.id}/find_related_bookings.json`, payload);
                        this.bookings = [];
                        for (let booking of res.body) {
                            this.bookings.push(booking);
                        }
                    } else if (this.entity.type === "mooring") {
                        const res = await this.$http.post(`/api/mooring/${this.entity.id}/find_related_bookings.json`, payload);
                        this.bookings = [];
                        for (let booking of res.body) {
                            this.bookings.push(booking);
                        }
                    }
                    this.dataLoading = false;
                });
            },
        },
        mounted: function () {
            this.$nextTick(async () => {
                let vm = this;
                this.addEventListeners();
                var dateNow = new Date();
                let el_fr = $(vm.$refs.datePicker);
                /*
                console.log(el_fr);
                console.log(el_fr.data("DateTimePicker"));
                */
                el_fr.data("DateTimePicker").date(dateNow);
            });
        },
        created: async function() {
            await this.lookupEntities()
        },
    }
</script>

<style lang="css" scoped>
  #spinnerLoader {
    width: 100%;
    text-align: center;
    padding: 1em 0;
  }
</style>
