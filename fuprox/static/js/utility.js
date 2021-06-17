
    function getFrequency(item){
    thisVal =  item.value;
    if(thisVal === "null"){
        $("#type").prop("disabled",true);
        $("#statusOne").prop("selected",true);
    }else if(thisVal === 'day'){
        $("#type").removeAttr("disabled");
        $("#dateCont").show();
        $("#monthCont").hide();
        $("#weekCont").hide();
    }else if(thisVal === "week"){
        $("#type").removeAttr("disabled");
        $("#dateCont").hide();
        $("#monthCont").show();
        $("#weekCont").show();

    }else if(thisVal === 'month'){
        $("#type").removeAttr("disabled");
        $("#dateCont").hide();
        $("#monthCont").show();
        $("#weekCont").hide();
    }
}

const daysInMonth  = (month, year) => {
    return new Date(year, month, 0).getDate();
}

const updateWeek = (item) => {
    let month = $("#month").val()
    if(month !== ""){
        let daysInMonths = new Date(month);
        let yearDate = daysInMonths.getFullYear();
        let monthDate = daysInMonths.getMonth()+1;
        var days = daysInMonth(monthDate,yearDate);
        let weeks = Math.floor(days/7);
        let extraDays = days%7;
        if(extraDays > 0){
            // five weeks
            $("#five").show();
        }else{
            // four weeks
            $("#five").hide();
        }
    }else{
        let error = $("#error");
        let monthHandle = $("#month");
        error.html("Month Required. Please Select Select A Month")
        error.show();
        monthHandle.addClass("is-invalid")
        setTimeout(()=>{
            error.hide()
            monthHandle.removeClass("is-invalid")
        },5000);
    }
}


var start = new Date(),
            prevDay,
            startHours = 8;
// 09:00 AM
start.setHours(8);
start.setMinutes(0);
// If today is Saturday or Sunday set 10:00 AM
if ([6, 0].indexOf(start.getDay()) !== -1) {
    start.setHours(10);
    startHours = 10
}
// var minHours =;
// var minDate = ;
// minDate : today;
$('#dailyCal').datepicker({
    language: 'en',
    startDate: start,
    maxDate: start,
    autoClose: true,
    position: "top left",
    onSelect: function (fd, d, picker) {
        // Do nothing if selection was cleared
        if (!d) return;
        let day = d.getDay();
        // Trigger only if date is changed
        if (prevDay !== undefined && prevDay === day) return;
        prevDay = day;
        // If chosen day is Saturday or Sunday when set
        // hour value for weekends, else restore defaults
        if (day === 6 || day === 0) {
            picker.update({
                minHours: 10,
                maxHours: 16
            })
        } else {
            picker.update({
                minHours: 9,
                maxHours: 18
            })
        }
    }
});


$('#month').datepicker({
language: 'en',
startDate: start,
autoClose : true,
view : "months",
minView : "months",
maxDate : start,
dataMinView : "months",
dataView : "months",
position: "top left",
onSelect: function (fd, d, picker) {
    // Do nothing if selection was cleared
    if (!d) return;
    var day = d.getDay();
    // Trigger only if date is changed
    if (prevDay !== undefined && prevDay === day) return;
    prevDay = day;
    // If chosen day is Saturday or Sunday when set
    // hour value for weekends, else restore defaults
    if (day === 6 || day === 0) {
        picker.update({
            minHours: 10,
            maxHours: 16
        })
    } else {
        picker.update({
            minHours: 9,
            maxHours: 18
        })
    }
}
});


