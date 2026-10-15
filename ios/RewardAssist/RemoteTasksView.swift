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
    @State private var autoSubmit = true
    @State private var clearInitial = true
    @State private var acceptedReviews: Set<String> = []
    @AppStorage("remoteWakeMac") private var wakeMac = ""
    @AppStorage("remoteWakeIP") private var wakeIP = ""
    @State private var wakeStatus = ""
    struct RemoteJob: Identifiable {
        let id: String
        let device: String
        let stage: String
        let info: [String:Any]
    }
    var body: some View {
        Form {
            Section {
                NavigationLink { WakeRelayView(sync:sync) } label: {
                    Label("Wake from anywhere", systemImage:"bolt.horizontal.circle.fill")
                }
                Text("Use a paired Android tablet at home to wake your sleeping computer over cellular.").font(.footnote).foregroundStyle(.secondary)
            }
            Section("Home computer") {
                if devices.isEmpty { Text("No computer online. Use Wake from anywhere with a paired tablet, or the local Wake button while on home Wi-Fi.").font(.footnote) }
                Picker("Computer", selection:$device) {
                    Text("Choose computer").tag("")
                    ForEach(devices,id: \.self) { Text("Computer " + $0.prefix(8)).tag($0) }
                }
                HStack {
                    TextField("PC MAC address", text:$wakeMac)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .font(.footnote)
                    Button(action: {
                        let (_, msg) = WakeOnLAN.send(mac: wakeMac, targetIP: wakeIP)
                        wakeStatus = msg
                    }) {
                        Label("Wake", systemImage:"bolt.fill")
                    }
                    .disabled(wakeMac.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
                if !wakeStatus.isEmpty {
                    Text(wakeStatus).font(.caption).foregroundStyle(.secondary)
                }
            }
            Section("New account setup") {
                Picker("Restaurant", selection:$app) {
                    ForEach(["Einstein Bros. Bagels","sweetFrog","Nothing Bundt Cakes","The Cheesecake Factory","Taco Bell","Dutch Bros","Chick-fil-A","Jeremiah's Italian Ice"],id: \.self) { Text($0) }
                }
                Text("Paste single or multiple details blocks ending with END. Dutch Bros, Chick-fil-A, and Jeremiah's need an attached Android device. Taco Bell continues on Android.").font(.footnote)
                if app == "Chick-fil-A" {
                    VStack(alignment: .leading, spacing: 4) {
                        Label("2-Day Advance Notice Required", systemImage: "clock.badge.exclamationmark.fill")
                            .font(.subheadline.bold())
                            .foregroundStyle(.red)
                        Text("Chick-fil-A requires birthdays to be saved at least 2 days before your birthday to issue the annual birthday reward. Once granted, rewards remain valid for 30 days.")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    .padding(.vertical, 4)
                    TextField("Pickup address or ZIP (e.g. Flower Mound, TX / 75022)", text: $location)
                    Picker("Pickup method", selection: $pickupMethod) {
                        Text("Drive-thru").tag("Drive-thru")
                        Text("Carry-out").tag("Carry-out")
                        Text("Curbside").tag("Curbside")
                    }
                    Picker("Reward item", selection: $reward) {
                        ForEach(["Chocolate Chunk Cookie", "Chocolate Fudge Brownie"], id: \.self) { Text($0) }
                    }
                    Toggle("Clear app storage before starting", isOn: $clearInitial)
                    Toggle("Autonomous checkout & auto-clear storage", isOn: $autoSubmit)
                    TextField("Android serial (optional with one phone)", text: $serial)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    Text("Supports multiple account blocks separated by END. The assistant autonomously places orders and clears app storage between accounts without manual prompts.").font(.footnote).foregroundStyle(.secondary)
                }
                if app == "Nothing Bundt Cakes" { Text("Allow about 2 hours after confirmed signup before checking the reward. Sync your wallet after completion to start its countdown and local reminder.").font(.footnote).foregroundStyle(.secondary) }
                Text("For programs requiring a password, add password: YOUR_PASSWORD before END. sweetFrog uses verification codes and does not need a password.").font(.footnote).foregroundStyle(.secondary)
                TextEditor(text:$details).frame(minHeight:140).textInputAutocapitalization(.never).autocorrectionDisabled()
                if app == "Taco Bell" {
                    TextField("Pickup address or ZIP",text:$location)
                    TextField("Pickup time (ASAP or 3:15 PM)",text:$pickupTime)
                    Picker("Pickup",selection:$pickupMethod) { Text("Drive-Thru").tag("Drive-Thru"); Text("In Store").tag("In Store") }
                    Picker("Reward",selection:$reward) { ForEach(["Soft Taco","Cantina Chicken Crispy Taco","Beefy 5-Layer Burrito"],id: \.self) { Text($0) } }
                    Picker("Payment",selection:$payment) { Text("Venmo").tag("venmo"); Text("Gift Card").tag("gift_card") }
                    if payment == "gift_card" { SecureField("Gift card number",text:$cardNumber); SecureField("Gift card PIN",text:$cardPIN) }
                    Toggle("Autonomous checkout & auto-clear storage", isOn: $autoSubmit)
                    TextField("Android serial (optional with one phone)",text:$serial).textInputAutocapitalization(.never).autocorrectionDisabled()
                    Text("Multi-account batches separated by END are supported. When autonomous checkout is enabled, orders are placed and storage is reset automatically.").font(.footnote)
                }
                Toggle("I authorize this account setup and the form submission using these details",isOn:$confirmed)
                Button("Start on computer") { Task { await submit() } }.disabled(busy || device.isEmpty || details.isEmpty || !confirmed)
            }
            Section("Recent requests") {
                ForEach(jobs) { job in
                    VStack(alignment:.leading,spacing:8) {
                        Text(job.stage.replacingOccurrences(of:"_",with:" ").capitalized).font(.headline)
                        Text("Request " + job.id.prefix(8)).font(.caption).foregroundStyle(.secondary)
                        if let text=job.info["message"] as? String, !text.isEmpty { Text(text).font(.footnote) }
                        else if job.stage == "attention" { Text("The computer did not provide an error description. Check Phone connection in Reward Assist on the PC. This request will not be retried automatically.").font(.footnote) }
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
                let taskEmail = (info["details"] as? String)?.extractEmail() ?? info["email"] as? String
                activity.record(id:id,program:info["app"] as? String,stage:stage,date:Date(timeIntervalSince1970:($0["updated"] as? Double ?? Date().timeIntervalSince1970 * 1000) / 1000),email:taskEmail)
                if (info["app"] as? String) == "Chick-fil-A" && stage == "complete" && !syncedCompletions.contains(id) {
                    Task {
                        let center = UNUserNotificationCenter.current()
                        let content = UNMutableNotificationContent()
                        content.title = "🎉 Chick-fil-A Order Ready!"
                        content.body = "Your Chick-fil-A order is ready for pickup! Head to your selected pickup spot."
                        content.sound = .default
                        let trigger = UNTimeIntervalNotificationTrigger(timeInterval: 15 * 60, repeats: false)
                        try? await center.add(UNNotificationRequest(identifier: "cfa-ready-\(id)", content: content, trigger: trigger))
                    }
                }
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
            if app == "Chick-fil-A" {
                let loc = location.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty ? "75022" : location
                let plan: [String:Any] = [
                    "location": loc,
                    "pickup_method": pickupMethod,
                    "reward": reward,
                    "auto_submit": autoSubmit,
                    "clear_initial": clearInitial
                ]
                content["cfa_plan"] = plan
                content["android_serial"] = serial
            }
            if app == "Taco Bell" {
                guard !location.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty else {message="Enter a pickup address or ZIP.";busy=false;return}
                var plan: [String:Any] = ["location":location,"pickup_time":pickupTime,"pickup_method":pickupMethod,"reward":reward,"payment_method":payment,"auto_submit":autoSubmit]
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

fileprivate extension String {
    func extractEmail() -> String? {
        let pattern = #"[A-Z0-9a-z._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,64}"#
        if let range = self.range(of: pattern, options: .regularExpression) {
            return String(self[range])
        }
        return nil
    }
}
