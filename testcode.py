oc.check = 0

                doc.paymentnext = 0 

                doc.daynext = None

                doc.nowtime = frappe.utils.nowtime()

                lastdaymonth = frappe.utils.get_last_day(frappe.utils.today())

                dsCusstomer = ["CDGT04-0000306"]

                checkOrder = frappe.utils.time_diff_in_seconds(frappe.utils.nowtime(),doc.nowtime)

                 

                #begindate = "2024-01-01"

                fromdate = doc.date_start

                todate = doc.date_end

                doc.payment = 0

                sosudenCuoi = 0

                monthFromday = frappe.utils.getdate(todate).month

                yearFromday = frappe.utils.getdate(todate).year

                customerList = doc.customer

                

                checkno = frappe.db.get_all('Customer Debit 2',

                    filters = [         

                          ["customer", "=", doc.customer],

                           ["year", "=", yearFromday],

                        ],

                    fields = ['name','customer'],

                    order_by = 'modified desc',

                )



                datathanhtoan =[]

                datamuahang= []

                lastmonthcheck = 0

                lastmonth = ""

                year = frappe.utils.getdate(doc.date_start).year

                if int(monthFromday) == 1:

                    lastmonthcheck = 12

                    year = year - 1 

                else:

                    lastmonthcheck = int(monthFromday) - 1 

                if lastmonthcheck <10:

                    lastmonth = "0"+str(lastmonthcheck)

                else:

                    lastmonth = str(lastmonthcheck)

              

            

                datarowtong2 = []

                firstdayLastMonth = frappe.utils.getdate(str(year)+"-"+str(lastmonth)+"-01")

                lastdayLastMonth = frappe.utils.get_last_day(firstdayLastMonth)

                

                

                dsGroupCheck = []

                    

                if doc.customer:

                    customerList = ""

                    doc.due_debit = 0 

                    doc.debt_on_time = 0 

                    doc.debt_less_than_30_days = 0 

                    doc.debt_30_to_90_days = 0 

                    doc.debt_over_90_days = 0 

                    

                    

                    doc.lai = 0 

                    dococde = ["H2","TL","HC"]

                    arrayLabel = ['Khách hàng', 'Mua Hàng', 'Thanh Toán', 'Cuối Kỳ', 'Ngày', 'Mô tả']

                    month = frappe.utils.getdate(doc.date_end).month

                    doc.month = str(month)

            

                    dsGroupCheck = []

                    datasend= json.dumps({

                        'customer':doc.customer

                    })

                    databangkeopen = []

                    datarowtong = []

                    debitTable = []

                    

                    customerGroupList = ""

                    customer_group = ""

                    customerid= ""

                    credit_days= 0 

                    

                    token = "token 1773d804508a47b:d3ca2affa83ccab"

                    link = 'https://ocrm.oshima.vn/api/method/'

                    link = link+str("osharegetcustomer")

                    getCustomer = frappe.make_post_request(link, data=datasend, headers={

                                            "Content-Type": "application/json",

                                            "Authorization": token

                                                                })

                                          

                    

                    #for data in getCustomer:

                    data = getCustomer.get("data")

                    dsErp = [] 

                    doc.status = str(customerid)

                    if data != 1 and data != []:

                        

                        sales_person= data[1]

                        doc.sales_person = sales_person

                        salename = sales_person

                        customerGroupList = data[0]

                        customer_group= data[0]

                        customerid = data[2]

                        company = data[3]

                        province_gso = data[4]

                        payment_terms = data[5] 

                        credit_days = data[6]

                        dsErp = data[7]

                        DSLaiSales = data[8]

                        doc.donhangconnotable = []

                        

                        doc.total = []

                        dsdonhangchitiet = []

                        province= ""

                        district = ""

                        Sumtinhlai = []

                        due_debit= 0

                        namsau = 0

                        erp_name = data[12]

                        monthFromday = frappe.utils.getdate(todate).month

                        yearFromday = frappe.utils.getdate(todate).year

                        customerList = doc.customer

                        

                        datarowtong2 = []

                

                   

                        def getmonthAndDay(fromdate,todate):

                            datecheck = fromdate

                            dsMonth = []

                            dsdate = []

                            

                            while frappe.utils.getdate(datecheck) <= frappe.utils.getdate(todate):

                                dsdate.append(datecheck)

                                monthcheck = frappe.utils.getdate(datecheck).month 

                                datecheck = frappe.utils.add_days(frappe.utils.getdate(datecheck),1)

                                

                                if monthcheck not in dsMonth:

                                    dsMonth.append(monthcheck)

                                 

                            monthSum = 0 

                            daysum = 0 

                            lastdaymonth = frappe.utils.get_last_day(todate)

                            firstdaymonth = frappe.utils.get_first_day(todate)

                            monthend = frappe.utils.getdate(todate).month 

                            

                            if len(dsMonth) == 1:

                                daysum = frappe.utils.date_diff(todate,fromdate) + 1

                            if len(dsMonth) > 1:

                                if frappe.utils.getdate( frappe.utils.get_last_day(fromdate)) > frappe.utils.getdate(fromdate):

                                    monthSum =  0

                                    daysum = frappe.utils.date_diff(frappe.utils.get_last_day(fromdate),fromdate)+1

                                    

                                if frappe.utils.getdate( frappe.utils.get_first_day(fromdate)) == frappe.utils.getdate(fromdate):

                                    monthSum =  1 

                                

                                if frappe.utils.getdate( frappe.utils.get_last_day(fromdate)) == frappe.utils.getdate(fromdate) and frappe.utils.getdate(fromdate) < frappe.utils.getdate(todate) :

                                    daysum = 1 + daysum

                                    #monthSum = monthSum - 1

                                

                                if frappe.utils.getdate(lastdaymonth) > frappe.utils.getdate(todate):

                                    

                                    for month in dsMonth:

                                        if month != monthend and month != frappe.utils.getdate(fromdate).month :

                                            monthSum = monthSum + 1 

                                        #if month == monthend:

                                    daysum = frappe.utils.date_diff(todate,firstdaymonth) + daysum+1

                                

                                if frappe.utils.getdate(lastdaymonth) == frappe.utils.getdate(todate):

                                   for month in dsMonth:

                                        if month != frappe.utils.getdate(fromdate).month :

                                            monthSum = monthSum + 1 

                                """if monthSum == 1:

                                    daysum = frappe.utils.date_diff(todate,fromdate)+1+ daysum"""

                                if monthSum <0:

                                    monthSum = 0 

                                

                            return monthSum,daysum,dsMonth

                        tongquahan = 0

                        designation = ["Quản lý Khu vực","Tele-sales","Trưởng Vùng","Giám đốc chi nhánh Miền Bắc"]   

                        dskhachang = []

                        

                        

                    

                        customerList2 = []

                        goupdata = []

                        

                        

                        goupdata = customerGroupList

                        dococde = ["H2","TL","HC"]

                        arrayLabel = ['Khách hàng', 'Mua Hàng', 'Thanh Toán', 'Cuối Kỳ', 'Ngày', 'Mô tả']

                        

                        dsloai = [" - Số phát sinh trong kỳ"," - Số dư đầu kỳ"," - Cộng số phát sinh trong kỳ"," - Số dư cuối kỳ"]

                        if customerGroupList != "no":

                            arrayLabel = ['Khách hàng','Đầu Kỳ','Mua Hàng', 'Thanh Toán', 'Cuối Kỳ', 'Ngày', 'Mô tả']

                        rofile = ["Admin","CCO","CFO","Kế toán trưởng","Kế toán công nợ","HR Admin Manager & Debt Account","Kế toán thanh toán"]

                        dataCheck = []

                        DSLaiSales = []

                   

                        def ttnhanh(delivery_date,company,customer,province_gso,credit_days):

                            check=[]



                            

                            daytt = 0

                    

                            if province_gso == "01" or province_gso == "79":

                                daytt=0

                            else:

                                daytt = 1

                            

                            day2 = ""

                            delivery_date = frappe.utils.getdate(delivery_date)

                            day2 = frappe.utils.add_days(delivery_date,daytt)

                            

                            due_date = frappe.utils.add_days(frappe.utils.getdate(day2),credit_days)

                            datecheck = delivery_date

                            dsDateCheck = []

                            dateHolidate = 0 

                            due_date = frappe.utils.add_days(frappe.utils.getdate(due_date),dateHolidate)

                            return due_date

                    

                             

                    

                    

                        dsCustomer_group= []

                        dskhachang.append(doc.customer)

                        dsCustomer_group.append(customer_group)

                        

                        

                     

                    

                    

                        dsdatabangke = []

                        dsdatabangkelast = []

                        lastday = frappe.utils.add_days(fromdate,-1)

                        dsKHFinal = []

                        checkdsKHFinal = []

                        GetCustomerDs = []

                        dsdatabangkeFinal = []

                        

                        checkdsKHFinal1 = []

                        tonghopcongnodailyAll = []

                        namcu = 0 

                        if len(dskhachang) == 1:

                            """filters = []

                            

                        

                            filters.append(["customerid", "=", customerid])

                            filters.append(["docdate", ">=", str(frappe.utils.getdate(doc.date_start))])

                            filters.append(["docdate", "<=", str(frappe.utils.getdate(doc.date_end))])

                            url = 'https://ocrmv3.oshima.vn/api/resource/'

                            doctype = "usp_Kct_SoChiTietCongNoDaiLy_WEB"

                            fields = ["*"]

                            filters = filters

                            or_filters = []

                            

                            limit_page_length = 5000000

                            url = url + doctype + "?fields=" + json.dumps(fields) + "&filters=" + json.dumps(filters) + "&or_filters=" + json.dumps(or_filters)+ "&limit_page_length=" + str(limit_page_length)

                            datacustomer = frappe.make_get_request(url, headers={

                                "Content-Type": "application/json",

                                "Authorization": "token 1773d804508a47b:9a10cd06d6a1818"

                            })

                            

                            dsdatabangke = datacustomer.get("data")

                            query = "EXEC usp_Kct_SoChiTietCongNoDaiLy_WEB @_CustomerId= '"+ str(customerid) + "', @_DocDate1= '"+ str(frappe.utils.getdate(fromdate)) + "', @_DocDate2='"+ str(frappe.utils.getdate(todate)) +"'"

                            dsdatabangke = frappe.make_post_request('https://bravo6.oshima.vn/getuspdata', data={

                                'query': query

                            })"""

                            """dsdatabangke = frappe.db.get_all("usp_Kct_SoChiTietCongNoDaiLy_WEB",

                                    filters=[        

                                        ["customerid","=", customerid],

                                    ],

                                    fields=["*"],

                                    order_by = 'docdate asc'

                                )"""

                            

                        checkdsKHFinal1 = []

                        tonghopcongnodailyAll = []

                        

                        

                        def dateGet(datedata):

                            dateGet = ""

                            if len(str(datedata)) > 4:

                                        dateGet = datedata

                                        dateGet = str(datedata)[0:10]

                            else: 

                                dateGet = datedata

                            return dateGet

                        customerList2 = []   

                        datarowtong = []

                        tonghopcongnodaily = []

                        dstest = []

                    

                        

                    

                        dsdonhangchitietLastMonth = []

                        def laiCheck(docno,conduTheodon,daytt,datesell,credittt,lai,getdaytt,duedate,credit_days,SongayQuahan,duoi15ngay,tu16den30ngay,tu31den90ngay,tren90,notronghan,fromdate,todate,laifull):

                            def getmonthAndDay(fromdate,todate):

                                datecheck = fromdate

                                dsMonth = []

                                dsdate = []

                                dsyear = []

                                checkmonthadd = 0 

                                while frappe.utils.getdate(datecheck) <= frappe.utils.getdate(todate):

                                    dsdate.append(datecheck)

                                    monthcheck = frappe.utils.getdate(datecheck).month 

                                    year = frappe.utils.getdate(datecheck).year 

                                    if year not in dsyear:

                                        dsyear.append(year)

                                        dsMonth.append(monthcheck)

                                        checkmonthadd = checkmonthadd + 1

                                    datecheck = frappe.utils.add_days(frappe.utils.getdate(datecheck),1)

                                    

                                    if monthcheck not in dsMonth:

                                        dsMonth.append(monthcheck)

                                        

                                         

                                monthSum = 0 

                                daysum = 0 

                                lastdaymonth = frappe.utils.get_last_day(todate)

                                firstdaymonth = frappe.utils.get_first_day(todate)

                                monthend = frappe.utils.getdate(todate).month 

                                if len(dsMonth) == 1:

                                    daysum = frappe.utils.date_diff(todate,fromdate) + 1

                                if len(dsMonth) > 1:

                                    if frappe.utils.getdate( frappe.utils.get_last_day(fromdate)) > frappe.utils.getdate(fromdate):

                                        monthSum =  0

                                        daysum = frappe.utils.date_diff(frappe.utils.get_last_day(fromdate),fromdate)+1

                                        

                                    if frappe.utils.getdate( frappe.utils.get_first_day(fromdate)) == frappe.utils.getdate(fromdate):

                                        monthSum =  1 

                                    

                                    if frappe.utils.getdate( frappe.utils.get_last_day(fromdate)) == frappe.utils.getdate(fromdate) and frappe.utils.getdate(fromdate) < frappe.utils.getdate(todate) :

                                        daysum = 1 + daysum

                                        #monthSum = monthSum - 1

                                    if frappe.utils.getdate(lastdaymonth) > frappe.utils.getdate(todate):

                                        

                                        for month in dsMonth:

                                            if month != monthend and month != frappe.utils.getdate(fromdate).month :

                                                monthSum = monthSum + 1 

                                            #if month == monthend:

                                        daysum = frappe.utils.date_diff(todate,firstdaymonth) + daysum+1

                                    if frappe.utils.getdate(lastdaymonth) == frappe.utils.getdate(todate):

                                        

                                        for month in dsMonth:

                                            if month != frappe.utils.getdate(fromdate).month :

                                                monthSum = monthSum + 1 

                                                

                                    """if monthSum == 1:

                                        daysum = frappe.utils.date_diff(todate,fromdate)+1+ daysum"""

                                    if monthSum <0:

                                        monthSum = 0 

                                    monthSum = checkmonthadd + monthSum

                                    

                                return monthSum,daysum,dsMonth

                            checkquahan = frappe.utils.date_diff(frappe.utils.getdate(daytt),frappe.utils.getdate(datesell))

                            

                            SongayQuahan = checkquahan-credit_days

                            

                            thanhtoan = 0 

                            dauky = 0 

                            """if credittt < 0 :

                                credittt = credittt * -1 

                                thanhtoan = 1 """

                            

                            

                    

                            if int(SongayQuahan) > 0 :

                                

                                if conduTheodon >0:

                                    if credittt < 0 :

                                        

                                        if docno != "dauky" :

                                            if int(SongayQuahan) > 0 :

        

                                                lai = round(conduTheodon*(SongayQuahan)*0.08/365,0) + lai

                                                getdaytt = str(getdaytt) + ", "+str(daytt) + " Lãi: "+str(conduTheodon)+"*"+str(SongayQuahan)+"*0.08/365" + "+ Số ngày quá hạn: "+str(SongayQuahan) + " Tiền còn lại: "+str(0) + "<br>"

                                        if docno == "dauky":

                                            checkdata = getmonthAndDay(duedate,frappe.utils.getdate(daytt))

                                            

                                            if int(SongayQuahan) > 0 :

                                                if checkdata[0] ==0 :

                                                    lai =  round(float(conduTheodon)*0.08/365,0)*checkdata[1] + lai

                                                    getdaytt = str(getdaytt) + ", "+str(daytt) + " Lãi: "+str(conduTheodon)+"* 0.08/365*"+str(checkdata[1]) + "+ Số ngày quá hạn: "+str(SongayQuahan) + " Tiền còn lại: "+str(0) + "<br>"

                                                else:

                                                    lai = round(float(conduTheodon)*0.08/12,0)*checkdata[0] + lai + round(float(conduTheodon)*0.08/365,0)*checkdata[1]

                                                    getdaytt = str(getdaytt) + ", "+str(daytt) + " Lãi: "+str(conduTheodon)+"* 0.08/12*"+str(checkdata[0])+"+"+str(conduTheodon)+"*0.08/365*"+str(checkdata[1]) + "+ Số ngày quá hạn: "+str(SongayQuahan) + " Tiền còn lại: "+str(0) + "<br>"

                                        if 0<int (SongayQuahan) <=30:

                                            tu16den30ngay = float(conduTheodon) + tu16den30ngay

                                        if 31<=int (SongayQuahan) <=90:

                                            tu31den90ngay =  float(conduTheodon)  + tu31den90ngay

                                        if int (SongayQuahan) >=91:

                                            if conduTheodon >0:

                                                tren90 =  float(conduTheodon) + tren90

                                        #conduTheodon = conduTheodon - credittt

                                        if credittt > 0 and credittt - conduTheodon >= 0:

                                            conduTheodon = 0

                                        

                                            

                                        if credittt == 0:

                                            conduTheodon = conduTheodon

                                        #conduTheodon = conduTheodon - credittt

                                            

                                        

                                    if conduTheodon <= credittt and credittt > 0  :

                                        

                                        if docno != "dauky" :

                                            

                                            if int(SongayQuahan) > 0 :

                                                lai = round(conduTheodon*(checkquahan-credit_days)*0.08/365,0) + lai

                                                getdaytt = str(getdaytt) + ", "+str(daytt) + " Lãi: "+str(conduTheodon)+"*"+str(SongayQuahan)+"*0.08/365" + "+ Số ngày quá hạn: "+str(SongayQuahan) + " Tiền còn lại: "+str(0) + "<br>"

                                            

                                        if docno == "dauky":

                                            checkdata = getmonthAndDay(duedate,frappe.utils.getdate(daytt))

                                            

                                            if int(SongayQuahan) > 0 :

                                                if checkdata[0] ==0 :

                                                    lai =  round(float(conduTheodon)*0.08/365,0)*checkdata[1] + lai

                                                    getdaytt = str(getdaytt) + ", "+str(daytt) + " Lãi: "+str(conduTheodon)+"* 0.08/365*"+str(checkdata[1]) + "+ Số ngày quá hạn: "+str(SongayQuahan) + " Tiền còn lại: "+str(0) + "<br>"

                                                else:

                                                    lai = round(float(conduTheodon)*0.08/12,0)*checkdata[0] + lai + round(float(conduTheodon)*0.08/365,0)*checkdata[1]

                                                    getdaytt = str(getdaytt) + ", "+str(daytt) + " Lãi: "+str(conduTheodon)+"* 0.08/12*"+str(checkdata[0])+"+"+str(conduTheodon)+"*0.08/365*"+str(checkdata[1]) + "+ Số ngày quá hạn: "+str(SongayQuahan) + " Tiền còn lại: "+str(0) + "<br>"

                                        

                                        if 0<int (SongayQuahan) <=30:

                                            tu16den30ngay = float(conduTheodon) + tu16den30ngay

                                        if 31<=int (SongayQuahan) <=90:

                                            tu31den90ngay =  float(conduTheodon)  + tu31den90ngay

                                        if int (SongayQuahan) >=91:

                                            if conduTheodon >0:

                                                tren90 =  float(conduTheodon) + tren90

                                        

                                        conduTheodon = 0

                               

                                    if conduTheodon > credittt and credittt > 0 :

                                        

                                        if docno != "dauky" :

                                            if int(SongayQuahan) > 0 :

                                                lai = round(credittt*(checkquahan-credit_days)*0.08/365,0)  + lai

                                                getdaytt = str(getdaytt) + ", "+str(daytt) + " Lãi: "+str(credittt)+"*"+str(SongayQuahan)+"*0.08/365" + "+ Số ngày quá hạn: "+str(SongayQuahan) + " Tiền còn lại: "+str(conduTheodon - credittt) + "<br>"

                                        if docno == "dauky":

                                            checkdata = getmonthAndDay(duedate,frappe.utils.getdate(daytt))

                                            if checkdata[0] ==0:

                                                if int(SongayQuahan) > 0 :

                                                    lai =  round(float(credittt)*0.08/365,0)*checkdata[1] + lai

                                                    getdaytt = str(getdaytt) + ", "+str(daytt) + " Lãi: "+str(credittt)+"* 0.08/365*"+str(checkdata[1])  + "+ Số ngày quá hạn: "+str(SongayQuahan) + " Tiền còn lại: "+str(conduTheodon - credittt) + "<br>"

                                            else:

                                                if int(SongayQuahan) > 0 :

                                                    lai = round(float(credittt)*0.08/12,0)*checkdata[0] + lai + round(float(credittt)*0.08/365,0)*checkdata[1]

                                                    getdaytt = str(getdaytt) + ", "+str(daytt) + " Lãi: "+str(credittt)+"* 0.08/12*"+str(checkdata[0])+"+"+str(credittt)+"*0.08/365*"+str(checkdata[1]) + "+ Số ngày quá hạn: "+str(SongayQuahan) + " Tiền còn lại: "+str(conduTheodon - credittt) + "<br>"

                                        if 0<int (SongayQuahan) <=30:

                                            tu16den30ngay = float(credittt) + tu16den30ngay

                                        if 31<=int (SongayQuahan) <=90:

                                            tu31den90ngay =  float(credittt)  + tu31den90ngay

                                        if int (SongayQuahan) >=91:

                                            if conduTheodon >0:

                                                tren90 =  float(credittt) + tren90

                                        conduTheodon = conduTheodon - credittt

                                        

                                    if conduTheodon > credittt and credittt == 0 :

                                        

                                        if docno != "dauky" :

                                            if int(SongayQuahan) > 0 :

                                                lai = round(conduTheodon*(checkquahan-credit_days)*0.08/365,0)  + lai

                                                getdaytt = str(getdaytt) + ", "+str(daytt) + " Lãi: "+str(conduTheodon)+"*"+str(SongayQuahan)+"*0.08/365" + "+ Số ngày quá hạn: "+str(SongayQuahan) + " Tiền còn lại: "+str(conduTheodon - conduTheodon) + "<br>"

                                        if docno == "dauky":

                                            

                                            checkdata = getmonthAndDay(duedate,frappe.utils.getdate(daytt))

                                            

                                                  

                                            if checkdata[0] ==0:

                                                if int(SongayQuahan) > 0 :

                                                    lai =  round(float(conduTheodon)*0.08/365,0)*checkdata[1] + lai

                                                    getdaytt = str(getdaytt) + ", "+str(daytt) + " Lãi: "+str(conduTheodon)+"* 0.08/365*"+str(checkdata[1])  + "+ Số ngày quá hạn: "+str(SongayQuahan) + " Tiền còn lại: "+str(conduTheodon - conduTheodon) + "<br>"

                                            else:

                                                if int(SongayQuahan) > 0 :

                                                    lai = round(float(conduTheodon)*0.08/12,0)*checkdata[0] + lai + round(float(conduTheodon)*0.08/365,0)*checkdata[1]

                                                    getdaytt = str(getdaytt) + ", "+str(daytt) + " Lãi: "+str(conduTheodon)+"* 0.08/12*"+str(checkdata[0])+"+"+str(conduTheodon)+"*0.08/365*"+str(checkdata[1]) + "+ Số ngày quá hạn: "+str(SongayQuahan) + " Tiền còn lại: "+str(conduTheodon - conduTheodon) + "<br>"

                                        

                                        if 0<int (SongayQuahan) <=30:

                                            tu16den30ngay = float(conduTheodon) + tu16den30ngay

                                        if 31<=int (SongayQuahan) <=90:

                                            tu31den90ngay =  float(conduTheodon)  + tu31den90ngay

                                        if int (SongayQuahan) >=91:

                                            if conduTheodon >0:

                                                tren90 =  float(conduTheodon) + tren90

                                        conduTheodon = conduTheodon 

                                        

                            else:

                                

                                if credittt > 0 :

                                    conduTheodon = conduTheodon - credittt

                                else:

                                    conduTheodon = conduTheodon 

                                if conduTheodon <0:

                                    conduTheodon = 0

                    

                                

                            return conduTheodon, lai,daytt,getdaytt,SongayQuahan ,tu16den30ngay, tu31den90ngay,tren90,notronghan,laifull ,credittt,duedate,credit_days,checkquahan,datesell

                        

                        laifull = 0 

                        dsdonhangchitiet = []

                        

                         

                        thanhtoantruhangtra = 0 

                        dsdateCheck = []

                        dsdataban = []

                        dsdatathanhtoan = []

                        salename = ""

                        saleteam = ""

                        dateCharge = ""

                        tratruochan = 0 

                        deducted_debt = 0

                        tongthanhtoan = 0 

                        deducted_Date =""

                        dateCharge = data[13]

                        deducted_debt = data[9]

                        deducted_Date = data[10]

                        dsCustomer = []

                        datasend= json.dumps({

                                'customer':doc.customer

                            })

                            

                            

                        token = "token 1773d804508a47b:d3ca2affa83ccab"

                        link = 'https://ocrm.oshima.vn/api/method/'

                        link = link+str("getlisterpcustomerid")

                        getCustomer = frappe.make_post_request(link, data=datasend, headers={

                                                "Content-Type": "application/json",

                                                "Authorization": token

                                                                    })

                                                                  

                        if getCustomer:

                            dsCustomer=  getCustomer.get('data')

                        date_start = doc.date_start

                        checkMien = 0 

                        if frappe.utils.getdate(dateCharge) <= frappe.utils.getdate(doc.date_end) <= frappe.utils.getdate(deducted_Date):

                            checkMien = 1 

                            dsdatathanhtoan.append({

                                    "account": "",

                                    "customerid": customerid,

                                    "docdate": str(doc.date_start ) + "T00:00:00.000Z",

                                    "docno": "Miễn tính nợ theo yêu cầu",

                                    "doccode": "H2",

                                    "description":"Miễn tính nợ theo yêu cầu",

                                    "debitamount": 0,

                                    "originaldebitamount": 0,

                                    "creditamount":deducted_debt ,

                                    'Thanh Toán':0,

                                    "originalcreditamount": 0,

                                    "stt":"",

                                    "customerid0": customerid,

                                    "crspaccount": "",

                                    "itemid": "",

                                    'Mô tả':"Miễn tính nợ theo yêu cầu",

                                    "itemname": "",

                                    "warehouseid": 0,

                                    "quantity": 0,

                                    "docgroup": "2",

                                    "_status": "3",

                                    "_formatstylekey": "",

                                    "id": "",

                                    "_linkcommand": "EDIT_H2 PrimaryKeyValue={=Id}",

                                    "customercode": doc.customer,

                                    "customername": "",

                                    "bookingdate": str(doc.date_start ) + "T00:00:00.000Z",

                                })

                        khuvuc= ""

                        firstdebt = 0 

                        debit = 0 

                        buyitem = 0 

                        sellitem = 0 

                        credit = 0 

                        balance = 0 

                        dauky = 0

                        listNPP = frappe.get_all('Customer Debit 2',

                            filters=[                     

                                ["customer", "=", doc.customer], 

                                ["year", "=", yearFromday],

                                #["date_end", "=", frappe.utils.getdate(str(year)+"-12-31")],  

                            ],

                            fields=['name','customer_id'],

                            

                            )

                        

                        #dateendold = frappe.utils.getdate(str(year)+"-"+str(lastmonth)+"-31")

                        dateendold = lastdayLastMonth

                        

                        listNPPOld = frappe.get_all('Customer Debt Transaction 2',

                            filters=[                     

                                ["customer", "=", doc.customer], 

                                #["date_start", "=", date_start],

                                ["date_end", "=", dateendold],  

                            ],

                            fields=['name','payment','closing_receivables_amounts','closing_prepayment_amount','daynext','paymentnext'],

                            

                            )

                        

                        paymentold = 0 

                        totalthanhtoan = 0 

                        if not doc.open_receivables_amount:

                            doc.open_receivables_amount =0 

                        if not doc.open_prepayment:

                            doc.open_prepayment =0     

                        daukyThangNow = doc.open_receivables_amount - doc.open_prepayment 

                        

                        

                        if listNPPOld:

                            paymentAdd = 0 

                            listDonhangconnoTableOldCheck = frappe.get_all('DonhangconnoTable2',

                                    filters=[                     

                                        ["parent", "=", listNPPOld[0].name], 

                                      ["thanhtoan", "!=", ""],  

                                   

                                    ],

                                    

                                    fields=['*'],

                                    order_by = 'ngayhoadon asc'

                                    

                                    )

                            

                            if listDonhangconnoTableOldCheck:

                                paymentold =listNPPOld[0].payment - listNPPOld[0].paymentnext

                                paymentAdd = float(listNPPOld[0].paymentnext)

                            else:

                                paymentold = daukyThangNow

                                if daukyThangNow < 0:

                                    daukyThangNow = daukyThangNow * -1

                                    paymentAdd = daukyThangNow

                            

                            if paymentAdd > 0:

                                dsdatathanhtoan.append({

                                        "account": "",

                                        "customerid": customerid,

                                        "docdate": str(doc.date_start) + "T00:00:00.000Z",

                                        "docno": "TT tháng trước",

                                        "doccode": "H2",

                                        "description":"TT tháng trước",

                                        "debitamount": 0,

                                        "originaldebitamount": 0,

                                        "creditamount":paymentAdd,

                                        "originalcreditamount": 0,

                                        "stt":"",

                                        "customerid0": customerid,

                                         'Thanh Toán':0,

                                        "crspaccount": "",

                                        'Mô tả':"TT tháng trước",

                                        "itemid": "",

                                        "itemname": "",

                                        "warehouseid": 0,

                                        "quantity": 0,

                                        "docgroup": "2",

                                        "_status": "3",

                                        "_formatstylekey": "",

                                        "id": "",

                                        "_linkcommand": "EDIT_H2 PrimaryKeyValue={=Id}",

                                        "customercode": doc.customer,

                                        "customername": "",

                                        "bookingdate": str(doc.ngayhoadon ) + "T00:00:00.000Z",

                                    })

                            

                            cuoikyThangLast = listNPPOld[0].closing_receivables_amounts - listNPPOld[0].closing_prepayment_amount 

                            if daukyThangNow - cuoikyThangLast > 0:

                                paymentold = paymentold +  (daukyThangNow - cuoikyThangLast)

                                #doc.check2 = 1 

                            if daukyThangNow - cuoikyThangLast < 0:

                                paymentold = paymentold -  (daukyThangNow - cuoikyThangLast)

                                #doc.check2 = 1 

                            listDonhangconnoTableOld = []

                            """if frappe.utils.getdate(dateendold)> frappe.utils.getdate("2024-12-31"):

                                listDonhangconnoTableOld = frappe.get_all('DonhangconnoTable2',

                                    filters=[                     

                                        ["parent", "=", listNPPOld[0].name], 

                                      ["thanhtoan", "!=", ""],  

                                      ["muahang", "=", 0],  

                                      ["payment_next", ">", 0],  

                                    ],

                                    

                                    fields=['*'],

                                    order_by = 'ngayhoadon asc'

                                    

                                    )

                            

                                if listDonhangconnoTableOld:

                                    for lis in listDonhangconnoTableOld:

                                        if not "ngày" in str(lis.thanhtoan):

                                            dsdatathanhtoan.append({

                                                "account": "",

                                                "customerid": customerid,

                                                "docdate": str(lis.ngayhoadon) + "T00:00:00.000Z",

                                                "docno": "TT tháng trước",

                                                "doccode": "H2",

                                                "description":"TT tháng trước",

                                                "debitamount": 0,

                                                "originaldebitamount": 0,

                                                "creditamount":float(lis.payment_next) ,

                                                "originalcreditamount": 0,

                                                "stt":"",

                                                "customerid0": customerid,

                                                "crspaccount": "",

                                                'Mô tả':"TT tháng trước",

                                                "itemid": "",

                                                 'Thanh Toán':0,

                                                "itemname": "",

                                                "warehouseid": 0,

                                                "quantity": 0,

                                                "docgroup": "2",

                                                "_status": "3",

                                                "_formatstylekey": "",

                                                "id": "",

                                                "_linkcommand": "EDIT_H2 PrimaryKeyValue={=Id}",

                                                "customercode": doc.customer,

                                                "customername": "",

                                                "bookingdate": str(doc.ngayhoadon ) + "T00:00:00.000Z",

                                            })

        

                            if  listDonhangconnoTableOld == [] and paymentold != 0:

                                dsdatathanhtoan.append({

                                    "account": "",

                                    "customerid": customerid,

                                    "docdate": str(doc.date_start ) + "T00:00:00.000Z",

                                    "docno": "TT tháng trước",

                                    "doccode": "H2",

                                    "description":"TT tháng trước",

                                    "debitamount": 0,

                                    "originaldebitamount": 0,

                                    "creditamount":paymentold ,

                                    "originalcreditamount": 0,

                                    "stt":"",

                                    "customerid0": customerid,

                                    "crspaccount": "",

                                    "itemid": "",

                                    "itemname": "",

                                     'Mô tả':"TT tháng trước",

                                     'Thanh Toán':0,

                                    "warehouseid": 0,

                                    "quantity": 0,

                                    "docgroup": "2",

                                    "_status": "3",

                                    "_formatstylekey": "",

                                    "id": "",

                                    "_linkcommand": "EDIT_H2 PrimaryKeyValue={=Id}",

                                    "customercode": doc.customer,

                                    "customername": "",

                                    "bookingdate": str(doc.date_start ) + "T00:00:00.000Z",

                                })"""

                        totalmuahang = 0 

                        totalmuahangold = 0 

                        if listNPPOld:

                            

                            #paymentold =listNPPOld[0].payment

                            

                            listDonhangconnoTableOld = frappe.get_all('DonhangconnoTable2',

                            filters=[                     

                                ["parent", "=", listNPPOld[0].name], 

                                 ["muahang", "!=", 0],  

                              

                            ],

                            or_filters=[                     

                                ["ngayquahan", ">=", frappe.utils.getdate(doc.date_start)],

                                ["conduTheodon", ">", 0],

                                ["thanhtoan", "=", ""],  

                            ],

                            fields=['*'],

                            order_by = 'ngay asc'

                            

                            )

                

                            if listDonhangconnoTableOld:

                                for lis in listDonhangconnoTableOld:

                                    debit = 0 

                                    date = ""

                                    duedatedata = ""

                                    if frappe.utils.getdate(lis.ngayquahan) < frappe.utils.getdate(doc.date_start):

                                        if lis.condutheodon > 0:

                                            debit = lis.condutheodon

                                            namcu = namcu + float(lis.condutheodon)

                                        else:

                                            if lis.quahan > 0:

                                                debit = lis.quahan

                                                namcu = namcu + float(lis.quahan)

                                    if frappe.utils.getdate(lis.ngayquahan) >= frappe.utils.getdate(doc.date_start):

                                        debit = lis.muahang

                                        namcu = namcu + float(debit)

                                        duedatedata = lis.ngayquahan

                                    if frappe.utils.getdate(lis.ngayquahan) < frappe.utils.getdate(doc.date_start):

                                        date =  str(frappe.utils.add_days(doc.date_start,credit_days*-1))

                                        duedatedata = doc.date_start

                                    else:

                                        date =lis.ngay

                                    

                                    #doc.test = str(namcu)

                                    totalmuahangold = totalmuahangold + debit

                                    datamuahang.append({

                                            'Ngày':date,

                                            'Mua hàng':int(debit),

                                            'Mã hóa đơn':lis.mahoadon,

                                            'total':0,

                                            'Ngày đến hạn thanh toán':"",

                                            'Cuối kỳ':0,

                                            'ngayhoadon':(lis.ngayhoadon),

                                            'trancode':"",

                                            'detail':lis.mota,

                                            'description':lis.mota,

                                            'bookingdate':doc.date_start,

                                            'duedate':duedatedata,

                                            

                                            

                                        })

                                    """dsdataban.append({

                                        "account": "",

                                        "customerid": customerid,

                                        "docdate": str(date),

                                        "docno": lis.mahoadon,

                                        "doccode": "H2",

                                        "description": lis.mota,

                                        "debitamount": debit,

                                        "originaldebitamount": 0,

                                        "creditamount": 0,

                                        "originalcreditamount": 0,

                                        "stt": "A010257193",

                                        "customerid0": customerid,

                                        "crspaccount": "",

                                        "itemid": "",

                                        "itemname": "",

                                        "warehouseid": 0,

                                        "quantity": 0,

                                        "docgroup": "2",

                                        "_status": "3",

                                        "_formatstylekey": "",

                                        "id": "",

                                        "_linkcommand": "EDIT_H2 PrimaryKeyValue={=Id}",

                                        "customercode": lis.madaily, 

                                        "customername": lis.tendaily,

                                        "bookingdate": lis.ngay

                                    })"""

                        

                        if listNPP:

                            agencycode = listNPP[0].customer_id

                            dataUSP_Buttoanbutru_web = frappe.db.get_all('USP_Buttoanbutru_web', 

                                or_filters=[

                                    ['creditcustomerid','in',dsCustomer],

                                    ['debitcustomerid','in',dsCustomer],

                                    ],

                                filters=[

                                    ['docno','!=',""],

                                    ['docdate','>=',doc.date_start],

                                    ['docdate','<=',doc.date_end],

                                    ],

                                fields =['*'],

                                )

                            if dataUSP_Buttoanbutru_web:

                                for butru in dataUSP_Buttoanbutru_web:

                                    if butru.creditcustomerid in dsCustomer and butru.creditaccount and "1311" in butru.creditaccount:

                                        doc.total_selling = doc.total_selling + butru.creditoriginalamount

                                        datathanhtoan.append({

                                            'Ngày':frappe.utils.getdate(butru.docdate),

                                            'ngayhoadon':frappe.utils.getdate(butru.docdate),

                                            'Mua hàng':butru.creditoriginalamount,

                                            'Mã hóa đơn':butru.docno,

                                            'total':0,

                                            'Mô tả':butru.description0,

                                             'Thanh Toán':0,

                                            'Ngày đến hạn thanh toán':frappe.utils.format_date(butru.docdate),

                                            'Cuối kỳ':0,

                                            'trancode':butru.trancode,

                                            'detail':butru.description0,

                                            'description':butru.description0,

                                            'duedate':"no",

                                            

                                        })

                                        

                                    if butru.debitcustomerid in dsCustomer and butru.debitaccount and "1311" in butru.debitaccount:

                                        doc.payment_amount = doc.payment_amount+  float(butru.debitoriginalamount)

                                                

                                        datamuahang.append({

                                            'Ngày':frappe.utils.getdate(butru.docdate),

                                            'ngayhoadon':frappe.utils.getdate(butru.docdate),

                                            'Mua hàng':butru.debitoriginalamount,

                                            'Mã hóa đơn':butru.docno,

                                            'total':0,

                                            

                                            'Ngày đến hạn thanh toán':frappe.utils.format_date(butru.docdate),

                                            'Cuối kỳ':0,

                                            'trancode':butru.trancode,

                                            'detail':butru.description0,

                                            'description':butru.description0,

                                            'duedate':"no",

                                            

                                        })    

                            listusp_Kct_SoChiTietCongNoDaiLy_WEB = frappe.get_all('usp_Kct_SoChiTietCongNoDaiLy_WEB',

                                filters=[                     

                                    ["agencycode", "=", agencycode], 

                                    ['deletedata','!=',"tao bu"],

                                     ['butru','=',0],

                                   ['docdate2','>=',frappe.utils.getdate(doc.date_start)],

                                   ['docdate2','<=',frappe.utils.getdate(doc.date_end)]

                                ],

                                fields=['*'],

                                order_by = 'docdate2 asc'

                                )

                            if listusp_Kct_SoChiTietCongNoDaiLy_WEB:

                                for debt in listusp_Kct_SoChiTietCongNoDaiLy_WEB:

                                    if debt.debitamount > 0 :

                                        doc.payment_amount = doc.payment_amount+ int(debt.debitamount)

                                        datamuahang.append({

                                            'Ngày':debt.docdate2,

                                            'ngayhoadon':debt.docdate2,

                                            'Mua hàng':int(debt.debitamount)+  int(debt.creditamount),

                                            'Mã hóa đơn':debt.docno,

                                            'total':0,

                                            'Ngày đến hạn thanh toán':frappe.utils.format_date(debt.docdate2),

                                            'Cuối kỳ':0,

                                            'trancode':debt.trancode,

                                            'detail':debt.description,

                                            'description':debt.description,

                                            'duedate':"no",

                                            

                                        })

                                    if debt.creditamount != 0 :

                                        

                                        doc.total_selling = doc.total_selling + float(debt.creditamount)

                                        datathanhtoan.append({

                                            #'Mua hàng':f'{int(debt.buying):,}',

                                            'Ngày':debt.docdate2,

                                            'Thanh Toán':int(debt.creditamount),

                                            'total':debt.creditamount,

                                            'Mô tả':debt.description,

                                            'Mã hóa đơn':debt.docno,

                                            

                                            'Cuối kỳ':f'{int(0):,}',

                                            'Mota':debt.description,

                                            'trancode':debt.trancode,

                                            #'detail':[],

                                            'color':"#0017C1"

                                        })

                            npp = frappe.get_doc("Customer Debit 2",listNPP[0].name)

                            tonghopcongnodaily = frappe.make_post_request('https://bravo6.oshima.vn/getsotonghopcongnodaily', data={

                                        'agencycode': customerid ,

                                        'datestart': frappe.utils.getdate(doc.date_start),

                                        'dateend':frappe.utils.getdate(doc.date_end),

                                    })

                            if tonghopcongnodaily: #not 'status' in 

                                doc.open_receivables_amount = round(float(tonghopcongnodaily[0]["DebitBal1"]),0)

                                doc.open_prepayment =  round(float(tonghopcongnodaily[0]["CreditBal1"]),0)

                                doc.payment_amount =   round(float(tonghopcongnodaily[0]["DebitAmount"]),0)

                                doc.total_selling =  round(float(tonghopcongnodaily[0]["CreditAmount"]),0)

                                doc.closing_receivables_amounts =  round(float(tonghopcongnodaily[0]["DebitBal2"]),0)

                                doc.closing_prepayment_amount =  round(float(tonghopcongnodaily[0]["CreditBal2"]),0)

                            else:

                                doc.open_receivables_amount = 0

                                doc.open_prepayment =   0

                                doc.payment_amount =   0

                                doc.total_selling =  0

                                doc.closing_receivables_amounts =  0

                                doc.closing_prepayment_amount =   0

                            firstdebt = doc.open_receivables_amount

                            debit =doc.open_prepayment

                            buyitem = doc.payment_amount

                            sellitem =  doc.total_selling

                            credit = doc.closing_receivables_amounts

                            balance = doc.closing_prepayment_amount

                            paymentold = firstdebt - debit

                 

                            doc.payment_amount = 0 

                            doc.total_selling = 0

                            """for debt in npp.debt_npp_summary_table:

                                if frappe.utils.getdate(doc.date_start) <= frappe.utils.getdate(debt.date) <= frappe.utils.getdate(doc.date_end):

                                    if debt.buying > 0 :

                                        doc.payment_amount = doc.payment_amount+ int(debt.buying)

                                        datamuahang.append({

                                            'Ngày':debt.date,

                                            'ngayhoadon':debt.date,

                                            'Mua hàng':int(debt.buying)+  int(debt.credit),

                                            'Mã hóa đơn':debt.po_no,

                                            'total':0,

                                            'Ngày đến hạn thanh toán':frappe.utils.format_date(debt.duedate),

                                            'Cuối kỳ':0,

                                            'trancode':debt.trancode,

                                            'detail':debt.description,

                                            'description':debt.description,

                                            'duedate':"no",

                                            

                                        })

                                    if debt.credit != 0 :

                                        

                                        doc.total_selling = doc.total_selling + float(debt.credit)

                                        datathanhtoan.append({

                                            #'Mua hàng':f'{int(debt.buying):,}',

                                            'Ngày':debt.date,

                                            'Thanh Toán':int(debt.credit),

                                            'total':debt.credit,

                                            'Mô tả':debt.description,

                                            'Mã hóa đơn':debt.po_no,

                                            

                                            'Cuối kỳ':f'{int(0):,}',

                                            'Mota':debt.description,

                                            'trancode':debt.trancode,

                                            #'detail':[],

                                            'color':"#0017C1"

                                        })"""

                     

                        

                        

                        dauky = firstdebt - debit

                        if dauky > 0 :

                            firstdebt = dauky

                            debit = 0 

                            

                        if dauky < 0 :

                            firstdebt = 0

                            debit = dauky 

                        if dauky == 0 :

                            firstdebt = 0

                            debit = 0

                        cuoikydata = credit - balance

                        if cuoikydata > 0 :

                            credit = cuoikydata

                            balance = 0 

                        if cuoikydata < 0 :

                            credit = 0

                            balance = cuoikydata 

                        if cuoikydata == 0 :

                            credit = 0

                            balance = 0  

                            

                        totalthanhtoan=  0

                        cuoiky = dauky 

                        dsloai = [" - Số phát sinh trong kỳ"," - Số dư đầu kỳ"," - Cộng số phát sinh trong kỳ"," - Số dư cuối kỳ"]

                        finalDebt =  sellitem - dauky

                        dataSum =finalDebt

                        tongduoi15ngay = 0 

                        tongtu16den30ngay= 0

                        tongtu31den90ngay= 0

                        tongtren90= 0

                        tongnotronghan = 0 

                        summfull= 0 

                        sumtest = 0 

                        company = data[11]

                        madaily = customerList

                        tendaily = data[12]

                        #

                        #if  frappe.utils.getdate(fromdate) < frappe.utils.getdate(deducted_Date) and frappe.utils.getdate(deducted_Date) >= frappe.utils.getdate(frappe.utils.today()):

                            #dauky = float(dauky) - float(deducted_debt)

                        for data in datathanhtoan:

                            #if data['Mua hàng'] > 0 :totalthanhtoan

                                totalthanhtoan = totalthanhtoan + data['Thanh Toán']

                        

                        """if dauky > 0:

                            #if dateCharge == "":

                            dsdataban.append({

                                "account": "",

                                "customerid": customerid,

                                "docdate": str(frappe.utils.add_days(doc.date_start, -1)) + "T00:00:00.000Z",

                                "docno": "dauky",

                                "doccode": "H2",

                                "description": "Nợ đầu kỳ " + str(frappe.utils.getdate(doc.date_start).year),

                                "debitamount": dauky,

                                "originaldebitamount": 0,

                                "creditamount": 0,

                                "originalcreditamount": 0,

                                "stt": "A010257193",

                                "customerid0": customerid,

                                "crspaccount": "",

                                "itemid": "",

                                "itemname": "",

                                "warehouseid": 0,

                                "quantity": 0,

                                "docgroup": "2",

                                "_status": "3",

                                "_formatstylekey": "",

                                "id": "",

                                "_linkcommand": "EDIT_H2 PrimaryKeyValue={=Id}",

                                "customercode": customerList, 

                                "customername": tendaily,

                                "bookingdate": "2024-01-04T00:00:00.000Z"

                            })

                    

                            else:

                                dsdataban.append({

                                    "account": "",

                                    "customerid": customerid,

                                    "docdate": str(dateCharge) + "T00:00:00.000Z",

                                    "docno": "dauky",

                                    "doccode": "H2",

                                    "description": "Nợ đầu kỳ " + str(frappe.utils.getdate(fromdate).year),

                                    "debitamount": dauky,

                                    "originaldebitamount": 0,

                                    "creditamount": 0,

                                    "originalcreditamount": 0,

                                    "stt": "A010257193",

                                    "customerid0": customerid,

                                    "crspaccount": "",

                                    "itemid": "",

                                    "itemname": "",

                                    "warehouseid": 0,

                                    "quantity": 0,

                                    "docgroup": "2",

                                    "_status": "3",

                                    "_formatstylekey": "",

                                    "id": "",

                                    "_linkcommand": "EDIT_H2 PrimaryKeyValue={=Id}",

                                    "customercode": customerList,

                                    "customername": tendaily,

                                    "bookingdate": "2024-01-04T00:00:00.000Z"

                                })"""

                        

                        tootalthanhtoan = 0

                        if datathanhtoan:

                            for data in datathanhtoan:

                                #if data['Thanh Toán'] > 0 :

                           

                                    dsdatathanhtoan.append({

                                        "account": "",

                                        "customerid": customerid,

                                        "docdate": str(data['Ngày'] ) + "T00:00:00.000Z",

                                        "docno": data['Mã hóa đơn'],

                                        "doccode": "H2",

                                        "description": data['Mô tả'],

                                        "debitamount": 0,

                                        "originaldebitamount": 0,

                                        "creditamount": data['Thanh Toán'],

                                        "originalcreditamount": 0,

                                        "stt":"",

                                        "customerid0": customerid,

                                        "crspaccount": "",

                                        "itemid": "",

                                        "itemname": "",

                                        "warehouseid": 0,

                                        "quantity": 0,

                                        "docgroup": "2",

                                        "_status": "3",

                                        "_formatstylekey": "",

                                        "id": "",

                                        "_linkcommand": "EDIT_H2 PrimaryKeyValue={=Id}",

                                        "customercode": customerList,

                                        "customername": tendaily,

                                        'payment_next':0,

                                        "bookingdate": str(data['Ngày'] ) + "T00:00:00.000Z",

                                        

                                    })

                

                        if doc.name == "2025-02-01-2025-02-28--202892":

                                frappe.log_error("sss111duedate",dsdatathanhtoan)                          

                        #doc.test = str(namcu)

                        if datamuahang:

                            for data in datamuahang:

                                #if data['Mua hàng'] > 0 :

                                    totalmuahang = totalmuahang + data['Mua hàng']

                                    dsdataban.append({

                                        "account": "",

                                        "customerid": customerid,

                                        "docdate": str(data['Ngày'] ) + "T00:00:00.000Z",

                                        "docno": data['Mã hóa đơn'],

                                        "doccode": "H2",

                                        "description": data['description'],

                                        "debitamount": data['Mua hàng'],

                                        "originaldebitamount": 0,

                                        "creditamount":0 ,

                                        'ngayhoadon':data['ngayhoadon'],

                                        "originalcreditamount": 0,

                                        "stt":"",

                                        "customerid0": customerid,

                                        "crspaccount": "",

                                        "itemid": "",

                                        "itemname": "",

                                        "warehouseid": 0,

                                        "quantity": 0,

                                        "docgroup": "2",

                                        "_status": "3",

                                        "_formatstylekey": "",

                                        "id": "",

                                        "_linkcommand": "EDIT_H2 PrimaryKeyValue={=Id}",

                                        "customercode": customerList,

                                        "customername": tendaily,

                                        "bookingdate": str(data['Ngày'] ) + "T00:00:00.000Z",

                                        'duedate':data['duedate']

                                    })

                    

                        

                        """for data in dsdatabangke:

                            if data["description"] not in dsloai :

                                date = dateGet(data["docdate"])

                                if   frappe.utils.getdate(date) <= frappe.utils.getdate(doc.date_end):

                                    if float(data["debitamount"] )  > 0:# and (str(data['CustomerCode_B']) in dsErp or str(data['CustomerCode_B']) == "None"):

                                        dsdataban.append(data)

                                    if float(data["creditamount"] )  > 0 :

                                        dsdatathanhtoan.append(data)"""

                        

                        daytt = ""

                        credittt = 0

                        """if dauky < 0:

                            credittt = credittt + dauky*-1

                            daytt =  str(frappe.utils.add_days(fromdate,-1))

                            tongthanhtoan = tongthanhtoan+ dauky*-1

                            #credittt = credittt - dauky"""

                        datemin = ""

                        laitong = 0 

                        datarowtong2= []

                        checkPay = 0

                        due_debit = 0 

                        #if docno == "C24TNB109":

                        for sell in dsdataban:

                            sell["docdate"] = frappe.utils.getdate(sell["docdate"])

                        dsdataban = sorted(dsdataban, key=lambda x: (x['docdate']), reverse=False)

                        dsdatathanhtoan = sorted(dsdatathanhtoan, key=lambda x: (x['docdate']), reverse=False)

                        paymentNext = 0 

                        dayNext = ""

                        for sell in dsdataban:

                            quahandon = 0 

                            checkQuahan = 0 

                            duoi15ngay = 0

                            tu16den30ngay= 0

                            tu31den90ngay = 0

                            checkPay = 0 

                            tren90 = 0

                            notronghan = 0

                            Songaytt = 0 

                            SongayQuahan = 0

                            SongaytraTruoc = 0 

                            duedate = ""

                            getdaytt = ""

                            getTT = ""

                            tonglai = 0 

                            lai = 0 

                            if not sell["debitamount"]:

                                sell["debitamount"] = 0

                            conduTheodon = float(sell["debitamount"])

                            datesell = dateGet(sell["docdate"])

                            ngaynhachen = ""

                            duedate = ttnhanh(datesell,company,sell["customercode"],province_gso,credit_days)

                            if len(str(duedate)) > 5:

                                ngaynhachen = frappe.utils.add_days(frappe.utils.getdate(duedate),-5)

                            if  frappe.utils.getdate(datesell) >= frappe.utils.getdate(deducted_Date) and frappe.utils.getdate(deducted_Date) >=frappe.utils.getdate(frappe.utils.today()):

                                credittt = float(credittt) + float(deducted_debt)

                                tongthanhtoan = float(tongthanhtoan) + float(deducted_debt)

                                deducted_debt = 0 

                            docno = sell["docno"]

                            thuKhautru = 0

                            if sell["duedate"] != "no":

                                duedate = frappe.utils.getdate(sell["duedate"])

                            

                            """   """   

                            """

                            

                            """

                            """if frappe.utils.getdate(datesell) <= frappe.utils.getdate(dateCharge) and  dateCharge != "":

                                datesell =dateCharge"""

                            if frappe.utils.getdate(duedate) <= frappe.utils.getdate(doc.date_end):

                                

                                #if frappe.utils.getdate(datesell) >= frappe.utils.getdate(dateCharge) or dateCharge == "":

                                    if frappe.utils.getdate(datesell) <= frappe.utils.getdate(todate):

                                         

                                        checkPay = 0

                                        for pay in dsdatathanhtoan:

                                                if pay["creditamount"] != 0 :

                                                    checkPay = 1 

                                        sodu = 0 

                                        if credittt == 0 :

                                            sodu = conduTheodon

                                        

                                        if credittt != 0 :

                                            

                                            if checkPay == 0 and credittt < 0:

                                                daytt = todate

                                            

                                            checkdata = laiCheck(sell["docno"],conduTheodon,daytt,datesell,credittt,lai,getdaytt,duedate,credit_days,SongayQuahan,duoi15ngay,tu16den30ngay,tu31den90ngay,tren90,notronghan,fromdate,todate,laifull)

                                            

                                            conduTheodon = checkdata[0]

                                            

                                            lai = checkdata[1]

                                            

                                            if checkPay == 0 :

                                                if conduTheodon > 0 and conduTheodon != sell["debitamount"]:

                                                    sodu = conduTheodon

                                            else:

                                                if conduTheodon > 0:

                                                    sodu = conduTheodon

                                            

                                            daytt = checkdata[2]

                                            getdaytt = checkdata[3]

                                            SongayQuahan = checkdata[4]

                                            #tu16den30ngay = checkdata[5]

                                            #tu31den90ngay = checkdata[6]

                                            #tren90 = checkdata[7]

                                            notronghan = checkdata[8]

                                            laifull =  checkdata[9]

                                            if checkPay == 1 :

                                                getTT = str(getTT)+" + "+str(frappe.utils.fmt_money(credittt,0))+"- ngày: "+str(daytt)

                                            

                                        if conduTheodon > 0 and checkPay ==0 :

                                            

                                            if sodu > 0:

                                                checkdata = laiCheck(sell["docno"],sodu,todate,datesell,0,lai,getdaytt,duedate,credit_days,SongayQuahan,duoi15ngay,tu16den30ngay,tu31den90ngay,tren90,notronghan,fromdate,todate,laifull)

                                                conduTheodon = checkdata[0]

                                                

                                                lai = checkdata[1]

                                                

                                                daytt = checkdata[2]

                                                getdaytt = checkdata[3]

                                                SongayQuahan = checkdata[4]

                                                

                                                #tu16den30ngay = checkdata[5]

                                                #tu31den90ngay = checkdata[6]

                                                #tren90 = checkdata[7]

                                                notronghan = checkdata[8]

                                                laifull =  checkdata[9]

                                                

                                        if conduTheodon > 0 and checkPay == 1:

                                            thanhtoan = 0 

                                            

                                            for pay in dsdatathanhtoan:

                                                daytt = dateGet(pay["docdate"])

                                                if pay["docno"] == "dauky":

                                                    daytt = str(frappe.utils.add_days(begindate,-1))

                                                for pay2 in dsdatathanhtoan:

                                                    datett2 = dateGet(pay2["docdate"])

                                                    if str(daytt) == str(datett2) and pay["stt"] != pay2["stt"]:

                                                        #testTT.append( frappe.utils.fmt_money(float(pay2["CreditAmount"]),0))

                                                        pay["creditamount"] = float(pay["creditamount"]) + float(pay2["creditamount"])

                                                        

                                                    

                                                        

                                                        pay2["creditamount"] = 0 

                                                thanhtoan = pay["creditamount"]

                                                dayNext = daytt

                                                tootalthanhtoan = tootalthanhtoan + thanhtoan

                                                

                                                if pay["creditamount"] < 0 :

                                                    

                                                    conduTheodon = conduTheodon -  pay["creditamount"] 

                                                    thuKhautru = thuKhautru - pay["creditamount"] 

                                                    pay["creditamount"]  = 0

                                                    

                                                if pay["creditamount"] > 0 :

                                                    getTT = str(getTT)+" + "+str(frappe.utils.fmt_money(thanhtoan,0))+"- ngày: "+str(daytt)

                                                    

                                                    checkdata = laiCheck(sell["docno"],conduTheodon,daytt,datesell,thanhtoan,lai,getdaytt,duedate,credit_days,SongayQuahan,duoi15ngay,tu16den30ngay,tu31den90ngay,tren90,notronghan,fromdate,todate,laifull)

                                                    conduTheodon = checkdata[0]

                                                    

                                                    lai = checkdata[1]

                                                    

                                                    daytt = checkdata[2]

                                                    getdaytt = checkdata[3]

                                                    SongayQuahan = checkdata[4]

                                                    #tu16den30ngay = checkdata[5]

                                                    #tu31den90ngay = checkdata[6]

                                                    #tren90 = checkdata[7]

                                                    notronghan = checkdata[8]

                                                    laifull =  checkdata[9]

                                                    pay["creditamount"] = 0

                                                    

                                                    credittt = credittt + thanhtoan

                                                    

                                                    for pay in dsdatathanhtoan:

                                                        if pay["creditamount"] != 0 :

                                                            checkPay = 1 

                                                             

                                                    if conduTheodon  <= 0 :

                                                        break

                                                

                                                    

                                            if conduTheodon > 0:

                                                checkPay = 0

                                                

                                                for pay in dsdatathanhtoan:

                                                    if pay["creditamount"] != 0 :

                                                        checkPay = 1 

                                                

                                                if checkPay == 0 :

                                                    

                                                    checkdata = laiCheck(sell["docno"],conduTheodon,todate,datesell,0,lai,getdaytt,duedate,credit_days,SongayQuahan,duoi15ngay,tu16den30ngay,tu31den90ngay,tren90,notronghan,fromdate,todate,laifull)

                                                    conduTheodon = checkdata[0]

                                                    

                                                    lai = checkdata[1]

                                                    daytt = checkdata[2]

                                                    getdaytt = checkdata[3]

                                                    SongayQuahan = checkdata[4]

                                                    #tu16den30ngay = checkdata[5]

                                                    #tu31den90ngay = checkdata[6]

                                                    #tren90 = checkdata[7]

                                                    notronghan = checkdata[8]

                                                    laifull =  checkdata[9]

                            

                            if conduTheodon > 0 :                         

                                namsau = namsau +  float(conduTheodon)                    

                            checkPay = 0

                            credittt =  credittt - float(sell["debitamount"]) - thuKhautru

                            

                            for pay in dsdatathanhtoan:

                                if pay["creditamount"] != 0 :

                                    checkPay = 1 

                            

                            if frappe.utils.getdate(todate) > frappe.utils.getdate(frappe.utils.today()):

                                todate = frappe.utils.today()

                            if frappe.utils.getdate(duedate)<= frappe.utils.getdate(todate) :#and (frappe.utils.getdate(duedate) >= frappe.utils.getdate(dateCharge) or dateCharge == "") :

                                

                                if checkPay == 0 :

                                    

                                    if credittt < 0 :

                                        

                                        if conduTheodon > 0:

                                            quahandon = conduTheodon

                                            due_debit = conduTheodon + due_debit

                                            

                                        if conduTheodon== 0:

                                            quahandon = float(sell["debitamount"])

                                            due_debit = float(sell["debitamount"]) + due_debit

                                        

                   

                                            

                                if quahandon > 0 and frappe.utils.getdate(duedate)  <= frappe.utils.getdate(todate):

                                    checkquahan = frappe.utils.date_diff(frappe.utils.getdate(doc.date_end),frappe.utils.getdate(sell['ngayhoadon']))

                                    checkquahan = checkquahan-credit_days

                                    if 0<int (checkquahan) <=30:

                                        tu16den30ngay = float(quahandon) 

                                    if 31<=int (checkquahan) <=90:

                                        

                                        tu31den90ngay =  float(quahandon)  

                                    if int (checkquahan) >=91:

                     

                                        tren90 =  float(quahandon) 

                                

                                tongtu16den30ngay = tongtu16den30ngay + int(tu16den30ngay)

                                tongtu31den90ngay = tongtu31den90ngay + int(tu31den90ngay)

                                

                                tongtren90 = tongtren90 + tren90

                            if frappe.utils.getdate(duedate)  <= frappe.utils.getdate(todate):

                                if credittt > 0:

                                    if conduTheodon == 0:

                                        paymentNext = credittt 

                                    else:

                                        paymentNext = 0

                                if credittt == 0:

                                    paymentNext = 0

                            tongthanhtoan = tongthanhtoan - float(sell["debitamount"])

                            tongnotronghan = tongnotronghan + int(notronghan)

                            #if credittt < float(sell["DebitAmount"]):

                            if lai <0: 

                                lai =0

                            laitong = laitong + lai

                            #if checkQuahan == 1:

                            if lai < 0:

                                lai =0 

                            

                            

                            doc.lai = doc.lai + lai

                            if frappe.utils.getdate(duedate)<= frappe.utils.getdate(doc.date_end):

                                if credittt > 0 :

                                    sosudenCuoi = credittt

                                if credittt <= 0 :

                                    sosudenCuoi = 0

                            

                            dsdonhangchitiet.append({

                                                    'ngay':frappe.utils.getdate(datesell),

                                                    'madaily':madaily,

                                                    'tendaily':tendaily,

                                                    'makhachhang': sell["customerid0"],

                                                    'khachhang':erp_name,

                                                    'sales':salename,

                                                    'vung':customer_group,

                                                    'ngayhoadon':frappe.utils.getdate(sell['ngayhoadon']),

                                                    'mahoadon':sell["docno"],

                                                    'muahang': sell["debitamount"] ,

                                                    'thanhtoan': str(getTT),

                                                    'cuoiky':credittt  ,

                                                    'hanno':credit_days,

                                                    'quahan':quahandon,

                                                    'ngayquahan':frappe.utils.getdate(duedate),

                                                    'Songayquahan':SongayQuahan,

                                                    'tratruochan':SongaytraTruoc,

                                                    'notronghan':notronghan ,

                                                    'tu16den30ngay': tu16den30ngay ,

                                                    'tu31den90ngay': tu31den90ngay,

                                                    'tren90':(tren90),

                                                    'nokhodoi':str(getdaytt),

                                                    'ngaynhachen':ngaynhachen,

                                                    'conlai':credittt  ,

                                                    'mota':sell["description"] ,

                                                    'saleteam':khuvuc,

                                                    'duedate':frappe.utils.getdate(duedate),

                                                    'Songaytt':Songaytt,

                                                    'condutheodon':conduTheodon,

                                                    'lai': lai ,

                                                    'daytt':daytt,

                                                    'stt':sell['stt']

                                                    }),

                            #if daytt == "2024-09-17":

                        doc.payment= float(sosudenCuoi) 

                        doc.team_cong_no = namsau

                        doc.debt_less_than_30_days =  int(tongtu16den30ngay) 

                        doc.debt_30_to_90_days = int(tongtu31den90ngay) 

                        

                        doc.debt_over_90_days = tongtren90 

        

                        if paymentNext > 0: 

                            doc.paymentnext = paymentNext 

                            doc.daynext = dayNext

                            #credittt = credittt  - paymentNext

                        

                        for pay in dsdatathanhtoan:

                            datett = dateGet(pay["docdate"])

                            tootalthanhtoan = tootalthanhtoan + pay["creditamount"] 

                            #if frappe.utils.getdate(datett) >= frappe.utils.getdate(dateCharge) or dateCharge == "":

                            if pay["creditamount"] == "":

                                pay["creditamount"] = 0

                            if pay["creditamount"] != 0: 

                                

                                """if pay["creditamount"] < 0 :

                                    pay["creditamount"] = pay["creditamount"] * -1"""

                                credittt = credittt + pay["creditamount"]

                                doc.payment= doc.payment + pay["creditamount"]

                                

                                dsdonhangchitiet.append({

                                    'ngay':(datett),

                                    'madaily':customerid,

                                    'tendaily':erp_name,

                                    'makhachhang': doc.customer,

                                    'khachhang':erp_name,

                                    'sales':salename,

                                    'vung':customer_group,

                                    'ngayhoadon':dateGet(pay["docdate"]),

                                    'mahoadon':pay["docno"],

                                    'muahang': 0 ,

                                    'thanhtoan': str(pay["creditamount"] ),

                                    'cuoiky':  credittt  ,

                                    'hanmucno':credit_days,

                                    'payment_next':pay["creditamount"] ,

                                    'payment_next':0,

        

                                    'conlai':credittt,

                                    'mota':pay["description"] ,

        

                                })       

                                pay["creditamount"] = 0 

                                datarowtong.extend(datarowtong2)

                        

                        doc.today = frappe.utils.today()

                     

                        if customerList2 != []:

                            customerList2.append({

                                        "firstdebt":firstdebt ,

                                        "debit":debit,

                                        #"sumallopenning": frappe.utils.fmt_money(sumopenall,0),

                                        "buyitem": buyitem ,

                                        "sellitem": sellitem ,

                                        "credit":credit ,

                                        "balance":balance ,

                                        'tongnotronghan': tongnotronghan,

                                        'tongduoi15ngay': laitong,

                                        'tongtu16den30ngay': tongtu16den30ngay,

                                        'tongtu31den90ngay': tongtu31den90ngay,

                                        'tongtren90': tongtren90,

                                        'quahan':due_debit,

                                        'credit_days':credit_days

                                        })

                            doc.extend('total',customerList2)

                        doc.due_debit = 0

                        

                        if dsdonhangchitiet != []:

                            doc.donhangconnotable = []

                

                            doc.extend("donhangconnotable",dsdonhangchitiet)

                        

                

                            if doc.donhangconnotable != []:

                                for total in doc.donhangconnotable:

                                    if total.quahan and float(total.quahan) > 0:

                                        doc.due_debit =  total.quahan + doc.due_debit

                                doc.debt_on_time = doc.closing_receivables_amounts - doc.closing_prepayment_amount - doc.due_debit

                

                

                

                        """tonghopcongnodaily = frappe.make_post_request('https://bravo6.oshima.vn/getsotonghopcongnodaily', data={

                                    'agencycode': customerid ,

                                    'datestart': frappe.utils.getdate(doc.date_start),

                                    'dateend':frappe.utils.getdate(todate),

                                })"""

                        query = (

                            "EXEC usp_Kcd_SoTongHopCongNoDaiLy "

                            "@_DocDate1 = '" + str(doc.date_start) + "',"

                            "@_DocDate2 = '" + str(doc.date_end) + "',"

                            "@_AgencyCode = '" + str(doc.customerid) + "'"

                        )

                    

                        def checkmonthAndYear(today):

                            month = frappe.utils.getdate(today).month

                            lastmonth = 1

                            if month == 1:

                                lastmonth = 12 

                            else:

                                lastmonth = month - 1 

                            year = frappe.utils.getdate(today).year 

                            if lastmonth == 12:

                                year = year - 1

                            return lastmonth,year

                        def checkbug(closing_receivables_amounts,closing_prepayment_amount,donhangconnotable,payment):

                            nocuoi = closing_receivables_amounts - closing_prepayment_amount

                            cuoiky = 0

                            check = 0 

                            if nocuoi<0:

                                nocuoi = nocuoi*-1 

                            if len(donhangconnotable)> 0:

                                cuoiky = donhangconnotable[-1].cuoiky

                                if cuoiky <0:

                                    cuoiky = cuoiky*-1 

                                if cuoiky != nocuoi:

                                    if payment < 0  and payment != cuoiky:

                                        cuoiky = cuoiky + payment

                                

                            if cuoiky <0:

                                cuoiky = cuoiky*-1 

                            if cuoiky != nocuoi:

                                check = 1

                            return check

                        

                        check = checkbug(doc.closing_receivables_amounts,doc.closing_prepayment_amount,doc.donhangconnotable,doc.payment)

                        if old_doc.debit and old_doc.closing_receivables_amounts and  doc.due_debit != old_doc.debit or ( old_doc.closing_receivables_amounts and int(doc.closing_receivables_amounts - doc.closing_prepayment_amount) != int(old_doc.closing_receivables_amounts - old_doc.closing_prepayment_amount )):

                            doc.today = None

                        

                        if check == 0 :

                            doc.link = "ok"

                        elif checkMien == 1:

                            doc.link = "ok"

                        else:

                            doc.link = "bug" 