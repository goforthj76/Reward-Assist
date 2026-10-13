import SwiftUI

struct RemoteTasksView: View {
    @ObservedObject var sync: ComputerSync
    @EnvironmentObject var activity: ActivityStore
    @EnvironmentObject var wallet: WalletStore
    @State private var syncedCompletions: Set<String> = []
    @State private var devices: [String] = []
    @State private var jobs: [RemoteJob] = []
    @State private var device = ""
    @State private var app = "Nothing Bundt Cakes"
    @State private var details = ""
    @State private var confirmed = false
    @State private var busy = false
    @State private var message = ""
    @State private var requestID = UUID().uuidString
    @State private var code = ""
    @State private var location = ""
    @State private var pickupTime = "ASAP"
    @State private var pickupMethod = "Drive-Thru"
    @State private var reward = "Soft Taco"
    @State private var payment = "venmo"
    @State private var serial = ""
    @State private var cardNumber = ""
    @State private var cardPIN = ""
    @State private var acceptedReviews: Set<String> = []
    struct RemoteJob: Identifiable {
        let id: String
        let device: String
        let stage: String
        let info: [String:Any]
    }
    var body: some View {
        Form {
            Section("Home computer") {
                if devices.isEmpty { Text("No computer online. Sign in and enable Phone requests in the updated desktop app.") }
                Picker("Computer", selection:$device) {
                    Text("Choose computer").tag("")
                    ForEach(devices,id: \.self) { Text("Computer " + $0.prefix(8)).tag($0) }
                }
            }
            Section("New account setup") {
                Picker("Restaurant", selection:$app) {
                    ForEach(["Nothing Bundt Cakes","The Cheesecake Factory","Taco Bell","Dutch Bros"],id: \.self) { Text($0) }
                }
                Text("Paste the same single-person details block used on the desktop. Dutch Bros needs an attached Android device. Taco Bell continues on the connected Android. Payment setup or unexpected device prompts may need attention there.").font(.footnote)
                if app == "Nothing Bundt Cakes" { Text("Allow about 2 hours after confirmed signup before checking the reward. Sync your wallet after completion to start its countdown and local reminder.").font(.footnote).foregroundStyle(.secondary) }
                TextEditor(text:$details).frame(minHeight:140).textInputAutocapitalization(.never).autocorrectionDisabled()
                if app == "Taco Bell" {
                    TextField("Pickup address or ZIP",text:$location)
                    TextField("Pickup time (ASAP or 3:15 PM)",text:$pickupTime)
                    Picker("Pickup",selection:$pickupMethod) { Text("Drive-Thru").tag("Drive-Thru"); Text("In Store").tag("In Store") }
                    Picker("Reward",selection:$reward) { ForEach(["Soft Taco","Cantina Chicken Crispy Taco","Beefy 5-Layer Burrito"],id: \.self) { Text($0) } }
                    Picker("Payment",selection:$payment) { Text("Venmo").tag("venmo"); Text("Gift Card").tag("gift_card") }
                    if payment == "gift_card" { SecureField("Gift card number",text:$cardNumber); SecureField("Gift card PIN",text:$cardPIN) }
                    TextField("Android serial (optional with one phone)",text:$serial).textInputAutocapitalization(.never).autocorrectionDisabled()
                    Text("The store search selects its first result. Review the actual store, items and total before placing the order. Venmo must already be configured on Android.").font(.footnote)
                }
                Toggle("I authorize this account setup and the form submission using these details",isOn:$confirmed)
                Button("Start on computer") { Task { await submit() } }.disabled(busy || device.isEmpty || details.isEmpty || !confirmed)
            }
            Section("Recent requests") {
                ForEach(jobs) { job in
                    VStack(alignment:.leading,spacing:8) {
                        Text(job.stage.replacingOccurrences(of:"_",with:" ").capitalized).font(.headline)
                        Text("Request " + job.id.prefix(8)).font(.caption).foregroundStyle(.secondary)
                        if let text=job.info["message"] as? String { Text(text).font(.footnote) }
                        if job.stage == "waiting_code" {
                            SecureField("Verification code",text:$code).keyboardType(.numberPad)
                            Button("Send code") { Task { await sendCode(job) } }.disabled(busy || code.count < 4 || code.count > 8)
                        }
                        if job.stage == "review_required", let nonce=job.info["nonce"] as? String, !nonce.isEmpty {
                            if job.info["reviewKind"] as? String == "order" {
                                Text(job.info["reviewText"] as? String ?? "Checkout details unavailable").font(.footnote).textSelection(.enabled)
                            } else if job.info["app"] as? String == "Taco Bell" {
                                Link("Read Taco Bell terms and Rewards conditions",destination:URL(string:"https://www.tacobell.com/legal/terms-of-use")!)
                                Text("Approve creating the account with the details you supplied and accepting Taco Bell's terms, including Rewards conditions.").font(.footnote)
                            } else {
                                Link("Review restaurant signup and terms",destination:URL(string:"https://www.thecheesecakefactory.com/account/signup")!)
                                Text("Enrollment may include promotional email and SMS consent. Review the restaurant's terms before approval.").font(.footnote)
                            }
                            Toggle("I reviewed and accept this step",isOn:Binding(get:{acceptedReviews.contains(nonce)},set:{if $0 {acceptedReviews.insert(nonce)} else {acceptedReviews.remove(nonce)}}))
                            Button(job.info["reviewKind"] as? String == "order" ? "Place this order" : "Accept terms and continue") { Task { await approve(job,nonce:nonce) } }.disabled(busy || !acceptedReviews.contains(nonce))
                        }
                        if ["queued","starting","running","waiting_code","review_required"].contains(job.stage) {
                            Button("Cancel request",role:.destructive) {Task {await cancel(job)}}.disabled(busy)
                            Text("Cancellation stops future steps when the computer checks in. It cannot undo a submitted account or order.").font(.caption)
                        }
                        if job.stage == "starting" { Text("If interrupted, check the computer. This request will not automatically restart.").font(.footnote) }
                    }
                }
                Button("Refresh status") { Task { await refresh() } }.disabled(busy)
                if !message.isEmpty { Text(message).font(.footnote) }
            }
        }.navigationTitle("Computer tasks")
        .task {
            while !Task.isCancelled {
                await refresh()
                do { try await Task.sleep(for:.seconds(5)) } catch { break }
            }
        }
    }
    @MainActor private func refresh() async {
        guard !busy else { return }
        do {
            let result = try await sync.remoteRead()
            devices = (result["devices"] as? [[String:Any]] ?? []).compactMap { $0["id"] as? String }
            jobs = (result["jobs"] as? [[String:Any]] ?? []).compactMap {
                guard let id=$0["id"] as? String, let device=$0["device"] as? String, let stage=$0["stage"] as? String else { return nil }
                let info = ($0["payload"] as? String).flatMap { try? sync.remoteDetails($0) } ?? [:]
                activity.record(id:id,program:info["app"] as? String,stage:stage,date:Date(timeIntervalSince1970:($0["updated"] as? Double ?? Date().timeIntervalSince1970 * 1000) / 1000))
                return RemoteJob(id:id,device:device,stage:stage,info:info)
            }
            let completed=jobs.filter { $0.stage == "complete" && !syncedCompletions.contains($0.id) }
            if !completed.isEmpty && !sync.busy {
                await sync.sync(email:sync.accountEmail,password:"",wallet:wallet)
                if sync.status.hasPrefix("Sync complete:") { syncedCompletions.formUnion(completed.map(\.id)) }
            }
        } catch { message = error.localizedDescription }
    }
    @MainActor private func submit() async {
        busy = true
        do {
            var content: [String:Any] = ["app":app,"details":details,"confirmed":confirmed]
            if app == "Taco Bell" {
                guard !location.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty else {message="Enter a pickup address or ZIP.";busy=false;return}
                var plan: [String:Any] = ["location":location,"pickup_time":pickupTime,"pickup_method":pickupMethod,"reward":reward,"payment_method":payment]
                if payment == "gift_card" && !cardNumber.isEmpty { plan["gift_card"]=["number":cardNumber,"pin":cardPIN] }
                content["taco_plan"]=plan;content["android_serial"]=serial
            }
            try await sync.remoteSend(action:"submit",id:requestID,device:device,content:content)
            cardNumber="";cardPIN=""
            requestID = UUID().uuidString
            details = ""
            confirmed = false
            message = "Request queued. Keep the desktop app open."
        } catch { message = error.localizedDescription }
        busy = false
        await refresh()
    }
    @MainActor private func cancel(_ job: RemoteJob) async {
        busy=true;defer{busy=false}
        do {try await sync.remoteSend(action:"cancel",id:job.id,device:job.device,content:[:]);message="Cancellation requested. Waiting for computer acknowledgement."}
        catch {message=error.localizedDescription}
    }
    @MainActor private func approve(_ job: RemoteJob, nonce:String) async {
        busy=true
        defer {busy=false}
        do {
            try await sync.remoteSend(action:"approve",id:job.id,device:job.device,content:["accepted":true,"nonce":nonce])
            acceptedReviews.remove(nonce)
            message="Approval sent. Waiting for the computer."
        } catch {message=error.localizedDescription}
    }
    @MainActor private func sendCode(_ job: RemoteJob) async {
        busy = true
        do {
            try await sync.remoteSend(action:"code",id:job.id,device:job.device,content:["code":code,"codePhase":job.info["codePhase"] as? String ?? "website"])
            code = ""
            message = "Code sent. Waiting for the computer."
        } catch { message = error.localizedDescription }
        busy = false
    }
}