$('#generate').on("click",()=>{
                // generics
                let period = $("#frequency").val();

                let status = $("#type").val();
                let date = $("#date").val();
                // getting the date info

                if(status !== "null" && period !== "null" && (date !== "" || $("#month").val() !== "")){
                    // date variables
                    let month,week,date,newDay;
                    let errorHandle = $("#error");
                    let generate = $("#generate");
                    let generating = $("#generating");
                    let done = $("#done");
                    // get new date
                    if(period === 'day'){
                        // fields : [period,status,date]
                        date = $("#date").val();

                    }else if(period === 'week'){
                        // fields : [period,status,month,week]
                        month = $("#month").val();
                        week = $("#weeks").val();
                        let daysInMonths = new Date(month);
                        let yearDate = daysInMonths.getFullYear();
                        let monthDate = daysInMonths.getMonth()+1;
                        let days = daysInMonth(monthDate,yearDate);
                        // let weekCount = Math.floor(days/7);
                        // let extraDays = days%7;
                        /**
                         * Date format 'MM:DD:YYYY'
                         * required Date format : 'YYYY:MM:DD'
                         */
                        let monthSegments = month.split("/");
                        let monthDay = Number(monthSegments[1]);
                        // getting the week numberp
                        if(week === "null"){
                            /// week cannot be null
                            let handle = $("#error");
                            handle.html("Week Required. Please Select Week")
                            handle.show();
                            $("#weeks").addClass("is-invalid")
                            setTimeout(()=>{
                                handle.hide()
                                $("#weeks").removeClass("is-invalid")
                            },5000);
                        }else if(Number(week) === 1){
                            newDay = monthDay+4;
                        }else if(Number(week) === 2){
                            newDay = monthDay+9;
                        }else if(Number(week) === 3){
                            newDay = monthDay+17;
                        }else if(Number(week) === 4){
                            newDay = monthDay+24;
                        }else if(Number(week) === 5){
                            newDay = monthDay+28;
                        }
                        // there minght be a zero issues here prepending to newDay
                        date = monthSegments[0]+"/"+newDay+"/"+monthSegments[2];

                    }else if(period === "month"){
                        // fields : [period,status,month]
                        /**
                         * here month is date since it is a monthly report
                         */
                        date = $("#month").val();

                    }

                    let unformattedTime = date.split("/").join("-").split("-");
                    let formattedTime = unformattedTime[2]+"-"+unformattedTime[0]+"-"+unformattedTime[1];
                    // we are going to make an ajax request based on the data
                    $.ajax({
                        url: process,
                        method: "POST",
                        data: {
                            category: "report",
                            status : status,
                            period : period,
                            time : formattedTime
                        },
                        beforeSend: ()=>{
                            $("#spinner").show();
                            done.hide();
                            generating.show();
                            generate.prop("disabled",true)
                        },
                        success: function (result) {
                            let done = 1002;

                            if(parseInt(status) === 6){
                                if(result.new.length || result.assigned.length > 0 || result.resolved.length > 0 || result.closed.length > 0 ){
                                    done = 1001;
                                    let newReport = result.new;
                                    let assigned = result.assigned;
                                    let resolved = result.resolved;
                                    let closed = result.closed;
                                    generateReport(newReport,"New Issues");
                                    generateReport(assigned,"Assigned Issues");
                                    generateReport(resolved,"Resolved Issues");
                                    generateReport(closed,"Closed Issues");
                                }
                            }else{
                                done =1001
                                generateReport(result);
                            }
                            // end report gen
                            if(result && done === 1001 ){
                                setTimeout(()=>{
                                    let statusMapper = ["New Issues","Assigned Issues","Resolved Issues","Closed Issues","","Escalated Issues","All Issues — {New, Assigned, Resolved,Escalated,Closed}"];

                                let name = `${formattedTime}__${period}__${statusMapper[status]}.xlsx`;
                                //  excel gen
                                excel = new ExcelGen({
                                    "src_id": "report",
                                    "show_header": true,
                                    "format": "xlsx",
                                });

                                excel.generate(name);
                                // end excel gen

                                    $("#generating").hide()
                                    errorHandle.show();
                                    setTimeout(()=>{
                                        $('#error').hide();
                                        $("#generate").prop("disabled",false)
                                    },5000);
                                },500)
                            }
                        },
                        complete : ()=>{
                            setTimeout(()=>{ $("#spinner").hide()} ,1000)
                        }
                    });
                }else{
                    $("#done").hide()
                    function error(id,msg){
                        let handle = $("#error");
                        handle.html(msg)
                        handle.show();
                        $(`#${id}`).addClass("is-invalid")
                        setTimeout(()=>{
                            handle.hide()
                            $(`#${id}`).removeClass("is-invalid")
                        },5000);
                    }
                    // some data is not set
                    if(period === "null"){
                        error("frequency","Duration Is Required.");
                    } else if(status === "null"){
                        error("type","Issue Type Is Required");
                    }else if(!date){
                        error("date","Date is Required");
                    }
                }
            });